#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ignitron Preset Tools (IPT) – Modular Version
---------------------------------------------
Launcher that calls:
  1. Preset Picker
  2. Preset Puller
  3. App Scraper
"""

import os, sys, time
import preset_picker
import preset_puller
import app_scraper

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def pause():
    input("\nPress Enter to return to menu...")

def run_preset_picker():
    print("Launching Preset Picker...")
    app = preset_picker.PresetPicker()
    app.mainloop()

def run_preset_puller():
    print("Launching Preset Puller...")
    fast_mode = "--fast" in sys.argv
    preset_puller.splash_screen(fast=fast_mode)

    print("Pull mode:")
    print("  1. Only presets in pedal’s PresetList.txt")
    print("  2. All presets on the pedal")
    while True:
        choice = input("Choose [1/2]: ").strip()
        if choice in ("1", "2"):
            include_only_active = (choice == "1")
            break
        print("Invalid choice. Please enter 1 or 2.")

    port = preset_puller.choose_serial_port()
    print("\n⚠️  Before connecting: HOLD PRESET 1 on the pedal.")
    input(f"Selected {port}. Press Enter when ready to continue...")

    preset_puller.pull_presets(
        port=port,
        baud=115200,
        include_only_active=include_only_active,
        open_folder_after=True
    )
    pause()

def run_app_scraper():
    print("Launching App Scraper...")
    try:
        app_scraper.main()
    except KeyboardInterrupt:
        print("Exiting App Scraper...")
    pause()

def menu():
    while True:
        clear_screen()
        print("==============================")
        print(" Ignitron Preset Tool (IPT)")
        print("==============================")
        print("1. Preset Picker")
        print("2. Preset Puller")
        print("3. App Scraper")
        print("4. Exit\n")

        choice = input("Choose an option [1-4]: ").strip()
        if choice == "1":
            run_preset_picker()
        elif choice == "2":
            run_preset_puller()
        elif choice == "3":
            run_app_scraper()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")
            time.sleep(1)

if __name__ == "__main__":
    menu()
