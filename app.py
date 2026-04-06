import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import winreg
from typing import Optional

import pystray

from config import (
    CMD_STATUS,
    CMD_VPN_OFF,
    CMD_VPN_ON,
    CONNECTIVITY_CHECKS,
    NOTEPADPP_CANDIDATES,
    ROUTER_HOST,
    ROUTER_PASSWORD,
    ROUTER_PORT,
    ROUTER_USER,
    STATUS_POLL_INTERVAL,
    TRAY_ICON_OFF,
    TRAY_ICON_ON,
    TRAY_ICON_UNKNOWN,
    VPN_RESTART_DELAY_SEC,
    format_host,
)
from icons import create_fallback_icon, load_icon_from_file
from models import ConnectivityCheck, RouterStats
from ssh_session import SSHSession
from ui import StatsWindow


class VPNTrayApp:
    ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
    STARTUP_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_VALUE_NAME = "xKeen Control"

    def __init__(self):
        self.icon: Optional[pystray.Icon] = None
        self.current_status: str = "unknown"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        self.ssh = SSHSession(ROUTER_HOST, ROUTER_PORT, ROUTER_USER, ROUTER_PASSWORD)
        self.ui = StatsWindow(self)

        self.icon_on = load_icon_from_file(TRAY_ICON_ON) or create_fallback_icon("on")
        self.icon_off = load_icon_from_file(TRAY_ICON_OFF) or create_fallback_icon("off")
        self.icon_unknown = load_icon_from_file(TRAY_ICON_UNKNOWN) or create_fallback_icon("unknown")

    def strip_ansi(self, text: str) -> str:
        return self.ANSI_RE.sub("", text)

    def _ssh_exec(self, cmd: str) -> str:
        return self.ssh.exec(cmd)

    def get_status(self) -> str:
        try:
            output = self._ssh_exec(CMD_STATUS)
            text = self.strip_ansi(output).lower()

            if "запущен" in text and "не запущен" not in text:
                return "on"
            if "не запущен" in text:
                return "off"
            return "unknown"
        except Exception:
            return "unknown"

    def vpn_on(self) -> None:
        try:
            self._ssh_exec(CMD_VPN_ON)
        except Exception:
            pass

    def vpn_off(self) -> None:
        try:
            self._ssh_exec(CMD_VPN_OFF)
        except Exception:
            pass

    def vpn_restart(self) -> None:
        self.vpn_off()
        time.sleep(VPN_RESTART_DELAY_SEC)
        self.vpn_on()

    def get_notepadpp_path(self) -> Optional[str]:
        path = shutil.which("notepad++.exe")
        if path:
            return path

        for candidate in NOTEPADPP_CANDIDATES:
            if os.path.isfile(candidate):
                return candidate
        return None

    def run_config_editor(self, path: str) -> None:
        editor = self.get_notepadpp_path()
        if editor:
            os.spawnl(os.P_NOWAIT, editor, editor, path)
            return
        os.startfile(path)

    def get_router_stats(self) -> RouterStats:
        uptime_raw = self.strip_ansi(self._ssh_exec("uptime"))
        mem_raw = self.strip_ansi(self._ssh_exec("free -m 2>/dev/null"))
        cpu_raw = self.strip_ansi(self._ssh_exec("top -bn1 | grep xray"))
        status = self.get_status()

        uptime_text = uptime_raw.strip()
        load = ""
        if "load average" in uptime_raw:
            load = uptime_raw.split("load average:")[-1].strip()
            uptime_text = uptime_raw.split("load average:")[0].rstrip(" ,")

        mem_lines = mem_raw.splitlines()
        mem_text = "Не удалось получить данные"
        if len(mem_lines) >= 2:
            parts = mem_lines[1].split()
            if len(parts) >= 7:
                total = parts[1]
                used = parts[2]
                free = parts[3]
                mem_text = f"{used} MB / {total} MB (свободно {free} MB)"

        xray_cpu = "Неизвестно"
        if cpu_raw:
            parts = cpu_raw.split()
            cpu_candidates = []
            for part in parts:
                candidate = part.rstrip("%")
                try:
                    float(candidate)
                    cpu_candidates.append(part)
                except ValueError:
                    continue
            if cpu_candidates:
                xray_cpu = f"{cpu_candidates[0].rstrip('%')}%"

        dashboard = f"""
================= VPN =================
Статус: {"ВКЛЮЧЕН" if status == "on" else "ВЫКЛЮЧЕН" if status == "off" else "НЕИЗВЕСТНО"}

================= Система =================
Аптайм:
{uptime_text}

Load average:
{load}

================= CPU =================
Нагрузка xray:
{xray_cpu}

================= Память =================
RAM:
{mem_text}
"""
        return RouterStats(
            text=dashboard.strip(),
            status=status,
            uptime=uptime_text or "Неизвестно",
            load_average=load or "Неизвестно",
            xray_cpu=xray_cpu,
            memory=mem_text,
        )

    def probe_url(self, name: str, url: str, expected: str, timeout: int = 6) -> ConnectivityCheck:
        start = time.perf_counter()
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "xKeen-Control/1.0",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ConnectivityCheck(
                    name=name,
                    url=url,
                    expected=expected,
                    ok=True,
                    status_code=getattr(response, "status", None),
                    latency_ms=latency_ms,
                )
        except urllib.error.HTTPError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ConnectivityCheck(
                name=name,
                url=url,
                expected=expected,
                ok=True,
                status_code=exc.code,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return ConnectivityCheck(
                name=name,
                url=url,
                expected=expected,
                ok=False,
                status_code=None,
                latency_ms=None,
                error=str(exc),
            )

    def get_connectivity_checks(self) -> list[ConnectivityCheck]:
        return [
            self.probe_url(item["name"], item["url"], item["expected"])
            for item in CONNECTIVITY_CHECKS
        ]

    def _compose_tray_title(self, status: str) -> str:
        if status == "on":
            prefix = "VPN: ВКЛЮЧЕН"
        elif status == "off":
            prefix = "VPN: ВЫКЛЮЧЕН"
        else:
            prefix = "VPN: НЕИЗВЕСТНО"

        try:
            checks = self.get_connectivity_checks()
            ok_count = sum(1 for check in checks if check.ok)
            failed_hosts = ", ".join(format_host(check.url) for check in checks if not check.ok)
            if failed_hosts:
                return f"{prefix} | Сайты: {ok_count}/{len(checks)} | Нет доступа: {failed_hosts}"
            return f"{prefix} | Сайты: {ok_count}/{len(checks)}"
        except Exception:
            return prefix

    def update_icon_status(self, new_status: str) -> None:
        with self.lock:
            self.current_status = new_status
            if not self.icon:
                return

            if new_status == "on":
                self.icon.icon = self.icon_on
            elif new_status == "off":
                self.icon.icon = self.icon_off
            else:
                self.icon.icon = self.icon_unknown
            self.icon.title = self._compose_tray_title(new_status)

        try:
            self.ui.root.after(0, lambda: self.ui.set_status_text(new_status))
        except Exception:
            pass

    def action_show(self, icon, item=None) -> None:
        self.ui.show()
        self.ui.set_status_text(self.current_status)
        self.ui.ensure_smb_connected()
        self.ui.reload_configs()
        self.ui.refresh_async()

    def action_settings(self, icon, item) -> None:
        self.ui.show_settings()

    def action_toggle(self, icon, item) -> None:
        with self.lock:
            status = self.current_status

        if status == "on":
            self.vpn_off()
        else:
            self.vpn_on()

        self.update_icon_status(self.get_status())

    def action_on(self, icon, item) -> None:
        self.vpn_on()
        self.update_icon_status(self.get_status())

    def action_off(self, icon, item) -> None:
        self.vpn_off()
        self.update_icon_status(self.get_status())

    def action_restart(self, icon, item) -> None:
        self.vpn_restart()
        self.update_icon_status(self.get_status())

    def action_check(self, icon, item) -> None:
        self.update_icon_status(self.get_status())

    def action_exit(self, icon, item) -> None:
        self.stop_event.set()
        try:
            self.ssh.close()
        except Exception:
            pass
        try:
            icon.stop()
        except Exception:
            pass
        try:
            self.ui.root.after(0, self.ui.root.quit)
        except Exception:
            pass

    def _startup_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vpn_tray.py")
        pythonw_path = sys.executable
        if pythonw_path.lower().endswith("python.exe"):
            candidate = pythonw_path[:-10] + "pythonw.exe"
            if os.path.isfile(candidate):
                pythonw_path = candidate

        return f'"{pythonw_path}" "{script_path}"'

    def is_startup_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.STARTUP_REG_PATH, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, self.STARTUP_VALUE_NAME)
                return bool(str(value).strip())
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def set_startup_enabled(self, enabled: bool) -> None:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            self.STARTUP_REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, self.STARTUP_VALUE_NAME, 0, winreg.REG_SZ, self._startup_command())
            else:
                try:
                    winreg.DeleteValue(key, self.STARTUP_VALUE_NAME)
                except FileNotFoundError:
                    pass

    def poll_status_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.update_icon_status(self.get_status())
            except Exception:
                self.update_icon_status("unknown")

            for _ in range(STATUS_POLL_INTERVAL):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

    def run(self) -> None:
        initial_status = self.get_status()
        self.current_status = initial_status

        menu = pystray.Menu(
            pystray.MenuItem("Показать информацию", self.action_show, default=True),
            pystray.MenuItem("Настройки", self.action_settings),
            pystray.MenuItem("Переключить VPN", self.action_toggle),
            pystray.MenuItem("Включить VPN", self.action_on),
            pystray.MenuItem("Выключить VPN", self.action_off),
            pystray.MenuItem("Перезапустить VPN", self.action_restart),
            pystray.MenuItem("Проверить статус", self.action_check),
            pystray.MenuItem("Выход", self.action_exit),
        )

        if initial_status == "on":
            start_icon = self.icon_on
        elif initial_status == "off":
            start_icon = self.icon_off
        else:
            start_icon = self.icon_unknown
        title = self._compose_tray_title(initial_status)

        self.icon = pystray.Icon("xkeen_control", start_icon, title, menu)

        thread = threading.Thread(target=self.poll_status_loop, daemon=True)
        thread.start()

        self.icon.run_detached()
        self.ui.root.mainloop()
