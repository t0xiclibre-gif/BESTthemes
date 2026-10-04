"""Applications de personnalisation installées en un clic via winget (sans terminal visible)."""
import shutil

from .. import winplat as wp

TOOLS = [
    {"id": "CharlesMilette.TranslucentTB", "name": "TranslucentTB",
     "desc": "Rend la barre des tâches transparente ou floutée. Indispensable pour un look macOS.",
     "url": "https://github.com/TranslucentTB/TranslucentTB", "tag": "Barre des tâches"},
    {"id": "WinStep.Nexus", "name": "Nexus Dock",
     "desc": "Un dock façon macOS en bas de l'écran, avec effet de zoom. Version gratuite.",
     "url": "https://www.winstep.net/nexus.htm", "tag": "Dock"},
    {"id": "RamenSoftware.Windhawk", "name": "Windhawk",
     "desc": "Des centaines de « mods » sûrs et réversibles : coins arrondis, barre des tâches "
             "personnalisée, animations… Le plus puissant pour aller plus loin.",
     "url": "https://windhawk.net", "tag": "Avancé"},
    {"id": "rocksdanister.LivelyWallpaper", "name": "Lively Wallpaper",
     "desc": "Pour aller plus loin que les fonds animés de BESTthemes : vidéos, pages web et "
             "fonds interactifs en fond d'écran. Gratuit et open source.",
     "url": "https://www.rocksdanister.com/lively/", "tag": "Fonds animés"},
    {"id": "Rainmeter.Rainmeter", "name": "Rainmeter",
     "desc": "Widgets de bureau : horloges, météo, visualiseurs de musique…",
     "url": "https://www.rainmeter.net", "tag": "Widgets"},
    {"id": "Flow-Launcher.Flow-Launcher", "name": "Flow Launcher",
     "desc": "Une recherche rapide façon Spotlight (macOS) : Alt + Espace.",
     "url": "https://www.flowlauncher.com", "tag": "Recherche"},
    {"id": "Microsoft.PowerToys", "name": "PowerToys",
     "desc": "Les outils officiels de Microsoft : FancyZones, sélecteur de couleur, recherche…",
     "url": "https://learn.microsoft.com/windows/powertoys/", "tag": "Microsoft"},
    {"id": "valinet.ExplorerPatcher", "name": "ExplorerPatcher",
     "desc": "Retrouver la barre des tâches et le menu Démarrer de Windows 10 sur Windows 11.",
     "url": "https://github.com/valinet/ExplorerPatcher", "tag": "Windows 11"},
    {"id": "StartIsBack.StartAllBack", "name": "StartAllBack",
     "desc": "Menu Démarrer et barre des tâches classiques très personnalisables (payant, essai gratuit).",
     "url": "https://www.startallback.com", "tag": "Payant"},
]


def winget():
    return shutil.which("winget") if wp.IS_WINDOWS else None


def available():
    return winget() is not None


def is_installed(tool_id):
    if not available():
        return False
    try:
        r = wp.run_hidden([winget(), "list", "--id", tool_id, "-e",
                           "--accept-source-agreements", "--disable-interactivity"], timeout=60)
    except Exception:  # noqa: BLE001
        return False
    return r.returncode == 0 and tool_id.lower().encode() in (r.stdout or b"").lower()


def install(tool_id):
    """Installe via winget. Windows peut afficher sa propre fenêtre d'autorisation (UAC)."""
    if not available():
        return False, "winget est introuvable : installez « App Installer » depuis le Microsoft Store."
    r = wp.run_hidden([winget(), "install", "--id", tool_id, "-e", "--silent",
                       "--accept-package-agreements", "--accept-source-agreements",
                       "--disable-interactivity"], timeout=1800)
    if r.returncode == 0:
        return True, ""
    out = (r.stdout or b"").decode(errors="replace") + (r.stderr or b"").decode(errors="replace")
    return False, out.strip()[-500:] or f"Erreur {r.returncode}"


def uninstall(tool_id):
    if not available():
        return False, "winget est introuvable."
    r = wp.run_hidden([winget(), "uninstall", "--id", tool_id, "-e", "--silent",
                       "--disable-interactivity"], timeout=900)
    return r.returncode == 0, (r.stderr or b"").decode(errors="replace")[-300:]
