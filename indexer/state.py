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
        """Determine whether *filepath* needs to be re-indexed.

        Also returns ``False`` if the file has been permanently failed
        (retry count exceeded) or is in a cooldown period (temporary
        failure within the backoff window).
        """
        filepath_str = str(filepath.absolute())

        with self.lock:
            if filepath_str not in self.state["indexed_files"]:
                return True

            stored_state = self.state["indexed_files"][filepath_str]

            # ── Permanently failed — never retry ──────────────────────
            if stored_state.get("failed"):
                logger.debug(f"Skipping permanently failed file: {filepath}")
                return False

            # ── Cooldown: temporary failure with backoff ──────────────
            retry_count = stored_state.get("embed_retries", 0)
            if retry_count > 0:
                import time
                # Exponential backoff: 2^retry_count minutes (capped at 60 min)
                cooldown_minutes = min(2 ** retry_count, 60)
                last_attempt = stored_state.get("last_embed_attempt", 0.0)
                elapsed = time.time() - last_attempt
                if elapsed < cooldown_minutes * 60:
                    logger.debug(
                        f"Skipping {filepath} — retry #{retry_count}, "
                        f"cooldown {cooldown_minutes}min, "
                        f"{int(cooldown_minutes * 60 - elapsed)}s remaining"
                    )
                    return False

            # ── Normal staleness check ────────────────────────────────
            current_mtime = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()

            if stored_state.get("last_modified") != current_mtime:
                # Checksum as a fallback/verification
                current_hash = self.get_file_hash(filepath)
                if stored_state.get("checksum") != current_hash:
                    return True

            return False

    def record_embed_failure(self, filepath: Path, max_retries: int = 5):
        """Record that embedding failed for *filepath*.

        Increments the retry counter.  When the counter exceeds
        *max_retries* the file is marked as permanently failed so it
        will never be retried again.
        """
        filepath_str = str(filepath.absolute())
        import time

        with self.lock:
            if filepath_str not in self.state["indexed_files"]:
                self.state["indexed_files"][filepath_str] = {}

            entry = self.state["indexed_files"][filepath_str]
            entry["last_embed_attempt"] = time.time()
            retries = entry.get("embed_retries", 0) + 1
            entry["embed_retries"] = retries

            if retries > max_retries:
                entry["failed"] = True
                logger.warning(
                    f"File {filepath} permanently failed after {retries} "
                    f"embedding retries.  It will be excluded from future "
                    f"indexing runs."
                )
            else:
                cooldown = min(2 ** retries, 60)
                logger.info(
                    f"Embedding failed for {filepath} (retry #{retries}). "
                    f"Next attempt in ~{cooldown}min."
                )

        self.save_state()

    def record_embed_success(self, filepath: Path):
        """Clear the retry counter after a successful embed."""
        filepath_str = str(filepath.absolute())
        with self.lock:
            if filepath_str in self.state["indexed_files"]:
                entry = self.state["indexed_files"][filepath_str]
                entry.pop("embed_retries", None)
                entry.pop("last_embed_attempt", None)
                entry.pop("failed", None)

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
