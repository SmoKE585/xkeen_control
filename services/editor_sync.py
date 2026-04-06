import os
import subprocess
import threading
from dataclasses import dataclass

from config import TEMP_CONFIG_DIR, XRAY_CONFIG_DIR
from ssh_session import SSHSession


@dataclass
class ConfigEditSession:
    remote_path: str
    local_path: str
    process: subprocess.Popen | None
    last_mtime: float
    upload_in_progress: bool = False


class ConfigEditorSync:
    def __init__(self, ssh: SSHSession):
        self.ssh = ssh
        self.sessions: dict[str, ConfigEditSession] = {}
        os.makedirs(TEMP_CONFIG_DIR, exist_ok=True)

    def normalize_remote_path(self, path: str) -> str:
        if path.startswith(XRAY_CONFIG_DIR):
            return path.replace("\\", "/")
        return f"{XRAY_CONFIG_DIR.rstrip('/')}/{path.lstrip('/').replace('\\', '/')}"

    def local_temp_path(self, remote_path: str) -> str:
        safe_name = remote_path.strip("/").replace("/", "__")
        return os.path.join(TEMP_CONFIG_DIR, safe_name)

    def open_for_edit(self, remote_path: str, editor_path: str | None) -> None:
        remote_path = self.normalize_remote_path(remote_path)
        local_path = self.local_temp_path(remote_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.ssh.download_file(remote_path, local_path)
        process = subprocess.Popen([editor_path, local_path]) if editor_path else None
        if editor_path is None:
            os.startfile(local_path)
        self.sessions[local_path] = ConfigEditSession(
            remote_path=remote_path,
            local_path=local_path,
            process=process,
            last_mtime=os.path.getmtime(local_path) if os.path.exists(local_path) else 0.0,
        )

    def sync(self, on_error) -> None:
        to_remove: list[str] = []
        for local_path, session in list(self.sessions.items()):
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
                        on_error("Ошибка загрузки", f"Не удалось загрузить файл на роутер:\n{exc}")
                    finally:
                        s.upload_in_progress = False

                threading.Thread(target=uploader, daemon=True).start()

            if session.process is not None and session.process.poll() is not None and not session.upload_in_progress:
                try:
                    os.remove(local_path)
                except OSError:
                    pass
                to_remove.append(local_path)
        for path in to_remove:
            self.sessions.pop(path, None)

    def cleanup(self) -> None:
        self.sessions.clear()
        if os.path.isdir(TEMP_CONFIG_DIR):
            for name in os.listdir(TEMP_CONFIG_DIR):
                path = os.path.join(TEMP_CONFIG_DIR, name)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
