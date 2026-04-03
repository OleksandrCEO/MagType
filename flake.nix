{
  description = "MagType - Local AI Dictation Environment (CUDA)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      # Allow unfree packages (required for NVIDIA/CUDA libraries)
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };

      # System libraries needed by pre-compiled PyPI wheels at runtime
      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        glib

        # CUDA Core
        cudaPackages.cudatoolkit
        cudaPackages.cudnn
        cudaPackages.libcublas
        cudaPackages.libcufft

        # UI libraries for pystray loaded via ctypes
        gtk3
        libappindicator-gtk3
      ];

    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          # Base Python (no Nix packages injected, pure environment)
          python3

          # System tools
          portaudio
          wl-clipboard
          ydotool
          libnotify
          ffmpeg
        ];

        # Tell Python/PyPI wheels where to find CUDA and standard C libraries.
        # /run/opengl-driver/lib contains libcuda.so directly from your host NVIDIA driver!
        LD_LIBRARY_PATH = "${pkgs.lib.makeLibraryPath runtimeLibs}:/run/opengl-driver/lib";

        shellHook = ''
          # Auto-create standard virtual environment if missing
          if [ ! -d ".venv" ]; then
            echo "Creating Python virtual environment (.venv)..."
            python3 -m venv .venv
          fi

          # Activate venv
          source .venv/bin/activate

          echo "🎙️ MagType CUDA Environment Loaded!"
          echo "⚠️  RUN ONCE: pip install numpy sounddevice soundfile faster-whisper pystray pillow"
        '';
      };
    };
}