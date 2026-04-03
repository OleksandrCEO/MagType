import os
import sys
import socket
import threading
import subprocess
import argparse
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

# --- Constants ---
SOCKET_PATH = "/tmp/magtype.sock"
AUDIO_SAMPLE_RATE = 16000
MODEL_SIZE = "base"  # Change to "large-v3" later, using "base" for quick testing


class SystemNotifier:
    """Handles system notifications via KDE/Linux native notify-send."""

    @staticmethod
    def notify(title: str, message: str, icon: str = "dialog-information"):
        # We use subprocess to call the system notification tool
        try:
            subprocess.run([
                "notify-send",
                "-a", "MagType",
                "-i", icon,
                "-t", "2000",  # Disappear after 2 seconds
                title,
                message
            ], check=True)
        except Exception as e:
            print(f"Failed to send notification: {e}")


class KeyboardController:
    """Handles interaction with Wayland via wtype."""

    @staticmethod
    def type_text(text: str):
        if not text:
            return

        try:
            # Using wtype to simulate keyboard input on Wayland
            subprocess.run(["wtype", text], check=True)
        except FileNotFoundError:
            SystemNotifier.notify("Error", "wtype is not installed!", "dialog-error")
        except Exception as e:
            SystemNotifier.notify("Error", f"Typing failed: {e}", "dialog-error")


class AudioRecorder:
    """Handles non-blocking audio recording."""

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_data = []
        self.stream = None

    def _callback(self, indata, frames, time, status):
        """Called for each audio block by sounddevice."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        if self.is_recording:
            self.audio_data.append(indata.copy())

    def start(self):
        self.audio_data = []
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self._callback
        )
        self.stream.start()

    def stop(self) -> str:
        """Stops recording and returns the path to the temporary WAV file."""
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.audio_data:
            return ""

        # Flatten the audio data array
        recording = np.concatenate(self.audio_data, axis=0)

        # Save to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        sf.write(temp_file.name, recording, self.sample_rate)
        return temp_file.name


class MagTypeDaemon:
    """Main daemon process handling state and IPC."""

    def __init__(self):
        self.recorder = AudioRecorder()
        self.notifier = SystemNotifier()
        self.keyboard = KeyboardController()

        # Load the model during initialization so it's ready instantly
        self.notifier.notify("MagType", "Loading AI Model...", "system-run")
        # device="cuda" for NVIDIA GPU, compute_type="float16" for better performance
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        self.notifier.notify("MagType", "Daemon Ready", "microphone")

        self.is_recording_state = False

    def handle_toggle(self):
        """Toggles between recording and transcribing states."""
        if not self.is_recording_state:
            self.is_recording_state = True
            self.notifier.notify("MagType", "Listening...", "media-record")
            self.recorder.start()
        else:
            self.is_recording_state = False
            self.notifier.notify("MagType", "Transcribing...", "media-playback-start")

            # Stop recording and get the audio file
            audio_path = self.recorder.stop()

            if audio_path:
                # Transcribe in a separate thread to not block the daemon
                threading.Thread(target=self._transcribe_and_type, args=(audio_path,)).start()

    def _transcribe_and_type(self, audio_path: str):
        try:
            segments, info = self.model.transcribe(audio_path, beam_size=5)
            text = "".join([segment.text for segment in segments]).strip()

            # Add a trailing space for convenience when dictating multiple sentences
            if text:
                self.keyboard.type_text(text + " ")
                self.notifier.notify("MagType", "Done", "emblem-default")
            else:
                self.notifier.notify("MagType", "No speech detected", "dialog-warning")

        except Exception as e:
            self.notifier.notify("Error", f"Transcription failed: {e}", "dialog-error")
        finally:
            # Clean up the temporary file
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def start_server(self):
        """Starts the Unix domain socket server."""
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(1)

        print(f"Daemon listening on {SOCKET_PATH}...")

        while True:
            conn, addr = server.accept()
            data = conn.recv(1024).decode('utf-8')
            if data == "TOGGLE":
                self.handle_toggle()
            conn.close()


def send_toggle_command():
    """Client function to trigger the daemon."""
    if not os.path.exists(SOCKET_PATH):
        print("Daemon is not running!")
        return

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(b"TOGGLE")
    except Exception as e:
        print(f"Failed to communicate with daemon: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MagType - Local AI Dictation")
    parser.add_argument("--daemon", action="store_true", help="Start the background daemon")
    parser.add_argument("--toggle", action="store_true", help="Toggle recording state")

    args = parser.parse_args()

    if args.daemon:
        daemon = MagTypeDaemon()
        daemon.start_server()
    elif args.toggle:
        send_toggle_command()
    else:
        parser.print_help()