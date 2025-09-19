@echo off
REM ==========================================================
REM  Ignitron Live Capture - Build Script
REM  Converts live_capture.py into a standalone EXE
REM  Requires: Python + PyInstaller installed
REM ==========================================================

echo.
echo 🎸 Building Ignitron Live Capture EXE...
echo.

REM Make sure PyInstaller is installed
pip install pyinstaller

REM Clean old builds
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "live_capture.spec" del /q live_capture.spec

REM Build EXE
pyinstaller --noconfirm --onefile --console ^
  --name "IgnitronLiveCapture" ^
  live_capture.py

echo.
echo ✅ Build complete!
echo EXE location: dist\IgnitronLiveCapture.exe
echo.

pause
