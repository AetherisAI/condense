Condense desktop test kit
==========================

1. Copy this whole folder (or the .tar.gz) onto the test machine.
2. Run:  ./setup-test.sh
3. Launch "Condense" from your app menu, or run ~/.local/bin/Condense.AppImage directly.
4. First-run wizard -> "Run locally" -> downloads ~750MB (embedder + model, both public;
   the engine itself ships inside this kit, no download needed) -> paste an LLM key or Skip
   (without a key, Ask/chat fails but Find/search still works).

Uninstall:  ./uninstall-test.sh

Requirements: Ubuntu 22.04+ (glibc-based Linux) with webkit2gtk-4.1 runtime libraries --
present by default on stock Ubuntu/GNOME desktops. No sudo needed for setup or uninstall.
If the AppImage won't launch (missing FUSE/libfuse2), run it with --appimage-extract-and-run.
