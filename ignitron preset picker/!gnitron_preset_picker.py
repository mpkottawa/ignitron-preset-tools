#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ignitron Preset Picker v1.0
-----------------------------------
Dark-mode GUI tool to build Spark-compatible PresetList.txt
and PresetListUUIDs.txt directly in the containing folder.

Features:
- Drag & drop or double-click to assign presets into banks/slots
- Add/remove banks dynamically (with confirmation + shifting)
- Preset usage tracking (color-coded)
- Exports in correct order with UUIDs matching selected presets
- Bootstrap dependency check on first run
"""

import os, sys, platform, subprocess, random, json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# ----------------- Bootstrap check (first run only) -----------------
MARKER_FILE = Path(__file__).parent / ".ignitron_ready"
try:
    import tkinter  # noqa
    from tkinter import Tk
except ImportError:
    print("❌ Tkinter is not installed on this system.")
    if platform.system() == "Linux":
        print("➡ On Debian/Ubuntu, run: sudo apt-get install python3-tk")
    elif platform.system() == "Darwin":
        print("➡ On macOS, reinstall Python from python.org (Tkinter is included).")
    elif platform.system() == "Windows":
        print("➡ On Windows, reinstall Python from python.org and make sure 'tcl/tk' is selected.")
    sys.exit(1)
else:
    if not MARKER_FILE.exists():
        _root = Tk()
        _root.withdraw()
        messagebox.showinfo(
            "Ignitron Preset Picker",
            "✅ All dependencies present.\nIgnitron Preset Picker is ready to run."
        )
        _root.destroy()
        MARKER_FILE.write_text("ready\n")

# ----------------- Utility -----------------
def safe_mkdir(p: Path):
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)

def timestamp_now():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# ----------------- Preset Picker GUI -----------------
class PresetPicker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ignitron Preset Picker v1.0")
        self.configure(bg="#1e1e1e")
        self.minsize(1200, 700)

        # Ask number of banks (initial)
        self.bank_count = simpledialog.askinteger("Banks", "Enter number of banks (1–30):", parent=self, minvalue=1, maxvalue=30)
        if not self.bank_count:
            self.destroy()
            return

        # Containing folder (where script lives)
        self.presets_dir = Path(__file__).parent

        # Load presets
        self.presets = self._load_presets(self.presets_dir)
        if not self.presets:
            messagebox.showerror("No presets", "No .json presets found in folder.")
            self.destroy()
            return

        self.used_counts = {p["filename"]: 0 for p in self.presets}
        self.slots = {(b, s): None for b in range(1, self.bank_count + 1) for s in range(1, 5)}
        self.last_placed_global = None

        # Dragging
        self.dragging_name = None
        self.drag_ghost = None

        # Build UI
        self._build_ui()
        self._render_banks()

        # Resize window to fit banks
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
        # Banner
        banner = tk.Frame(self, bg="#D7261E", height=50)
        banner.pack(side="top", fill="x")
        tk.Label(
            banner, text="IGNITRON PRESET PICKER v1.0",
            bg="#D7261E", fg="white",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=20)

        # Wrapper
        wrapper = ttk.Frame(self)
        wrapper.pack(fill="both", expand=True)

        # Left pane
        left = tk.Frame(wrapper, bg="#252526")
        left.pack(side="left", fill="y", padx=12, pady=12)

        tk.Label(left, text="Presets", fg="#dddddd", bg="#252526").pack(anchor="w")
        self.preset_list = tk.Listbox(left, width=44, height=34, activestyle="none",
                                      bg="#2c2c2c", fg="#dddddd", selectbackground="#444444")
        self.preset_list.pack(fill="y", expand=False)

        for p in self.presets:
            self.preset_list.insert("end", p["filename"])

        self._refresh_list_colors()

        # Bind interactions
        self.preset_list.bind("<ButtonPress-1>", self._start_drag_from_list)
        self.preset_list.bind("<B1-Motion>", self._update_drag)
        self.preset_list.bind("<ButtonRelease-1>", self._drop_anywhere)
        self.preset_list.bind("<Double-Button-1>", self._on_double_click)

        # Buttons
        ttk.Button(left, text="Export", command=self._export).pack(pady=6, fill="x")
        ttk.Button(left, text="Clear All", command=self._clear_all).pack(pady=6, fill="x")
        ttk.Button(left, text="Add Bank", command=self._add_bank).pack(pady=6, fill="x")
        ttk.Button(left, text="Close", command=self._on_close).pack(pady=6, fill="x")

        # Right container
        self.right_container = tk.Frame(wrapper, bg="#1e1e1e")
        self.right_container.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        # Grid frame
        self.grid_frame = tk.Frame(self.right_container, bg="#1e1e1e")
        self.grid_frame.pack(fill="both", expand=True)
        self.slot_widgets = {}

    # ----------------- Render Banks -----------------
    def _render_banks(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.slot_widgets.clear()

        for b in range(1, self.bank_count + 1):
            bank_frame = tk.Frame(self.grid_frame, bg="#1e1e1e")
            bank_frame.pack(fill="x", pady=(6, 2))

            tk.Label(bank_frame, text=f"Bank {b}", font=("Segoe UI", 12, "bold"),
                     bg="#1e1e1e", fg="#dddddd").pack(side="left")

            btn = ttk.Button(bank_frame, text="❌ Remove", command=lambda bb=b: self._remove_bank(bb))
            btn.pack(side="right")

            slots_frame = tk.Frame(self.grid_frame, bg="#1e1e1e")
            slots_frame.pack(fill="x", pady=(0, 6))
            for s in range(1, 5):
                lbl = tk.Label(slots_frame, text="[Empty]", bd=1, relief="groove",
                               width=32, height=2, bg="#333333", fg="#dddddd")
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
            # shift banks down
            for bb in range(b, self.bank_count):
                for s in range(1, 5):
                    self.slots[(bb, s)] = self.slots.get((bb + 1, s))
            # delete last
            for s in range(1, 5):
                self.slots.pop((self.bank_count, s), None)
            self.bank_count -= 1
            self._render_banks()
            self._fit_to_banks()

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
        if idx < 0: return
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
        if self.drag_ghost: self.drag_ghost.geometry(f"+{x+12}+{y+12}")

    def _remove_ghost(self):
        if self.drag_ghost:
            self.drag_ghost.destroy()
            self.drag_ghost = None

    def _update_drag(self, event):
        if self.dragging_name: self._move_ghost(self.winfo_pointerx(), self.winfo_pointery())

    def _drop_anywhere(self, event):
        if not self.dragging_name: return
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        if hasattr(widget, "_bank"):
            self._assign_to_slot(widget._bank, widget._slot, self.dragging_name)
        self.dragging_name = None
        self._remove_ghost()

    def _drop_on_slot(self, event):
        if not self.dragging_name: return
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
        for k in self.used_counts: self.used_counts[k] = 0
        self.last_placed_global = None
        self._refresh_list_colors()

    # ----------------- Export -----------------
    def _export(self):
        lines, uuids = [], []
        globally_last = self.last_placed_global
        for b in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {b}")
            assigned = [self.slots[(b, s)] for s in range(1, 5) if self.slots[(b, s)]]
            if not assigned and globally_last: assigned = [globally_last]
            while len(assigned) < 4 and assigned: assigned.append(assigned[-1])
            for fn in assigned:
                if fn:
                    lines.append(fn)
                    preset = next((p for p in self.presets if p["filename"] == fn), None)
                    if preset: uuids.append(f"{fn} {preset['uuid']}")

        # Write files
        with open(self.presets_dir / "PresetList.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(self.presets_dir / "PresetListUUIDs.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(uuids) + "\n")
        messagebox.showinfo("Export Complete", "PresetList.txt and PresetListUUIDs.txt written.")

    # ----------------- Helpers -----------------
    def _refresh_list_colors(self):
        for i in range(self.preset_list.size()):
            fn = self.preset_list.get(i)
            used = self.used_counts.get(fn, 0) > 0
            if used:
                self.preset_list.itemconfig(i, {'bg': '#2d6a4f', 'fg': '#80ff80'})
            else:
                self.preset_list.itemconfig(i, {'bg': '#2c2c2c', 'fg': '#ffcc66'})

    def _slot_hover(self, event): event.widget.configure(bg="#444444")
    def _slot_unhover(self, event):
        b, s = event.widget._bank, event.widget._slot
        val = self.slots[(b, s)]
        event.widget.configure(bg="#2d6a4f" if val else "#333333")

    def _fit_to_banks(self):
        self.update_idletasks()
        scr_h = self.winfo_screenheight()
        req_h = self.grid_frame.winfo_reqheight() + 200
        self.geometry(f"{self.winfo_width()}x{min(req_h, scr_h-100)}")

    def _on_close(self): self.destroy()

# ----------------- Run -----------------
if __name__ == "__main__":
    app = PresetPicker()
    app.mainloop()
