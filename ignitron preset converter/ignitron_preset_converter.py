#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ignitron Preset Converter / Manager
-----------------------------------

One-stop utility to:
- Parse Ignitron serial output to JSON preset files (and index)
- Convert stored .txt/.log dumps into JSONs
- GUI to build PresetList.txt by dragging presets into banks/slots
- Exports PresetList_* to ./dist (filenames only, no UUIDs)
- Serial live capture prefers only the pedal's active presets from LISTBANKS

Requirements:
    Python 3.8+
    Optional: pyserial (for live serial capture)
    Tkinter (standard on most Python installs)

Pack to EXE (example):
    pyinstaller --noconfirm --onefile --name "IgnitronPresetConverter" ignitron_preset_converter.py

"""

import os
import re
import sys
import json
import time
import queue
import random
import threading
import subprocess
import platform
from datetime import datetime
from pathlib import Path

# Optional serial import
try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:
    serial = None
    list_ports = None

# Optional tkinter import (GUI PresetList Builder)
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
except Exception:
    tk = None  # we’ll guard usage


# ==========================================================
# ----------------- Global Regex Patterns ------------------
# ==========================================================

FILENAME_RE = re.compile(r"Reading preset filename:\s*/?([^\s]+)")
JSON_RE = re.compile(r"JSON STRING:\s*(\{.*\})")
LISTBANKS_START_RE = re.compile(r"^\s*LISTBANKS_START\s*$")
LISTBANKS_DONE_RE = re.compile(r"^\s*LISTBANKS_DONE\s*$")
LISTPRESETS_START_RE = re.compile(r"^\s*LISTPRESETS_START\s*$")
LISTPRESETS_DONE_RE = re.compile(r"^\s*LISTPRESETS_DONE\s*$")
BANK_HEADER_RE = re.compile(r"^\s*--\s*Bank\s+(\d+)", re.IGNORECASE)

# ==========================================================
# ----------------- Utility & OS Helpers -------------------
# ==========================================================

def timestamp_now():
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def resolve_out_paths(base_out="presets_json", base_index="preset_index.txt"):
    """
    Build run-scoped, timestamped paths:
      - presets_json_YYYY-MM-DD_HH-MM/
      - preset_index_YYYY-MM-DD_HH-MM.txt
    """
    ts = timestamp_now()
    out_dir = Path(f"{base_out}_{ts}")
    index_path = Path(f"{Path(base_index).stem}_{ts}{Path(base_index).suffix}")
    return out_dir, index_path


def open_folder(path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        print(f"⚠️ Could not open folder automatically: {e}")


def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def print_divider(title: str = ""):
    print("\n" + ("-" * 48))
    if title:
        print(title)
        print("-" * 48)


# ==========================================================
# ------------------- Core Extraction ----------------------
# ==========================================================

def _extract_lines_to_files(lines, out_dir: Path, index_path: Path, include_only: set | None = None):
    """
    Parse streamed text lines that contain:
      "Reading preset filename: <name>"
      "JSON STRING: {...}"

    Save each preset JSON as <out_dir>/<filename>. If include_only is provided,
    only save filenames that are listed there (case-sensitive match on name).
    Write index with "filename.json UUID-IN-UPPERCASE".
    """
    safe_mkdir(out_dir)
    saved = 0
    skipped_dupe = 0
    skipped_no_filename = 0
    broken = 0
    skipped_not_in_list = 0
    entries = []

    current_filename = None

    for raw in lines:
        line = raw.rstrip("\r\n")

        # filename line
        fm = FILENAME_RE.search(line)
        if fm:
            current_filename = Path(fm.group(1).strip()).name
            continue

        # JSON line
        if "JSON STRING:" in line:
            jm = JSON_RE.search(line)
            if not jm:
                continue

            if not current_filename:
                skipped_no_filename += 1
                continue

            if include_only is not None and current_filename not in include_only:
                skipped_not_in_list += 1
                current_filename = None
                continue

            raw_json = jm.group(1).strip()
            try:
                parsed = json.loads(raw_json)
                out_file = out_dir / current_filename
                if out_file.exists():
                    skipped_dupe += 1
                else:
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(parsed, f, indent=4)
                    uuid = str(parsed.get("UUID", "UNKNOWN")).upper()
                    entries.append(f"{current_filename} {uuid}")
                    saved += 1
            except Exception:
                broken += 1
                # drop a broken stub for inspection
                stub = out_dir / (Path(current_filename).stem + "_BROKEN.json")
                try:
                    with open(stub, "w", encoding="utf-8") as f:
                        f.write(raw_json)
                except Exception:
                    pass

            current_filename = None  # reset for next

    if entries:
        with open(index_path, "a", encoding="utf-8") as idx:
            for e in entries:
                idx.write(e + "\n")

    return {
        "saved": saved,
        "skipped_dupe": skipped_dupe,
        "skipped_no_filename": skipped_no_filename,
        "broken": broken,
        "skipped_not_in_list": skipped_not_in_list,
    }


def extract_presets_from_log(log_path: Path, out_dir: Path, index_path: Path, include_only: set | None = None):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return _extract_lines_to_files(lines, out_dir, index_path, include_only=include_only)


def extract_presets_from_folder(folder: Path, out_dir: Path, index_path: Path, include_only: set | None = None):
    stats_total = {"saved": 0, "skipped_dupe": 0, "skipped_no_filename": 0, "broken": 0, "skipped_not_in_list": 0}
    files = list(folder.glob("*.txt")) + list(folder.glob("*.log"))
    if not files:
        print("ℹ️ No .txt or .log files found in that folder.")
        return stats_total

    for fp in files:
        print(f"\n📂 Processing {fp}")
        s = extract_presets_from_log(fp, out_dir, index_path, include_only=include_only)
        for k in stats_total:
            stats_total[k] += s[k]
    return stats_total


def cleanup_if_empty(stats, out_dir: Path, index_path: Path):
    if stats["saved"] == 0:
        if out_dir.exists():
            try:
                for f in out_dir.glob("*"):
                    f.unlink()
                out_dir.rmdir()
                print(f"🗑️ Removed empty folder: {out_dir}")
            except Exception:
                pass
        if index_path.exists():
            try:
                index_path.unlink()
                print(f"🗑️ Removed empty index: {index_path}")
            except Exception:
                pass


def print_summary(stats, out_dir: Path, index_path: Path):
    print("\n✅ Done.")
    print(f"Saved: {stats['saved']}")
    print(f"Duplicates skipped: {stats['skipped_dupe']}")
    print(f"Skipped (no filename): {stats['skipped_no_filename']}")
    if "skipped_not_in_list" in stats:
        print(f"Skipped (not in PresetList): {stats['skipped_not_in_list']}")
    print(f"Broken JSON: {stats['broken']}")

    if stats["saved"] > 0:
        print(f"\n📂 Presets saved in: {out_dir.resolve()}")
        print(f"📄 Index written to: {index_path.resolve()}")
        try:
            choice = input("\nOpen presets folder now? (Y/N): ").strip().lower()
        except KeyboardInterrupt:
            print()
            choice = "n"
        if choice == "y":
            open_folder(out_dir)
    else:
        cleanup_if_empty(stats, out_dir, index_path)
        print("\nℹ️ No presets saved this run.")


# ==========================================================
# ------------------ Serial Live Capture -------------------
# ==========================================================

class SerialReader(threading.Thread):
    """
    Line-buffered serial reader on a background thread.
    Pushes decoded lines into a queue.
    """
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
                    elif b == 13:  # CR - ignore
                        continue
                    else:
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


def parse_presetlist_from_lines(lines):
    """
    Given raw device lines (already normalised), extract the filenames
    listed in LISTBANKS block (if present) as a set.
    Format example:
        -- Bank 1
        FileA.json
        FileB.json
        FileC.json
        FileD.json
        -- Bank 2
        ...
    """
    in_section = False
    keep = []
    for ln in lines:
        if LISTBANKS_START_RE.match(ln):
            in_section = True
            continue
        if LISTBANKS_DONE_RE.match(ln):
            in_section = False
            break
        if in_section:
            # skip bank header lines, otherwise take filename line (only .json names)
            if BANK_HEADER_RE.match(ln):
                continue
            candidate = ln.strip()
            if not candidate:
                continue
            if candidate.lower().endswith(".json"):
                # store basename only
                keep.append(Path(candidate).name)
    return set(keep)


def live_serial_capture_and_save(port: str,
                                 baud: int = 115200,
                                 include_only_active: bool = True,
                                 open_folder_after: bool = True):
    """
    Connect to Ignitron serial, request LISTBANKS (to know which presets are active),
    then request LISTPRESETS and save the intersection. If bank list absent, saves all.

    Also, if bank list was present, create ./dist/PresetList_*.txt (filenames only).
    """
    if serial is None:
        print("❌ pyserial is not installed. Install with: pip install pyserial")
        return

    out_dir, index_path = resolve_out_paths()
    safe_mkdir(out_dir)

    print_divider("Serial Live Capture")
    print(f"Opening {port} @ {baud} ...")

    reader = SerialReader(port, baud)
    reader.start()
    time.sleep(0.2)

    all_lines = []

    # Step 1: List banks
    print("→ Requesting LISTBANKS ...")
    reader.write_line("LISTBANKS")
    banks_lines = []
    got_banks = False
    start_ts = time.time()
    while time.time() - start_ts < 5.0:  # up to 5 seconds for bank data
        try:
            typ, payload = reader.q.get(timeout=0.25)
        except queue.Empty:
            continue

        if typ == "__ERROR__":
            print(payload)
            break
        if typ == "line":
            line = payload
            all_lines.append(line)
            if LISTBANKS_START_RE.match(line):
                got_banks = True
            if got_banks:
                banks_lines.append(line)
            if LISTBANKS_DONE_RE.match(line):
                break

    include_only = set()
    if include_only_active and banks_lines:
        include_only = parse_presetlist_from_lines(banks_lines)
        if include_only:
            print(f"✅ Pedal PresetList detected: {len(include_only)} filenames to keep.")
        else:
            print("ℹ️ LISTBANKS returned, but no filenames found. Will save all.")
    else:
        if include_only_active:
            print("ℹ️ No LISTBANKS response. Will save all presets.")
        include_only = None  # None => do not filter

    # Step 2: List presets
    print("→ Requesting LISTPRESETS ...")
    reader.write_line("LISTPRESETS")

    # Collect until LISTPRESETS_DONE
    presets_lines = []
    got_lp = False
    start_ts = time.time()
    # Allow plenty of time if there are many presets
    while time.time() - start_ts < 60.0:
        try:
            typ, payload = reader.q.get(timeout=0.5)
        except queue.Empty:
            # Wait a bit more; if we already saw DONE, break
            if got_lp:
                break
            continue

        if typ == "__ERROR__":
            print(payload)
            break
        if typ == "line":
            line = payload
            all_lines.append(line)
            if LISTPRESETS_START_RE.match(line):
                got_lp = True
            if got_lp:
                presets_lines.append(line)
            if LISTPRESETS_DONE_RE.match(line):
                break

    # Extract from presets_lines
    stats = _extract_lines_to_files(presets_lines, out_dir, index_path, include_only=include_only)

    # If we had LISTBANKS and include_only is used, also write a PresetList to ./dist
    if include_only_active and include_only:
        ts = timestamp_now()
        dist_dir = Path("dist")
        safe_mkdir(dist_dir)
        presetlist_fp = dist_dir / f"PresetList_{ts}.txt"
        # group in banks of 4, keep order as received is unknown; here we just chunk in 4s
        files = list(include_only)
        with open(presetlist_fp, "w", encoding="utf-8") as f:
            bank_num = 1
            for i in range(0, len(files), 4):
                f.write(f"-- Bank {bank_num}\n")
                chunk = files[i:i+4]
                for fn in chunk:
                    f.write(fn + "\n")
                bank_num += 1
        print(f"📄 PresetList written to: {presetlist_fp.resolve()}")

    # Finish up
    reader.stop()
    reader.join(timeout=1.0)

    print_summary(stats, out_dir, index_path)

    if stats["saved"] > 0 and open_folder_after:
        try:
            choice = input("\nOpen presets folder now? (Y/N): ").strip().lower()
        except KeyboardInterrupt:
            print()
            choice = "n"
        if choice == "y":
            open_folder(out_dir)


# ==========================================================
# ----------------- PresetList Builder GUI -----------------
# ==========================================================

class PresetListBuilder(tk.Toplevel):
    """
    Drag-and-drop & double-click GUI to assemble PresetList.
    - Left: all *.json in a chosen folder (color-coded)
        * orange: not used
        * green: used at least once
    - Right: banks × 4 slots
    - Buttons: Export, Clear All, Random Fill, Close
    - Double-click a preset → fills next empty slot (top-left → bottom-right)
    - Dragging supported (start in list → drop over slot)
    - Export writes to ./dist/PresetList_*.txt (filenames only).
    """
    def __init__(self, master):
        super().__init__(master)
        self.title("PresetList Builder")
        self.geometry("1200x760")
        self.minsize(1100, 640)

        # Ask number of banks
        self.bank_count = None
        while self.bank_count is None:
            value = simpledialog.askinteger("Banks", "Enter number of banks (1–30):", parent=self, minvalue=1, maxvalue=30)
            if value is None:
                messagebox.showinfo("Canceled", "No bank count entered, closing.")
                self.destroy()
                return
            self.bank_count = value

        # Ask presets folder
        self.presets_dir = filedialog.askdirectory(parent=self, title="Select presets folder (JSON files)")
        if not self.presets_dir:
            messagebox.showinfo("Canceled", "No folder selected, closing.")
            self.destroy()
            return
        self.presets_dir = Path(self.presets_dir)

        # Load presets
        self.presets = self._load_presets(self.presets_dir)
        if not self.presets:
            messagebox.showerror("No presets", "No .json presets found in that folder.")
            self.destroy()
            return

        # State
        self.used_counts = {p["filename"]: 0 for p in self.presets}
        self.slots = {(b, s): None for b in range(1, self.bank_count + 1) for s in range(1, 5)}
        self.last_placed_global = None

        # Drag variables
        self.dragging_name = None
        self.drag_ghost = None

        # Build UI
        self._build_ui()

        # Keybinds
        self.bind("<Escape>", lambda e: self._cancel_drag())

        # on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------- File loading ---------
    def _load_presets(self, folder: Path):
        presets = []
        for jf in sorted(folder.glob("*.json")):
            try:
                with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                uuid = str(data.get("UUID", "UNKNOWN")).upper()
                presets.append({"filename": jf.name, "uuid": uuid, "name": str(data.get("Name", jf.stem))})
            except Exception:
                presets.append({"filename": jf.name, "uuid": "UNKNOWN", "name": jf.stem})
        return presets

    # --------- UI build ---------
    def _build_ui(self):
        wrapper = ttk.Frame(self)
        wrapper.pack(fill="both", expand=True)

        left = ttk.Frame(wrapper)
        left.pack(side="left", fill="y", padx=12, pady=12)

        ttk.Label(left, text="Presets (double-click to add / drag to slot)").pack(anchor="w")
        self.preset_list = tk.Listbox(left, width=44, height=34, activestyle="none")
        self.preset_list.pack(fill="y", expand=False)

        for p in self.presets:
            self.preset_list.insert("end", p["filename"])

        self._refresh_list_colors()

        # List interactions
        self.preset_list.bind("<ButtonPress-1>", self._start_drag_from_list)
        self.preset_list.bind("<B1-Motion>", self._update_drag)
        self.preset_list.bind("<ButtonRelease-1>", self._drop_anywhere)
        self.preset_list.bind("<Double-Button-1>", self._on_double_click)

        # Buttons on left
        ttk.Button(left, text="Export PresetList", command=self._export).pack(pady=(12, 4), fill="x")
        ttk.Button(left, text="Random Fill Unfilled", command=self._random_fill).pack(pady=4, fill="x")
        ttk.Button(left, text="Clear All", command=self._clear_all).pack(pady=4, fill="x")
        ttk.Button(left, text="Close", command=self._on_close).pack(pady=(16, 0), fill="x")

        # Right: scrollable banks grid
        right_container = ttk.Frame(wrapper)
        right_container.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        canvas = tk.Canvas(right_container, borderwidth=0)
        vscroll = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        self.grid_frame = ttk.Frame(canvas)

        self.grid_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        self.slot_widgets = {}
        # Build banks
        for b in range(1, self.bank_count + 1):
            bank_lab = ttk.Label(self.grid_frame, text=f"Bank {b}", font=("Segoe UI", 10, "bold"))
            bank_lab.grid(row=(b - 1) * 2, column=0, columnspan=4, sticky="w", pady=(8, 2))

            row = (b - 1) * 2 + 1
            for s in range(1, 5):
                lbl = tk.Label(
                    self.grid_frame,
                    text="[Empty]",
                    bd=1,
                    relief="groove",
                    width=32,
                    height=2,
                    bg="#e5e7eb",  # gray-200
                )
                lbl.grid(row=row, column=s - 1, padx=6, pady=6, sticky="nsew")
                lbl._bank = b
                lbl._slot = s
                lbl.bind("<Enter>", self._slot_hover)
                lbl.bind("<Leave>", self._slot_unhover)
                lbl.bind("<ButtonRelease-1>", self._drop_on_slot)
                lbl.bind("<Button-3>", self._clear_slot)  # right-click clear
                self.slot_widgets[(b, s)] = lbl

        for s in range(4):
            self.grid_frame.grid_columnconfigure(s, weight=1)

    # --------- Double-click behavior ---------
    def _on_double_click(self, event):
        idx = self.preset_list.curselection()
        if not idx:
            return
        filename = self.preset_list.get(idx[0])
        # find next empty slot in reading order
        for b in range(1, self.bank_count + 1):
            for s in range(1, 5):
                if self.slots[(b, s)] is None:
                    self._assign_to_slot(b, s, filename)
                    return
        messagebox.showinfo("All filled", "All slots are filled. Clear a slot or increase banks.")

    # --------- Random fill ---------
    def _random_fill(self):
        if not self.presets:
            return
        filenames = [p["filename"] for p in self.presets]
        empties = [(b, s) for (b, s), v in self.slots.items() if v is None]
        if not empties:
            messagebox.showinfo("Nothing to fill", "All slots are already filled.")
            return
        for (b, s) in empties:
            self._assign_to_slot(b, s, random.choice(filenames))

    # --------- Drag & drop helpers ---------
    def _start_drag_from_list(self, event):
        idx = self.preset_list.nearest(event.y)
        if idx < 0:
            return
        filename = self.preset_list.get(idx)
        self.dragging_name = filename
        self._create_ghost(event.x_root, event.y_root, filename)

    def _create_ghost(self, x_root, y_root, text):
        self._remove_ghost()
        self.drag_ghost = tk.Toplevel(self)
        self.drag_ghost.overrideredirect(True)
        label = tk.Label(self.drag_ghost, text=text, bg="#fde68a", bd=1, relief="solid")  # amber
        label.pack()
        self._move_ghost(x_root, y_root)

    def _move_ghost(self, x_root, y_root):
        if self.drag_ghost is not None:
            self.drag_ghost.geometry(f"+{x_root+12}+{y_root+12}")

    def _remove_ghost(self):
        if self.drag_ghost is not None:
            try:
                self.drag_ghost.destroy()
            except Exception:
                pass
            self.drag_ghost = None

    def _update_drag(self, event):
        if self.dragging_name:
            self._move_ghost(self.winfo_pointerx(), self.winfo_pointery())

    def _drop_anywhere(self, event):
        if not self.dragging_name:
            return
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        if hasattr(widget, "_bank") and hasattr(widget, "_slot"):
            self._assign_to_slot(widget._bank, widget._slot, self.dragging_name)
        self.dragging_name = None
        self._remove_ghost()

    def _drop_on_slot(self, event):
        if not self.dragging_name:
            return
        widget = event.widget
        if hasattr(widget, "_bank") and hasattr(widget, "_slot"):
            self._assign_to_slot(widget._bank, widget._slot, self.dragging_name)
        self.dragging_name = None
        self._remove_ghost()

    def _cancel_drag(self):
        self.dragging_name = None
        self._remove_ghost()

    def _slot_hover(self, event):
        event.widget.configure(bg="#bfdbfe")  # blue-200

    def _slot_unhover(self, event):
        b, s = event.widget._bank, event.widget._slot
        val = self.slots[(b, s)]
        event.widget.configure(bg="#d1fae5" if val else "#e5e7eb")  # green if filled else gray

    # --------- Slot operations ---------
    def _assign_to_slot(self, bank, slot, filename):
        self.slots[(bank, slot)] = filename
        lbl = self.slot_widgets[(bank, slot)]
        lbl.configure(text=filename, bg="#d1fae5")  # green
        self.used_counts[filename] = self.used_counts.get(filename, 0) + 1
        self.last_placed_global = filename
        self._refresh_list_colors()

    def _clear_slot(self, event):
        lbl = event.widget
        b, s = lbl._bank, lbl._slot
        filename = self.slots[(b, s)]
        if filename:
            if filename in self.used_counts:
                self.used_counts[filename] = max(0, self.used_counts[filename] - 1)
            self.slots[(b, s)] = None
            lbl.configure(text="[Empty]", bg="#e5e7eb")
            self._refresh_list_colors()

    def _clear_all(self):
        for (b, s), lbl in self.slot_widgets.items():
            self.slots[(b, s)] = None
            lbl.configure(text="[Empty]", bg="#e5e7eb")
        for k in self.used_counts.keys():
            self.used_counts[k] = 0
        self.last_placed_global = None
        self._refresh_list_colors()

    def _refresh_list_colors(self):
        # Listbox per-item coloring (Tk 8.6+ supports .itemconfig)
        for i in range(self.preset_list.size()):
            fn = self.preset_list.get(i)
            used = self.used_counts.get(fn, 0) > 0
            if used:
                self.preset_list.itemconfig(i, {'bg': '#d1fae5', 'fg': '#065f46'})  # green
            else:
                self.preset_list.itemconfig(i, {'bg': '#ffedd5', 'fg': '#92400e'})  # orange

    # --------- Export (to ./dist) ---------
    def _export(self):
        # Build list of lines with banks + 4 lines (auto-fill with last placed if needed)
        lines = []
        globally_last = self.last_placed_global

        any_placed = any(v is not None for v in self.slots.values())
        if not any_placed:
            messagebox.showerror("Nothing placed", "Place at least one preset before exporting.")
            return

        for b in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {b}")
            assigned = [self.slots[(b, s)] for s in range(1, 5) if self.slots[(b, s)] is not None]
            if len(assigned) == 0:
                if globally_last is None:
                    messagebox.showerror("No presets", "No presets available to auto-fill empty banks.")
                    return
                assigned = [globally_last]

            while len(assigned) < 4:
                assigned.append(assigned[-1])

            for i in range(4):
                fn = assigned[i]
                lines.append(fn)

        ts = timestamp_now()
        dist_dir = Path("dist")
        safe_mkdir(dist_dir)
        file_name = f"PresetList_{ts}.txt"
        file_path = dist_dir / file_name
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            messagebox.showerror("Export failed", f"Could not write file:\n{e}")
            return

        messagebox.showinfo("Export Complete",
                            f"✅ {file_name} created with {self.bank_count} banks\nSaved in:\n{file_path.resolve()}")

        # open folder (dist)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{dist_dir}"')
            elif platform.system() == "Darwin":
                subprocess.call(["open", str(dist_dir)])
            else:
                subprocess.call(["xdg-open", str(dist_dir)])
        except Exception:
            pass

    # --------- Close & return to menu ---------
    def _on_close(self):
        try:
            self.destroy()
        except Exception:
            pass


# ==========================================================
# ----------------------- Menu UI --------------------------
# ==========================================================

def list_serial_ports():
    if list_ports is None:
        print("❌ pyserial is not installed. Install with: pip install pyserial")
        return []
    ports = list(list_ports.comports())
    result = []
    for p in ports:
        display = f"{p.device} - {p.description or ''}".strip()
        result.append((p.device, display))
    return result


def run_menu():
    while True:
        print("\n🎸 Ignitron Preset Converter / Manager")
        print("------------------------------------")
        print("1. Convert a single log file")
        print("2. Convert a folder of log files")
        print("3. Convert a full dump file")
        print("4. Build PresetList.txt from presets (GUI)")
        print("5. Live capture from Ignitron over Serial (save ALL presets)")
        print("6. Live capture from Ignitron (save ONLY presets found in pedal's PresetList)")
        print("7. Exit")

        try:
            choice = input("Select an option (1-7): ").strip()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

        if choice == "1":
            path_str = input("Enter the path to your log file: ").strip().strip('"')
            log_file = Path(path_str)
            if not log_file.exists():
                print("❌ File not found.")
                continue
            out_dir, index_path = resolve_out_paths()
            stats = extract_presets_from_log(log_file, out_dir, index_path)
            print_summary(stats, out_dir, index_path)
            input("\nPress Enter to return to menu...")

        elif choice == "2":
            folder_str = input("Enter the path to the folder with logs: ").strip().strip('"')
            folder = Path(folder_str)
            if not folder.exists() or not folder.is_dir():
                print("❌ Folder not found.")
                continue
            out_dir, index_path = resolve_out_paths()
            stats = extract_presets_from_folder(folder, out_dir, index_path)
            print_summary(stats, out_dir, index_path)
            input("\nPress Enter to return to menu...")

        elif choice == "3":
            dump_str = input("Enter the path to your full dump file: ").strip().strip('"')
            dump_file = Path(dump_str)
            if not dump_file.exists():
                print("❌ File not found.")
                continue
            out_dir, index_path = resolve_out_paths()
            stats = extract_presets_from_log(dump_file, out_dir, index_path)
            print_summary(stats, out_dir, index_path)
            input("\nPress Enter to return to menu...")

        elif choice == "4":
            if tk is None:
                print("❌ Tkinter is not available in this Python environment.")
                input("\nPress Enter to return to menu...")
                continue
            try:
                root = tk.Tk()
                root.withdraw()
                builder = PresetListBuilder(root)
                # Block here until window closes
                builder.wait_window()
                try:
                    root.destroy()
                except Exception:
                    pass
            except Exception as e:
                print(f"❌ Could not start GUI: {e}")
            # back to menu

        elif choice in ("5", "6"):
            if serial is None:
                print("❌ pyserial is not installed. Install with: pip install pyserial")
                input("\nPress Enter to return to menu...")
                continue

            ports = list_serial_ports()
            if not ports:
                print("❌ No serial ports found.")
                input("\nPress Enter to return to menu...")
                continue

            print("\nAvailable serial ports:")
            for idx, (_, display) in enumerate(ports, start=1):
                print(f"  {idx}. {display}")
            try:
                sel = int(input("Pick a port: ").strip())
                if sel < 1 or sel > len(ports):
                    print("❌ Invalid selection.")
                    continue
            except Exception:
                print("❌ Invalid selection.")
                continue

            port_name = ports[sel - 1][0]
            try:
                baud = int(input("Baud rate (default 115200): ").strip() or "115200")
            except Exception:
                baud = 115200

            include_only_active = (choice == "6")
            live_serial_capture_and_save(
                port=port_name,
                baud=baud,
                include_only_active=include_only_active,
                open_folder_after=True,
            )
            input("\nPress Enter to return to menu...")

        elif choice == "7":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice, try again.")


# ==========================================================
# ------------------------- Main ---------------------------
# ==========================================================

if __name__ == "__main__":
    run_menu()
