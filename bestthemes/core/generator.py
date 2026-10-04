"""Générateur de thèmes : GTK 3 + bordures xfwm4 + dock Plank à partir d'une palette."""
import json
import math
import re
import shutil
import unicodedata
from pathlib import Path
from string import Template

import cairo

from . import colors as C
from . import paths

PREFIX = "BT-"
_TEMPLATES = paths.DATA_DIR / "templates"

BUTTON_STYLES = {
    "macos": "Ronds colorés (macOS)",
    "windows": "Carrés plats (Windows)",
    "minimal": "Minimalistes",
    "circles": "Cercles d'accent",
}


def load_palettes():
    data = json.loads((paths.DATA_DIR / "palettes.json").read_text())
    return data["palettes"]


def palette(name):
    for p in load_palettes():
        if p["id"] == name or p["name"] == name:
            return dict(p)
    raise KeyError(name)


def slug(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    return s or "Perso"


def theme_name(p):
    return PREFIX + slug(p["name"])


def derive(p):
    """Calcule toutes les couleurs dérivées d'une palette de base."""
    bg = p["bg"]
    fg = p.get("fg") or C.readable_on(bg, "#eeeeee", "#2e2e2e")
    dark = C.is_dark(bg)
    accent = p["accent"]
    surface = p.get("surface") or C.shade(bg, 0.06)
    base = p.get("base") or (C.darken(bg, 0.12) if dark else C.lighten(bg, 0.6))
    header = p.get("header") or (C.darken(bg, 0.18) if dark else C.darken(bg, 0.04))
    red = p.get("red", "#e5484d")
    yellow = p.get("yellow", "#f5a524")
    green = p.get("green", "#30a46c")
    border = p.get("border") or C.mix(bg, fg, 0.14)
    button = p.get("button") or (C.lighten(bg, 0.07) if dark else C.lighten(bg, 0.45))
    panel = p.get("panel") or header
    v = {
        "name": p["name"],
        "dark": dark,
        "dark_suffix": "-dark" if dark else "",
        "bg": bg,
        "fg": fg,
        "fg_dim": C.mix(fg, bg, 0.42),
        "base": base,
        "base_hover": C.mix(base, fg, 0.06),
        "surface": surface,
        "header": header,
        "sidebar": p.get("sidebar") or C.mix(bg, header, 0.5),
        "border": border,
        "accent": accent,
        "accent_fg": p.get("accent_fg") or C.readable_on(accent),
        "accent_hover": C.shade(accent, 0.12),
        "accent_dark": C.darken(accent, 0.18),
        "accent_alpha": C.rgba(accent, 0.3),
        "link": p.get("link") or (C.lighten(accent, 0.25) if dark else C.darken(accent, 0.1)),
        "button": button,
        "button_hover": C.shade(button, 0.07),
        "button_active": C.shade(button, 0.14),
        "button_disabled": C.mix(button, bg, 0.5),
        "button_border": C.mix(button, fg, 0.12),
        "red": red, "red_dark": C.darken(red, 0.2), "red_hover": C.shade(red, 0.1),
        "red_fg": C.readable_on(red),
        "yellow": yellow, "yellow_fg": C.readable_on(yellow),
        "green": green,
        "tooltip": p.get("tooltip") or ("#101010" if not dark else C.lighten(surface, 0.08)),
        "tooltip_fg": "#f5f5f5" if not dark else fg,
        "scroll": C.mix(base, fg, 0.3),
        "scroll_hover": C.mix(base, fg, 0.45),
        "trough": C.mix(bg, fg, 0.15),
        "switch_knob": "#ffffff" if not dark else C.mix(fg, bg, 0.1),
        "lighter_knob": C.lighten(accent, 0.85),
        "shadow": "rgba(0,0,0,0.35)" if dark else "rgba(0,0,0,0.15)",
        "osd": C.rgba(C.darken(bg, 0.5) if dark else "#202020", 0.9),
        "osd_fg": "#f0f0f0",
        "panel": panel,
        "panel_fg": p.get("panel_fg") or C.readable_on(panel, "#eeeeee", "#2a2a2a"),
        "panel_hover": C.shade(panel, 0.1),
        "panel_active": C.shade(panel, 0.18),
        "radius": f"{int(p.get('radius', 8))}px",
        "radius_small": f"{max(0, int(p.get('radius', 8)) - 2)}px",
        "radius_check": f"{min(5, max(0, int(p.get('radius', 8)) // 2))}px",
        "title_active": p.get("title_fg") or fg,
        "title_inactive": C.mix(fg, header, 0.5),
    }
    return v


# --------------------------------------------------------------------- GTK 3


def render_gtk_css(p):
    tpl = Template((_TEMPLATES / "gtk3.css").read_text())
    return tpl.safe_substitute(derive(p))


def _gtk2_rc(v):
    return f"""# {v['name']} — gtkrc minimal généré par BESTthemes
gtk-color-scheme = "bg_color:{v['bg']}\\nfg_color:{v['fg']}\\nbase_color:{v['base']}\\ntext_color:{v['fg']}\\nselected_bg_color:{v['accent']}\\nselected_fg_color:{v['accent_fg']}\\ntooltip_bg_color:{v['tooltip']}\\ntooltip_fg_color:{v['tooltip_fg']}"
style "bt-default" {{
  bg[NORMAL] = @bg_color
  bg[PRELIGHT] = shade (1.05, @bg_color)
  bg[SELECTED] = @selected_bg_color
  bg[ACTIVE] = shade (0.9, @bg_color)
  bg[INSENSITIVE] = @bg_color
  fg[NORMAL] = @fg_color
  fg[PRELIGHT] = @fg_color
  fg[SELECTED] = @selected_fg_color
  fg[ACTIVE] = @fg_color
  fg[INSENSITIVE] = mix (0.5, @fg_color, @bg_color)
  base[NORMAL] = @base_color
  base[SELECTED] = @selected_bg_color
  base[ACTIVE] = @selected_bg_color
  text[NORMAL] = @text_color
  text[SELECTED] = @selected_fg_color
  text[ACTIVE] = @selected_fg_color
}}
class "GtkWidget" style "bt-default"
"""


# --------------------------------------------------------------------- xfwm4

TITLE_H = 32


def _surface(w, h):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return s, cairo.Context(s)


def _rgb(ctx, hexc, a=1.0):
    r, g, b = C.to_rgb(hexc)
    ctx.set_source_rgba(r, g, b, a)


def _rounded_top(ctx, x, y, w, h, r):
    ctx.new_path()
    ctx.move_to(x, y + h)
    ctx.line_to(x, y + r)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.line_to(x + w, y)
    ctx.line_to(x + w, y + h)
    ctx.close_path()


def _corner(path, v, state, side, r, border):
    w = max(r, 2) + border
    s, ctx = _surface(w, TITLE_H)
    header = v["header"] if state == "active" else C.mix(v["header"], v["bg"], 0.35)
    ctx.save()
    if side == "right":
        ctx.translate(w, 0)
        ctx.scale(-1, 1)
    if r > 0:
        _rounded_top(ctx, 0, 0, w + 1, TITLE_H, r)
    else:
        ctx.rectangle(0, 0, w, TITLE_H)
    _rgb(ctx, header)
    ctx.fill()
    ctx.restore()
    s.write_to_png(str(path))


def _fill_png(path, w, h, hexc):
    s, ctx = _surface(w, h)
    _rgb(ctx, hexc)
    ctx.paint()
    s.write_to_png(str(path))


def _title_png(path, v, state):
    header = v["header"] if state == "active" else C.mix(v["header"], v["bg"], 0.35)
    s, ctx = _surface(4, TITLE_H)
    _rgb(ctx, header)
    ctx.paint()
    s.write_to_png(str(path))


def _glyph(ctx, kind, cx, cy, size, color, width=1.4):
    _rgb(ctx, color)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    h = size / 2
    if kind == "close":
        ctx.move_to(cx - h, cy - h)
        ctx.line_to(cx + h, cy + h)
        ctx.move_to(cx + h, cy - h)
        ctx.line_to(cx - h, cy + h)
        ctx.stroke()
    elif kind == "hide":
        ctx.move_to(cx - h, cy + (h * 0.15))
        ctx.line_to(cx + h, cy + (h * 0.15))
        ctx.stroke()
    elif kind == "maximize":
        ctx.rectangle(cx - h, cy - h, size, size)
        ctx.stroke()
    elif kind == "maximize-toggled":
        o = size * 0.25
        ctx.rectangle(cx - h, cy - h + o, size - o, size - o)
        ctx.stroke()
        ctx.move_to(cx - h + o, cy - h + o)
        ctx.line_to(cx - h + o, cy - h)
        ctx.line_to(cx + h, cy - h)
        ctx.line_to(cx + h, cy + h - o)
        ctx.line_to(cx + h - o, cy + h - o)
        ctx.stroke()
    elif kind in ("shade", "shade-toggled"):
        d = -1 if kind == "shade" else 1
        ctx.move_to(cx - h, cy - d * h * 0.4)
        ctx.line_to(cx, cy + d * h * 0.4)
        ctx.line_to(cx + h, cy - d * h * 0.4)
        ctx.stroke()
    elif kind in ("stick", "stick-toggled"):
        ctx.arc(cx, cy, h * 0.55, 0, 2 * math.pi)
        if kind == "stick-toggled":
            ctx.fill()
        else:
            ctx.stroke()
    elif kind == "menu":
        for dy in (-h * 0.6, 0, h * 0.6):
            ctx.move_to(cx - h, cy + dy)
            ctx.line_to(cx + h, cy + dy)
        ctx.stroke()


def _button_png(path, v, style, kind, state, win_state):
    """Dessine un bouton de barre de titre."""
    header = v["header"] if win_state == "active" else C.mix(v["header"], v["bg"], 0.35)
    fg = v["title_active"] if win_state == "active" else v["title_inactive"]
    if style == "macos":
        w = 22
    elif style == "windows":
        w = 40
    else:
        w = 28
    s, ctx = _surface(w, TITLE_H)
    _rgb(ctx, header)
    ctx.paint()
    cx, cy = w / 2, TITLE_H / 2
    base_kind = kind.replace("-toggled", "") if kind != "maximize-toggled" else "maximize"
    mac_colors = {"close": v["red"], "hide": v["yellow"], "maximize": v["green"]}

    if style in ("macos", "circles"):
        if style == "macos":
            col = mac_colors.get(base_kind, C.mix(fg, header, 0.4))
        else:
            col = v["red"] if base_kind == "close" else v["accent"]
        if state == "inactive":
            col = C.mix(header, v["fg"], 0.25)
        elif state == "pressed":
            col = C.darken(col, 0.25)
        rad = 6.5
        ctx.arc(cx, cy, rad, 0, 2 * math.pi)
        _rgb(ctx, col)
        ctx.fill_preserve()
        _rgb(ctx, C.darken(col, 0.18), 0.6)
        ctx.set_line_width(0.8)
        ctx.stroke()
        if state in ("prelight", "pressed") or style == "circles" and state != "inactive":
            glyph_col = C.darken(col, 0.6) if style == "macos" else C.readable_on(col)
            _glyph(ctx, kind, cx, cy, 5.5, glyph_col, 1.3)
    elif style == "windows":
        if state in ("prelight", "pressed"):
            hover = v["red"] if base_kind == "close" else C.shade(header, 0.12 if state == "prelight" else 0.2)
            if base_kind == "close" and state == "pressed":
                hover = C.darken(v["red"], 0.15)
            _rgb(ctx, hover)
            ctx.rectangle(0, 0, w, TITLE_H)
            ctx.fill()
            glyph = C.readable_on(hover) if base_kind == "close" else fg
        else:
            glyph = fg if state == "active" else C.mix(fg, header, 0.4)
        _glyph(ctx, kind, cx, cy, 9, glyph, 1.1)
    else:  # minimal
        glyph = fg if state == "active" else C.mix(fg, header, 0.45)
        if state in ("prelight", "pressed"):
            ctx.arc(cx, cy, 10, 0, 2 * math.pi)
            _rgb(ctx, v["red"] if base_kind == "close" else C.shade(header, 0.15))
            ctx.fill()
            glyph = C.readable_on(v["red"]) if base_kind == "close" else v["accent"]
        _glyph(ctx, kind, cx, cy, 8, glyph, 1.6)
    s.write_to_png(str(path))


THEMERC = """# Thème xfwm4 généré par BESTthemes
active_text_color=$title_active
inactive_text_color=$title_inactive
active_text_shadow_color=#000000
inactive_text_shadow_color=#000000
title_shadow_active=false
title_shadow_inactive=false
title_alignment=center
full_width_title=true
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_horizontal_offset=0
button_offset=$button_offset
button_spacing=$button_spacing
show_app_icon=false
shadow_delta_height=0
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=-3
shadow_opacity=40
maximized_offset=0
"""


def write_xfwm4(dest, p, style):
    v = derive(p)
    d = Path(dest) / "xfwm4"
    d.mkdir(parents=True, exist_ok=True)
    r = min(int(p.get("radius", 8)), 14)
    border = 1
    edge = C.mix(v["header"], v["fg"], 0.08) if v["dark"] else C.darken(v["header"], 0.12)
    for ws in ("active", "inactive"):
        _corner(d / f"top-left-{ws}.png", v, ws, "left", r, border)
        _corner(d / f"top-right-{ws}.png", v, ws, "right", r, border)
        for i in range(1, 6):
            _title_png(d / f"title-{i}-{ws}.png", v, ws)
        _fill_png(d / f"left-{ws}.png", border, 4, edge)
        _fill_png(d / f"right-{ws}.png", border, 4, edge)
        _fill_png(d / f"bottom-{ws}.png", 4, border, edge)
        _fill_png(d / f"bottom-left-{ws}.png", border, border, edge)
        _fill_png(d / f"bottom-right-{ws}.png", border, border, edge)
    kinds = ["close", "hide", "maximize", "maximize-toggled", "menu", "shade",
             "shade-toggled", "stick", "stick-toggled"]
    for kind in kinds:
        for state in ("active", "inactive", "prelight", "pressed"):
            ws = "inactive" if state == "inactive" else "active"
            _button_png(d / f"{kind}-{state}.png", v, style, kind, state, ws)
    rc = Template(THEMERC).safe_substitute(
        v,
        button_offset=10 if style in ("macos", "circles") else (0 if style == "windows" else 6),
        button_spacing=2 if style in ("macos", "circles") else 0,
    )
    (d / "themerc").write_text(rc)


# --------------------------------------------------------------------- Plank

PLANK_TEMPLATE = """# Thème Plank généré par BESTthemes
[PlankTheme]
TopRoundness=$top_round
BottomRoundness=0
LineWidth=1
OuterStrokeColor=$outer
FillStartColor=$fill_start
FillEndColor=$fill_end
InnerStrokeColor=$inner

[PlankDockTheme]
HorizPadding=6
TopPadding=4
BottomPadding=6
ItemPadding=6
IndicatorSize=4
IconShadowSize=2
UrgentBounceHeight=1.66666666666667
LaunchBounceHeight=0.625
FadeOpacity=1
ClickTime=300
UrgentBounceTime=600
LaunchBounceTime=600
ActiveTime=300
SlideTime=300
FadeTime=250
HideTime=150
GlowSize=30
GlowTime=10000
GlowPulseTime=2000
UrgentHueShift=150
ItemMoveTime=450
CascadeHide=true
"""


def write_plank(dest_dir, p):
    v = derive(p)
    d = Path(dest_dir)
    d.mkdir(parents=True, exist_ok=True)
    fill = v["panel"]
    text = Template(PLANK_TEMPLATE).safe_substitute(
        top_round=max(4, int(p.get("radius", 8)) + 4),
        outer=C.plank_color(C.darken(fill, 0.3), 120),
        fill_start=C.plank_color(C.shade(fill, 0.05), 215),
        fill_end=C.plank_color(fill, 215),
        inner=C.plank_color(C.lighten(fill, 0.15), 60),
    )
    (d / "dock.theme").write_text(text)
    return d


# --------------------------------------------------------------------- Ensemble


def generate(p, style="macos", plank=True, dest_root=None):
    """Crée le thème complet et renvoie {gtk, xfwm4, plank} -> noms."""
    paths.ensure_dirs()
    name = theme_name(p)
    root = Path(dest_root or paths.USER_THEMES) / name
    if root.exists():
        shutil.rmtree(root)
    (root / "gtk-3.0").mkdir(parents=True)
    (root / "gtk-2.0").mkdir()
    v = derive(p)
    (root / "gtk-3.0" / "gtk.css").write_text(render_gtk_css(p))
    (root / "gtk-3.0" / "gtk-dark.css").write_text(render_gtk_css({**p}))
    (root / "gtk-2.0" / "gtkrc").write_text(_gtk2_rc(v))
    write_xfwm4(root, p, style)
    (root / "index.theme").write_text(
        "[Desktop Entry]\nType=X-GNOME-Metatheme\n"
        f"Name={name}\nComment=Généré par BESTthemes ({p['name']})\nEncoding=UTF-8\n\n"
        f"[X-GNOME-Metatheme]\nGtkTheme={name}\nMetacityTheme={name}\n"
        f"IconTheme={p.get('icons', 'Papirus')}\nButtonLayout={'close,minimize,maximize:' if style == 'macos' else ':minimize,maximize,close'}\n")
    (root / "bestthemes.json").write_text(json.dumps({"palette": p, "style": style}, indent=1))
    result = {"gtk": name, "xfwm4": name}
    if plank:
        pd = (Path(dest_root) / "plank" if dest_root else paths.USER_PLANK_THEMES) / name
        if pd.exists():
            shutil.rmtree(pd)
        write_plank(pd, p)
        result["plank"] = name
    return result


def list_generated():
    """Thèmes générés précédemment (pour les rééditer)."""
    out = []
    if paths.USER_THEMES.is_dir():
        for d in sorted(paths.USER_THEMES.glob(PREFIX + "*")):
            meta = d / "bestthemes.json"
            if meta.is_file():
                try:
                    out.append((d.name, json.loads(meta.read_text())))
                except ValueError:
                    pass
    return out
