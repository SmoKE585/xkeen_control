import json
import os
import shutil
import time
import urllib.error
import urllib.request
from typing import Optional

from config import (
    CMD_STATUS,
    CMD_VPN_OFF,
    CMD_VPN_ON,
    CONNECTIVITY_CHECKS,
    NOTEPADPP_CANDIDATES,
    OUTBOUNDS_CONFIG_PATH,
    ROUTER_HOST,
    ROUTER_PASSWORD,
    ROUTER_PORT,
    ROUTER_USER,
    ROUTING_CONFIG_PATH,
    SITE_CHECKS_FILE,
    TEMP_CONFIG_DIR,
    VPN_RESTART_DELAY_SEC,
    XRAY_CONFIG_DIR,
)
from models import ConnectivityCheck, RouterStats
from ssh_session import SSHSession


class RouterService:
    def __init__(self):
        self.ssh = SSHSession(ROUTER_HOST, ROUTER_PORT, ROUTER_USER, ROUTER_PASSWORD)

    @staticmethod
    def strip_ansi(text: str) -> str:
        import re
        return re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", text)

    def close(self) -> None:
        self.ssh.close()

    def exec(self, cmd: str) -> str:
        return self.ssh.exec(cmd)

    def get_status(self) -> str:
        try:
            output = self.exec(CMD_STATUS)
            text = self.strip_ansi(output).lower()
            if "запущен" in text and "не запущен" not in text:
                return "on"
            if "не запущен" in text:
                return "off"
            return "unknown"
        except Exception:
            return "unknown"

    def vpn_on(self) -> None:
        self.exec(CMD_VPN_ON)

    def vpn_off(self) -> None:
        self.exec(CMD_VPN_OFF)

    def vpn_restart(self) -> None:
        self.vpn_off()
        time.sleep(VPN_RESTART_DELAY_SEC)
        self.vpn_on()

    def get_notepadpp_path(self) -> Optional[str]:
        path = shutil.which("notepad++.exe")
        if path:
            return path
        for candidate in NOTEPADPP_CANDIDATES:
            if candidate and os.path.isfile(candidate):
                return candidate
        return None

    def list_configs(self) -> list[str]:
        files = [f for f in self.ssh.listdir(XRAY_CONFIG_DIR) if f.lower().endswith(".json")]
        return files or ["[пусто]"]

    def get_router_stats(self) -> RouterStats:
        uptime_raw = self.strip_ansi(self.exec("uptime"))
        mem_raw = self.strip_ansi(self.exec("free -m 2>/dev/null"))
        cpu_raw = self.strip_ansi(self.exec("top -bn1 | grep xray"))
        status = self.get_status()

        uptime_text = uptime_raw.strip()
        load = ""
        if "load average" in uptime_raw:
            load = uptime_raw.split("load average:")[-1].strip()
            uptime_text = uptime_raw.split("load average:")[0].rstrip(" ,")

        mem_text = "Не удалось получить данные"
        mem_lines = mem_raw.splitlines()
        if len(mem_lines) >= 2:
            parts = mem_lines[1].split()
            if len(parts) >= 4:
                mem_text = f"{parts[2]} MB / {parts[1]} MB (свободно {parts[3]} MB)"

        xray_cpu = "Неизвестно"
        if cpu_raw:
            for part in cpu_raw.split():
                candidate = part.rstrip("%")
                try:
                    float(candidate)
                    xray_cpu = f"{candidate}%"
                    break
                except ValueError:
                    continue

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
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "xKeen-Control/1.0", "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return ConnectivityCheck(name=name, url=url, expected=expected, ok=True, status_code=getattr(response, "status", None), latency_ms=int((time.perf_counter() - start) * 1000))
        except urllib.error.HTTPError as exc:
            return ConnectivityCheck(name=name, url=url, expected=expected, ok=True, status_code=exc.code, latency_ms=int((time.perf_counter() - start) * 1000))
        except Exception as exc:
            return ConnectivityCheck(name=name, url=url, expected=expected, ok=False, status_code=None, latency_ms=None, error=str(exc))

    def load_site_checks(self) -> list[dict]:
        if os.path.isfile(SITE_CHECKS_FILE):
            try:
                with open(SITE_CHECKS_FILE, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, list):
                    return loaded
            except Exception:
                pass
        return [dict(item) for item in CONNECTIVITY_CHECKS]

    def save_site_checks(self, checks: list[dict]) -> None:
        os.makedirs(os.path.dirname(SITE_CHECKS_FILE), exist_ok=True)
        with open(SITE_CHECKS_FILE, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(checks, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def get_connectivity_checks(self) -> list[ConnectivityCheck]:
        return [self.probe_url(item["name"], item["url"], item["expected"]) for item in self.load_site_checks()]

    def read_remote_json(self, remote_path: str) -> dict:
        return json.loads(self.exec(f"cat {remote_path}"))

    def write_remote_json(self, remote_path: str, data: dict) -> None:
        os.makedirs(TEMP_CONFIG_DIR, exist_ok=True)
        temp_path = os.path.join(TEMP_CONFIG_DIR, "json_save_tmp.json")
        try:
            with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            self.ssh.upload_file(temp_path, remote_path)
        finally:
            if os.path.isfile(temp_path):
                os.remove(temp_path)

    def load_outbounds_config(self) -> dict:
        return self.read_remote_json(OUTBOUNDS_CONFIG_PATH)

    def save_outbounds_config(self, data: dict) -> None:
        self.write_remote_json(OUTBOUNDS_CONFIG_PATH, data)

    def load_routing_config(self) -> dict:
        return self.read_remote_json(ROUTING_CONFIG_PATH)

    def save_routing_config(self, data: dict) -> None:
        self.write_remote_json(ROUTING_CONFIG_PATH, data)
