import yaml
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_dir: Path, debounce_seconds: int = 5):
        self.state_dir = state_dir
        self.state_file = state_dir / "state.yaml"
        self.pid_file = state_dir / "indexer.pid"
        self.state: Dict[str, Any] = {"indexed_files": {}}
        self.debounce_seconds = debounce_seconds
        self.last_save_time = 0.0
        self.lock = threading.Lock()
        self._load_state()

    def _load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self.state = yaml.safe_load(f) or {"indexed_files": {}}
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                self.state = {"indexed_files": {}}
        else:
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, force: bool = False):
        import time
        current_time = time.time()
        
        with self.lock:
            if not force and (current_time - self.last_save_time) < self.debounce_seconds:
                return

            try:
                with open(self.state_file, "w") as f:
                    yaml.safe_dump(self.state, f)
                self.last_save_time = current_time
                logger.debug("State saved to disk")
            except Exception as e:
                logger.error(f"Failed to save state file: {e}")

    def get_file_hash(self, filepath: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def should_reindex(self, filepath: Path) -> bool:
        filepath_str = str(filepath.absolute())
        
        with self.lock:
            if filepath_str not in self.state["indexed_files"]:
                return True
            stored_state = self.state["indexed_files"][filepath_str]

        current_mtime = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
        
        if stored_state["last_modified"] != current_mtime:
            # Checksum as a fallback/verification
            current_hash = self.get_file_hash(filepath)
            if stored_state["checksum"] != current_hash:
                return True
        
        return False

    def update_file_state(self, filepath: Path, chunk_count: int):
        filepath_str = str(filepath.absolute())
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
        checksum = self.get_file_hash(filepath)
        now = datetime.now().isoformat()
        
        with self.lock:
            self.state["indexed_files"][filepath_str] = {
                "last_modified": mtime,
                "checksum": checksum,
                "chunk_count": chunk_count,
                "indexed_at": now
            }
        self.save_state()

    def flush(self):
        """Force save the state to disk."""
        self.save_state(force=True)

    def write_pid(self):
        import os
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def remove_pid(self):
        if self.pid_file.exists():
            self.pid_file.unlink()

    def get_pid(self) -> Optional[int]:
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except Exception:
                return None
        return None
