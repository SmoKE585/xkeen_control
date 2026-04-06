import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import winreg
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle

from config import (
    APP_ICON_ICO,
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
    TEMP_CONFIG_DIR,
    TRAY_ICON_OFF,
    TRAY_ICON_ON,
    TRAY_ICON_UNKNOWN,
    VPN_RESTART_DELAY_SEC,
    XRAY_CONFIG_DIR,
    format_host,
)
from models import ConnectivityCheck, RouterStats
from ssh_session import SSHSession
from ui import MainWindow


class AppSignals(QObject):
    tray_status_changed = Signal(str)
    status_changed = Signal(str)
    connection_changed = Signal(bool)
    stats_changed = Signal(object)
    checks_changed = Signal(list)
    busy_changed = Signal(bool)
    error_occurred = Signal(str, str)
    configs_changed = Signal(list)
    tray_tooltip_changed = Signal(str)


class ConfigEditSession:
    def __init__(self, remote_path: str, local_path: str, process: subprocess.Popen | None):
        self.remote_path = remote_path
        self.local_path = local_path
        self.process = process
        self.last_mtime = os.path.getmtime(local_path) if os.path.exists(local_path) else 0.0
        self.upload_in_progress = False


class VPNTrayApp:
    ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
    STARTUP_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_VALUE_NAME = "xKeen Control"

    def __init__(self):
        QGuiApplication.setApplicationDisplayName("xKeen Control")

        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)

        self.current_status: str = "unknown"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.signals = AppSignals()
        self.config_sessions: dict[str, ConfigEditSession] = {}

        self.ssh = SSHSession(ROUTER_HOST, ROUTER_PORT, ROUTER_USER, ROUTER_PASSWORD)
        self.window = MainWindow(self)
        self.tray = self.window.tray_icon

        self.signals.status_changed.connect(self.window.set_status_text)
        self.signals.tray_status_changed.connect(self._apply_status)
        self.signals.connection_changed.connect(self.window.set_connection_state)
        self.signals.stats_changed.connect(self.window.update_stats_cards)
        self.signals.checks_changed.connect(self.window.update_connectivity_checks)
        self.signals.busy_changed.connect(self.window.set_busy)
        self.signals.error_occurred.connect(self.window.show_error)
        self.signals.configs_changed.connect(self.window.update_configs)
        self.signals.tray_tooltip_changed.connect(self._apply_tray_tooltip)

        self.icon_on = self._load_icon(TRAY_ICON_ON, QStyle.SP_DialogApplyButton)
        self.icon_off = self._load_icon(TRAY_ICON_OFF, QStyle.SP_DialogCancelButton)
        self.icon_unknown = self._load_icon(TRAY_ICON_UNKNOWN, QStyle.SP_MessageBoxQuestion)
        self.window.setWindowIcon(self._load_window_icon())
        self.tray.setIcon(self.icon_unknown)

        self._setup_tray_menu()
        os.makedirs(TEMP_CONFIG_DIR, exist_ok=True)
        self.cleanup_temp_dir()

        self.config_sync_timer = QTimer()
        self.config_sync_timer.setInterval(1500)
        self.config_sync_timer.timeout.connect(self.sync_temp_configs)

    def _load_window_icon(self) -> QIcon:
        if os.path.isfile(APP_ICON_ICO):
            icon = QIcon(APP_ICON_ICO)
            if not icon.isNull():
                return icon
        return self.qt_app.style().standardIcon(QStyle.SP_ComputerIcon)

    def _load_icon(self, path: str, fallback: QStyle.StandardPixmap) -> QIcon:
        if os.path.isfile(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
        return self.qt_app.style().standardIcon(fallback)

    def _setup_tray_menu(self) -> None:
        menu = QMenu()

        show_action = QAction("Открыть", self.window)
        show_action.triggered.connect(self.action_show)
        menu.addAction(show_action)

        menu.addSeparator()

        on_action = QAction("Включить", self.window)
        on_action.triggered.connect(self.action_on)
        menu.addAction(on_action)

        off_action = QAction("Выключить", self.window)
        off_action.triggered.connect(self.action_off)
        menu.addAction(off_action)

        restart_action = QAction("Перезапустить", self.window)
        restart_action.triggered.connect(self.action_restart)
        menu.addAction(restart_action)

        menu.addSeparator()

        settings_action = QAction("Настройки", self.window)
        settings_action.triggered.connect(self.action_settings)
        menu.addAction(settings_action)

        refresh_action = QAction("Проверить статус", self.window)
        refresh_action.triggered.connect(self.action_check)
        menu.addAction(refresh_action)

        menu.addSeparator()

        exit_action = QAction("Выход", self.window)
        exit_action.triggered.connect(self.action_exit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.window.on_tray_activated)

    def _apply_tray_tooltip(self, tooltip: str) -> None:
        self.tray.setToolTip(tooltip)

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
        self._ssh_exec(CMD_VPN_ON)

    def vpn_off(self) -> None:
        self._ssh_exec(CMD_VPN_OFF)

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
        remote_path = self._normalize_remote_path(path)
        local_path = self._local_temp_path(remote_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.ssh.download_file(remote_path, local_path)

        editor = self.get_notepadpp_path()
        process = None
        if editor:
            process = subprocess.Popen([editor, local_path])
        else:
            os.startfile(local_path)

        self.config_sessions[local_path] = ConfigEditSession(remote_path, local_path, process)
        if not self.config_sync_timer.isActive():
            self.config_sync_timer.start()

    def _normalize_remote_path(self, path: str) -> str:
        if path.startswith(XRAY_CONFIG_DIR):
            return path.replace("\\", "/")
        return f"{XRAY_CONFIG_DIR.rstrip('/')}/{path.lstrip('/').replace('\\', '/')}"

    def _local_temp_path(self, remote_path: str) -> str:
        safe_name = remote_path.strip("/").replace("/", "__")
        return os.path.join(TEMP_CONFIG_DIR, safe_name)

    def sync_temp_configs(self) -> None:
        if not self.config_sessions:
            self.config_sync_timer.stop()
            return

        to_remove: list[str] = []
        for local_path, session in list(self.config_sessions.items()):
            if not os.path.exists(local_path):
                to_remove.append(local_path)
                continue

            try:
                current_mtime = os.path.getmtime(local_path)
            except OSError:
                to_remove.append(local_path)
                continue

            if current_mtime > session.last_mtime and not session.upload_in_progress:
                session.last_mtime = current_mtime
                session.upload_in_progress = True

                def uploader(s: ConfigEditSession = session) -> None:
                    try:
                        self.ssh.upload_file(s.local_path, s.remote_path)
                    except Exception as exc:
                        self.signals.error_occurred.emit("Ошибка загрузки", f"Не удалось загрузить файл на роутер:\n{exc}")
                    finally:
                        s.upload_in_progress = False

                threading.Thread(target=uploader, daemon=True).start()

            if session.process is not None and session.process.poll() is not None and not session.upload_in_progress:
                try:
                    os.remove(local_path)
                except OSError:
                    pass
                to_remove.append(local_path)

        for local_path in to_remove:
            self.config_sessions.pop(local_path, None)

    def cleanup_temp_dir(self) -> None:
        if os.path.isdir(TEMP_CONFIG_DIR):
            for name in os.listdir(TEMP_CONFIG_DIR):
                path = os.path.join(TEMP_CONFIG_DIR, name)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass

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
            if len(parts) >= 4:
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

Средняя нагрузка:
{load}

================= CPU =================
Нагрузка xkeen:
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
            prefix = "xKeen Control: ВКЛЮЧЕН"
        elif status == "off":
            prefix = "xKeen Control: ВЫКЛЮЧЕН"
        else:
            prefix = "xKeen Control: НЕИЗВЕСТНО"

        try:
            checks = self.get_connectivity_checks()
            ok_count = sum(1 for check in checks if check.ok)
            failed_hosts = ", ".join(format_host(check.url) for check in checks if not check.ok)
            if failed_hosts:
                return f"{prefix} | Сайты: {ok_count}/{len(checks)} | Нет доступа: {failed_hosts}"
            return f"{prefix} | Сайты: {ok_count}/{len(checks)}"
        except Exception:
            return prefix

    def _apply_status(self, new_status: str) -> None:
        with self.lock:
            self.current_status = new_status
            if new_status == "on":
                self.tray.setIcon(self.icon_on)
            elif new_status == "off":
                self.tray.setIcon(self.icon_off)
            else:
                self.tray.setIcon(self.icon_unknown)

        self.signals.status_changed.emit(new_status)
        self.signals.tray_tooltip_changed.emit(self._compose_tray_title(new_status))

    def update_icon_status(self, new_status: str) -> None:
        self.signals.tray_status_changed.emit(new_status)

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
        except (FileNotFoundError, OSError):
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

    def reload_configs(self) -> None:
        items: list[str] = []
        try:
            files = [f for f in self.ssh.listdir(XRAY_CONFIG_DIR) if f.lower().endswith(".json")]
            items = files or ["[пусто]"]
        except Exception as exc:
            items = [f"[ошибка] {exc}"]
        self.signals.configs_changed.emit(items)

    def refresh_async(self) -> None:
        def worker() -> None:
            self.signals.busy_changed.emit(True)
            try:
                stats = self.get_router_stats()
                status = self.get_status()
                checks = self.get_connectivity_checks()
                self.signals.connection_changed.emit(True)
                self.signals.stats_changed.emit(stats)
                self.signals.status_changed.emit(status)
                self.signals.checks_changed.emit(checks)
                self.update_icon_status(status)
                self.reload_configs()
            except Exception as exc:
                self.signals.connection_changed.emit(False)
                self.signals.error_occurred.emit("Ошибка обновления", str(exc))
            finally:
                self.signals.busy_changed.emit(False)

        threading.Thread(target=worker, daemon=True).start()

    def run_vpn_action_async(self, action, action_name: str) -> None:
        def worker() -> None:
            self.signals.busy_changed.emit(True)
            try:
                action()
                self.refresh_async()
            except Exception as exc:
                self.signals.error_occurred.emit("Ошибка", f"{action_name} не выполнен:\n{exc}")
                self.signals.busy_changed.emit(False)

        threading.Thread(target=worker, daemon=True).start()

    def action_show(self) -> None:
        self.window.show_main()
        self.refresh_async()

    def action_settings(self) -> None:
        self.window.show_settings()

    def action_on(self) -> None:
        self.run_vpn_action_async(self.vpn_on, "Запуск xkeen")

    def action_off(self) -> None:
        self.run_vpn_action_async(self.vpn_off, "Остановка xkeen")

    def action_restart(self) -> None:
        self.run_vpn_action_async(self.vpn_restart, "Перезапуск xkeen")

    def action_check(self) -> None:
        self.refresh_async()

    def action_exit(self) -> None:
        self.stop_event.set()
        self.config_sync_timer.stop()
        try:
            self.ssh.close()
        except Exception:
            pass
        self.cleanup_temp_dir()
        self.tray.hide()
        self.qt_app.quit()

    def poll_status_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                status = self.get_status()
                self.update_icon_status(status)
            except Exception:
                self.update_icon_status("unknown")

            for _ in range(STATUS_POLL_INTERVAL):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

    def run(self) -> None:
        initial_status = self.get_status()
        self.current_status = initial_status
        self.update_icon_status(initial_status)
        self.reload_configs()
        self.tray.show()
        self.config_sync_timer.start()

        poll_thread = threading.Thread(target=self.poll_status_loop, daemon=True)
        poll_thread.start()

        QTimer.singleShot(0, self.refresh_async)
        sys.exit(self.qt_app.exec())
