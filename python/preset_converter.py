#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ignitron Preset Converter App
-----------------------------
Batch convert preset JSON files into Ignitron format.

Handles:
- Old legacy format (with pedals like Compressor, UniVibe, DelayEchoFilt)
- Spark App backups (with "sigpath" and "meta")
- Skips already-converted Ignitron presets

Features:
- Recursive folder scanning (works with Spark App backup tree)
- Flattens all converted files into a single "converted" folder
- Each file is named after the preset's Name (spaces removed, UUID appended if duplicate)
- Live log window in GUI
- Popup after conversion to open folder or close
- Uses explorer on Windows (works with UNC paths, e.g., \\murphlink\...)
"""

import os
import json
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import sys

# Map old pedal names to Ignitron ones
PEDAL_MAP = {
    "Compressor": "LA2AComp",
    "Twin": "Rectifier",
    "UniVibe": "GuitarEQ6",
    "DelayEchoFilt": "DelayMono"
    # Extend this mapping as needed
}

# ---------- Conversion Functions ----------

def convert_old_preset(old_preset: dict) -> dict:
    """Convert old legacy preset format into Ignitron format."""
    new_preset = {
        "PresetNumber": old_preset.get("PresetNumber", 0),
        "UUID": str(uuid.uuid4()),
        "Name": old_preset.get("Name", "ConvertedPreset"),
        "Version": old_preset.get("Version", "0.7"),
        "Description": old_preset.get("Description", ""),
        "Icon": old_preset.get("Icon", "icon.png"),
        "BPM": int(old_preset.get("BPM", 120)),
        "Pedals": [],
        "Checksum": "CA"
    }

    for pedal in old_preset.get("Pedals", []):
        name = pedal.get("Name", "")
        new_name = PEDAL_MAP.get(name, name)
        new_preset["Pedals"].append({
            "Name": new_name,
            "IsOn": pedal.get("IsOn", False),
            "Parameters": pedal.get("Parameters", [])
        })

    return new_preset


def convert_spark_app_preset(spark_preset: dict) -> dict:
    """Convert Spark app backup format into Ignitron format."""
    meta = spark_preset.get("meta", {})

    new_preset = {
        "PresetNumber": 127,  # default, can be adjusted if needed
        "UUID": meta.get("id", str(uuid.uuid4())),
        "Name": meta.get("name", "ConvertedPreset"),
        "Version": meta.get("version", "0.7"),
        "Description": meta.get("description", ""),
        "Icon": meta.get("icon", "icon.png"),
        "BPM": int(spark_preset.get("bpm", 120)),
        "Pedals": [],
        "Checksum": "CA"
    }

    for pedal in spark_preset.get("sigpath", []):
        params = [p.get("value", 0) for p in pedal.get("params", [])]
        new_preset["Pedals"].append({
            "Name": pedal.get("dspId", "Unknown"),
            "IsOn": pedal.get("active", False),
            "Parameters": params
        })

    return new_preset

# ---------- Format Detection ----------

def is_old_format(preset: dict) -> bool:
    """Detect if preset matches the old (pre-Ignitron) format."""
    if not isinstance(preset, dict):
        return False
    if "Pedals" not in preset:
        return False

    legacy_names = {"Compressor", "UniVibe", "DelayEchoFilt"}
    pedal_names = {p.get("Name", "") for p in preset.get("Pedals", [])}

    checksum = str(preset.get("Checksum", ""))

    if pedal_names & legacy_names:
        return True
    if checksum.isdigit():
        return True

    return False


def is_spark_app_format(preset: dict) -> bool:
    """Detect if preset comes directly from Spark app backup."""
    return "sigpath" in preset and "meta" in preset

# ---------- Folder Processing ----------

def safe_filename(name: str, uuid_str: str, out_folder: str) -> str:
    """Generate safe filename with spaces removed, fallback to UUID if needed."""
    base = name.replace(" ", "") or "ConvertedPreset"
    outfile = os.path.join(out_folder, f"{base}.json")
    if os.path.exists(outfile):
        outfile = os.path.join(out_folder, f"{base}_{uuid_str}.json")
    return outfile

def process_folder(folder: str, log_box):
    """Recursively process JSON files in a folder, converting as needed.
       Saves all converted files into a single 'converted' folder."""
    out_folder = os.path.join(folder, "converted")
    os.makedirs(out_folder, exist_ok=True)

    converted = 0
    skipped = 0

    for root, _, files in os.walk(folder):
        for filename in files:
            if not filename.lower().endswith(".json"):
                continue

            infile = os.path.join(root, filename)

            # Skip files already in converted folder
            if out_folder in infile:
                continue

            try:
                with open(infile, "r") as f:
                    data = json.load(f)

                if is_old_format(data):
                    new_data = convert_old_preset(data)
                elif is_spark_app_format(data):
                    new_data = convert_spark_app_preset(data)
                else:
                    log_box.insert(tk.END, f"⏭ Skipped (already Ignitron): {filename}\n")
                    skipped += 1
                    continue

                outfile = safe_filename(new_data.get("Name", "ConvertedPreset"),
                                        new_data["UUID"], out_folder)

                with open(outfile, "w") as f:
                    json.dump(new_data, f, indent=4)

                log_box.insert(tk.END, f"✔ Converted: {os.path.basename(outfile)}\n")
                converted += 1

            except Exception as e:
                log_box.insert(tk.END, f"❌ Error processing {filename}: {e}\n")

    log_box.insert(tk.END, f"\nDone! {converted} converted, {skipped} skipped.\n")
    log_box.see(tk.END)

    # Popup after completion
    if converted > 0:
        if messagebox.askyesno("Conversion Complete",
                               f"{converted} presets converted.\nOpen converted folder?"):
            open_folder_explorer(out_folder)

# ---------- Helpers ----------

def open_folder_explorer(path: str):
    """Open folder in system file explorer, UNC path safe with drive letter fallback."""
    if sys.platform.startswith("win"):
        # Normalize slashes
        norm_path = os.path.normpath(path)

        # If path starts with \\murphlink\murphlink, replace with M:\
        if norm_path.lower().startswith(r"\\murphlink\murphlink".lower()):
            drive_path = norm_path.replace(r"\\murphlink\murphlink", "M:", 1)
        else:
            drive_path = norm_path

        try:
            subprocess.Popen(["explorer", drive_path])
        except Exception:
            # fallback to UNC if replacement fails
            subprocess.Popen(["explorer", norm_path])

    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])  # macOS
    else:
        subprocess.Popen(["xdg-open", path])  # Linux


# ---------- GUI ----------

def choose_folder(log_box):
    folder = filedialog.askdirectory()
    if folder:
        process_folder(folder, log_box)

def main():
    root = tk.Tk()
    root.title("Ignitron Preset Converter")
    root.geometry("700x500")

    lbl = tk.Label(root, text="Select a folder with presets to convert", font=("Arial", 12))
    lbl.pack(pady=10)

    log_box = scrolledtext.ScrolledText(root, width=80, height=20, wrap=tk.WORD)
    log_box.pack(pady=10)

    btn = tk.Button(root, text="Choose Folder", command=lambda: choose_folder(log_box),
                    height=2, width=25)
    btn.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
