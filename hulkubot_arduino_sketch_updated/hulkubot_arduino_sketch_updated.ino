#include <Wire.h>

#define DOF_BOARD_ADDR 0x15 
#define BUZZER_REG 0x06     
#define READ_ANGLES_REG 0x15 // <-- UPDATE THIS if your board uses a different register to read angles
#define TORQUE_REG 0x1A      // <-- UPDATE THIS if your board uses a different register for torque enable/disable

#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN); 
}

void loop() {
  if (Serial.available() >= 3) {
    // Check for header 0x55 0xAA
    if (Serial.read() == 0x55) {
      if (Serial.read() == 0xAA) {
        uint8_t cmd = Serial.read();

        // ---------------------------------
        // COMMAND 1: MOVE
        // ---------------------------------
        if (cmd == 0x01) {
          uint8_t buf[14];
          Serial.readBytes(buf, 14); // Read time(2) + 6*pos(12)
          
          // Send Time Array (using your working hex code 0x1E)
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(0x1E);
          Wire.write(buf[0]); // Time High
          Wire.write(buf[1]); // Time Low
          Wire.endTransmission();

          // Send Position Array (using your working hex code 0x1D)
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(0x1D);
          for(int i=2; i<14; i++) {
            Wire.write(buf[i]);
          }
          Wire.endTransmission();
        }

        // ---------------------------------
        // COMMAND 2: READ ANGLES
        // ---------------------------------
        // ---------------------------------
        // COMMAND 2: READ RAW PULSES
        // ---------------------------------
        else if (cmd == 0x02) {
          uint8_t resp[15];
          resp[0] = 0x55; 
          resp[1] = 0xAA; 
          resp[2] = 0x02;
          
          for (int id = 1; id <= 6; id++) {
            Wire.beginTransmission(DOF_BOARD_ADDR);
            Wire.write(0x30 + id); 
            Wire.write(0x00); 
            Wire.endTransmission();
            delay(3); // Crucial 3ms delay
            uint16_t pos = 0; // Default to 0 if read fails
            
            // Casting to int is crucial here for the ESP32 Wire library to use the correct overload!
            Wire.requestFrom((int)DOF_BOARD_ADDR, (int)2);
            
            if (Wire.available() >= 2) {
              uint8_t msb = Wire.read(); 
              uint8_t lsb = Wire.read();
              pos = (msb << 8) | lsb; 
            }
            
            // Pack MSB and LSB into our 15-byte response
            int idx = 3 + (id - 1) * 2;
            resp[idx] = (pos >> 8) & 0xFF;
            resp[idx+1] = pos & 0xFF;
          }
          
          Serial.write(resp, 15);
        }


        // ---------------------------------
        // COMMAND 3: BUZZER
        // ---------------------------------
        else if (cmd == 0x03) {
          uint8_t state;
          Serial.readBytes(&state, 1);
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(BUZZER_REG);
          Wire.write(state); // 0xFF for ON, 0x00 for OFF
          Wire.endTransmission();
        }

        // ---------------------------------
        // COMMAND 4: TORQUE (Drag & Teach)
        // ---------------------------------
        else if (cmd == 0x04) {
          uint8_t state;
          Serial.readBytes(&state, 1);
          Wire.beginTransmission(DOF_BOARD_ADDR);
          Wire.write(TORQUE_REG);
          Wire.write(state); // 0x00 for OFF (Drag mode), 0x01 for ON (Hold mode)
          Wire.endTransmission();
        }
      }
    }
  }
}
