"""Utility functions for step validation and DSL extraction."""

from pathlib import Path
from typing import Optional


# ============================================================================
# Type extraction and validation helpers
# ============================================================================


def get_relative_path(file_path: str) -> Optional[str]:
    """Convert an absolute file path (from inspect.getfile()) to a relative path from the repository root.

    Assumes main.py runs from within the same repository as the steps are defined.
    Finds the repo root by walking up from the file_path or current working directory,
    looking for .git or pyproject.toml.
    """
    if not file_path:
        return None

    try:
        # inspect.getfile() returns an absolute path, so resolve it
        abs_path = Path(file_path).resolve()
    except (OSError, RuntimeError):
        # If resolve fails, use the path as-is
        abs_path = Path(file_path)
        if not abs_path.is_absolute():
            abs_path = Path.cwd() / abs_path

    # Find repo root by walking up from the file path
    search_path = abs_path.parent if abs_path.is_file() else abs_path
    for parent in [search_path] + list(search_path.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            try:
                return str(abs_path.relative_to(parent))
            except ValueError:
                # File is not under this parent, continue searching
                pass

    # Fallback: try to find repo root from current working directory
    # This works because main.py runs from within the same repo as the steps
    try:
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                try:
                    return str(abs_path.relative_to(parent))
                except ValueError:
                    # File is not under this parent, continue searching
                    pass
    except (OSError, RuntimeError):
        pass

    # If no repo root found, return the original path
    return file_path
