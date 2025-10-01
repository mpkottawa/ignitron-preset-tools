#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ignitron Preset Tools v1.1.0 (All-in-One)
------------------------------------------
Includes three working apps merged together:
1) Preset Picker (GUI) with PresetList.pdf export
2) Preset Puller v1.1
3) Preset App Scraper
"""

import os, sys, time

# ==========================================================
# ===============  START: PRESET PICKER  ===================
# ==========================================================
# (code from preset_picker.py)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ignitron Preset Picker v1.0 + Preset Chart
-----------------------------------
Dark-mode GUI tool to build Spark-compatible PresetList.txt,
PresetListUUIDs.txt, and automatically generate presetlist.pdf
in the same folder.
"""

import sys, random, json, os, subprocess, platform
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ----------------- Preset Chart Generator -----------------
def generate_chart(base_dir):
    """Generate presetlist.pdf in the same folder as PresetList.txt"""
    txt_file = os.path.join(base_dir, "PresetList.txt")
    output_path = os.path.join(base_dir, "presetlist.pdf")

    if not os.path.exists(txt_file):
        print(f"❌ PresetList.txt not found at {txt_file}")
        return None

    # Parse presetlist.txt
    banks = {}
    current_bank = None
    with open(txt_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("-- Bank"):
                current_bank = line.replace("--", "").strip()
                banks[current_bank] = []
            else:
                name = line.replace(".json", "").replace("_", " ")
                banks[current_bank].append(name)

    # Build table
    header = ["Bank", "Slot 0", "Slot 1", "Slot 2", "Slot 3"]
    table_data = [header]
    for bank, presets in banks.items():
        while len(presets) < 4:
            presets.append("—")
        table_data.append([bank] + presets)

    # PDF setup
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph("<font color='#E74C3C'><b>Ignitron Preset Chart</b></font>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    table = Table(table_data, colWidths=[60, 110, 110, 110, 110])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.black),
        ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor("#E74C3C")),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1),
            [colors.HexColor("#FDF2E9"), colors.HexColor("#FAD7A0")]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#922B21")),
    ]))

    elements.append(table)
    doc.build(elements)

    print(f"✔ Preset chart generated: {output_path}")

    # Try auto-open
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", output_path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", output_path])
        else:
            subprocess.Popen(["xdg-open", output_path])
    except Exception as e:
        print(f"⚠️ Could not auto-open PDF: {e}")

    return output_path


