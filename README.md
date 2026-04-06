# VPN_TRAY

Windows tray app for managing Xray VPN on a router over SSH.

## Features

- tray icon with VPN status
- enable, disable and restart VPN
- restart action with `stop -> wait 3 sec -> start`
- Windows autostart toggle
- router diagnostics in the main window
- connectivity checks for direct, RU and NL routes
- browse and edit Xray JSON configs from SMB share
- open configs in Notepad++ when available

## Project Files

- [app.py](./app.py) - app logic, SSH commands, tray actions
- [ui.py](./ui.py) - Tkinter UI
- [ssh_session.py](./ssh_session.py) - reusable Paramiko session
- [config.py](./config.py) - router, SMB and command settings
- [vpn_tray.spec](./vpn_tray.spec) - PyInstaller spec

## Configuration

Edit [config.py](./config.py):

- `ROUTER_HOST`
- `ROUTER_PORT`
- `ROUTER_USER`
- `ROUTER_PASSWORD`
- `SMB_HOST`
- `SMB_USER`
- `SMB_PASS`
- `XRAY_CONFIG_DIR`
- `CMD_VPN_ON`
- `CMD_VPN_OFF`
- `CMD_STATUS`
- `CONNECTIVITY_CHECKS`

For local secrets create `config_local.py`. It overrides values from `config.py` and is ignored by git.

Example:

```python
SMB_PASS = "your_password"
ROUTER_PASSWORD = "your_password"
```

## Run

```powershell
python vpn_tray.py
```

## Build EXE

```powershell
cmd /c build_exe.bat
```

Built file:

```text
dist\vpn_tray.exe
```

## Requirements

- Windows 10/11
- Python 3.11+
- router with SSH access
- SMB access to Xray config directory

## Dependencies

- `paramiko`
- `pystray`
- `pillow`
- `pyinstaller`
