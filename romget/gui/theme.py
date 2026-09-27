"""Palette, typographie et animations de l'interface romget.

Animations maison à base de ``widget.after`` : Tkinter ne connaît ni CSS ni
GPU, mais l'interpolation de couleurs, les déplacements et les fondus PIL
suffisent pour des transitions fluides à 60 images/s.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

# Palette sombre type launcher (Steam/Epic).
BG = "#171a21"  # fond principal
PANEL = "#1e2530"  # champs, panneaux
CARD = "#242c38"  # cartes au repos
CARD_HOVER = "#2b3543"  # cartes survolées
BORDER = "#39424f"
ACCENT = "#66c0f4"  # accent principal (bleu Steam)
ACCENT_DARK = "#3d6e96"
SUCCESS = "#6cbd91"
WARNING = "#d8b356"
DANGER = "#d4655f"
TEXT = "#e8eaed"
MUTED = "#9aa5b1"

# Hiérarchie typographique.
F_TITLE = ("TkDefaultFont", 15, "bold")
F_H2 = ("TkDefaultFont", 12, "bold")
F_BODY = ("TkDefaultFont", 10)
F_SMALL = ("TkDefaultFont", 9)
F_TINY = ("TkDefaultFont", 8)


def score_color(score):
    """Échelle de couleur pour les notes : vert ≥ 85, ambre ≥ 70, rouge sinon."""
    if score >= 85:
        return SUCCESS
    if score >= 70:
        return WARNING
    return DANGER


def lerp_color(a, b, t):
    """Interpolation linéaire entre deux couleurs ``#rrggbb``."""
    ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg_, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        round(ar + (br - ar) * t),
        round(ag + (bg_ - ag) * t),
        round(ab + (bb - ab) * t),
    )


def _ease_out(t):
    return 1 - (1 - t) ** 3


def animate(widget, duration_ms, step, on_done=None, delay=0, ease=None):
    """Appelle ``step(t)`` (t easing de 0 à 1) puis ``on_done``.

    Retourne un état mutable : ``state["cancelled"] = True`` interrompt
    l'animation. Les callbacks sont ignorés si le widget est détruit.
    """
    ease = ease or _ease_out
    frames = max(2, int(duration_ms / 16))
    interval = max(1, int(duration_ms / frames))
    state = {"i": 0, "cancelled": False}

    def tick():
        if state["cancelled"]:
            return
        try:
            # winfo_exists() lève TclError si l'interpréteur est détruit.
            if not widget.winfo_exists():
                return
            state["i"] += 1
            t = min(1.0, state["i"] / frames)
            step(ease(t))
            if t < 1.0:
                widget.after(interval, tick)
            elif on_done:
                on_done()
        except tk.TclError:
            state["cancelled"] = True

    widget.after(delay, tick) if delay else widget.after(0, tick)
    return state


def _rounded(canvas, x1, y1, x2, y2, radius, **kwargs):
    """Rectangle arrondi via polygone lissé (recette Tk classique)."""
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


_BUTTON_KINDS = {
    # (fond, texte, fond survolé)
    "primary": (ACCENT, "#10212e", "#8bd0f7"),
    "ghost": ("#2e3744", TEXT, "#3b4c5e"),
    "danger": ("#43302f", TEXT, DANGER),
}


class HoverButton(tk.Canvas):
    """Bouton plat à coins arrondis avec transition de couleur au survol."""

    def __init__(self, parent, text, command, kind="ghost", height=30, bg=BG):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.normal, self.fg, self.hover = _BUTTON_KINDS[kind]
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        self.font = tkfont.Font(family=family, size=9, weight="bold")
        width = self.font.measure(text) + 28
        self.configure(width=width)
        self._rect = _rounded(self, 1, 1, width - 1, height - 1, 7, fill=self.normal, outline="")
        self._label = self.create_text(
            width / 2, height / 2, text=text, fill=self.fg, font=self.font
        )
        self.bind("<Enter>", lambda event: self._transition(self.hover))
        self.bind("<Leave>", lambda event: self._transition(self.normal))
        self.bind("<ButtonRelease-1>", lambda event: self.command())

    def _transition(self, target):
        start = self.itemcget(self._rect, "fill")
        animate(
            self,
            130,
            lambda t: self.itemconfigure(self._rect, "fill", lerp_color(start, target, t)),
        )


class ToastManager:
    """Notifications empilées en bas à droite : glissement, fondu, repli au clic."""

    WIDTH = 330

    def __init__(self, root):
        self.root = root
        self.toasts = []

    def show(self, message, kind="info"):
        try:
            toast = _Toast(self, message, kind)
        except tk.TclError:
            return  # fenêtre en cours de destruction
        self.toasts.append(toast)
        self._restack()

    def dismiss(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
        self._restack()

    def _restack(self):
        try:
            self.root.update_idletasks()
            x = self.root.winfo_rootx() + self.root.winfo_width() - self.WIDTH - 18
            y = self.root.winfo_rooty() + self.root.winfo_height() - 84
            for toast in reversed(self.toasts):
                y -= toast.height
                toast.move(x, y)
                y -= 10
        except tk.TclError:
            pass


class _Toast:
    COLORS = {"info": ACCENT, "success": SUCCESS, "error": DANGER}

    def __init__(self, manager, message, kind):
        self.manager = manager
        self.top = tk.Toplevel(manager.root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.0)
        color = self.COLORS.get(kind, ACCENT)
        outer = tk.Frame(self.top, bg=BORDER)
        outer.pack()
        tk.Frame(outer, bg=color, width=4).pack(side="left", fill="y")
        inner = tk.Frame(outer, bg=PANEL)
        inner.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        tk.Label(
            inner,
            text=message,
            bg=PANEL,
            fg=TEXT,
            font=F_SMALL,
            wraplength=ToastManager.WIDTH - 40,
            justify="left",
            anchor="w",
        ).pack(padx=10, pady=9, fill="x")
        self.top.update_idletasks()
        self.height = self.top.winfo_reqheight()
        self.top.geometry(f"{ToastManager.WIDTH}x{self.height}")
        self.top.bind("<Button-1>", lambda event: self.close())
        animate(self.top, 180, lambda t: self.top.attributes("-alpha", 0.95 * t))
        self.top.after(3800, self._fade_out)

    def move(self, x, y):
        try:
            self.top.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _fade_out(self):
        animate(
            self.top,
            300,
            lambda t: self.top.attributes("-alpha", 0.95 * (1 - t)),
            on_done=self.close,
        )

    def close(self):
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        self.manager.dismiss(self)
