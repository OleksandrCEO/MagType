"""
Cross-platform icon management for MagType.

Handles icon path resolution across different platforms and installation methods:
- NixOS: Uses MAGTYPE_ICONS_PATH environment variable
- Linux: XDG directories or relative paths
- macOS: Application bundle or relative paths
"""

import os
import platform
from pathlib import Path
from typing import Optional


class IconManager:
    """Manages icon paths across different platforms."""

    ICON_NAMES = ["idle", "listening", "transcribing"]

    def __init__(self, custom_path: Optional[str] = None):
        self.system = platform.system()
        self.icons_dir = self._resolve_icons_dir(custom_path)

    def _resolve_icons_dir(self, custom_path: Optional[str]) -> Path:
        """Resolve the icons directory based on platform and environment."""

        # Priority 1: Custom path provided
        if custom_path and os.path.isdir(custom_path):
            return Path(custom_path)

        # Priority 2: Environment variable (Nix-friendly)
        env_path = os.environ.get("MAGTYPE_ICONS_PATH")
        if env_path and os.path.isdir(env_path):
            return Path(env_path)

        # Priority 3: Platform-specific standard locations
        candidates = self._get_platform_candidates()

        for candidate in candidates:
            if candidate.is_dir() and self._validate_icons_dir(candidate):
                return candidate

        # Priority 4: Relative to this module
        module_relative = Path(__file__).parent.parent / "icons"
        if module_relative.is_dir():
            return module_relative

        raise FileNotFoundError(
            f"Could not find icons directory. Searched:\n"
            f"  - Custom path: {custom_path}\n"
            f"  - MAGTYPE_ICONS_PATH: {env_path}\n"
            f"  - Platform candidates: {candidates}\n"
            f"  - Module relative: {module_relative}"
        )

    def _get_platform_candidates(self) -> list[Path]:
        """Get platform-specific icon directory candidates."""
        candidates = []

        if self.system == "Darwin":
            # macOS: Check application bundle and user directories
            candidates.extend([
                Path.home() / "Library" / "Application Support" / "MagType" / "icons",
                Path("/Applications/MagType.app/Contents/Resources/icons"),
            ])

        elif self.system == "Linux":
            # Linux: XDG directories
            xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            candidates.extend([
                Path(xdg_data) / "magtype" / "icons",
                Path("/usr/share/magtype/icons"),
                Path("/usr/local/share/magtype/icons"),
                # NixOS store paths are handled via environment variable
            ])

        return candidates

    def _validate_icons_dir(self, path: Path) -> bool:
        """Check if directory contains all required icons."""
        for name in self.ICON_NAMES:
            # Check for both SVG and PNG
            if not (path / f"{name}.svg").exists() and not (path / f"{name}.png").exists():
                return False
        return True

    def get_icon_path(self, state: str) -> str:
        """Get the full path for a specific icon state."""
        if state not in self.ICON_NAMES:
            raise ValueError(f"Unknown icon state: {state}. Valid: {self.ICON_NAMES}")

        # Prefer SVG, fallback to PNG
        svg_path = self.icons_dir / f"{state}.svg"
        if svg_path.exists():
            return str(svg_path)

        png_path = self.icons_dir / f"{state}.png"
        if png_path.exists():
            return str(png_path)

        raise FileNotFoundError(f"Icon not found: {state} in {self.icons_dir}")

    def get_all_icons(self) -> dict[str, str]:
        """Get paths for all icons."""
        return {name: self.get_icon_path(name) for name in self.ICON_NAMES}


def get_socket_path() -> str:
    """Get platform-appropriate socket path."""
    system = platform.system()

    if system == "Darwin":
        # macOS: User-specific socket in home directory
        return str(Path.home() / ".magtype.sock")
    else:
        # Linux: Standard /tmp location
        return "/tmp/magtype.sock"
