"""Nonblocking process lock: avoid simultaneous CLI/server writes to one catalogue."""
from pathlib import Path

class OperationLock:
    def __init__(self, path):
        self.path = Path(path)
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a+b')
        try:
            try:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.unlock = lambda: fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            except ImportError:
                import msvcrt
                self.handle.seek(0); self.handle.write(b'0'); self.handle.flush(); self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                self.unlock = lambda: (self.handle.seek(0), msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1))
        except OSError as exc:
            self.handle.close()
            raise RuntimeError('Another collection/report build is running for this project') from exc
        return self
    def __exit__(self, *args):
        self.unlock(); self.handle.close()
