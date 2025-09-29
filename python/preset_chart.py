#!/usr/bin/env python3
# preset_chart.py
# Always looks for /ignitron/data/PresetList.txt and outputs /ignitron/data/presetlist.pdf

import os, subprocess, platform
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def generate_chart():
    # Fixed input/output locations
    base_dir = os.path.join(os.path.sep, "ignitron", "data")
    txt_file = os.path.join(base_dir, "PresetList.txt")
    output_path = os.path.join(base_dir, "presetlist.pdf")

    if not os.path.exists(txt_file):
        print(f"❌ PresetList.txt not found at {txt_file}")
        return None

    # Parse banks
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

    # Auto-open PDF
    try:
        if platform.system() == "Windows":
            os.startfile(output_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", output_path])
        else:
            subprocess.Popen(["xdg-open", output_path])
    except:
        pass

    return output_path

if __name__ == "__main__":
    generate_chart()
