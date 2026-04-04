"""
Cross-platform clipboard controller for MagType.

Provides clipboard and keyboard simulation support for:
- Linux (Wayland via wl-copy + ydotool)
- Linux (X11 via xclip + xdotool)
- macOS (pbcopy + osascript)
"""

import os
import platform
import subprocess
import shutil


class ClipboardController:
    """Cross-platform clipboard operations and virtual key injection."""

    def __init__(self):
        self.system = platform.system()
        self.is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        self._check_dependencies()

    def _check_dependencies(self):
        """Verify required tools are installed."""
        if self.system == "Darwin":
            required = ["pbcopy", "osascript"]
        elif self.system == "Linux":
            if self.is_wayland:
                required = ["wl-copy", "ydotool"]
            else:
                required = ["xclip", "xdotool"]
        else:
            raise OSError(f"Unsupported platform: {self.system}")

        missing = [cmd for cmd in required if not shutil.which(cmd)]
        if missing:
            raise RuntimeError(
                f"Missing required tools: {', '.join(missing)}\n"
                f"Please install them for your platform."
            )

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard."""
        if not text:
            return False

        try:
            if self.system == "Darwin":
                subprocess.run(
                    ["pbcopy"],
                    input=text.encode("utf-8"),
                    check=True
                )
            elif self.is_wayland:
                subprocess.run(
                    ["wl-copy", text],
                    check=True
                )
            else:  # X11
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"),
                    check=True
                )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Clipboard copy failed: {e}")
            return False

    def simulate_paste(self) -> bool:
        """Simulate Ctrl+V (or Cmd+V on macOS) keypress."""
        try:
            if self.system == "Darwin":
                subprocess.run([
                    "osascript", "-e",
                    'tell application "System Events" to keystroke "v" using command down'
                ], check=True)

            elif self.is_wayland:
                # ydotool scancodes: 29 = Left Ctrl, 47 = V
                subprocess.run([
                    "ydotool", "key",
                    "29:1", "47:1", "47:0", "29:0"
                ], check=True)

            else:  # X11
                subprocess.run([
                    "xdotool", "key", "ctrl+v"
                ], check=True)

            return True
        except subprocess.CalledProcessError as e:
            print(f"Paste simulation failed: {e}")
            return False

    @staticmethod
    def paste_text(text: str):
        """Copy text to clipboard and simulate paste keystroke."""
        if not text:
            return

        controller = ClipboardController()
        if controller.copy_to_clipboard(text):
            controller.simulate_paste()