# ----------------- Preset Picker GUI -----------------
class PresetPicker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ignitron Preset Picker v1.0")
        self.configure(bg="#1e1e1e")
        self.minsize(1200, 700)

        try:
            self.state("zoomed")   # works on Windows
        except Exception:
            self.attributes("-zoomed", True)

        self.bank_count = simpledialog.askinteger(
            "Banks", "Enter number of banks (1–30):",
            parent=self, minvalue=1, maxvalue=30
        )
        if not self.bank_count:
            self.destroy()
            return

        if getattr(sys, "frozen", False):
            default_dir = Path(sys.executable).parent
        else:
            default_dir = Path(__file__).parent

        self.presets_dir = filedialog.askdirectory(
            parent=self,
            title="Select presets folder (JSON files)",
            initialdir=default_dir
        )
        if not self.presets_dir:
            messagebox.showinfo("Canceled", "No folder selected, closing.")
            self.destroy()
            return
        self.presets_dir = Path(self.presets_dir)

        self.presets = self._load_presets(self.presets_dir)
        if not self.presets:
            messagebox.showerror("No presets", "No .json presets found in that folder.")
            self.destroy()
            return

        self.used_counts = {p["filename"]: 0 for p in self.presets}
        self.slots = {(b, s): None for b in range(1, self.bank_count + 1) for s in range(1, 5)}
        self.last_placed_global = None

        self.dragging_name = None
        self.drag_ghost = None

        self._build_ui()
        self._render_banks()
        self.after(200, self._fit_to_banks)

    # ----------------- Load Presets -----------------
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

    # ----------------- Build UI -----------------
    def _build_ui(self):
        banner = tk.Frame(self, bg="#D7261E", height=50)
        banner.pack(side="top", fill="x")
        tk.Label(
            banner, text="IGNITRON PRESET PICKER v1.0",
            bg="#D7261E", fg="white",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=20)

        wrapper = ttk.Frame(self)
        wrapper.pack(fill="both", expand=True)

        left = tk.Frame(wrapper, bg="#252526")
        left.pack(side="left", fill="y", padx=12, pady=12)

        tk.Label(left, text="Presets", fg="#dddddd", bg="#252526").pack(anchor="w")
        self.preset_list = tk.Listbox(
            left, width=44, height=34, activestyle="none",
            bg="#2c2c2c", fg="#dddddd", selectbackground="#444444"
        )
        self.preset_list.pack(fill="y", expand=False)

        for p in self.presets:
            self.preset_list.insert("end", p["filename"])

        self._refresh_list_colors()

        self.preset_list.bind("<ButtonPress-1>", self._start_drag_from_list)
        self.preset_list.bind("<B1-Motion>", self._update_drag)
        self.preset_list.bind("<ButtonRelease-1>", self._drop_anywhere)
        self.preset_list.bind("<Double-Button-1>", self._on_double_click)

        ttk.Button(left, text="Export", command=self._export).pack(pady=6, fill="x")
        ttk.Button(left, text="Fill Empty Slots", command=self._random_fill).pack(pady=6, fill="x")
        ttk.Button(left, text="Clear All", command=self._clear_all).pack(pady=6, fill="x")
        ttk.Button(left, text="Add Bank", command=self._add_bank).pack(pady=6, fill="x")
        ttk.Button(left, text="Close", command=self._on_close).pack(pady=6, fill="x")

        self.right_container = tk.Frame(wrapper, bg="#1e1e1e")
        self.right_container.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        self.canvas = tk.Canvas(self.right_container, bg="#1e1e1e", highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self.right_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        self.grid_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=self.canvas.winfo_width()))

        self._enable_canvas_mousewheel()
        self.slot_widgets = {}

    # ----------------- Mouse wheel handling -----------------
    def _enable_canvas_mousewheel(self):
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if hasattr(event, "num") and event.num in (4, 5):
            delta = -1 if event.num == 4 else 1
        else:
            delta = -1 * (event.delta // 120 if event.delta else 0)
        self.canvas.yview_scroll(delta, "units")

    # ----------------- Render Banks -----------------
    def _render_banks(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.slot_widgets.clear()

        for b in range(1, self.bank_count + 1):
            bank_frame = tk.Frame(self.grid_frame, bg="#1e1e1e")
            bank_frame.pack(fill="x", pady=(6, 2))

            tk.Label(
                bank_frame, text=f"Bank {b}", font=("Segoe UI", 12, "bold"),
                bg="#1e1e1e", fg="#dddddd"
            ).pack(side="left")

            btn = ttk.Button(bank_frame, text="❌ Remove", command=lambda bb=b: self._remove_bank(bb))
            btn.pack(side="right")

            slots_frame = tk.Frame(self.grid_frame, bg="#1e1e1e")
            slots_frame.pack(fill="x", pady=(0, 6))
            for s in range(1, 5):
                lbl = tk.Label(
                    slots_frame, text="[Empty]", bd=1, relief="groove",
                    width=32, height=2, bg="#333333", fg="#dddddd"
                )
                lbl.grid(row=0, column=s - 1, padx=6, pady=6, sticky="nsew")
                lbl._bank, lbl._slot = b, s
                lbl.bind("<Enter>", self._slot_hover)
                lbl.bind("<Leave>", self._slot_unhover)
                lbl.bind("<ButtonRelease-1>", self._drop_on_slot)
                lbl.bind("<Button-3>", self._clear_slot)
                self.slot_widgets[(b, s)] = lbl

    # ----------------- Add/Remove Banks -----------------
    def _add_bank(self):
        self.bank_count += 1
        self.slots.update({(self.bank_count, s): None for s in range(1, 5)})
        self._render_banks()
        self._fit_to_banks()

    def _remove_bank(self, b):
        if messagebox.askyesno("Confirm", f"Delete Bank {b}? Presets will be lost."):
            for bb in range(b, self.bank_count):
                for s in range(1, 5):
                    self.slots[(bb, s)] = self.slots.get((bb + 1, s))
            for s in range(1, 5):
                self.slots.pop((self.bank_count, s), None)
            self.bank_count -= 1
            self._render_banks()
            self._fit_to_banks()

    # ----------------- Smart Fill -----------------
    def _random_fill(self):
        if not self.presets:
            return

        all_files = [p["filename"] for p in self.presets]
        used = {fn for fn in self.slots.values() if fn}
        unused = [fn for fn in all_files if fn not in used]

        empties = [(b, s) for (b, s), v in self.slots.items() if v is None]
        if not empties:
            messagebox.showinfo("Nothing to fill", "All slots are already filled.")
            return

        random.shuffle(unused)
        for (b, s) in empties:
            if unused:
                self._assign_to_slot(b, s, unused.pop())
            else:
                break

        empties = [(b, s) for (b, s), v in self.slots.items() if v is None]
        for (b, s) in empties:
            self._assign_to_slot(b, s, random.choice(all_files))

    # ----------------- Double-click -----------------
    def _on_double_click(self, event):
        idx = self.preset_list.curselection()
        if not idx:
            return
        filename = self.preset_list.get(idx[0])
        for b in range(1, self.bank_count + 1):
            for s in range(1, 5):
                if self.slots[(b, s)] is None:
                    self._assign_to_slot(b, s, filename)
                    return

    # ----------------- Drag & Drop -----------------
    def _start_drag_from_list(self, event):
        idx = self.preset_list.nearest(event.y)
        if idx < 0:
            return
        self.dragging_name = self.preset_list.get(idx)
        self._create_ghost(event.x_root, event.y_root, self.dragging_name)

    def _create_ghost(self, x, y, text):
        self._remove_ghost()
        self.drag_ghost = tk.Toplevel(self)
        self.drag_ghost.overrideredirect(True)
        lbl = tk.Label(self.drag_ghost, text=text, bg="#555555", fg="white", bd=1, relief="solid")
        lbl.pack()
        self._move_ghost(x, y)

    def _move_ghost(self, x, y):
        if self.drag_ghost:
            self.drag_ghost.geometry(f"+{x+12}+{y+12}")

    def _remove_ghost(self):
        if self.drag_ghost:
            self.drag_ghost.destroy()
            self.drag_ghost = None

    def _update_drag(self, event):
        if self.dragging_name:
            self._move_ghost(self.winfo_pointerx(), self.winfo_pointery())

    def _drop_anywhere(self, event):
        if not self.dragging_name:
            return
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        if hasattr(widget, "_bank"):
            self._assign_to_slot(widget._bank, widget._slot, self.dragging_name)
        self.dragging_name = None
        self._remove_ghost()

    def _drop_on_slot(self, event):
        if not self.dragging_name:
            return
        self._assign_to_slot(event.widget._bank, event.widget._slot, self.dragging_name)
        self.dragging_name = None
        self._remove_ghost()

    # ----------------- Slot ops -----------------
    def _assign_to_slot(self, b, s, fn):
        self.slots[(b, s)] = fn
        lbl = self.slot_widgets[(b, s)]
        lbl.configure(text=fn, bg="#2d6a4f")
        self.used_counts[fn] = self.used_counts.get(fn, 0) + 1
        self.last_placed_global = fn
        self._refresh_list_colors()

    def _clear_slot(self, event):
        lbl = event.widget
        b, s = lbl._bank, lbl._slot
        fn = self.slots[(b, s)]
        if fn:
            self.used_counts[fn] = max(0, self.used_counts[fn] - 1)
            self.slots[(b, s)] = None
            lbl.configure(text="[Empty]", bg="#333333")
            self._refresh_list_colors()

    def _clear_all(self):
        for k in self.slots.keys():
            self.slots[k] = None
        for lbl in self.slot_widgets.values():
            lbl.configure(text="[Empty]", bg="#333333")
        for k in self.used_counts:
            self.used_counts[k] = 0
        self.last_placed_global = None
        self._refresh_list_colors()

    # ----------------- Export -----------------
    def _export(self):
        lines, uuids = [], []
        globally_last = self.last_placed_global

        for b in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {b}")
            assigned = [self.slots[(b, s)] for s in range(1, 5) if self.slots[(b, s)]]

            if not assigned and globally_last:
                assigned = [globally_last]

            while len(assigned) < 4 and assigned:
                assigned.append(assigned[-1])

            for fn in assigned:
                if fn:
                    lines.append(fn)
                    preset = next((p for p in self.presets if p["filename"] == fn), None)
                    if preset:
                        uuids.append(f"{fn} {preset['uuid']}")

        with open(self.presets_dir / "PresetList.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(self.presets_dir / "PresetListUUIDs.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(uuids) + "\n")

        # Generate presetlist.pdf in same folder
        try:
            generate_chart(str(self.presets_dir))
        except Exception as e:
            print(f"⚠️ Failed to generate preset chart: {e}")

        messagebox.showinfo("Export Complete", "PresetList.txt, PresetListUUIDs.txt, and presetlist.pdf written.")

    # ----------------- Helpers -----------------
    def _refresh_list_colors(self):
        for i in range(self.preset_list.size()):
            fn = self.preset_list.get(i)
            used = self.used_counts.get(fn, 0) > 0
            if used:
                self.preset_list.itemconfig(i, {'bg': '#2d6a4f', 'fg': '#80ff80'})
            else:
                self.preset_list.itemconfig(i, {'bg': '#2c2c2c', 'fg': '#ffcc66'})

    def _slot_hover(self, event):
        event.widget.configure(bg="#444444")

    def _slot_unhover(self, event):
        b, s = event.widget._bank, event.widget._slot
        val = self.slots[(b, s)]
        event.widget.configure(bg="#2d6a4f" if val else "#333333")

    def _fit_to_banks(self):
        self.update_idletasks()
        scr_h = self.winfo_screenheight()
        req_h = min(self.canvas.winfo_reqheight() + 200, scr_h - 100)
        self.geometry(f"{self.winfo_width()}x{req_h}")

    def _on_close(self):
        self.destroy()


# ==========================================================
# ===============  END: PRESET PICKER  =====================
# ==========================================================


# ==========================================================
# ===============  START: PRESET PULLER  ===================
# ==========================================================
# (code from preset_puller.py)
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


# ==========================================================
# ===============  END: PRESET PULLER  =====================
# ==========================================================


# ==========================================================
# ============  START: PRESET APP SCRAPER  =================
# ==========================================================
# (code from preset_app_scraper.py)
import serial
import re
import json
import os
import time

PORT = "COM9"   # adjust if needed
BAUD = 115200

def normalize_number(val):
    if isinstance(val, float):
        if val.is_integer():
            return int(val)
        return round(val, 4)
    return val

def normalize_json(obj):
    if isinstance(obj, dict):
        return {k: normalize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize_json(v) for v in obj]
    else:
        return normalize_number(obj)

def connect():
    return serial.Serial(PORT, BAUD, timeout=0.5)

def main():
    print("Ignitron Spark App Tool (App Preset Capture)")
    ser = connect()
    print(f"Connected on {PORT} at {BAUD}")

    # make timestamped session folder
    session_folder = time.strftime("presets_%Y%m%d_%H%M%S")
    os.makedirs(session_folder, exist_ok=True)
    print(f"📂 Saving captured presets into: {session_folder}")

    last_uuid = None
    buffer = ""
    capturing = False

    while True:
        try:
            line = ser.readline().decode(errors="ignore").rstrip()
            if not line:
                continue

            print(line)

            # start capture when JSON begins
            if line.startswith("received from app:") or line.startswith("JSON STRING:"):
                buffer = ""
                capturing = True
                continue

            if capturing:
                buffer += line + "\n"
                if line.strip().endswith("}"):
                    capturing = False
                    try:
                        raw_preset = json.loads(buffer)

                        uuid = raw_preset.get("UUID")
                        if uuid == last_uuid:
                            continue
                        last_uuid = uuid

                        preset = normalize_json(raw_preset)

                        safe_name = re.sub(r'\W+', '', preset.get("Name", "preset"))
                        if not safe_name:
                            safe_name = "preset"
                        fname = os.path.join(session_folder, f"{safe_name}.json")

                        with open(fname, "w", encoding="utf-8") as f:
                            json.dump(preset, f, indent=4)

                        print(f"✅ Saved preset: {fname}")

                    except Exception as e:
                        print(f"⚠️ Failed to parse buffered JSON: {e}")
                        print("--- RAW BUFFER START ---")
                        print(buffer)
                        print("--- RAW BUFFER END ---")

        except KeyboardInterrupt:
            print("Exiting...")
            ser.close()
            break

def preset_app_scraper():
    main()

# ==========================================================
# ============  END: PRESET APP SCRAPER  ===================
# ==========================================================


# ==========================================================
# =======================  MENU  ===========================
# ==========================================================

def clear_screen(): os.system("cls" if os.name=="nt" else "clear")
def pause(): 
    try: input("\nPress Enter to return to menu...")
    except EOFError: pass

def run_preset_picker(): 
    PresetPicker().mainloop()

def run_preset_app_scraper():
    try: 
        preset_app_scraper()
    except KeyboardInterrupt: 
        print("Exiting Preset App Scraper…")
    pause()

def run_preset_puller():
    splash_screen()
    print("Pull mode:\n  1. Only active presets (LISTBANKS)\n  2. All presets (LISTALL)")
    choice = input("Choose [1/2]: ").strip()
    port = choose_serial_port()
    if not port: 
        pause(); return
    input(f"\n⚠️ Hold PRESET 1 on pedal. Selected {port}. Press Enter when ready…")
    pull_presets(port, 115200, (choice == "1"), True)
    pause()

def run_preset_app_scraper():
    try: 
        preset_app_scraper()
    except KeyboardInterrupt: 
        print("Exiting Preset App Scraper…")
    pause()
    
def menu():
    while True:
        clear_screen()
        print("==============================")
        print(" Ignitron Preset Tools v1.1.0 ")
        print("==============================")
        print("1. Preset Picker")
        print("2. Preset Puller")
        print("3. Preset App Scraper")
        print("4. Exit\n")
        choice = input("Choose an option [1-4]: ").strip()
        if choice == "1": run_preset_picker()
        elif choice == "2": run_preset_puller()
        elif choice == "3": run_preset_app_scraper()
        elif choice == "4": 
            print("Goodbye!"); break
        else: 
            print("Invalid choice."); time.sleep(1)

if __name__ == "__main__":
    menu()
