import os
import sys


def load_env_file(path: str) -> dict[str, str]:
    if not os.path.isfile(path):
        return {}

    values: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def env_value(name: str, default: str, file_values: dict[str, str]) -> str:
    return os.environ.get(name, file_values.get(name, default))


def resolve_app_dir(base_dir: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return base_dir


def find_env_file(base_dir: str, filename: str = ".env") -> str:
    app_dir = resolve_app_dir(base_dir)
    candidates = [
        os.path.join(app_dir, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(base_dir, filename),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        full = os.path.abspath(candidate)
        if full in seen:
            continue
        seen.add(full)
        if os.path.isfile(full):
            return full
    return os.path.join(app_dir, filename)
