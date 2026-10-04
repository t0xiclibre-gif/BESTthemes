"""Point d'entrée de l'exécutable Windows (PyInstaller)."""
import sys
from pathlib import Path


def _open_log():
    """Journal BESTthemes-journal.txt à côté du .exe (pratique sur une clé USB),
    sinon dans %LOCALAPPDATA%\\BESTthemes. L'exécutable n'a pas de console :
    sans ce fichier, les erreurs seraient invisibles."""
    import os
    candidates = [Path(sys.executable).resolve().parent,
                  Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "BESTthemes"]
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            name = "BESTthemes-fond-anime-journal.txt" if "--live" in sys.argv else "BESTthemes-journal.txt"
            return open(d / name, "w", encoding="utf-8", buffering=1)
        except OSError:
            continue
    return None


if getattr(sys, "frozen", False):
    _log = _open_log()
    if _log:
        import datetime
        import faulthandler
        import platform
        sys.stdout = sys.stderr = _log
        print(f"BESTthemes — {datetime.datetime.now():%Y-%m-%d %H:%M:%S} — "
              f"{platform.platform()} — Python {platform.python_version()}")
        faulthandler.enable(_log)

        def _hook(t, e, tb):
            import traceback
            traceback.print_exception(t, e, tb)
        sys.excepthook = _hook
else:
    # Lancement depuis les sources : rend visibles `bestthemes` (racine) et `bestthemes_win`.
    _here = Path(__file__).resolve().parent
    for p in (_here.parent, _here):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

if "--live" in sys.argv:
    # Lecteur du fond d'écran animé (processus séparé, lancé par BESTthemes ou à la connexion)
    from bestthemes_win.live_player import main  # noqa: E402
else:
    from bestthemes_win.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
