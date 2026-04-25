"""
WFD Pro Clock - Python Serial Controller
Controls a WFD Pro 7x7 LED matrix clock via serial port (CH341 USB).

Protocol reverse-engineered from WFDPro配置软件.exe

Serial: 115200 baud, timeout=1s
All commands start with 0xAA (170) followed by a command type byte.
"""

import serial
import serial.tools.list_ports
import json
import time
import sys
from datetime import datetime


# =============================================================================
# Protocol Constants
# =============================================================================
HEADER = 0xAA  # 170 - all commands start with this

CMD_FRAME_DATA    = 0x01  # Send animation frame
CMD_SENSITIVITY   = 0x02  # Set sensitivity (1-5)
CMD_DISPLAY_MODE  = 0x03  # Set display mode (1-4)
CMD_SYSTEM_STATS  = 0x04  # Send CPU/MEM/GPU to bar display
CMD_SYNC_TIME     = 0x05  # Sync clock time
CMD_NIGHT_MODE    = 0x06  # Set night mode times
CMD_BRIGHTNESS    = 0x07  # Set brightness (1-4)
CMD_HOUR_MODE     = 0x08  # 12h/24h mode (1=12h, 0=24h)
CMD_REQUEST_PARAMS = 0x09  # Request current device settings

DISPLAY_MODES = {
    1: "Bottom to Top",
    2: "Top to Bottom",
    3: "Center to Sides",
    4: "Sides to Center",
}

BAUD_RATE = 115200
TIMEOUT = 1


