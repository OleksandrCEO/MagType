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

      # Essential libraries for CUDA, Qt6, and UI rendering
      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        glib
        libGL
        libxkbcommon
        fontconfig
        freetype
        wayland
        # Qt6 modules
        qt6.qtbase
        qt6.qtsvg
        qt6.qtwayland
        # Audio processing
        portaudio
        libsndfile
        # NVIDIA CUDA stack
        cudaPackages.cudatoolkit
        cudaPackages.cudnn
        cudaPackages.libcublas
      ];

      # Python environment with required ML and UI packages
      pythonEnv = pkgs.python3.withPackages (ps: with ps; [
        pyqt6
        numpy
        sounddevice
        soundfile
        faster-whisper
      ]);

      # Application dependencies available in PATH
      binPath = with pkgs; [
        wl-clipboard
        ydotool
        libnotify
        ffmpeg
      ];

    in
    {
      packages.${system}.default = pkgs.stdenv.mkDerivation {
        pname = "magtype";
        version = "1.0.0";
        src = ./.;

        nativeBuildInputs = [ pkgs.makeWrapper ];

        installPhase = ''
          mkdir -p $out/bin $out/share/magtype $out/share/icons/magtype

          # Deploy source code and assets
          cp main.py $out/share/magtype/
          cp -r icons/* $out/share/icons/magtype/ || true

          # Create a wrapper to handle environment variables and library paths
          makeWrapper ${pythonEnv}/bin/python $out/bin/magtype \
            --add-flags "$out/share/magtype/main.py" \
            --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath runtimeLibs}:/run/opengl-driver/lib" \
            --set QT_QPA_PLATFORM "wayland;xcb" \
            --set QT_PLUGIN_PATH "${pkgs.qt6.qtbase}/${pkgs.qt6.qtbase.qtPluginPrefix}" \
            --set NIXOS_OZONE_WL "1" \
            --prefix PATH : "${pkgs.lib.makeBinPath binPath}" \
            --set MAGTYPE_ICONS_PATH "$out/share/icons/magtype"
        '';
      };

      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          pythonEnv
        ] ++ binPath;

        # Ensure CUDA and OpenGL libraries are visible during development
        LD_LIBRARY_PATH = "${pkgs.lib.makeLibraryPath runtimeLibs}:/run/opengl-driver/lib";

        shellHook = ''
          export QT_QPA_PLATFORM=wayland
          export MAGTYPE_ICONS_PATH="./icons"
          echo "🎙️ MagType (CUDA) dev environment loaded"
        '';
      };
    };
}