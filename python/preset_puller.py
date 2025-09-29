#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ignitron Preset Puller v1.1
--------------------------------
Connects to the Ignitron pedal over serial, fetches either:
 - Only presets listed in the pedal's active PresetList
 - OR all presets stored on the pedal

Each preset is saved as JSON into ./presets_TIMESTAMP/

Usage:
    python puller.py
    python puller.py --fast   # skip splash delays
"""

import os
import re
import sys
import time
import json
import queue
import serial
import threading
import serial.tools.list_ports
from pathlib import Path
from datetime import datetime

# ==========================================================
# ------------------ Regex Patterns ------------------------
# ==========================================================
LISTBANKS_START_RE   = re.compile(r"^LISTBANKS_START", re.I)
LISTBANKS_DONE_RE    = re.compile(r"^LISTBANKS_DONE", re.I)
BANK_HEADER_RE       = re.compile(r"^--\s*Bank\b", re.I)

LISTPRESETS_START_RE = re.compile(r"^LISTPRESETS_START", re.I)
LISTPRESETS_DONE_RE  = re.compile(r"^LISTPRESETS_DONE", re.I)

# ==========================================================
# ------------------ Serial Reader -------------------------
# ==========================================================
class SerialReader(threading.Thread):
    """Line-buffered serial reader on a background thread."""
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.1):
        super().__init__(daemon=True)
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self._stop = threading.Event()
        self.q = queue.Queue()
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port_name, self.baud, timeout=self.timeout)
        except Exception as e:
            self.q.put(("__ERROR__", f"Serial open failed: {e}"))
            return

        buf = bytearray()
        try:
            while not self._stop.is_set():
                chunk = self.ser.read(1024)
                if not chunk:
                    continue
                for b in chunk:
                    if b == 10:  # LF
                        line = buf.decode(errors="ignore").rstrip("\r")
                        buf.clear()
                        self.q.put(("line", line))
                    elif b != 13:
                        buf.append(b)
        except Exception as e:
            self.q.put(("__ERROR__", f"Serial read error: {e}"))
        finally:
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def write_line(self, s: str):
        try:
            if self.ser and self.ser.is_open:
                self.ser.write((s + "\n").encode())
        except Exception:
            pass

# ==========================================================
# ------------------ Utilities -----------------------------
# ==========================================================
def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def timestamp_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def resolve_out_paths():
    ts = timestamp_now()
    out_dir = Path(f"presets_{ts}")
    return out_dir, ts

def print_divider(title=""):
    print("\n" + "="*60)
    if title:
        print(title)
        print("="*60)

def print_summary(stats, out_dir, ts):
    print("\n✅ Preset pull complete.")
    print(f"   Scanned:   {stats['scanned']}")
    print(f"   Saved:     {stats['saved']}")
    print(f"   Skipped:   {stats['skipped']}")
    print(f"   Duplicate: {stats['duplicate']}")
    print(f"   Folder:    {out_dir.resolve()}")

def open_folder(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f"open '{path}'")
        else:
            os.system(f"xdg-open '{path}'")
    except Exception:
        pass

def _basename(name: str) -> str:
    return Path(name.strip().lstrip("/")).name

def _clean_json_text(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start:end+1]
    return text

# ==========================================================
# ------------------ Preset Handling -----------------------
# ==========================================================
def parse_presetlist_from_lines(lines):
    in_section = False
    keep = []
    for ln in lines:
        if LISTBANKS_START_RE.match(ln):
            in_section = True
            continue
        if LISTBANKS_DONE_RE.match(ln):
            break
        if in_section:
            if BANK_HEADER_RE.match(ln):
                continue
            candidate = ln.strip()
            if candidate.lower().endswith(".json"):
                keep.append(_basename(candidate))
    return keep

def _normalize_for_ignitron(preset: dict) -> dict:
    # Strip Spark-only fields
    preset.pop("PresetNumber", None)

    # Ensure required Ignitron fields
    preset.setdefault("Version", "0.7")
    preset.setdefault("Description", "")
    preset.setdefault("Icon", "icon.png")
    preset.setdefault("BPM", 120.0)

    if "UUID" in preset:
        preset["UUID"] = str(preset["UUID"]).upper()

    return preset

def _write_preset_file(filename, buffer, out_dir, include_only):
    json_text = "\n".join(buffer)
    json_text = _clean_json_text(json_text)

    try:
        preset = json.loads(json_text)
        preset = _normalize_for_ignitron(preset)
        uuid_up = preset.get("UUID", "")

        base = _basename(filename)
        if (include_only is None) or (base in include_only):
            with open(out_dir / base, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2)
            return True, uuid_up
        return False, uuid_up

    except Exception as e:
        print(f"⚠️ Failed to process preset {filename}: {e}")
        return False, ""

def _extract_lines_to_files(lines, out_dir: Path, include_only=None):
    safe_mkdir(out_dir)
    scanned, saved, skipped, duplicate = 0, 0, 0, 0
    seen_files = set()

    filename, buffer = None, []
    collecting = False

    for ln in lines:
        low = ln.lower()

        if low.startswith("reading preset filename:"):
            if filename and buffer:
                scanned += 1
                base = _basename(filename)
                if base in seen_files:
                    duplicate += 1
                else:
                    ok, _ = _write_preset_file(filename, buffer, out_dir, include_only)
                    if ok:
                        saved += 1
                    else:
                        skipped += 1
                    seen_files.add(base)

            filename = ln.split(":", 1)[-1].strip()
            buffer = []
            collecting = False
            continue

        if ("JSON STRING" in ln and "{" in ln):
            collecting = True
            buffer.append(ln[ln.index("{"):])
            continue

        if ln.lstrip().startswith("{"):
            collecting = True
            buffer.append(ln)
            continue

        if collecting:
            buffer.append(ln)

    if filename and buffer:
        scanned += 1
        base = _basename(filename)
        if base in seen_files:
            duplicate += 1
        else:
            ok, _ = _write_preset_file(filename, buffer, out_dir, include_only)
            if ok:
                saved += 1
            else:
                skipped += 1
            seen_files.add(base)

    return {"scanned": scanned, "saved": saved, "skipped": skipped, "duplicate": duplicate}

# ==========================================================
# ------------------ Preset Pull ---------------------------
# ==========================================================
def pull_presets(port: str,
                 baud: int = 115200,
                 include_only_active: bool = True,
                 open_folder_after: bool = True):
    out_dir, ts = resolve_out_paths()
    safe_mkdir(out_dir)

    print_divider("Serial Preset Pull")
    print(f"Opening {port} @ {baud} ...")

    reader = SerialReader(port, baud)
    reader.start()
    time.sleep(0.2)

    # Step 1: LISTBANKS
    print("→ Requesting LISTBANKS ...")
    reader.write_line("LISTBANKS")
    banks_lines = []
    got_banks = False
    start_ts = time.time()
    while time.time() - start_ts < 5.0:
        try:
            typ, payload = reader.q.get(timeout=0.25)
        except queue.Empty:
            continue
        if typ == "line":
            line = payload
            if LISTBANKS_START_RE.match(line):
                got_banks = True
            if got_banks:
                banks_lines.append(line)
            if LISTBANKS_DONE_RE.match(line):
                break

    include_only = None
    if include_only_active and banks_lines:
        ordered_list = parse_presetlist_from_lines(banks_lines)
        include_only = set(ordered_list)
        if include_only:
            print(f"✅ Pedal PresetList detected: {len(include_only)} filenames to keep.")
        else:
            print("ℹ️ LISTBANKS returned, but no filenames found. Will save all.")

    # Step 2: LISTPRESETS
    print("→ Requesting LISTPRESETS ...")
    reader.write_line("LISTPRESETS")
    presets_lines = []
    got_lp = False
    start_ts = time.time()
    while time.time() - start_ts < 120.0:
        try:
            typ, payload = reader.q.get(timeout=0.5)
        except queue.Empty:
            if got_lp:
                break
            continue
        if typ == "line":
            line = payload
            if LISTPRESETS_START_RE.match(line):
                got_lp = True
            if got_lp:
                presets_lines.append(line)
            if LISTPRESETS_DONE_RE.match(line):
                break

    stats = _extract_lines_to_files(presets_lines, out_dir, include_only)

    reader.stop()
    reader.join(timeout=1.0)

    print_summary(stats, out_dir, ts)

    if stats["saved"] > 0 and open_folder_after:
        open_folder(out_dir)

# ==========================================================
# ------------------ Splash Screen -------------------------
# ==========================================================
def splash_screen(fast=False):
    print("="*60)
    print("    🎸  Ignitron Preset Puller  🎛️")
    print("    \"Because tone should be saved, not lost.\"")
    print("="*60, "\n")

    steps = [
        "Plugging in the cable... 🎤",
        "Warming up the tubes... 🔥",
        "Tuning the strings... 🎵",
        "Ready to rock! 🤘"
    ]
    for step in steps:
        print("   " + step)
        if not fast:
            time.sleep(0.8)
    print()

# ==========================================================
# ------------------ Entry Point ---------------------------
# ==========================================================
def choose_serial_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("❌ No serial ports found.")
        sys.exit(1)

    print("\nAvailable serial ports:")
    for i, p in enumerate(ports, 1):
        print(f"  {i}. {p.device} ({p.description})")

    while True:
        try:
            choice = int(input("\nSelect COM port number: ").strip())
            if 1 <= choice <= len(ports):
                return ports[choice - 1].device
        except ValueError:
            pass
        print("Invalid choice. Try again.")

if __name__ == "__main__":
    fast_mode = "--fast" in sys.argv
    splash_screen(fast=fast_mode)
    print_divider("Ignitron Preset Puller")

    print("Pull mode:")
    print("  1. Only presets in pedal’s PresetList.txt")
    print("  2. All presets on the pedal")
    while True:
        choice = input("Choose [1/2]: ").strip()
        if choice in ("1", "2"):
            include_only_active = (choice == "1")
            break
        print("Invalid choice. Please enter 1 or 2.")

    port = choose_serial_port()
    print("\n⚠️  Before connecting: HOLD PRESET 1 on the pedal.")
    input(f"Selected {port}. Press Enter when ready to continue...")

    pull_presets(
        port=port,
        baud=115200,
        include_only_active=include_only_active,
        open_folder_after=True
    )

    input("\nPress Enter to exit...")
