#!/usr/bin/env python3
"""Launcher for the HulkuBot AI GUI — runs Streamlit as a subprocess."""

import os
import sys
import subprocess
from ament_index_python.packages import get_package_share_directory


def main():
    package_name = 'hulku_ai_gui'

    try:
        share_dir = get_package_share_directory(package_name)
        script_path = os.path.join(share_dir, 'scripts', 'app.py')

        if not os.path.exists(script_path):
            print(f"Error: Streamlit app not found at {script_path}")
            return

        print(f"🚀 Launching HulkuBot AI GUI from: {script_path}")

        cmd = [sys.executable, "-m", "streamlit", "run", script_path,
               "--server.headless", "true"]
        subprocess.run(cmd)

    except Exception as e:
        print(f"Failed to launch GUI: {e}")


if __name__ == '__main__':
    main()
