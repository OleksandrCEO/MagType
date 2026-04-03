{
  description = "MagType - Local AI Dictation Environment (CUDA)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };

      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        glib

        # Графіка та Qt6
        libGL
        libxkbcommon
        fontconfig
        freetype
        wayland

        # Системні модулі Qt6 (необхідні для PyQt6)
        qt6.qtbase
        qt6.qtsvg
        qt6.qtwayland

        # X11 залежності (про всяк випадок)
        xorg.libX11
        xorg.libXcursor
        xorg.libXext
        xorg.libXrender
        xorg.libXi
        xorg.libxcb

        # Audio
        portaudio
        libsndfile

        # CUDA
        cudaPackages.cudatoolkit
        cudaPackages.cudnn
        cudaPackages.libcublas
      ];
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          python3
          python3Packages.pyqt6

          portaudio
          wl-clipboard
          ydotool
          libnotify
          ffmpeg

          qt6.qtbase
          qt6.qtsvg
        ];

        LD_LIBRARY_PATH = "${pkgs.lib.makeLibraryPath runtimeLibs}:/run/opengl-driver/lib";

        shellHook = ''
          if [ ! -d ".venv" ]; then
            python3 -m venv .venv
          fi
          source .venv/bin/activate

          # Шлях до плагінів Qt (важливо для SVG та Wayland)
          export QT_PLUGIN_PATH="${pkgs.qt6.qtbase}/${pkgs.qt6.qtbase.qtPluginPrefix}:${pkgs.qt6.qtsvg}/${pkgs.qt6.qtbase.qtPluginPrefix}"
          export QT_QPA_PLATFORM=wayland

          echo "🎙️ MagType CUDA Environment Loaded!"
        '';
      };
    };
}