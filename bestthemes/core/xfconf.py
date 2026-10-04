"""Petite enveloppe autour de xfconf-query."""
import shutil
import subprocess

XFCONF = shutil.which("xfconf-query") or "xfconf-query"


def _run(args):
    try:
        r = subprocess.run([XFCONF, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def available():
    return shutil.which("xfconf-query") is not None


def get(channel, prop, default=None):
    out = _run(["-c", channel, "-p", prop])
    if out is None:
        return default
    out = out.rstrip("\n")
    if out.startswith("Value is an array"):
        return [line for line in out.splitlines()[2:]]
    return out


def get_int(channel, prop, default=0):
    try:
        return int(float(get(channel, prop)))
    except (TypeError, ValueError):
        return default


def get_bool(channel, prop, default=False):
    v = get(channel, prop)
    if v is None:
        return default
    return v.strip().lower() == "true"


def _type_of(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    return "string"


def _fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def set(channel, prop, value, vtype=None):
    """Définit une propriété en la créant si nécessaire."""
    vtype = vtype or _type_of(value)
    if _run(["-c", channel, "-p", prop, "-s", _fmt(value)]) is not None:
        return True
    return _run(["-c", channel, "-p", prop, "-n", "-t", vtype, "-s", _fmt(value)]) is not None


def reset(channel, prop):
    return _run(["-c", channel, "-p", prop, "-r"]) is not None


def list_props(channel, prefix=""):
    out = _run(["-c", channel, "-l"] + (["-p", prefix] if prefix else []))
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def list_values(channel, prefix=""):
    """Retourne {prop: valeur} pour les propriétés scalaires."""
    out = _run(["-c", channel, "-l", "-v"] + (["-p", prefix] if prefix else []))
    result = {}
    if not out:
        return result
    for line in out.splitlines():
        parts = line.split(None, 1)
        if not parts:
            continue
        val = parts[1] if len(parts) > 1 else ""
        if val == "<<UNSUPPORTED>>":
            continue
        result[parts[0]] = val
    return result


def set_array(channel, prop, values, vtype="double"):
    """Définit une propriété tableau (ex. background-rgba)."""
    args = ["-c", channel, "-p", prop, "-n", "--force-array"]
    for v in values:
        args += ["-t", vtype, "-s", _fmt(v)]
    if _run(args) is not None:
        return True
    _run(["-c", channel, "-p", prop, "-r"])
    return _run(args) is not None
