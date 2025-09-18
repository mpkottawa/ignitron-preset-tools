@echo off
REM ===========================================
REM Ignitron Preset Picker EXE Builder v1.0
REM Keeps last 3 builds in /releases
REM ===========================================

cd /d "%~dp0"

REM ---- Set version here ----
set version=1.0

REM ---- Get timestamp for file naming ----
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do (
    set datestr=%%c-%%a-%%b
)
for /f "tokens=1-2 delims=:." %%a in ("%time%") do (
    set timestr=%%a%%b
)

set filename=!gnitron_preset_picker_v%version%_%datestr%_%timestr%.exe

echo Building Ignitron Preset Picker v%version% EXE...
pyinstaller --noconfirm --onefile --windowed "!gnitron_preset_picker.py"

echo Copying build to releases...
if not exist releases mkdir releases
copy "dist\!gnitron_preset_picker.exe" "releases\%filename%"

REM ---- Keep only the last 3 builds in /releases ----
pushd releases
for /f "skip=3 delims=" %%f in ('dir /b /o-d !gnitron_preset_picker_v*.exe') do del "%%f"
popd

echo.
echo ✅ Build complete!
echo    Latest EXE: dist\!gnitron_preset_picker.exe
echo    Archived builds (last 3): releases\
pause
