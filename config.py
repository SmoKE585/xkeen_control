import os
from urllib.parse import urlparse
from env_utils import env_value, find_env_file, load_env_file, resolve_app_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = resolve_app_dir(BASE_DIR)
ENV_FILE = find_env_file(BASE_DIR)
ENV = load_env_file(ENV_FILE)
ICON_DIR = os.path.join(BASE_DIR, "assets", "icons")
APP_DATA_DIR = env_value("APP_DATA_DIR", os.path.join(os.environ.get("LOCALAPPDATA", APP_DIR), "xKeen Control"), ENV)
APP_ICON_ICO = env_value("APP_ICON_ICO", os.path.join(ICON_DIR, "app.ico"), ENV)
TRAY_ICON_ON = env_value("TRAY_ICON_ON", os.path.join(ICON_DIR, "vpn_on.svg"), ENV)
TRAY_ICON_OFF = env_value("TRAY_ICON_OFF", os.path.join(ICON_DIR, "vpn_off.svg"), ENV)
TRAY_ICON_UNKNOWN = env_value("TRAY_ICON_UNKNOWN", os.path.join(ICON_DIR, "vpn_unknow.svg"), ENV)

ROUTER_HOST = env_value("ROUTER_HOST", "192.168.1.1", ENV)
ROUTER_PORT = int(env_value("ROUTER_PORT", "22", ENV))
ROUTER_USER = env_value("ROUTER_USER", "root", ENV)
ROUTER_PASSWORD = env_value("ROUTER_PASSWORD", "change_me", ENV)

CMD_VPN_ON = env_value("CMD_VPN_ON", "xkeen -restart", ENV)
CMD_VPN_OFF = env_value("CMD_VPN_OFF", "xkeen -stop", ENV)
CMD_STATUS = env_value("CMD_STATUS", "xkeen -status", ENV)

STATUS_POLL_INTERVAL = int(env_value("STATUS_POLL_INTERVAL", "180", ENV))
XRAY_CONFIG_DIR = env_value("XRAY_CONFIG_DIR", "/opt/etc/xray/configs", ENV)
VPN_RESTART_DELAY_SEC = int(env_value("VPN_RESTART_DELAY_SEC", "3", ENV))
TEMP_CONFIG_DIR = env_value(
    "TEMP_CONFIG_DIR",
    os.path.join(
        APP_DATA_DIR,
        "temp_configs",
    ),
    ENV,
)
SITE_CHECKS_FILE = env_value("SITE_CHECKS_FILE", os.path.join(APP_DATA_DIR, "site_checks.json"), ENV)
OUTBOUNDS_CONFIG_PATH = env_value("OUTBOUNDS_CONFIG_PATH", f"{XRAY_CONFIG_DIR.rstrip('/')}/04_outbounds.json", ENV)
ROUTING_CONFIG_PATH = env_value("ROUTING_CONFIG_PATH", f"{XRAY_CONFIG_DIR.rstrip('/')}/05_routing.json", ENV)

NOTEPADPP_CANDIDATES = [
    env_value("NOTEPADPP_PATH", "", ENV),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Notepad++", "notepad++.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Notepad++", "notepad++.exe"),
]

CONNECTIVITY_CHECKS = [
    {
        "name": env_value("CHECK_1_NAME", "Прямое подключение", ENV),
        "url": env_value("CHECK_1_URL", "https://ya.ru", ENV),
        "expected": env_value("CHECK_1_EXPECTED", "direct", ENV),
    },
    {
        "name": env_value("CHECK_2_NAME", "RU маршрут", ENV),
        "url": env_value("CHECK_2_URL", "https://www.youtube.com", ENV),
        "expected": env_value("CHECK_2_EXPECTED", "RU", ENV),
    },
    {
        "name": env_value("CHECK_3_NAME", "NL маршрут", ENV),
        "url": env_value("CHECK_3_URL", "https://example.com", ENV),
        "expected": env_value("CHECK_3_EXPECTED", "GE", ENV),
    },
]


def format_host(url: str) -> str:
    return urlparse(url).netloc or url
