# 📘 Ignitron Preset Tools – macOS Guide

## 1. Running Directly with Python
If you already have Python 3 installed on your Mac:

```bash
# Clone the mac_support branch
git clone https://github.com/mpkottawa/ignitron-preset-tools.git -b mac_support
cd ignitron-preset-tools

# Make launcher executable
chmod +x run_mac.sh

# Run the tool
./run_mac.sh
```

👉 This requires Python 3 and `pyserial`. If needed, install with:
```bash
pip3 install pyserial
```

---

## 2. Using the Prebuilt macOS Binary
If you don’t want to install Python, you can grab a standalone binary.

1. Go to the repo’s [**Actions tab**](../../actions).  
2. Select the latest **macOS Build** run.  
3. Scroll down to **Artifacts** → download **IgnitronPresetTools-macOS.zip**.  
4. Extract the zip, then in Terminal:

```bash
cd ~/Downloads/IgnitronPresetTools-macOS
chmod +x ignitron_preset_tools
./ignitron_preset_tools
```

---

## 3. Notes
- The macOS build is currently **unsigned**. On first run, you may see a warning about unidentified developer.  
  - To bypass: right-click → **Open**, then confirm.  
- Tested builds target **macOS ARM64 (M1/M2/M3)**. For Intel Macs, you may need to rebuild locally using:
  ```bash
  pyinstaller --onefile ignitron_preset_tools.py
  ```

---

✅ With this file in place, Mac users will know exactly how to use your project.
