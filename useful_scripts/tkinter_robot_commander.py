import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import struct
import threading
import time

# Protocol Constants
HEADER_TX = 0xA6  # PC -> ESP32
HEADER_RX = 0xA5  # ESP32 -> PC
CMD_MOVE = 1
CMD_RGB = 2
CMD_TORQUE = 3
CMD_BUZZ = 4
CMD_GET_ENCODERS = 5  # NEW: Polling Command

class RobotControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Robot Arm Controller (4-Motor Polling)")
        self.root.geometry("650x450")
        
        self.serial_port = None
        self.is_connected = False
        self.running = True
        
        # Lock to prevent UI buttons from interrupting the master polling loop
        self.tx_lock = threading.Lock() 
        
        self.angles_rx = [tk.StringVar(value="0") for _ in range(4)] # Reduced to 4
        self.sliders = []
        
        self.create_widgets()
        
        # Start a single, unified Master Loop
        threading.Thread(target=self.master_serial_loop, daemon=True).start()

    def create_widgets(self):
        # --- Connection Frame ---
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        self.port_var = tk.StringVar()
        self.port_cb = ttk.Combobox(conn_frame, textvariable=self.port_var, state="readonly")
        self.port_cb.pack(side="left", padx=5)
        self.refresh_ports()
        
        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).pack(side="left", padx=5)
        self.btn_connect = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=5)

        # --- Telemetry Frame ---
        telemetry_frame = ttk.LabelFrame(self.root, text="Real-Time Telemetry (RX)", padding=10)
        telemetry_frame.pack(fill="x", padx=10, pady=5)
        
        for i in range(4): # Reduced to 4
            ttk.Label(telemetry_frame, text=f"J{i+1}:").grid(row=0, column=i*2, padx=5)
            ttk.Label(telemetry_frame, textvariable=self.angles_rx[i], width=5, foreground="blue").grid(row=0, column=i*2+1)

        # --- Movement Frame ---
        move_frame = ttk.LabelFrame(self.root, text="Arm Control (TX)", padding=10)
        move_frame.pack(fill="x", padx=10, pady=5)
        
        limits = [(0, 180), (0, 180), (0, 180), (0, 180)] # Reduced to 4
        for i in range(4):
            ttk.Label(move_frame, text=f"Joint {i+1}").grid(row=i, column=0, padx=5, pady=2)
            slider = ttk.Scale(move_frame, from_=limits[i][0], to=limits[i][1], orient="horizontal", length=300)
            slider.set(90) # Default home position
            slider.grid(row=i, column=1, padx=5, pady=2)
            self.sliders.append(slider)
            
            # Value display
            val_label = ttk.Label(move_frame, text="90")
            val_label.grid(row=i, column=2, padx=5)
            slider.configure(command=lambda val, l=val_label: l.config(text=f"{float(val):.0f}"))

        ttk.Label(move_frame, text="Time (ms)").grid(row=4, column=0, padx=5, pady=10)
        self.time_slider = ttk.Scale(move_frame, from_=10, to=3000, orient="horizontal", length=300)
        self.time_slider.set(1000)
        self.time_slider.grid(row=4, column=1, padx=5, pady=10)
        self.time_label = ttk.Label(move_frame, text="1000")
        self.time_label.grid(row=4, column=2, padx=5)
        self.time_slider.configure(command=lambda val: self.time_label.config(text=f"{float(val):.0f}"))

        # --- Utility Frame ---
        util_frame = ttk.LabelFrame(self.root, text="Utilities", padding=10)
        util_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(util_frame, text="Torque ON", command=lambda: self.send_torque(1)).pack(side="left", padx=5)
        ttk.Button(util_frame, text="Torque OFF", command=lambda: self.send_torque(0)).pack(side="left", padx=5)
        
        self.buzzer_var = tk.IntVar(value=0)
        ttk.Checkbutton(util_frame, text="Buzzer", variable=self.buzzer_var, command=self.send_buzzer).pack(side="left", padx=10)

        ttk.Label(util_frame, text="R:").pack(side="left")
        self.r_val = ttk.Entry(util_frame, width=3); self.r_val.insert(0, "0"); self.r_val.pack(side="left")
        ttk.Label(util_frame, text="G:").pack(side="left")
        self.g_val = ttk.Entry(util_frame, width=3); self.g_val.insert(0, "255"); self.g_val.pack(side="left")
        ttk.Label(util_frame, text="B:").pack(side="left")
        self.b_val = ttk.Entry(util_frame, width=3); self.b_val.insert(0, "0"); self.b_val.pack(side="left")
        ttk.Button(util_frame, text="Set RGB", command=self.send_rgb).pack(side="left", padx=10)

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_cb['values'] = ports
        if ports:
            self.port_cb.current(0)

    def toggle_connection(self):
        if self.is_connected:
            self.serial_port.close()
            self.is_connected = False
            self.btn_connect.config(text="Connect")
            for i in range(4):
                self.angles_rx[i].set("0")
        else:
            try:
                self.serial_port = serial.Serial(self.port_var.get(), 115200, timeout=0.05)
                self.is_connected = True
                self.btn_connect.config(text="Disconnect")
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))

    def build_packet(self, cmd_type, params):
        # Ensure exact payload length (4 params + 1 time/extra = 5 slots)
        while len(params) < 5:
            params.append(0)
        params = params[:5] 
            
        packet_without_checksum = struct.pack('<BB5h', HEADER_TX, cmd_type, *params)
        checksum = sum(packet_without_checksum[1:]) & 0xFF
        return packet_without_checksum + struct.pack('<B', checksum)

    def send_packet(self, packet):
        if self.is_connected and self.serial_port:
            try:
                with self.tx_lock: 
                    self.serial_port.write(packet)
            except Exception as e:
                print(f"Serial Write Error: {e}")

    # --- UI Commands ---
    def send_torque(self, state):
        self.send_packet(self.build_packet(CMD_TORQUE, [state]))

    def send_buzzer(self):
        self.send_packet(self.build_packet(CMD_BUZZ, [self.buzzer_var.get()]))

    def send_rgb(self):
        try:
            self.send_packet(self.build_packet(CMD_RGB, [int(self.r_val.get()), int(self.g_val.get()), int(self.b_val.get())]))
        except ValueError:
            messagebox.showwarning("Input Error", "RGB values must be integers (0-255).")

    # --- Master Polling Loop ---
    def master_serial_loop(self):
        """Unified thread that handles Request-Response polling to prevent USB collisions"""
        while self.running:
            if self.is_connected and self.serial_port:
                try:
                    # 1. Clear Noise
                    self.serial_port.reset_input_buffer()

                    # 2. Request Encoders
                    req_packet = self.build_packet(CMD_GET_ENCODERS, [0, 0, 0, 0, 0])
                    self.send_packet(req_packet)

                    # 3. Read Response
                    header = self.serial_port.read(1)
                    if header == bytes([HEADER_RX]):
                        payload = self.serial_port.read(9) # 4 shorts + 1 byte checksum
                        if len(payload) == 9:
                            unpacked = struct.unpack('<hhhhB', payload)
                            angles = unpacked[0:4]
                            recv_check = unpacked[4]
                            calc_check = sum(payload[0:8]) & 0xFF 
                            
                            if calc_check == recv_check:
                                self.root.after(0, self.update_telemetry_ui, angles)

                    # 4. Send the Current UI Slider Values
                    angles = [int(s.get()) for s in self.sliders]
                    t = int(self.time_slider.get())
                    move_packet = self.build_packet(CMD_MOVE, angles + [t])
                    self.send_packet(move_packet)

                except Exception as e:
                    pass # Ignore timeouts/disconnects and keep looping

            time.sleep(0.01) # Loop at ~20Hz

    def update_telemetry_ui(self, angles):
        for i in range(4):
            self.angles_rx[i].set(str(angles[i]))

    def on_closing(self):
        self.running = False
        if self.is_connected:
            self.serial_port.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotControllerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()