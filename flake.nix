{
  description = "MagType - Local AI Dictation Environment";

  inputs = {
    # Using the stable 25.11 branch to match the system OS
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # Define the Python environment with required packages
      pythonEnv = pkgs.python3.withPackages (ps: with ps; [
        numpy
        sounddevice
        soundfile
        faster-whisper
      ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        # System-level dependencies required for the script to run
        buildInputs = with pkgs; [
          pythonEnv
          portaudio     # Required underlying C library for sounddevice
          wtype         # Wayland keystroke simulator
          libnotify     # Required for notify-send utility
          ffmpeg        # Preparing for the future MP4 transcription task
        ];

        # Shell hook to verify the environment is loaded
        shellHook = ''
          echo "🎙️ MagType development environment loaded!"
          echo "Python: $(python --version)"
          echo "Available tools: wtype, notify-send, ffmpeg"
        '';
      };
    };
}