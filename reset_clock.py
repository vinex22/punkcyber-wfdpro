"""
WFD Pro Clock - Factory Reset Script
Resets all known settings to defaults and clears any corrupted state.
Use this if the VU meter or other features stop working.

Usage: python reset_clock.py [PORT]
  PORT defaults to COM8 if not specified.
"""
from wfd_clock import WFDClock
import sys
import time

port = sys.argv[1] if len(sys.argv) > 1 else 'COM8'

clock = WFDClock()
print(f"Connecting to {port}...")
clock.connect(port)
time.sleep(1)

print("Resetting to factory defaults...")

# Reset known settings
clock.set_sensitivity(3)
time.sleep(0.1)
clock.set_display_mode(1)
time.sleep(0.1)
clock.set_brightness(2)
time.sleep(0.1)
clock.set_hour_mode(False)  # 24h
time.sleep(0.1)
clock.set_night_mode(0, 0, 0, 0)  # disabled
time.sleep(0.1)
clock.sync_time()
time.sleep(0.1)

# Clear any corrupted state from unknown commands (0x0A-0x10)
print("Clearing corrupted registers (0x0A-0x10)...")
for cmd in range(0x0A, 0x11):
    clock._send(bytearray([0xAA, cmd, 0]))
    time.sleep(0.1)

# Send blank frame to clear matrix
print("Clearing matrix display...")
clock._send(bytearray([0xAA, 0x01, 1, 1, 0, 0, 0, 0, 0, 0, 0, 5]))
time.sleep(0.2)

print("\nReset complete! Disconnecting...")
clock.disconnect()
print("Unplug USB, wait 3 seconds, and replug to fully restore.")
