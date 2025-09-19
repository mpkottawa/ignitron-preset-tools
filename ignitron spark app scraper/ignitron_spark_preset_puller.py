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

if __name__ == "__main__":
    main()
