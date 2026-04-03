import os
import sys
import socket
import threading
import subprocess
import argparse
import tempfile
import signal
from pathlib import Path

# --- Constants ---
SOCKET_PATH = "/tmp/magtype.sock"
AUDIO_SAMPLE_RATE = 16000


class ClipboardController:
    """Handles Wayland clipboard operations and virtual key injection."""

    @staticmethod
    def paste_text(text: str):
        if not text:
            return

        try:
            # Copy text to Wayland clipboard
            subprocess.run(["wl-copy", text], check=True)
            try:
                # Trigger Ctrl+V using ydotool (requires ydotoold running)
                # Keycodes: 29=Ctrl, 47=V. Format: code:state (1=pressed, 0=released)
                subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True)
            except Exception:
                # Silently fail if ydotool is not configured or daemon is missing
                pass

        except Exception as e:
            print(f"Clipboard operation failed: {e}")


class TrayIconManager:
    """Manages the system tray icon using PyQt6 with Wayland support."""

    def __init__(self):
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
        from PyQt6.QtGui import QIcon
        from PyQt6.QtCore import QTimer

        self.QIcon = QIcon

        # Initialize or retrieve existing Qt Application
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Signal processing hack: QTimer forces the Python interpreter to wake up
        # periodically, allowing it to catch SIGINT (Ctrl+C).
        self.timer = QTimer()
        self.timer.start(500)
        self.timer.timeout.connect(lambda: None)

        # Icon Path Resolution: Prioritize Env Var (Nix), then Config, then local
        env_icons = os.environ.get("MAGTYPE_ICONS_PATH")
        user_icons = Path.home() / ".config" / "magtype" / "icons"

        if env_icons and os.path.exists(env_icons):
            self.icons_dir = env_icons
        elif user_icons.exists():
            self.icons_dir = str(user_icons)
        else:
            self.icons_dir = str(Path(__file__).parent / "icons")
            os.makedirs(self.icons_dir, exist_ok=True)

        # Pre-load icons to avoid disk I/O during state transitions
        self.icons = {
            "idle": self._get_svg_icon("idle.svg", "#888888"),
            "listening": self._get_svg_icon("listening.svg", "#ff4444"),
            "transcribing": self._get_svg_icon("transcribing.svg", "#44ff44")
        }

        # Setup System Tray and Context Menu
        self.tray = QSystemTrayIcon(self.icons["idle"])
        self.menu = QMenu()

        exit_action = self.menu.addAction("Exit MagType")
        exit_action.triggered.connect(self.stop_all)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def _get_svg_icon(self, filename: str, color: str):
        """Generates a default SVG icon if the file is missing."""
        file_path = os.path.join(self.icons_dir, filename)
        if not os.path.exists(file_path):
            svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
            <svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <circle cx="32" cy="32" r="24" fill="{color}" />
            </svg>"""
            try:
                with open(file_path, "w") as f:
                    f.write(svg_content)
            except IOError:
                # Fallback if directory is read-only (Nix Store)
                pass
        return self.QIcon(file_path)

    def set_state_idle(self):
        self.tray.setIcon(self.icons["idle"])

    def set_state_listening(self):
        self.tray.setIcon(self.icons["listening"])

    def set_state_transcribing(self):
        self.tray.setIcon(self.icons["transcribing"])

    def stop_all(self):
        """Graceful shutdown logic."""
        print("\n[+] Shutting down...")
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        os._exit(0)

    def run(self):
        self.app.exec()


class AudioRecorder:
    """Handles non-blocking audio capture using sounddevice."""

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        import sounddevice as sd
        import numpy as np
        self.sd = sd
        self.np = np
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_data = []
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if self.is_recording:
            self.audio_data.append(self.np.copy(indata))

    def start(self):
        self.audio_data = []
        self.is_recording = True
        self.stream = self.sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self._callback
        )
        self.stream.start()

    def stop(self) -> str:
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.audio_data:
            return ""

        import soundfile as sf
        recording = self.np.concatenate(self.audio_data, axis=0)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        sf.write(temp_file.name, recording, self.sample_rate)
        return temp_file.name


class MagTypeDaemon:
    """Core logic: handles AI models, recording states, and IPC commands."""

    def __init__(self, config: argparse.Namespace, tray_manager: TrayIconManager):
        from faster_whisper import WhisperModel

        self.recorder = AudioRecorder()
        self.clipboard = ClipboardController()
        self.tray = tray_manager
        self.is_recording_state = False
        self.config = config

        # Persistent storage for user vocabulary
        self.config_dir = Path.home() / ".config" / "magtype"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.vocab_file = self.config_dir / "vocabulary.txt"
        self.vocabulary = self._load_vocabulary()

        print(f"Loading Whisper '{self.config.model}' on {self.config.device.upper()}...")
        compute_type = "float16" if self.config.device == "cuda" else "int8"
        self.model = WhisperModel(
            self.config.model,
            device=self.config.device,
            compute_type=compute_type
        )
        print("Daemon ready. Listening for IPC toggle commands.")

    def _load_vocabulary(self) -> str:
        if not self.vocab_file.exists():
            return ""
        return self.vocab_file.read_text(encoding="utf-8").replace("\n", ", ")

    def handle_toggle(self):
        """Main state machine for recording."""
        if not self.is_recording_state:
            self.is_recording_state = True
            self.tray.set_state_listening()
            self.recorder.start()
        else:
            self.is_recording_state = False
            self.tray.set_state_transcribing()

            audio_path = self.recorder.stop()
            if audio_path:
                threading.Thread(target=self._transcribe_and_type, args=(audio_path,), daemon=True).start()
            else:
                self.tray.set_state_idle()

    def _transcribe_and_type(self, audio_path: str):
        """Worker thread for transcription."""
        try:
            segments, _ = self.model.transcribe(
                audio_path,
                beam_size=5,
                language=self.config.lang,
                initial_prompt=self.vocabulary if self.vocabulary else None
            )
            text = " ".join([segment.text.strip() for segment in segments]).strip()

            if text:
                self.clipboard.paste_text(text + " ")

        except Exception as e:
            print(f"Transcription failed: {e}")
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            # Reload vocabulary in case the user updated the file
            self.vocabulary = self._load_vocabulary()
            self.tray.set_state_idle()

    def start_socket_server(self):
        """Unix Socket Server for receiving commands from the client instance."""
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(5)

        while True:
            try:
                conn, _ = server.accept()
                data = conn.recv(1024).decode('utf-8')
                if data == "TOGGLE":
                    self.handle_toggle()
                conn.close()
            except Exception:
                pass


def send_toggle_command():
    """Client-side: sends a toggle signal to the running daemon."""
    if not os.path.exists(SOCKET_PATH):
        print("Error: MagType daemon is not running.")
        sys.exit(1)

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(b"TOGGLE")
    except Exception as e:
        print(f"IPC Error: {e}")
    finally:
        client.close()


def shutdown_handler(signum, frame):
    """Cleanly handles termination signals."""
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    os._exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MagType - Local AI Dictation")
    parser.add_argument("--daemon", action="store_true", help="Start the background service")
    parser.add_argument("--toggle", action="store_true", help="Toggle dictation state")
    parser.add_argument("--lang", type=str, default="uk", help="Language code (uk, en, etc.)")
    parser.add_argument("--model", type=str, default="large-v3", help="Whisper model size")
    parser.add_argument("--device", type=str, default="cuda", choices=["cpu", "cuda"], help="Compute device")

    args = parser.parse_args()

    if args.daemon:
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        tray = TrayIconManager()
        daemon = MagTypeDaemon(args, tray)

        # Run IPC server in a separate thread
        ipc_thread = threading.Thread(target=daemon.start_socket_server, daemon=True)
        ipc_thread.start()

        # Qt Main Loop
        tray.run()

    elif args.toggle:
        send_toggle_command()
    else:
        parser.print_help()