# =============================================================================
# WFD Clock Controller
# =============================================================================
class WFDClock:
    def __init__(self, port=None):
        self.ser = None
        self.port = port
        self.is_device_ready = False

    @staticmethod
    def list_ports():
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [(p.device, p.description) for p in ports]

    def connect(self, port=None):
        """Connect to WFD clock on specified port."""
        if port:
            self.port = port

        if not self.port:
            raise ValueError("No port specified. Use list_ports() to find available ports.")

        # Close existing connection
        if self.ser and self.ser.is_open:
            self.ser.close()

        self.ser = serial.Serial(port=self.port, baudrate=BAUD_RATE, timeout=TIMEOUT)

        # DTR/RTS handshake sequence (required by WFD clock)
        self.ser.setDTR(False)
        self.ser.setRTS(False)
        time.sleep(0.1)
        self.ser.setDTR(True)
        self.ser.setRTS(True)

        self.is_device_ready = False
        print(f"Connected to {self.port} (waiting for device ready...)")

        # Wait for device ready signal
        self._wait_for_ready()

    def _wait_for_ready(self, timeout=5):
        """Wait for device to send ready signal."""
        start = time.time()
        buffer = bytearray()
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                buffer.extend(data)
                try:
                    text = buffer.decode('utf-8')
                    # Device sends text containing "初始化完成" when ready
                    if '初始化完成' in text:
                        self.is_device_ready = True
                        print("Device ready!")
                        # Request current params
                        self.request_params()
                        return True
                except UnicodeDecodeError:
                    pass
            time.sleep(0.1)
        print("Warning: Device did not send ready signal within timeout.")
        return False

    def disconnect(self):
        """Disconnect from the clock."""
        if self.ser and self.ser.is_open:
            # Pulse DTR to trigger a clean reset so the clock resumes normal mode
            self.ser.setDTR(False)
            self.ser.setRTS(False)
            time.sleep(0.1)
            self.ser.setDTR(True)
            self.ser.setRTS(True)
            time.sleep(0.1)
            self.ser.close()
        self.ser = None
        self.is_device_ready = False
        print("Disconnected.")

    def _send(self, data):
        """Send raw bytes to the device."""
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Not connected. Call connect() first.")
        self.ser.write(data)

    # ---- Commands ----

    def sync_time(self, dt=None):
        """Sync the clock time. Uses current time if dt is None."""
        if dt is None:
            dt = datetime.now()

        time_data = bytearray([
            HEADER,
            CMD_SYNC_TIME,
            dt.year - 2000,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
        ])
        self._send(time_data)
        print(f"Time synced: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def set_brightness(self, level):
        """Set brightness level (1-4)."""
        level = max(1, min(4, int(level)))
        self._send(bytearray([HEADER, CMD_BRIGHTNESS, level]))
        print(f"Brightness set to {level}")

    def send_system_stats(self, cpu, mem, gpu=0):
        """Send system stats to the dedicated bar display.
        cpu: CPU usage percentage (0-100)
        mem: Memory usage percentage (0-100)
        gpu: GPU usage percentage (0-100)
        """
        cpu = max(0, min(100, int(cpu)))
        mem = max(0, min(100, int(mem)))
        gpu = max(0, min(100, int(gpu)))
        self._send(bytearray([HEADER, CMD_SYSTEM_STATS, cpu, mem, gpu]))
        print(f"System stats sent: CPU={cpu}% MEM={mem}% GPU={gpu}%")

    def set_sensitivity(self, level):
        """Set sensitivity level (1-5)."""
        level = max(1, min(5, int(level)))
        self._send(bytearray([HEADER, CMD_SENSITIVITY, level]))
        print(f"Sensitivity set to {level}")

    def set_display_mode(self, mode):
        """Set display mode (1-4). See DISPLAY_MODES dict."""
        mode = max(1, min(4, int(mode)))
        self._send(bytearray([HEADER, CMD_DISPLAY_MODE, mode]))
        print(f"Display mode set to {mode} ({DISPLAY_MODES.get(mode, '?')})")

    def set_hour_mode(self, use_12h=True):
        """Toggle 12h/24h mode. True = 12h, False = 24h."""
        val = 1 if use_12h else 0
        self._send(bytearray([HEADER, CMD_HOUR_MODE, val]))
        print(f"Hour mode: {'12h' if use_12h else '24h'}")

    def set_night_mode(self, start_hour=0, start_min=0, end_hour=0, end_min=0):
        """Set night mode time range. All zeros = disabled."""
        self._send(bytearray([
            HEADER, CMD_NIGHT_MODE,
            start_hour, start_min,
            end_hour, end_min,
        ]))
        if start_hour == 0 and start_min == 0 and end_hour == 0 and end_min == 0:
            print("Night mode disabled")
        else:
            print(f"Night mode: {start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}")

    def request_params(self):
        """Request current device settings. Device will respond with config data."""
        self._send(bytearray([HEADER, CMD_REQUEST_PARAMS]))
        print("Requested device parameters")

    # ---- Frame / Animation ----

    @staticmethod
    def _encode_row(row):
        """Encode a 7-element row list [0/1, ...] into a single byte.
        bit6=col0, bit5=col1, ..., bit0=col6
        """
        byte = 0
        for i, bit in enumerate(row):
            if bit:
                byte |= (1 << (6 - i))
        return byte

    def send_frame(self, frame_data, frame_index, total_frames):
        """Send a single animation frame.

        frame_data: dict with 'data' (7x7 matrix) and 'time_slot' (1-20)
        """
        buf = bytearray()
        buf.append(HEADER)
        buf.append(CMD_FRAME_DATA)
        buf.append(total_frames)
        buf.append(frame_index + 1)  # 1-based

        for row in frame_data['data']:
            buf.append(self._encode_row(row))

        time_slot = max(1, min(20, frame_data.get('time_slot', 5)))
        buf.append(time_slot)

        self._send(buf)
        print(f"  Sent frame {frame_index + 1}/{total_frames} "
              f"(time_slot={time_slot}, bytes={' '.join(f'{b:02X}' for b in buf)})")

    def send_animation(self, frames):
        """Send a full animation (list of frame dicts).

        Each frame: {"data": [[0/1]*7]*7, "time_slot": int}
        """
        total = len(frames)
        print(f"Sending {total} frames...")
        for i, frame in enumerate(frames):
            self.send_frame(frame, i, total)
            time.sleep(0.1)  # Small delay between frames
        print("Animation sent!")

    def send_animation_file(self, filepath):
        """Load and send an animation from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            frames = json.load(f)
        self.send_animation(frames)

    # ---- Read response ----

    def read_response(self, timeout=2):
        """Read and parse response from device."""
        start = time.time()
        buffer = bytearray()
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                buffer.extend(data)

                # Try to decode text portion
                try:
                    text = buffer.decode('utf-8')
                    print(f"  Device text: {text.strip()}")
                except UnicodeDecodeError:
                    pass

                # Parse binary commands (start with 0xAA)
                if len(data) >= 2 and data[0] == HEADER:
                    cmd_type = data[1]
                    self._parse_response(cmd_type, data)
                    return data
            time.sleep(0.05)
        return buffer if buffer else None

    def _parse_response(self, cmd_type, data):
        """Parse a binary response from the device."""
        if cmd_type == CMD_SENSITIVITY and len(data) >= 3:
            print(f"  Device sensitivity: {data[2]}")
        elif cmd_type == CMD_DISPLAY_MODE and len(data) >= 3:
            mode = data[2]
            print(f"  Device display mode: {mode} ({DISPLAY_MODES.get(mode, '?')})")
        elif cmd_type == CMD_NIGHT_MODE and len(data) >= 6:
            print(f"  Device night mode: {data[2]:02d}:{data[3]:02d} - {data[4]:02d}:{data[5]:02d}")
        elif cmd_type == CMD_BRIGHTNESS and len(data) >= 3:
            print(f"  Device brightness: {data[2]}")
        elif cmd_type == CMD_HOUR_MODE and len(data) >= 3:
            print(f"  Device hour mode: {'12h' if data[2] == 1 else '24h'}")


# =============================================================================
# Helper: Create simple patterns
# =============================================================================
def make_frame(matrix, time_slot=5):
    """Create a frame dict from a 7x7 matrix."""
    return {"data": matrix, "time_slot": time_slot}


def blank_matrix():
    """Return a blank 7x7 matrix."""
    return [[0]*7 for _ in range(7)]


def full_matrix():
    """Return a fully-lit 7x7 matrix."""
    return [[1]*7 for _ in range(7)]


def heart_pattern():
    """Return a heart shape on 7x7 matrix."""
    return [
        [0, 0, 1, 0, 1, 0, 0],
        [0, 1, 1, 1, 1, 1, 0],
        [1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1],
        [0, 1, 1, 1, 1, 1, 0],
        [0, 0, 1, 1, 1, 0, 0],
    ]


# =============================================================================
# CLI
# =============================================================================
def main():
    clock = WFDClock()

    # List ports
    ports = clock.list_ports()
    if not ports:
        print("No serial ports found. Is the clock connected?")
        print("Make sure CH341 driver is installed.")
        sys.exit(1)

    print("Available ports:")
    for i, (dev, desc) in enumerate(ports):
        print(f"  [{i}] {dev} - {desc}")

    # Auto-select if only one CH341 port
    ch341_ports = [(d, desc) for d, desc in ports if 'CH340' in desc or 'CH341' in desc or 'USB' in desc.upper()]
    if len(ch341_ports) == 1:
        port = ch341_ports[0][0]
        print(f"\nAuto-selected: {port}")
    elif len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        idx = int(input("\nSelect port number: "))
        port = ports[idx][0]

    # Connect
    clock.connect(port)

    # Interactive loop
    print("\nCommands:")
    print("  time       - Sync current time")
    print("  bright N   - Set brightness (1-4)")
    print("  sens N     - Set sensitivity (1-5)")
    print("  mode N     - Set display mode (1-4)")
    print("  12h / 24h  - Set hour mode")
    print("  night HH:MM-HH:MM  - Set night mode")
    print("  night off  - Disable night mode")
    print("  stats      - Send current CPU/MEM/GPU to bar display")
    print("  send FILE  - Send animation JSON file")
    print("  heart      - Send heart animation")
    print("  read       - Read device response")
    print("  params     - Request device params")
    print("  quit       - Exit")
    print()

    try:
        while True:
            raw = input("wfd> ").strip()
            if not raw:
                continue
            cmd = raw.lower()

            import shlex
            try:
                parts = shlex.split(raw)
            except ValueError:
                parts = raw.split()
            parts_lower = [p.lower() for p in parts]

            if parts_lower[0] in ('quit', 'exit', 'q'):
                break
            elif parts_lower[0] == 'time':
                clock.sync_time()
            elif parts_lower[0] == 'bright' and len(parts) > 1:
                clock.set_brightness(int(parts[1]))
            elif parts_lower[0] == 'sens' and len(parts) > 1:
                clock.set_sensitivity(int(parts[1]))
            elif parts_lower[0] == 'mode' and len(parts) > 1:
                clock.set_display_mode(int(parts[1]))
            elif parts_lower[0] == '12h':
                clock.set_hour_mode(True)
            elif parts_lower[0] == '24h':
                clock.set_hour_mode(False)
            elif parts_lower[0] == 'night':
                if len(parts) > 1 and parts_lower[1] == 'off':
                    clock.set_night_mode(0, 0, 0, 0)
                elif len(parts) > 1 and '-' in parts[1]:
                    start, end = parts[1].split('-')
                    sh, sm = map(int, start.split(':'))
                    eh, em = map(int, end.split(':'))
                    clock.set_night_mode(sh, sm, eh, em)
                else:
                    print("Usage: night HH:MM-HH:MM  or  night off")
            elif parts_lower[0] == 'send' and len(parts) > 1:
                clock.send_animation_file(parts[1])
            elif parts_lower[0] == 'stats':
                import psutil
                cpu = int(psutil.cpu_percent(interval=1))
                mem = int(psutil.virtual_memory().percent)
                clock.send_system_stats(cpu, mem, 0)
            elif parts_lower[0] == 'heart':
                frames = [make_frame(heart_pattern(), 10)]
                clock.send_animation(frames)
            elif parts_lower[0] == 'read':
                clock.read_response()
            elif parts_lower[0] == 'params':
                clock.request_params()
                time.sleep(0.5)
                clock.read_response()
            else:
                print(f"Unknown command: {raw}")

    except KeyboardInterrupt:
        print()
    finally:
        clock.disconnect()


if __name__ == '__main__':
    main()
