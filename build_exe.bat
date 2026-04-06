@echo off
setlocal

cd /d "%~dp0"

echo ============================================
echo VPN_TRAY build
echo Project dir: %cd%
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  pause
  exit /b 1
)

echo [1/3] Upgrade pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip.
  pause
  exit /b 1
)

echo [2/3] Install dependencies...
python -m pip install --upgrade pyinstaller paramiko pillow PySide6
if errorlevel 1 (
  echo [ERROR] Failed to install dependencies.
  pause
  exit /b 1
)

echo [3/3] Build EXE...
python -m PyInstaller --clean --noconfirm vpn_tray.spec
if errorlevel 1 (
  echo [ERROR] Build failed.
  pause
  exit /b 1
)

if exist "dist\vpn_tray.exe" (
  copy /Y "dist\vpn_tray.exe" "vpn_tray.exe" >nul
  if errorlevel 1 (
    echo [WARN] dist\vpn_tray.exe was built, but vpn_tray.exe in project root is locked.
    echo [WARN] Use dist\vpn_tray.exe or close the running app and copy again.
  ) else (
    echo [OK] vpn_tray.exe updated in project root.
  )
) else (
  echo [WARN] dist\vpn_tray.exe was not found after build.
)

echo.
echo Build finished.
pause
exit /b 0
