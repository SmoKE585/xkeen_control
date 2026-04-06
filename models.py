from dataclasses import dataclass
from typing import Optional


@dataclass
class RouterStats:
    text: str
    status: str
    uptime: str
    load_average: str
    xray_cpu: str
    memory: str


@dataclass
class ConnectivityCheck:
    name: str
    url: str
    expected: str
    ok: bool
    status_code: Optional[int]
    latency_ms: Optional[int]
    error: str = ""
