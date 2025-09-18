
<img width="1024" height="1024" alt="IPP" src="https://github.com/user-attachments/assets/7d3e422d-674f-4cb8-9652-00ece44fd6bd" />




Ignitron Preset Picker v1.0
===========================

A simple tool to build and export Spark-compatible preset lists.


How to Use
----------

1. Place !gnitron_preset_picker.exe inside your /data folder
   (where your .json presets are stored).

2. Double-click !gnitron_preset_picker.exe to launch.

3. When prompted, choose how many banks to start with
   (you can add/remove later).

4. Drag presets from the left pane into banks/slots on the right.
   - Double-click to quickly assign.
   - Right-click a slot to clear it.
   - Add Bank / Remove Bank buttons adjust layout dynamically.

5. Click Export to save:
   - PresetList.txt → ordered list of presets per bank.
   - PresetListUUIDs.txt → filenames + UUIDs of only the selected presets.

Both files will be written directly into the same /data folder,
overwriting previous versions.


Features
--------

- Dark Mode UI
- Dynamic banks (add/remove)
- Drag & drop preset assignment
- Auto-fill empty slots with last preset
