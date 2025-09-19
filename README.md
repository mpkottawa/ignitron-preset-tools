# Ignitron Preset Tools – Setup Guide

---

## 1. Enable Serial Commands in Firmware
Before flashing, modify your **Ignitron.ino** firmware to handle preset requests.  
Use the following snippets:

### 📦 Snippet A – At the TOP of Ignitron.ino
```cpp
#include "SparkPresetControl.h"

SparkPresetControl &presetControl = SparkPresetControl::getInstance();
📦 Snippet B – Add this NEW FUNCTION after your includes
cpp
Copy code
void handleSerialCommand(String cmd) {
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "LISTBANKS") {
        Serial.println("LISTBANKS_START");
        for (int b = 0; b < presetControl.getBankCount(); b++) {
            Serial.printf("-- Bank %d\n", b + 1);
            for (int s = 0; s < presetControl.getSlotsPerBank(); s++) {
                String filename = presetControl.getPresetFilename(b, s);
                if (filename.length() > 0) {
                    Serial.println(filename);
                }
            }
        }
        Serial.println("LISTBANKS_DONE");
    }

    else if (cmd == "LISTPRESETS") {
        Serial.println("LISTPRESETS_START");

        for (int i = 0; i < presetControl.getTotalPresets(); i++) {
            String filename = presetControl.getPresetFilenameByIndex(i);
            String json = presetControl.getPresetJsonByIndex(i);

            Serial.printf("Reading preset filename: %s\n", filename.c_str());
            Serial.print("JSON STRING: ");
            Serial.println(json);
        }

        Serial.println("LISTPRESETS_DONE");
    }
}
📦 Snippet C – Inside your loop()
cpp
Copy code
if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleSerialCommand(cmd);
}
2. Install Ignitron firmware
Flash the modified Ignitron.ino firmware to your ESP32 pedal (via PlatformIO or Arduino IDE).

Make sure the pedal boots and presets work normally before connecting to the tool.

3. Connect the Pedal
Plug your Ignitron pedal into your PC with a USB cable.

On Windows, check Device Manager → Ports to find which COM port the pedal is on.

4. Run Ignitron Preset Tools
Launch ignitron_preset_tools.exe

You’ll see the menu:

markdown
Copy code
==============================
 Ignitron Preset Tool (IPT)
==============================
1. Preset Picker
2. Preset Puller
3. App Scraper
4. Exit
Option 1 – Preset Picker → Build banks/slots and export PresetList.txt.

Option 2 – Preset Puller → Choose to grab only the pedal’s PresetList or all presets.

When prompted, hold Preset 1 button on your pedal, then press Enter.

Presets are saved into presets_YYYYMMDD_HHMMSS folder.

Option 3 – App Scraper → Stream presets directly as you switch them in the Spark App.

5. Results
Presets are saved as individual .json files.

A PresetListUUIDs.txt file is also created with preset UUIDs.

Files open in any text editor and can be reloaded into Ignitron or shared.
