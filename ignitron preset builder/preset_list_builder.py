#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Standalone PresetList Builder (GUI)
===================================

This is a stripped-down version of the IPC PresetListBuilder, packaged as a
standalone app. It loads presets from a folder of JSON files, lets you drag/drop
or double-click to arrange them into banks × 4 slots, and exports a
PresetList_<timestamp>.txt file (filenames only, no UUIDs).

Dependencies:
    - Python 3.8+
    - Tkinter (bundled with most Python installs)

Usage:
    python preset_list_builder.py
"""

import json
import random
import platform
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog


# ---------- Utils ----------

def safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def timestamp_now():
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------- GUI ----------

class PresetListBuilder(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Standalone PresetList Builder")
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
                presets.append({"filename": jf.name, "name": str(data.get("Name", jf.stem))})
            except Exception:
                presets.append({"filename": jf.name, "name": jf.stem})
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
                    bg="#e5e7eb",
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
        for b in range(1, self.bank_count + 1):
            for s in range(1, 5):
                if self.slots[(b, s)] is None:
                    self._assign_to_slot(b, s, filename)
                    return
        messagebox.showinfo("All filled", "All slots are filled.")

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
        label = tk.Label(self.drag_ghost, text=text, bg="#fde68a", bd=1, relief="solid")
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
        event.widget.configure(bg="#bfdbfe")

    def _slot_unhover(self, event):
        b, s = event.widget._bank, event.widget._slot
        val = self.slots[(b, s)]
        event.widget.configure(bg="#d1fae5" if val else "#e5e7eb")

    # --------- Slot operations ---------
    def _assign_to_slot(self, bank, slot, filename):
        self.slots[(bank, slot)] = filename
        lbl = self.slot_widgets[(bank, slot)]
        lbl.configure(text=filename, bg="#d1fae5")
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
        for i in range(self.preset_list.size()):
            fn = self.preset_list.get(i)
            used = self.used_counts.get(fn, 0) > 0
            if used:
                self.preset_list.itemconfig(i, {'bg': '#d1fae5', 'fg': '#065f46'})
            else:
                self.preset_list.itemconfig(i, {'bg': '#ffedd5', 'fg': '#92400e'})

    # --------- Export ---------
    def _export(self):
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

        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{dist_dir}"')
            elif platform.system() == "Darwin":
                subprocess.call(["open", str(dist_dir)])
            else:
                subprocess.call(["xdg-open", str(dist_dir)])
        except Exception:
            pass

    # --------- Close ---------
    def _on_close(self):
        try:
            self.destroy()
        except Exception:
            pass


def main():
    app = PresetListBuilder()
    app.mainloop()


if __name__ == "__main__":
    main()
