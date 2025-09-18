#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ignitron Spark Preset Builder v1.1
==================================
Dynamic bank management version:
- Add bank at the top (shifts others down).
- Remove bank per-bank with ❌ button (confirm first).
- Banks below shift up on delete.
- Export outputs PresetList.txt and PresetListUUIDs.txt in order.
"""

import json
import random
import platform
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

APP_VERSION = "1.1"


class PresetListBuilder(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ignitron Spark Preset Builder v" + APP_VERSION)

        # fullscreen windowed
        self.state("zoomed")
        try:
            self.attributes("-fullscreen", True)
            self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        except Exception:
            pass

        self.presets_dir = Path(__file__).parent

        # Initial bank count
        self.bank_count = simpledialog.askinteger(
            "Banks", "Enter number of banks (1–30):",
            parent=self, minvalue=1, maxvalue=30
        )
        if not self.bank_count:
            messagebox.showinfo("Canceled", "No bank count entered, closing.")
            self.destroy()
            return

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

        # Dragging
        self.dragging_name = None
        self.drag_ghost = None

        # Build UI
        self._build_ui()
        self._render_banks()
        self._update_status()

        self.bind("<Escape>", lambda e: self._cancel_drag())
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

        # Left preset list
        left = ttk.Frame(wrapper)
        left.pack(side="left", fill="y", padx=12, pady=12)

        ttk.Label(left, text="Presets (double-click to add / drag to slot)").pack(anchor="w")
        self.preset_list = tk.Listbox(left, width=44, height=34, activestyle="none")
        self.preset_list.pack(fill="y", expand=False)

        for p in self.presets:
            self.preset_list.insert("end", p["filename"])

        self._refresh_list_colors()

        self.preset_list.bind("<ButtonPress-1>", self._start_drag_from_list)
        self.preset_list.bind("<B1-Motion>", self._update_drag)
        self.preset_list.bind("<ButtonRelease-1>", self._drop_anywhere)
        self.preset_list.bind("<Double-Button-1>", self._on_double_click)

        ttk.Button(left, text="Export PresetList", command=self._export).pack(pady=(12, 4), fill="x")
        ttk.Button(left, text="Random Fill Unfilled", command=self._random_fill).pack(pady=4, fill="x")
        ttk.Button(left, text="Clear All", command=self._clear_all).pack(pady=4, fill="x")
        ttk.Button(left, text="Close", command=self._on_close).pack(pady=(16, 0), fill="x")

        # Right container
        right_container = ttk.Frame(wrapper)
        right_container.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        # Logo
        logo_frame = tk.Frame(right_container, bg="#D7261E")
        logo_frame.pack(anchor="ne", pady=(0, 8), fill="x")
        tk.Label(
            logo_frame,
            text="IGNITRON\nSPARK PRESET BUILDER v" + APP_VERSION,
            font=("Segoe UI", 12, "bold"),
            fg="white",
            bg="#D7261E",
            justify="center"
        ).pack(anchor="e", padx=8, pady=4)

        # Add bank button
        self.topbar = ttk.Frame(right_container)
        self.topbar.pack(anchor="w", fill="x", pady=(0, 6))
        ttk.Button(self.topbar, text="+ Add Bank (at top)", command=self._add_bank).pack(side="left", padx=4)

        # Scrollable banks
        canvas = tk.Canvas(right_container, borderwidth=0)
        vscroll = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        self.grid_frame = ttk.Frame(canvas)
        self.grid_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # Status bar
        self.status = ttk.Label(self, text="", anchor="e")
        self.status.pack(side="bottom", fill="x")

    # --------- Render banks ---------
    def _render_banks(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        self.slot_widgets = {}
        for b in range(1, self.bank_count + 1):
            row = (b - 1) * 2
            bank_header = ttk.Frame(self.grid_frame)
            bank_header.grid(row=row, column=0, columnspan=4, sticky="we", pady=(8, 2))

            ttk.Label(bank_header, text=f"Bank {b}", font=("Segoe UI", 10, "bold")).pack(side="left")
            ttk.Button(bank_header, text="❌ Remove", width=8,
                       command=lambda bb=b: self._remove_bank(bb)).pack(side="left", padx=6)

            for s in range(1, 5):
                lbl = tk.Label(
                    self.grid_frame,
                    text=self.slots.get((b, s), "[Empty]") or "[Empty]",
                    bd=1, relief="groove", width=32, height=2,
                    bg="#d1fae5" if self.slots.get((b, s)) else "#e5e7eb",
                )
                lbl.grid(row=row + 1, column=s - 1, padx=6, pady=6, sticky="nsew")
                lbl._bank, lbl._slot = b, s
                lbl.bind("<Enter>", self._slot_hover)
                lbl.bind("<Leave>", self._slot_unhover)
                lbl.bind("<ButtonRelease-1>", self._drop_on_slot)
                lbl.bind("<Button-3>", self._clear_slot)
                self.slot_widgets[(b, s)] = lbl

            for s in range(4):
                self.grid_frame.grid_columnconfigure(s, weight=1)

    # --------- Bank controls ---------
    def _add_bank(self):
        self.bank_count += 1
        # shift all banks down
        new_slots = {}
        for (b, s), v in sorted(self.slots.items(), reverse=True):
            new_slots[(b + 1, s)] = v
        for s in range(1, 5):
            new_slots[(1, s)] = None
        self.slots = new_slots
        self._render_banks()
        self._update_status()

    def _remove_bank(self, bank_num):
        if messagebox.askyesno("Confirm", f"Delete Bank {bank_num}? This cannot be undone."):
            # shift everything above down
            new_slots = {}
            for (b, s), v in self.slots.items():
                if b < bank_num:
                    new_slots[(b, s)] = v
                elif b > bank_num:
                    new_slots[(b - 1, s)] = v
            self.bank_count -= 1
            self.slots = new_slots
            self._render_banks()
            self._update_status()

    # --------- Status ---------
    def _update_status(self):
        filled = sum(1 for v in self.slots.values() if v)
        total = self.bank_count * 4
        self.status.config(text=f"Banks: {self.bank_count} | Presets placed: {filled}/{total}")

    # --------- Preset assignment ---------
    def _on_double_click(self, event):
        idx = self.preset_list.curselection()
        if not idx:
            return
        filename = self.preset_list.get(idx[0])
        for b in range(1, self.bank_count + 1):
            for s in range(1, 5):
                if self.slots.get((b, s)) is None:
                    self._assign_to_slot(b, s, filename)
                    return
        messagebox.showinfo("All filled", "All slots are filled.")
        self._update_status()

    def _random_fill(self):
        if not self.presets:
            return
        filenames = [p["filename"] for p in self.presets]
        for (b, s), v in self.slots.items():
            if v is None:
                self._assign_to_slot(b, s, random.choice(filenames))
        self._update_status()

    def _assign_to_slot(self, bank, slot, filename):
        self.slots[(bank, slot)] = filename
        lbl = self.slot_widgets[(bank, slot)]
        lbl.config(text=filename, bg="#d1fae5")
        self.used_counts[filename] = self.used_counts.get(filename, 0) + 1
        self.last_placed_global = filename
        self._refresh_list_colors()
        self._update_status()

    def _clear_slot(self, event):
        lbl = event.widget
        b, s = lbl._bank, lbl._slot
        filename = self.slots[(b, s)]
        if filename:
            self.used_counts[filename] = max(0, self.used_counts.get(filename, 0) - 1)
            self.slots[(b, s)] = None
            lbl.config(text="[Empty]", bg="#e5e7eb")
            self._refresh_list_colors()
            self._update_status()

    def _clear_all(self):
        for (b, s), lbl in self.slot_widgets.items():
            self.slots[(b, s)] = None
            lbl.config(text="[Empty]", bg="#e5e7eb")
        for k in self.used_counts.keys():
            self.used_counts[k] = 0
        self.last_placed_global = None
        self._refresh_list_colors()
        self._update_status()

    def _refresh_list_colors(self):
        for i in range(self.preset_list.size()):
            fn = self.preset_list.get(i)
            used = self.used_counts.get(fn, 0) > 0
            if used:
                self.preset_list.itemconfig(i, {'bg': '#d1fae5', 'fg': '#065f46'})
            else:
                self.preset_list.itemconfig(i, {'bg': '#ffedd5', 'fg': '#92400e'})

    # --------- Drag helpers ---------
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
        tk.Label(self.drag_ghost, text=text, bg="#fde68a", bd=1, relief="solid").pack()
        self._move_ghost(x_root, y_root)

    def _move_ghost(self, x_root, y_root):
        if self.drag_ghost:
            self.drag_ghost.geometry(f"+{x_root+12}+{y_root+12}")

    def _remove_ghost(self):
        if self.drag_ghost:
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
        event.widget.config(bg="#bfdbfe")

    def _slot_unhover(self, event):
        b, s = event.widget._bank, event.widget._slot
        val = self.slots.get((b, s))
        event.widget.config(bg="#d1fae5" if val else "#e5e7eb")

    # --------- Export ---------
    def _export(self):
        lines, uuid_lines = [], []
        globally_last = self.last_placed_global
        any_placed = any(v for v in self.slots.values())
        if not any_placed:
            messagebox.showerror("Nothing placed", "Place at least one preset before exporting.")
            return

        preset_lookup = {p["filename"]: p["uuid"] for p in self.presets}

        for b in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {b}")
            assigned = [self.slots.get((b, s)) for s in range(1, 5) if self.slots.get((b, s))]
            if not assigned:
                if not globally_last:
                    messagebox.showerror("No presets", "No presets to auto-fill.")
                    return
                assigned = [globally_last]
            while len(assigned) < 4:
                assigned.append(assigned[-1])
            for fn in assigned:
                lines.append(fn)
                uuid_lines.append(f"{fn} {preset_lookup.get(fn, 'UNKNOWN').upper()}")

        (self.presets_dir / "PresetList.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.presets_dir / "PresetListUUIDs.txt").write_text("\n".join(uuid_lines) + "\n", encoding="utf-8")

        messagebox.showinfo("Export Complete",
                            f"✅ PresetList.txt and PresetListUUIDs.txt updated in:\n{self.presets_dir.resolve()}")

        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{self.presets_dir}"')
            elif platform.system() == "Darwin":
                subprocess.call(["open", str(self.presets_dir)])
            else:
                subprocess.call(["xdg-open", str(self.presets_dir)])
        except Exception:
            pass

    def _on_close(self):
        self.destroy()


def main():
    app = PresetListBuilder()
    app.mainloop()


if __name__ == "__main__":
    main()
