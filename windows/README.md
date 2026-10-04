# BESTthemes for Windows — developer notes

User documentation (features, download, installation) is in the [main README](../README.md).

The Windows app is written with Qt (PySide6) and reuses the shared engine of the Linux version
(`bestthemes/core`: palettes, wallpaper generator, animated scenes, photo gallery, safe archive
extraction, xfce-look.org API).

## Principles

- **No admin rights, no system files.** Only per-user settings are changed (HKCU registry,
  `SystemParametersInfo`, `desktop.ini` of the user's own folders).
- **Everything is undoable.** `core/backup.py` snapshots every tracked registry value and state
  before each change; the original state is saved on first launch.

## Run & test

```sh
pip install -r windows/requirements.txt
python windows/launcher.py                                  # on Linux/macOS: demo mode (simulated registry)
python -m unittest discover -s windows/tests -t windows     # ⚠️ on Windows this changes real settings
python windows/launcher.py --selftest                       # opens every page, exit code 0 = OK
python windows/launcher.py --live --window                  # animated wallpaper in a normal window
```

## Build

On Windows with Python 3.12 and Inno Setup 6, double-click `packaging\build.bat`. It produces:

- `dist\BESTthemes-Setup-x.y.z.exe` — per-user installer (`installer.iss`)
- `dist\BESTthemes-Portable-x.y.z.exe` — single-file portable build (`bestthemes_win_portable.spec`)

GitHub Actions (`.github/workflows/windows.yml`) does the same on every push and attaches both
files to the release when a `v*` tag is pushed.

## Animated wallpaper

`live_player.py` runs as a separate process (`BESTthemes.exe --live`) so it keeps running after the
app is closed; it is started at logon through the `HKCU\…\Run` key. It attaches its window to the
Explorer `WorkerW` layer behind the desktop icons (with the Windows 11 24H2 variant where `WorkerW`
is a child of `Progman`), re-reads `live.json` every second, pauses when a maximized or full-screen
window covers a monitor, and restarts itself if Explorer restarts.
