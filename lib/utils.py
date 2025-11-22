"""Utility functions for step validation and DSL extraction."""

from pathlib import Path
from typing import Optional


# ============================================================================
# Type extraction and validation helpers
# ============================================================================


def find_repo_root(file_path: str) -> Optional[Path]:
    """Find the repository root by looking for .git directory or pyproject.toml."""
    path = Path(file_path).resolve()

    # If it's a file, start from its parent directory
    if path.is_file():
        path = path.parent

    # Walk up the directory tree looking for repo markers
    for parent in [path] + list(path.parents):
        # Check for common repository markers
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    # If no marker found, return None
    return None


def get_relative_path(file_path: str) -> Optional[str]:
    """Convert an absolute file path to a relative path from the repository root."""
    if not file_path:
        return None

    try:
        abs_path = Path(file_path).resolve()
        repo_root = find_repo_root(file_path)

        if repo_root:
            try:
                relative_path = abs_path.relative_to(repo_root)
                return str(relative_path)
            except ValueError:
                # File is not under the repo root
                return file_path
        else:
            # No repo root found, return absolute path as fallback
            return file_path
    except Exception:
        # If anything goes wrong, return the original path
        return file_path
