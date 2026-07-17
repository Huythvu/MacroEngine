@echo off
REM ============================================================
REM  Build MacroEngine.exe  (run this ON WINDOWS, double-click it)
REM  Requires Python 3.10+ installed and on PATH.
REM  Produces:  dist\MacroEngine.exe   (a single double-clickable file)
REM ============================================================

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo.
echo Building MacroEngine.exe ...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name MacroEngine ^
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
