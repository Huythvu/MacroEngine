@echo off
REM ============================================================
REM  Build MacroEngine.exe  (run this ON WINDOWS, double-click it)
REM  Requires Python 3.10+ installed and on PATH.
REM  Produces:  dist\MacroEngine.exe   (a single double-clickable file)
REM ============================================================

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller Pillow
if errorlevel 1 goto :error

REM --- Optional custom icon -----------------------------------------------
REM Drop your image at assets\icon_source.png (or .jpg) and it becomes the
REM exe icon automatically. If none is present, the build proceeds iconless.
REM TODO(audit): if several icon_source.* files exist, each is converted and
REM the last one wins; consider stopping after the first match.
set ICON_ARG=
for %%F in (assets\icon_source.png assets\icon_source.jpg assets\icon_source.jpeg) do (
    if exist "%%F" (
        echo Generating icon from %%F ...
        python tools\make_icon.py "%%F" -o assets\MacroEngine.ico
    )
)
if exist assets\MacroEngine.ico set ICON_ARG=--icon assets\MacroEngine.ico

echo.
echo Building MacroEngine.exe ...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name MacroEngine ^
    %ICON_ARG% ^
    --collect-submodules pynput ^
    --collect-submodules mss ^
    run.py
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  Done!  Your program is at:  dist\MacroEngine.exe
echo  Double-click it to run. (Right-click - Run as administrator
echo  if you need to control games that run elevated.)
echo ============================================================
pause
exit /b 0

:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
