"""Native folder picker — OS-appropriate folder selection for P3d."""

from __future__ import annotations

import sys
from pathlib import Path


def select_folder_native(prompt: str = "Select project folder") -> Path | None:
    """Open a native folder picker dialog.

    Returns the selected folder path, or None if cancelled.
    Uses platform-appropriate implementation.
    """
    if sys.platform == "win32":
        return _select_folder_windows(prompt)
    elif sys.platform == "darwin":
        return _select_folder_macos(prompt)
    else:
        return _select_folder_tkinter(prompt)


def _select_folder_windows(prompt: str) -> Path | None:
    """Windows folder picker using tkinter (available in Python stdlib)."""
    return _select_folder_tkinter(prompt)


def _select_folder_macos(prompt: str) -> Path | None:
    """macOS folder picker using tkinter (available in Python stdlib)."""
    return _select_folder_tkinter(prompt)


def _select_folder_tkinter(prompt: str) -> Path | None:
    """Cross-platform folder picker using tkinter.

    tkinter is part of Python stdlib and available on all platforms.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes("-topmost", True)  # Keep on top

        folder_path = filedialog.askdirectory(
            title=prompt,
            mustexist=True,
        )

        root.destroy()

        if folder_path:
            return Path(folder_path)
        return None

    except ImportError:
        # tkinter not available (e.g., headless environment)
        return None
    except Exception as exc:
        print(f"Folder picker error: {exc}")
        return None


def select_folder_cli(prompt: str = "Enter project folder path") -> Path | None:
    """CLI fallback for folder selection (test/development use only).

    This is NOT the normal customer flow. Normal customers use the native picker.
    """
    try:
        path_str = input(f"{prompt}: ").strip()
        if not path_str:
            return None
        return Path(path_str)
    except (EOFError, KeyboardInterrupt):
        return None
