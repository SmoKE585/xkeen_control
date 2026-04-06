import threading
from typing import Optional

import paramiko


class SSHSession:
    """Reusable SSH connection with auto-reconnect."""

    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 5):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

        self._client: Optional[paramiko.SSHClient] = None
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None

    def _connect_locked(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
        )
        try:
            transport = client.get_transport()
            if transport:
                transport.set_keepalive(30)
        except Exception:
            pass

        self._client = client

    def ensure_connected(self) -> None:
        with self._lock:
            if self._client is None:
                self._connect_locked()
                return

            try:
                transport = self._client.get_transport()
                if transport is None or not transport.is_active():
                    self.close()
                    self._connect_locked()
            except Exception:
                self.close()
                self._connect_locked()

    def exec(self, cmd: str) -> str:
        with self._lock:
            self.ensure_connected()
            assert self._client is not None
            try:
                _stdin, stdout, stderr = self._client.exec_command(cmd)
                out = stdout.read().decode(errors="ignore")
                err = stderr.read().decode(errors="ignore")
                return (out + ("\n" + err if err else "")).strip()
            except Exception:
                self.close()
                self._connect_locked()
                assert self._client is not None
                _stdin, stdout, stderr = self._client.exec_command(cmd)
                out = stdout.read().decode(errors="ignore")
                err = stderr.read().decode(errors="ignore")
                return (out + ("\n" + err if err else "")).strip()

    def listdir(self, path: str) -> list[str]:
        with self._lock:
            self.ensure_connected()
            assert self._client is not None
            sftp = self._client.open_sftp()
            try:
                return sorted(sftp.listdir(path), key=str.lower)
            finally:
                sftp.close()

    def download_file(self, remote_path: str, local_path: str) -> None:
        with self._lock:
            self.ensure_connected()
            assert self._client is not None
            sftp = self._client.open_sftp()
            try:
                sftp.get(remote_path, local_path)
            finally:
                sftp.close()

    def upload_file(self, local_path: str, remote_path: str) -> None:
        with self._lock:
            self.ensure_connected()
            assert self._client is not None
            sftp = self._client.open_sftp()
            try:
                sftp.put(local_path, remote_path)
            finally:
                sftp.close()
