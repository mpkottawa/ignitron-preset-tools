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

# ----------------- Run -----------------
if __name__ == "__main__":
    app = PresetPicker()
    app.mainloop()
