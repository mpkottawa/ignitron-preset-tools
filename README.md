<img width="1024" height="1024" alt="IPT" src="https://github.com/user-attachments/assets/232fbc66-9883-433b-a46b-68cead18deec" />

# Ignitron Preset Tools

*Shoutout to stangreg for this great project https://github.com/stangreg/Ignitron *

this program was coded 100% with chatgpt. I wanted a way to backup presets with ignitron, and struggled with pulling data back from the esp32 and converting it.  i simply asked chatgpt if it could
convert extracted raw preset data into usable .json files .  Then I just kept asking for more.

it includes the 3 standalone .exe's(preset_picker.exe, and preset_puller.exe, app_scraper.exe) which are all integrated with Ignitron Preset Tools.exe.  
To use, run  Ignitron Preset Tools.exe, which should be located inside the Ignitron Preset Tools which can be placed in the root directory of your `ignitron` folder:

```
/ignitron/Ignitron Preset Tools/ignitron_preset_tools.exe
```

To enable the Ignitron pedal to pull current pedal presets(by responding to the calls: LISTPRESETS and LISTBANKS), as well as stream presets from the app, two firmware files must be modified:

- `ignitron.ino` (main Ignitron folder) → **3 edits**  
- `SparkPresetControl.cpp` (in `/src` folder) → **1 edit**

You can either manually edit these files as described below, or replace them entirely with provided versions and update pedal-specific bits (pins, LEDs, display, etc.).

---

## A. Preset Pulling Setup  
(edit `/ignitron/ignitron.ino`)

### 1. Add this include at the top with the other libraries:
```cpp
#include <LittleFS.h>
```

---

### 2. Add this line right below `void loop()`:
```cpp
handleSerialCommands();   // so it will react to LISTPRESETS
```

---

### 3. Add the following block at the **end of the file**:
```cpp
// === BEGIN: LISTPRESETS serial support =======================================

// Case-insensitive “.json” check
static bool hasJsonExt(const char *name) {
  if (!name) return false;
  size_t len = strlen(name);
  if (len < 5) return false;
  const char *ext = name + (len - 5);
  return ext[0] == '.' &&
         (ext[1] == 'j' || ext[1] == 'J') &&
         (ext[2] == 's' || ext[2] == 'S') &&
         (ext[3] == 'o' || ext[3] == 'O') &&
         (ext[4] == 'n' || ext[4] == 'N');
}

// Dump entire JSON file to a single line (removes CR/LF/TAB)
static void printJsonFileSingleLine(File &f) {
  Serial.print("JSON STRING: ");
  while (f.available()) {
    char c = (char)f.read();
    if (c == '\r' || c == '\n' || c == '\t') continue;
    Serial.write(c);
  }
  Serial.println();
}

// List every *.json at the LittleFS root
static void listAllPresets() {
  Serial.println("LISTPRESETS_START");

  File root = LittleFS.open("/");
  if (!root) {
    Serial.println("⚠️ Could not open LittleFS root");
    Serial.println("LISTPRESETS_DONE");
    return;
  }

  while (true) {
    File f = root.openNextFile();
    if (!f) break;

    if (!f.isDirectory()) {
      const char *name = f.name();
      if (name && hasJsonExt(name)) {
        Serial.print("Reading preset filename: ");
        Serial.println(name);
        printJsonFileSingleLine(f);
      }
    }
    f.close();
  }

  Serial.println("LISTPRESETS_DONE");
}

// Robust line-buffered serial command reader
static void handleSerialCommands() {
  static String buf;

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      String cmd = buf;
      buf = "";
      cmd.trim();
      if (cmd.length() == 0) return;

      String u = cmd;
      u.toUpperCase();

      if (u == "LISTPRESETS") {
        listAllPresets();
      }
      if (u == "LISTBANKS") {
        File f = LittleFS.open("/PresetList.txt");
        if (f) {
          Serial.println("LISTBANKS_START");
          while (f.available()) {
            char c = f.read();
            if (c == '\r') continue;
            Serial.write(c);
          }
          Serial.println("LISTBANKS_DONE");
          f.close();
        } else {
          Serial.println("⚠️ PresetList.txt not found");
          Serial.println("LISTBANKS_DONE");
        }
      }
    } else {
      buf += c;
      if (buf.length() > 256) {
        buf.remove(0, buf.length() - 256);
      }
    }
  }
}

// === END: LISTPRESETS serial support =========================================
```

---

## B. Spark App Streaming Setup  
(edit `/ignitron/src/SparkPresetControl.cpp`)

Add the following lines **after** `DEBUG_PRINTLN(appReceivedPreset_.json.c_str());` inside  
`SparkPresetControl::updateFromSparkResponseAmpPreset`:

```cpp
// 🔧 Added for App Scraper
Serial.println("received from app:");
Serial.println(appReceivedPreset_.json.c_str());
```

