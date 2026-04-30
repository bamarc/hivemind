import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import pathspec

logger = logging.getLogger(__name__)

class GitManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.is_git_repo = self._check_is_git_repo()
        self.spec = self._load_gitignore()

    def _check_is_git_repo(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _load_gitignore(self) -> Optional[pathspec.PathSpec]:
        gitignore_path = self.root_path / ".gitignore"
        if not gitignore_path.exists():
            return None
        
        try:
            with open(gitignore_path, "r") as f:
                lines = f.readlines()
            return pathspec.PathSpec.from_lines("gitignore", lines)
        except Exception as e:
            logger.error(f"Failed to load .gitignore: {e}")
            return None

    def is_ignored(self, filepath: Path) -> bool:
        if not self.spec:
            return False
        
        # pathspec expects paths relative to the root
        try:
            relative_path = filepath.relative_to(self.root_path)
            return self.spec.match_file(str(relative_path))
        except ValueError:
            # File is outside root_path
            return False

    def is_tracked(self, filepath: Path) -> bool:
        if not self.is_git_repo:
            return True # If not a repo, assume tracked/indexable

        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(filepath)],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_commit_metadata(self, filepath: Path) -> Dict[str, Any]:
        if not self.is_git_repo:
            return {}

        try:
            # Get last commit info for this file
            result = subprocess.run(
                [
                    "git", "log", "-1", 
                    "--format=%H%n%an%n%ae%n%ad%n%s", 
                    "--date=iso",
                    "--", str(filepath)
                ],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return {}

            lines = result.stdout.strip().split("\n")
            if len(lines) < 5:
                return {}

            return {
                "commit_hash": lines[0],
                "commit_author": lines[1],
                "commit_email": lines[2],
                "commit_date": lines[3],
                "commit_subject": lines[4]
            }
        except Exception as e:
            logger.error(f"Failed to get git metadata for {filepath}: {e}")
            return {}
