# WFD Pro Clock - Project Wiki

## Overview
The **WFD Pro** is a 7x7 LED dot-matrix clock that connects via USB serial (CH340/CH341 chip). It displays time, animations, and supports various configuration options. The original Chinese configuration software (`WFDPro配置软件.exe`) was a PyInstaller-packaged PyQt5 app.

This project provides a pure Python replacement (`wfd_clock.py`) for controlling the clock, reverse-engineered from the original exe.

## Hardware
- **Display:** 7x7 LED matrix
- **Connection:** USB serial via CH340/CH341 chip
- **Driver:** CH341SER.EXE (included in `WFD Pro配置软件/`)
- **Baud Rate:** 115200
- **Serial Settings:** timeout=1s, DTR/RTS handshake required

## Serial Protocol

All commands start with header byte `0xAA` (170), followed by a command type byte.

### Command Reference

| Cmd Byte | Name | Payload | Description |
|----------|------|---------|-------------|
| `0x01` | Frame Data | `<total_frames> <frame_index+1> <7 row bytes> <time_slot>` | Send animation frame |
| `0x02` | Sensitivity | `<level 1-5>` | Set flip sensitivity |
| `0x03` | Display Mode | `<mode 1-4>` | Set display animation style |
| `0x04` | System Stats | `<cpu%> <mem%> <gpu%>` | Send CPU/MEM/GPU to bar display (0-100 each) |
| `0x05` | Sync Time | `<year-2000> <month> <day> <hour> <minute> <second>` | Set clock time |
| `0x06` | Night Mode | `<start_hour> <start_min> <end_hour> <end_min>` | Set night mode (all zeros = disabled) |
| `0x07` | Brightness | `<level 1-4>` | Set LED brightness |
| `0x08` | Hour Mode | `<0 or 1>` | 0=24h, 1=12h |
| `0x09` | Request Params | *(none)* | Request current device settings |

### Display Modes
| Value | Description |
|-------|-------------|
| 1 | Bottom to Top |
| 2 | Top to Bottom |
| 3 | Center to Sides |
| 4 | Sides to Center |

### Row Encoding (Frame Data)
Each row of the 7x7 matrix is encoded as a single byte:
- Bit 6 = column 0 (leftmost)
- Bit 5 = column 1
- ...
- Bit 0 = column 6 (rightmost)

Example: row `[0, 0, 1, 0, 1, 0, 0]` → `0b0010100` = `0x14` (20)

### Connection Handshake
1. Open serial port at 115200 baud, timeout=1
2. Set DTR=False, RTS=False
3. Wait 100ms
4. Set DTR=True, RTS=True
5. Wait for device to send text containing `初始化完成` ("initialization complete")
6. Send `[0xAA, 0x09]` to request current parameters

### Device Responses
The device sends:
- UTF-8 text messages (ready signal, status)
- Binary responses prefixed with `0xAA` + command type + data

Response parsing for `0xAA 0x09` returns current values for:
- Sensitivity (cmd 0x02, 1 byte)
- Display mode (cmd 0x03, 1 byte)
- Night mode (cmd 0x06, 4 bytes: start_h, start_m, end_h, end_m)
- Brightness (cmd 0x07, 1 byte)
- Hour mode (cmd 0x08, 1 byte)

## Animation JSON Format
Animations are stored as JSON arrays of frame objects:

```json
[
  {
    "data": [
      [0, 0, 1, 0, 1, 0, 0],
      [0, 1, 1, 1, 1, 1, 0],
      [1, 1, 1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1, 1, 1],
      [0, 1, 1, 1, 1, 1, 0],
      [0, 0, 1, 1, 1, 0, 0]
    ],
    "time_slot": 5
  }
]
```

- `data`: 7x7 array, 0=off, 1=on
- `time_slot`: display duration (1-20, roughly in 100ms units)

## File Structure
```
wfdpro/
├── wfd_clock.py                    # Main Python controller (CLI + library)
├── system_monitor.py               # Bonus: system monitor GUI (unrelated)
├── system_monitor_venv/            # Python venv with PyQt5, psutil, pyserial
├── extract_methods.py              # Script used to disassemble the exe bytecode
├── methods_disasm.txt              # Full disassembly of key methods
├── disasm_full.txt                 # Module-level disassembly
└── WFDPro配置软件.exe_extracted/   # Extracted PyInstaller contents
```

## Usage

### CLI Mode
```bash
cd wfdpro
system_monitor_venv\Scripts\activate  # or source on Linux/Mac
python wfd_clock.py
```

Commands at `wfd>` prompt:
- `time` - Sync clock to PC time
- `bright N` - Brightness 1-4
- `sens N` - Sensitivity 1-5
- `mode N` - Display mode 1-4
- `12h` / `24h` - Hour format
- `night HH:MM-HH:MM` - Night mode
- `night off` - Disable night mode
- `send FILE` - Send animation JSON
- `heart` - Quick heart pattern
- `params` - Read device settings
- `quit` - Exit

### Library Mode
```python
from wfd_clock import WFDClock
clock = WFDClock()
clock.connect("COM8")
clock.sync_time()
clock.set_brightness(3)
clock.send_animation_file("path/to/animation.json")
clock.disconnect()
```

## Reverse Engineering Notes
- Original exe: `WFDPro配置软件.exe` (~40MB, PyInstaller + Python 3.13)
- Extracted using `pyinstxtractor-ng`
- Main script: `20250610.pyc` (class `DotMatrixGUI` extending `QMainWindow`)
- Protocol decoded from bytecode disassembly using Python `dis` module
- 2305 lines of original source (line numbers from bytecode)
- Key imports: serial, PyQt5, requests, psutil, pyperclip, json
