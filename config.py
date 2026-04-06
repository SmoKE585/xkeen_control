import os
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "assets", "icons")
APP_ICON_ICO = os.path.join(ICON_DIR, "app.ico")
TRAY_ICON_ON = os.path.join(ICON_DIR, "tray_on.png")
TRAY_ICON_OFF = os.path.join(ICON_DIR, "tray_off.png")
TRAY_ICON_UNKNOWN = os.path.join(ICON_DIR, "tray_unknown.png")

SMB_HOST = r"\\192.168.1.1"
SMB_USER = "admin"
SMB_PASS = "change_me"

ROUTER_HOST = "192.168.1.1"
ROUTER_PORT = 22
ROUTER_USER = "root"
ROUTER_PASSWORD = "change_me"

CMD_VPN_ON = "xkeen -restart"
CMD_VPN_OFF = "xkeen -stop"
CMD_STATUS = "xkeen -status"

STATUS_POLL_INTERVAL = 180
XRAY_CONFIG_DIR = r"\\192.168.1.1\data\etc\xray\configs"
VPN_RESTART_DELAY_SEC = 3

NOTEPADPP_CANDIDATES = [
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Notepad++", "notepad++.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Notepad++", "notepad++.exe"),
]

CONNECTIVITY_CHECKS = [
    {
        "name": "Прямое подключение",
        "url": "https://ya.ru",
        "expected": "Должно открываться напрямую",
    },
    {
        "name": "RU маршрут",
        "url": "https://www.youtube.com",
        "expected": "Маршрут через RU сервер",
    },
    {
        "name": "NL маршрут",
        "url": "https://example.com",
        "expected": "Маршрут через Нидерланды",
    },
]


def format_host(url: str) -> str:
    return urlparse(url).netloc or url


try:
    from config_local import *  # type: ignore[F403]
except ImportError:
    pass
