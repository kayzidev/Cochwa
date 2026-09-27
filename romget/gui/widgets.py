"""Cartes jeux animées (Canvas) et grille adaptative avec réutilisation.

Animations : apparition en cascade à l'affichage d'un onglet, jaquettes en
fondu (crossfade placeholder → cover), survol (contour accentué + léger
zoom), squelette pulsant en attente de jaquette, bouton avec transition de
couleur. La grille réutilise les cartes inchangées (``begin``/``commit``)
au lieu de tout détruire et reconstruire à chaque affichage.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk

from romget.gui import theme
from romget.gui.theme import animate, lerp_color

COVER_W, COVER_H = 150, 225
CARD_W, CARD_H = 210, 366
_SKELETON_A = "#262e3a"
_SKELETON_B = "#333d4d"
_SHADOW = "#10131a"
_BTN_BG = "#31435a"
_BTN_FG_HOVER = "#10212e"

_mask = None
_fonts = {}  # par interpréteur Tk : les polices meurent avec leur root


def _rounded_mask():
    global _mask
    if _mask is None:
        mask = Image.new("L", (COVER_W, COVER_H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, COVER_W - 1, COVER_H - 1), radius=8, fill=255)
        _mask = mask
    return _mask


def _canvas_font(widget, size, weight="normal"):
    """Police canvas mise en cache par interpréteur Tk (une font appartient à
    son root ; la réutiliser après destruction du root lève TclError)."""
    per_root = _fonts.setdefault(str(widget.tk), {})
    key = (size, weight)
    if key not in per_root:
        family = tkfont.nametofont("TkDefaultFont", root=widget).actual("family")
        per_root[key] = tkfont.Font(root=widget, family=family, size=size, weight=weight)
    return per_root[key]


def load_image(path, size=(150, 225)):
    try:
        with Image.open(path) as source:
            img = ImageOps.pad(source.convert("RGB"), size, color=theme.PANEL)
            return ImageTk.PhotoImage(img)
    except (OSError, ValueError):
        return None


def make_placeholder(size=(150, 225), text="?"):
    image = Image.new("RGB", size, _SKELETON_A)
    return ImageTk.PhotoImage(image)


def bind_recursive(widget, sequence, callback):
    """Lie un événement à un widget et tous ses enfants (les clics sur les
    labels d'une carte remontent ainsi au même gestionnaire)."""
    widget.bind(sequence, callback)
    for child in widget.winfo_children():
        bind_recursive(child, sequence, callback)


class GameCard(tk.Canvas):
    """Carte jeu : jaquette arrondie, titre, méta, badges et bouton d'action."""

    def __init__(
        self,
        parent,
        title,
        subtitle="",
        size_bytes=0,
        image=None,  # accepté pour compatibilité ; le squelette animé prime
        on_download=None,
        on_play=None,
        is_installed=False,
        action=None,
        action_text="Détails",
        badges=None,
        key=None,
    ):
        super().__init__(
            parent, width=CARD_W, height=CARD_H, bg=theme.BG, highlightthickness=0, bd=0
        )
        self.key = key if key is not None else title
        self._photo = None
        self._photo_zoom = None
        self._cover_path = None
        self._pulse_on = False
        self._pulse_anim = None
        self._hover = False
        self._action = None
        self._raw_title = ""
        self._raw_meta = ""
        self._badges = []

        x0, y0, x1, y1 = 4, 4, CARD_W - 4, CARD_H - 6
        self._shadow = theme._rounded(
            self, x0 + 2, y0 + 3, x1 + 2, y1 + 3, 12, fill=_SHADOW, outline=""
        )
        self._body = theme._rounded(
            self, x0, y0, x1, y1, 12, fill=theme.CARD, outline=theme.BORDER, width=1
        )
        cx = CARD_W // 2
        self._img = self.create_image(cx, 14 + COVER_H // 2, tags=("content",))
        self._qmark = self.create_text(
            cx,
            14 + COVER_H // 2,
            text="?",
            fill=theme.MUTED,
            font=_canvas_font(self, 26, "bold"),
            tags=("content",),
        )
        self._title = self.create_text(
            cx,
            248,
            anchor="n",
            width=CARD_W - 24,
            justify="center",
            fill=theme.TEXT,
            font=_canvas_font(self, 10, "bold"),
            tags=("content",),
        )
        self._meta = self.create_text(
            cx,
            276,
            anchor="n",
            width=CARD_W - 24,
            justify="center",
            fill=theme.MUTED,
            font=_canvas_font(self, 9),
            tags=("content",),
        )
        self._size = self.create_text(
            cx, 318, anchor="n", fill=theme.MUTED, font=_canvas_font(self, 8), tags=("content",)
        )
        bx0, by0, bx1, by1 = 30, CARD_H - 40, CARD_W - 30, CARD_H - 14
        self._btn = theme._rounded(
            self, bx0, by0, bx1, by1, 7, fill=_BTN_BG, outline="", tags=("content", "btn")
        )
        self._btn_text = self.create_text(
            cx,
            (by0 + by1) // 2,
            fill=theme.TEXT,
            font=_canvas_font(self, 9, "bold"),
            tags=("content", "btn"),
        )
        self.tag_bind("btn", "<Enter>", lambda event: self._btn_hover(True))
        self.tag_bind("btn", "<Leave>", lambda event: self._btn_hover(False))
        self.tag_bind("btn", "<Button-1>", lambda event: self._run_action())
        self.bind("<Enter>", lambda event: self._hover_card(True))
        self.bind("<Leave>", lambda event: self._hover_card(False))

        if action is None and (on_download or on_play):

            def action():
                (on_play if is_installed and on_play else on_download)(self)

        self.reconfigure(
            title=title,
            subtitle=subtitle,
            size_bytes=size_bytes,
            action=action,
            action_text=action_text,
            badges=badges,
        )
        self._start_pulse()

    # -- Contenu ------------------------------------------------------

    def reconfigure(
        self,
        title=None,
        subtitle=None,
        size_bytes=None,
        action=None,
        action_text=None,
        badges=None,
        **_ignored,
    ):
        """Met à jour les textes/badges d'une carte réutilisée (jaquette conservée)."""
        if title is not None:
            self._raw_title = title
        if subtitle is not None:
            self._raw_meta = subtitle
        if badges is not None:
            self._badges = badges
        if size_bytes is not None:
            from romget.util import human_size

            self.itemconfigure(self._size, text=human_size(size_bytes) if size_bytes else "")
        self._action = action
        self.itemconfigure(self._btn_text, text=action_text or "")
        state = "normal" if action else "hidden"
        self.itemconfigure(self._btn, state=state)
        self.itemconfigure(self._btn_text, state=state)
        self._layout_text()

    @staticmethod
    def _fit(text, font, max_width, max_lines):
        """Tronque avec « … » pour tenir en ``max_lines`` lignes de ``max_width``."""
        words = text.split()
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if font.measure(trial) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines:
                    break
        if len(lines) < max_lines and current:
            lines.append(current)
        if " ".join(lines).split() != words and lines:
            last = lines[-1]
            while last and font.measure(last + "…") > max_width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
        return "\n".join(lines)

    def _text_height(self, item):
        bbox = self.bbox(item)
        return bbox[3] - bbox[1] if bbox else 0

    def _layout_text(self):
        """Empile titre → méta → badges → taille sans chevauchement, le bouton
        restant ancré en bas. Titre : 2 lignes max ; méta : 1 ligne."""
        cx = CARD_W // 2
        self.itemconfigure(
            self._title,
            text=self._fit(self._raw_title, _canvas_font(self, 10, "bold"), CARD_W - 24, 2),
        )
        self.itemconfigure(
            self._meta, text=self._fit(self._raw_meta, _canvas_font(self, 9), CARD_W - 24, 1)
        )
        y = 246
        self.coords(self._title, cx, y)
        y += self._text_height(self._title) + 4
        self.coords(self._meta, cx, y)
        if self._raw_meta:
            y += self._text_height(self._meta) + 6
        self._draw_chips(self._badges, y)
        if self._badges:
            y += 20
        self.coords(self._size, cx, y)

    def _draw_chips(self, badges, y):
        self.delete("chip")
        if not badges:
            return
        font = _canvas_font(self, 8, "bold")
        widths = [font.measure(text) + 16 for text, _ in badges]
        total = sum(widths) + 6 * (len(badges) - 1)
        x = (CARD_W - total) / 2
        y0, y1 = y, y + 16
        for (text, color), width in zip(badges, widths):
            theme._rounded(
                self,
                x,
                y0,
                x + width,
                y1,
                8,
                fill=lerp_color(color, theme.CARD, 0.82),
                outline=color,
                width=1,
                tags=("content", "chip"),
            )
            self.create_text(
                x + width / 2,
                (y0 + y1) / 2,
                text=text,
                fill=color,
                font=font,
                tags=("content", "chip"),
            )
            x += width + 6

    # -- Jaquette -----------------------------------------------------

    def _set_cover_pil(self, pil):
        rounded = pil.convert("RGBA")
        rounded.putalpha(_rounded_mask())
        self._photo = ImageTk.PhotoImage(rounded)
        self.itemconfigure(self._img, image=self._photo)

    def set_cover(self, path):
        """Fondu placeholder → jaquette ; ``None`` = placeholder statique."""
        path = str(path) if path else None
        if path and path == self._cover_path:
            return
        # Annule le squelette pulsant : sinon ses frames en cours repeindraient
        # le placeholder par-dessus la jaquette (cover visible seulement au survol).
        self._pulse_on = False
        if self._pulse_anim:
            self._pulse_anim["cancelled"] = True
            self._pulse_anim = None
        if not path:
            self._cover_path = None
            self._set_cover_pil(Image.new("RGB", (COVER_W, COVER_H), _SKELETON_A))
            self.itemconfigure(self._qmark, state="normal")
            return
        try:
            with Image.open(path) as source:
                cover = ImageOps.pad(source.convert("RGB"), (COVER_W, COVER_H), color=theme.PANEL)
        except (OSError, ValueError):
            self.set_cover(None)
            return
        self._cover_path = path
        self.itemconfigure(self._qmark, state="hidden")
        start = Image.new("RGB", (COVER_W, COVER_H), _SKELETON_A)
        animate(
            self,
            220,
            lambda t: self._set_cover_pil(Image.blend(start, cover, t)),
            on_done=lambda: self._finish_cover(cover),
        )

    def _finish_cover(self, cover):
        self._set_cover_pil(cover)
        zw, zh = int(COVER_W * 1.07), int(COVER_H * 1.07)
        zoomed = cover.resize((zw, zh), Image.LANCZOS).crop(
            ((zw - COVER_W) // 2, (zh - COVER_H) // 2, (zw + COVER_W) // 2, (zh + COVER_H) // 2)
        )
        rgba = zoomed.convert("RGBA")
        rgba.putalpha(_rounded_mask())
        self._photo_zoom = ImageTk.PhotoImage(rgba)
        if self._hover:
            self.itemconfigure(self._img, image=self._photo_zoom)

    def _start_pulse(self):
        self._pulse_on = True
        self._pulse_step(False)

    def _pulse_step(self, reverse):
        if not self._pulse_on or not self.winfo_exists():
            return
        a, b = (_SKELETON_B, _SKELETON_A) if reverse else (_SKELETON_A, _SKELETON_B)
        self._pulse_anim = animate(
            self,
            900,
            lambda t: self._set_cover_pil(
                Image.new("RGB", (COVER_W, COVER_H), lerp_color(a, b, t))
            ),
            on_done=lambda: self._pulse_step(not reverse),
            ease=lambda t: t,
        )

    # -- Survol et action ----------------------------------------------

    def _hover_card(self, entering):
        if entering == self._hover:
            return
        self._hover = entering
        border = (theme.BORDER, theme.ACCENT) if entering else (theme.ACCENT, theme.BORDER)
        fill = (theme.CARD, theme.CARD_HOVER) if entering else (theme.CARD_HOVER, theme.CARD)
        animate(
            self,
            140,
            lambda t: self.itemconfigure(
                self._body,
                outline=lerp_color(border[0], border[1], t),
                fill=lerp_color(fill[0], fill[1], t),
            ),
        )
        if self._photo_zoom is not None:
            self.itemconfigure(self._img, image=self._photo_zoom if entering else self._photo)

    def _btn_hover(self, entering):
        self.configure(cursor="hand2" if entering else "")
        a, b = (_BTN_BG, theme.ACCENT) if entering else (theme.ACCENT, _BTN_BG)
        fa, fb = (theme.TEXT, _BTN_FG_HOVER) if entering else (_BTN_FG_HOVER, theme.TEXT)
        animate(
            self,
            120,
            lambda t: (
                self.itemconfigure(self._btn, fill=lerp_color(a, b, t)),
                self.itemconfigure(self._btn_text, fill=lerp_color(fa, fb, t)),
            ),
        )

    def _run_action(self):
        if self._action:
            self._action()

    # -- Apparition (cascade) -------------------------------------------

    def appear(self, delay=0):
        """Fondu + remontée de 12 px ; le contenu est révélé en fin de course."""
        self.itemconfigure("content", state="hidden")
        self.itemconfigure(self._body, fill=theme.BG, outline=theme.BG)
        self.itemconfigure(self._shadow, fill=theme.BG)
        self._appear_offset = 12.0
        self.move("all", 0, 12)

        def step(t):
            self.itemconfigure(
                self._body,
                fill=lerp_color(theme.BG, theme.CARD, t),
                outline=lerp_color(theme.BG, theme.BORDER, t),
            )
            self.itemconfigure(self._shadow, fill=lerp_color(theme.BG, _SHADOW, t))
            offset = 12 * (1 - t)
            self.move("all", 0, offset - self._appear_offset)
            self._appear_offset = offset

        def done():
            self.itemconfigure("content", state="normal")
            if self._cover_path is not None:
                self.itemconfigure(self._qmark, state="hidden")
            if not self._action:
                self.itemconfigure(self._btn, state="hidden")
                self.itemconfigure(self._btn_text, state="hidden")

        animate(self, 200, step, on_done=done, delay=delay)


class GameGrid(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.cards = []
        self.columns = 1
        self._stale = {}
        self._fresh = []
        self._empty_text = ""
        self.empty_label = ttk.Label(
            self, text="", foreground=theme.MUTED, font=("TkDefaultFont", 11)
        )
        self.inner.bind(
            "<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self.resize)
        self._wheel(self.canvas)

    def _wheel(self, widget):
        widget.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"))
        widget.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"))
        widget.bind(
            "<MouseWheel>",
            lambda event: self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"),
        )
        for child in widget.winfo_children():
            self._wheel(child)

    # -- Cycle de rendu différencié --------------------------------------

    def begin(self):
        """Démarre un cycle : les cartes existantes deviennent réutilisables."""
        self._stale = {card.key: card for card in self.cards}
        self.cards = []

    def add(self, **kwargs):
        key = kwargs.get("key") or kwargs.get("title")
        card = self._stale.pop(key, None)
        if card is not None:
            card.reconfigure(**kwargs)
        else:
            card = GameCard(self.inner, **kwargs)
            self._fresh.append(card)
            self._wheel(card)
        self.cards.append(card)
        self.layout()
        self._update_empty()
        return card

    def commit(self):
        """Termine le cycle : détruit les cartes disparues, anime les nouvelles."""
        for card in self._stale.values():
            card.destroy()
        self._stale = {}
        fresh, self._fresh = self._fresh, []
        self.layout()
        self._update_empty()
        for i, card in enumerate(fresh):
            if card.winfo_exists():
                card.appear(delay=min(i * 25, 400))

    def clear(self):
        for card in self.cards + list(self._stale.values()):
            card.destroy()
        self.cards.clear()
        self._stale = {}
        self._fresh = []
        self.canvas.yview_moveto(0)
        self._update_empty()

    # -- État vide --------------------------------------------------------

    def set_empty(self, text):
        self._empty_text = text
        self._update_empty()

    def _update_empty(self):
        if self.cards or not self._empty_text:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text=self._empty_text)
            self.empty_label.place(relx=0.5, rely=0.4, anchor="center")

    # -- Disposition --------------------------------------------------------

    def resize(self, event):
        columns = max(1, event.width // 230)
        self.canvas.itemconfigure(self.window, width=event.width)
        if columns != self.columns:
            for i in range(self.columns):
                self.inner.columnconfigure(i, weight=0)
            self.columns = columns
            self.layout()

    def layout(self):
        for i, card in enumerate(self.cards):
            card.grid(row=i // self.columns, column=i % self.columns, padx=5, pady=5, sticky="nsew")
        for i in range(self.columns):
            self.inner.columnconfigure(i, weight=1, uniform="cards")
