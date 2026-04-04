# MagType

Local AI-powered voice dictation tool using OpenAI Whisper. Transcribes speech to text and automatically pastes it at your cursor position.

## Features

- **Offline transcription** — all processing happens locally using faster-whisper
- **GPU acceleration** — CUDA support for fast transcription
- **Multi-language** — auto-detection or manual selection (Ukrainian, Russian, English)
- **System tray** — visual feedback for recording/transcribing states
- **Custom vocabulary** — improve accuracy with domain-specific terms
- **Hotkey activation** — toggle recording with a single keypress

## Architecture

```
┌─────────────┐    Unix Socket    ┌─────────────────┐
│   Toggle    │ ───────────────▶  │     Daemon      │
│  (hotkey)   │                   │                 │
└─────────────┘                   │  ┌───────────┐  │
                                  │  │  Whisper  │  │
                                  │  │   Model   │  │
                                  │  └───────────┘  │
                                  │        ↓        │
                                  │  ┌───────────┐  │
                                  │  │ Clipboard │  │
                                  │  │  + Paste  │  │
                                  │  └───────────┘  │
                                  └─────────────────┘
```

## Requirements

### System Dependencies

| Component | Purpose |
|-----------|---------|
| Python 3.10+ | Runtime |
| PyQt6 | System tray GUI |
| faster-whisper | Speech recognition |
| sounddevice | Audio capture |
| wl-clipboard | Clipboard access (Wayland) |
| ydotool | Key simulation (Wayland) |

### Hardware

- **Minimum**: 4GB RAM, any modern CPU (slow transcription)
- **Recommended**: NVIDIA GPU with 4GB+ VRAM for real-time transcription

## Installation

### NixOS / Nix

```bash
# Add to flake inputs
inputs.magtype.url = "github:OleksandrCEO/MagType";

# Enable module
services.magtype.enable = true;

# Or run directly
nix run github:OleksandrCEO/MagType -- --daemon
```

### CachyOS / Arch Linux

```bash
# Install dependencies
sudo pacman -S python python-pip python-pyqt6 portaudio \
    wl-clipboard ydotool ffmpeg

# For CUDA support
sudo pacman -S cuda cudnn

# Install Python packages
pip install --user faster-whisper sounddevice soundfile numpy

# Clone and run
git clone https://github.com/OleksandrCEO/MagType
cd magtype
python main.py --daemon
```

**Note**: Start ydotoold service:
```bash
sudo systemctl enable --now ydotool
# Add user to input group
sudo usermod -aG input $USER
```

### Ubuntu / Debian

```bash
# System dependencies
sudo apt update
sudo apt install python3 python3-pip python3-pyqt6 portaudio19-dev \
    wl-clipboard ffmpeg libsndfile1

# ydotool (may need to build from source on older Ubuntu)
sudo apt install ydotool  # Ubuntu 23.04+

# For CUDA (Ubuntu with NVIDIA drivers)
# Follow: https://developer.nvidia.com/cuda-downloads

# Python packages
pip3 install --user faster-whisper sounddevice soundfile numpy

# Clone and run
git clone https://github.com/OleksandrCEO/MagType
cd MagType
python3 main.py --daemon
```

### macOS

```bash
# Install Homebrew dependencies
brew install python portaudio ffmpeg

# Install Python packages
pip3 install faster-whisper sounddevice soundfile numpy pyqt6

# Clone repository
git clone https://github.com/OleksandrCEO/MagType
cd MagType

# Run (CPU mode, macOS typically doesn't have CUDA)
python3 main.py --daemon --device cpu
```

**Note**: Grant accessibility permissions for keyboard simulation (see Cross-Platform Support section).

## Usage

### Start Daemon

```bash
# With auto language detection (default)
python main.py --daemon

# Force specific language
python main.py --daemon --lang uk

# Use specific model
python main.py --daemon --model medium

# CPU-only mode
python main.py --daemon --device cpu
```

### Toggle Recording

```bash
python main.py --toggle
```

### Hotkey Setup

Bind `magtype --toggle` to your preferred hotkey in your desktop environment.

**Example for Hyprland** (`~/.config/hypr/hyprland.conf`):
```
bind = , F9, exec, magtype --toggle
```

**Example for GNOME**:
```bash
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \
    "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/magtype/']"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/magtype/ \
    name 'MagType Toggle'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/magtype/ \
    command 'python /path/to/magtype/main.py --toggle'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/magtype/ \
    binding 'F9'
```

## Configuration

### Custom Vocabulary

Create `~/.config/magtype/vocabulary.txt` with domain-specific terms (one per line):

```
Kubernetes
PostgreSQL
OAuth2
```

This improves transcription accuracy for technical terms.

### Available Models

| Model | VRAM | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~1GB | Fastest | Low |
| base | ~1GB | Fast | Basic |
| small | ~2GB | Good | Good |
| medium | ~5GB | Moderate | High |
| large-v3 | ~10GB | Slow | Best |

## Project Structure

```
magtype/
├── main.py              # Entry point and daemon logic
├── core/
│   ├── __init__.py
│   ├── clipboard.py     # Cross-platform clipboard controller
│   └── icons.py         # Cross-platform icon management
├── icons/
│   ├── idle.svg
│   ├── listening.svg
│   └── transcribing.svg
├── docs/
│   └── INSTALL.md       # Detailed installation guides
└── flake.nix            # NixOS flake
```

## Cross-Platform Support

MagType automatically detects your platform and uses appropriate tools:

| Platform | Clipboard | Key Simulation |
|----------|-----------|----------------|
| Linux (Wayland) | wl-copy | ydotool |
| Linux (X11) | xclip | xdotool |
| macOS | pbcopy | osascript |

### X11 Linux

Install X11 tools instead of Wayland ones:
```bash
# Arch/CachyOS
sudo pacman -S xclip xdotool

# Ubuntu/Debian
sudo apt install xclip xdotool
```

### macOS Permissions

macOS requires accessibility permissions for keyboard simulation:
1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Accessibility**
3. Add Terminal (or Python) to the allowed list

## Troubleshooting

### "CUDA out of memory"

Use a smaller model or CPU mode:
```bash
python main.py --daemon --model small
python main.py --daemon --device cpu
```

### ydotool permission denied

```bash
sudo usermod -aG input $USER
# Log out and back in
```

### No audio captured

Check microphone permissions and default device:
```bash
# List audio devices
python -c "import sounddevice; print(sounddevice.query_devices())"
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue first to discuss proposed changes.