### Final snippet should look like:
```cpp
void SparkPresetControl::updateFromSparkResponseAmpPreset(char *presetJson) {
    presetEditMode_ = PRESET_EDIT_STORE;
    appReceivedPreset_ = presetBuilder.getPresetFromJson(presetJson);

    DEBUG_PRINTLN("received from app:");
    DEBUG_PRINTLN(appReceivedPreset_.json.c_str());

    // 🔧 Added for App Scraper
    Serial.println("received from app:");
    Serial.println(appReceivedPreset_.json.c_str());

    presetNumToEdit_ = 0;
}
```

---

## Building
After edits, **compile and flash to pedal**.  
Enjoy!

---

# Ignitron Preset Tools Operation

## Overview
- Ensure your pedal connects to your device running the Spark app (BLE or SRL). I have only tested this over SRL. 

- Preset pulling only works when the pedal is connected via USB in **AMP mode** (hold switch 1 while booting). 

-before plugging in the usb, put the pedal in AMP mode(power it on while holding switch 1) 

- Keep switch 1 pressed while the tool starts its connection. The pedal will reboot, and you can release switch 1 after the screen cycles.  

---


### Main Menu
When you run `ignitron_preset_tools.exe`, you’ll see 4 options:

```
1. Preset Picker
2. Preset Puller
3. App Scraper
4. Exit
```

### 1. Preset Picker
**Description:**  
Load your `/data` folder of presets, organize them in the GUI, and export the 2 files needed to build your preset banks.
<img width="1914" height="1025" alt="Screenshot 2025-09-19 185020" src="https://github.com/user-attachments/assets/c4d7df5b-296b-4690-9aad-0d835d0a1afb" />

**OPERATION**
it starts with asking for how many banks, select 1-30.

<img width="218" height="142" alt="Screenshot 2025-09-19 184915" src="https://github.com/user-attachments/assets/3f0d051a-cc6f-4793-a56b-81f4f25aa419" />

then asks for your data folder, point it to /ignitron/data/.

<img width="779" height="498" alt="Screenshot 2025-09-19 184957" src="https://github.com/user-attachments/assets/a641fc86-161d-4f8b-95d0-d70b108447b2" />

after it opens up, you can see all presets from that folder on the left. you can then drag each preset to where you want it, if you double click it will 
add that preset to the next available slot. you can add or delete banks.  a button to fill all empty slots with random presets, will fill with unused presets from 
the left , then fill the rest with all presets in random locations to fill the grid.

when you're happy with your setup, hit the export button to update the /data/presetlist.txt, and the /data/PresetListUUIDs.txt, ready to upload to the pedal.  
Recompile and upload to the pedal and all your banks are where you put them.

it makes a presetlist.txt file like:
<img width="361" height="722" alt="Screenshot 2025-09-19 211613" src="https://github.com/user-attachments/assets/eeb15bff-ed62-4fc0-a372-c4fce5920a67" />

and the PresetListUUIDs.txt file like:
<img width="690" height="684" alt="Screenshot 2025-09-19 211746" src="https://github.com/user-attachments/assets/d68d71a6-bfbc-4f44-9d12-d7c4d5dd2ffa" />

which are formatted correctly, and directly ready to upload to your pedal upon save

---

### 2. Preset Scraper
**Description**

use this tool to retrieve, convert, and save presets from your ignitron pedal to your computer.  It pulls your presets saved to preset banks on the pedal, or pull all presets in the entire system.

**OPERATION**

preset puller starts and asks pull mode:

   1. Only presets in pedal's presetlist.txt

   2. All presets on the pedal


<img width="586" height="562" alt="Screenshot 2025-09-19 204658" src="https://github.com/user-attachments/assets/3024e33a-39b6-46ba-bebe-8c331e9ccfb9" />


 it then asks for your connection port, enter the corresponding number for that port

 
<img width="578" height="187" alt="Screenshot 2025-09-19 205323" src="https://github.com/user-attachments/assets/00ef57e0-18df-4fb8-9602-a4cd8bf34267" />


 at this point, hold down switch 1 on the pedal and hit enter, keep holding 1 until you see the screen reboot and be in AMP mode(shows BLE or SRL.
 it will display the results after.  


<img width="682" height="291" alt="Screenshot 2025-09-19 210222" src="https://github.com/user-attachments/assets/655a60e7-1a0f-451e-8e2d-8049cbae2f0b" />


it will then open the save folder which should be time stamped.


<img width="959" height="860" alt="Screenshot 2025-09-19 210209" src="https://github.com/user-attachments/assets/68e1246a-3708-424e-830d-f377f69218ba" />



all these can be moved to your data folder and used with preset picker to save them to the pedal.(although they were pulled from the pedal.


---

## 3. App Scraper
**Description:**  
this tool is my favourite.  you connect to the pedal over usb, connect the app to the pedal over bluetooth, it monitors for preset chitchat, converts 
and saves selected presets to your computer. click a preset in the app, it saves directly to your computer.








