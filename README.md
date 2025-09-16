
<img width="1024" height="1024" alt="IPF" src="https://github.com/user-attachments/assets/c6bd31e3-f3af-44b6-a7b4-3e8ac541a622" />



# ignitron-preset-tools
backup and store custom presets on the ignitron pedal, pull presets live over serial.


Ignitron Preset Tools ■
Standalone Python tools for working with **Ignitron guitar pedal presets**.
This branch currently provides the **Live Capture Tool**:
a serial-based dumper that captures all presets directly from your pedal, saves them as JSON files, and
builds a UUID index.
■ Features
- Connects to an Ignitron pedal over serial (USB).
- Dumps each preset as a **JSON file**.
- Generates a `PresetListUUIDs_TIMESTAMP.txt` file with:
FileName.json UUID-IN-UPPERCASE
- Two pull modes:
1. **Only active presets** in the pedal’s `PresetList.txt`
2. **All presets** on the pedal
- Guitar-themed splash screen ■
- Optional **fast mode** (`--fast`) skips splash delays.
■ Output Example
After a capture, you’ll get a folder like:
```
presets_20250915_230901/
■■■ PresetListUUIDs_20250915_230901.txt
■■■ SweetChildOfMine.json
■■■ SlashAFD.json
■■■ NovemberRainSolo.json
■■■ ComfortablyNumbSolo.json
```
`PresetListUUIDs_20250915_230901.txt` contains lines like:```
SweetChildOfMine.json C6CC85D6-A6F5-4302-AFF6-0060D996A3B1
SlashAFD.json E476C555-23B8-437F-B870-727E3B3F4E6B
NovemberRainSolo.json 26D19176-2730-458E-8D8B-2566B6D10E52
```
■ Installation
Clone the repo:
```
git clone https://github.com/mpkottawa/ignitron-preset-tools
cd ignitron-preset-tools
```
Install dependencies:
```
pip install -r requirements.txt
```
■■ Usage
Run normally:
```
python live_capture.py
```
Run in fast mode (skip splash delays):
```
python live_capture.py --fast
```
### ■ Steps1. Start the tool.
2. Choose pull mode:
- `1` = only active presets from pedal’s `PresetList.txt`
- `2` = all presets
3. Choose COM port (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux).
4. **Hold PRESET 1 on the pedal** before continuing.
5. Press Enter → tool captures and saves presets.
■ Requirements
- Python **3.8+**
- `pyserial` (`pip install pyserial`)
■ License
MIT License. See LICENSE for details.
■ Credits
Built for Ignitron pedal users who don’t just play presets — they **collect them**.
