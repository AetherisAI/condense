"""The Condense Agent desktop app: a small always-on Tkinter window over the sync engine.

The window shows the folders being watched and the last sync result, with **Sync now** /
**Pause** / **Add folder** and a **⚙ gear** that opens settings (engine URL, bearer token, the
list of watched folders, recursive, and the "delete from index when removed locally" toggle). A
:class:`~agent.watcher.Watcher` feeds change events in; each one schedules a
:func:`~agent.sync.sync` pass on a background thread so the UI never blocks. All widget mutation
is marshalled back onto the Tk thread via ``root.after``. Buttons are custom rounded-pill canvas
widgets (:class:`RoundedButton`) styled after the web UI.

``main()`` is the ``sift-agent`` entry point.
"""

from __future__ import annotations

import sys
import threading

try:  # Tk ships with python.org builds; Homebrew/Linux need an extra package (see _TK_HINT).
    import tkinter as tk
    from tkinter import filedialog, ttk
    from tkinter import font as tkfont

    _TK_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment-dependent
    tk = None  # type: ignore[assignment]
    _TK_ERROR = exc

from agent.client import SiftClient
from agent.config import AgentConfig, load, save
from agent.sync import Summary, sync
from agent.watcher import Watcher

_TK_HINT = (
    "Condense Agent needs Tkinter, which isn't available in this Python.\n"
    "  macOS (Homebrew):  brew install python-tk@3.12\n"
    "  Ubuntu/Debian:     sudo apt install python3-tk\n"
    "  (or use a python.org build, which bundles Tk)"
)

# Palette lifted from the web UI (web/src/index.css :root) so the app matches the product brand.
ACCENT = "#7c5cff"  # blue-purple — the buttons/logo accent from the web UI
ACCENT_ACTIVE = "#6a45f0"
PAGE_BG = "#f6f6f8"
SURFACE = "#ffffff"
TEXT_H = "#0b0a10"
TEXT = "#45424f"
MUTED = "#8b8794"
BORDER = "#d8d7dc"
HOVER = "#efeef3"
PRESS = "#e6e5ec"
# Brand mark colours (web/src/Logo.tsx): purple core, deeper-purple emitted dot, black orbs.
_LOGO_CORE = "#aa3bff"
_LOGO_OUT = "#8f1fe6"
_LOGO_DOT = "#0b0a10"
_LOGO_GLOW = "#efe3ff"
_LOGO_RING = "#e7d3ff"

# 8 input dots on the r=8 ring (matches Logo.tsx ORBS), absorbed into the core at (16, 12.5).
_ORBS = [
    (0, -8),
    (5.66, -5.66),
    (8, 0),
    (5.66, 5.66),
    (0, 8),
    (-5.66, 5.66),
    (-8, 0),
    (-5.66, -5.66),
]


def _draw_logo(canvas, size: int = 40) -> None:
    """Render the Condense brand mark (web/src/Logo.tsx geometry) onto ``canvas``, static."""
    s = size / 32.0
    cx, cy = 16.0, 12.5

    def oval(x: float, y: float, r: float, **kw) -> None:
        canvas.create_oval((x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s, **kw)

    oval(cx, cy, 4.5, fill=_LOGO_GLOW, outline="")  # soft glow behind the core
    oval(cx, cy, 8, outline=_LOGO_RING, width=max(1, round(0.8 * s)))  # the input ring
    for ox, oy in _ORBS:
        oval(cx + ox, cy + oy, 1.15, fill=_LOGO_DOT, outline="")  # the "many" dots
    oval(cx, cy, 2.1, fill=_LOGO_CORE, outline="")  # the core they collapse into
    oval(16, 26, 1.8, fill=_LOGO_OUT, outline="")  # the single distilled output dot


def _pill_points(x1: float, y1: float, x2: float, y2: float, r: float) -> list[float]:
    """Corner points for a rounded rectangle drawn as a smoothed polygon (Aqua anti-aliases it)."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
    ]


class RoundedButton(tk.Canvas):
    """A clean, Apple-style rounded-pill button drawn on a canvas, with hover/press feedback.

    ``variant`` is ``"primary"`` (purple accent, white text), ``"secondary"`` (white chip with a
    hairline border), or ``"icon"`` (square-ish, for the gear). Sizes itself to its text.
    """

    def __init__(
        self,
        parent,
        text: str = "",
        command=None,
        *,
        variant: str = "secondary",
        padx: int = 11,
        pady: int = 4,
        font=("", 10),
        min_width: int = 0,
        parent_bg: str = PAGE_BG,
    ) -> None:
        super().__init__(parent, highlightthickness=0, bd=0, bg=parent_bg, takefocus=0)
        self._command = command
        self._variant = variant
        self._padx, self._pady = padx, pady
        self._font = tkfont.Font(font=font)
        self._text = text
        self._min_width = min_width
        self._hover = False
        self._pressed = False
        self._size()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _size(self) -> None:
        # NB: not ``self._w``/``self._h`` — Tk's Canvas uses ``_w`` for its widget path name.
        tw = self._font.measure(self._text)
        th = self._font.metrics("linespace")
        self._bw = max(self._min_width, tw + 2 * self._padx)
        self._bh = th + 2 * self._pady
        self.configure(width=self._bw, height=self._bh)

    def _palette(self) -> tuple[str, str, str | None]:
        if self._variant == "primary":
            bg = ACCENT_ACTIVE if (self._hover or self._pressed) else ACCENT
            return bg, "white", None
        # secondary / icon
        if self._pressed:
            bg = PRESS
        elif self._hover:
            bg = HOVER
        else:
            bg = PAGE_BG if self._variant == "icon" else SURFACE
        return bg, TEXT_H, BORDER

    def _draw(self) -> None:
        self.delete("all")
        bg, fg, outline = self._palette()
        pts = _pill_points(1.0, 1.0, self._bw - 1, self._bh - 1, self._bh / 2)
        kw: dict = {"smooth": True, "fill": bg}
        kw.update({"outline": outline, "width": 1} if outline else {"outline": bg})
        self.create_polygon(pts, **kw)
        self.create_text(
            self._bw / 2,
            self._bh / 2 + (1 if self._pressed else 0),
            text=self._text,
            fill=fg,
            font=self._font,
        )

    def _on_enter(self, _e) -> None:
        self._hover = True
        self.configure(cursor="hand2")
        self._draw()

    def _on_leave(self, _e) -> None:
        self._hover = self._pressed = False
        self.configure(cursor="")
        self._draw()

    def _on_press(self, _e) -> None:
        self._pressed = True
        self._draw()

    def _on_release(self, _e) -> None:
        fired = self._pressed and self._hover
        self._pressed = False
        self._draw()
        if fired and self._command is not None:
            self._command()

    def set_text(self, text: str) -> None:
        self._text = text
        self._size()
        self._draw()


class AgentApp:
    """Owns the window, the HTTP client, the watcher, and the single-flight sync loop."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._cfg: AgentConfig = load()
        self._client: SiftClient | None = None
        self._watcher: Watcher | None = None
        self._paused = False

        self._sync_lock = threading.Lock()
        self._syncing = False
        self._pending = False
        self._managed: set[str] = set()  # on-disk paths seen so far — scopes delete_removed

        root.title("Condense Agent")
        root.minsize(440, 0)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_theme()
        self._build_ui()
        self._refresh_path_label()

        # Boot: start watching if we have enough config, otherwise nudge the user to settings.
        if self._cfg.configured:
            self._restart()
        else:
            self._status.set("Not configured — open ⚙ Settings")
            self._root.after(200, self._open_settings)

    # --- UI construction ----------------------------------------------------------

    def _apply_theme(self) -> None:
        """Theme ttk widgets (labels, entries, checks) to match the web UI's light palette."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - platform-dependent
            pass
        self._root.configure(bg=PAGE_BG)
        style.configure(".", background=PAGE_BG, foreground=TEXT)
        style.configure("TFrame", background=PAGE_BG)
        style.configure("TLabel", background=PAGE_BG, foreground=TEXT)
        style.configure(
            "Title.TLabel", background=PAGE_BG, foreground=TEXT_H, font=("", 13, "bold")
        )
        style.configure("Path.TLabel", background=PAGE_BG, foreground=TEXT_H)
        style.configure("Status.TLabel", background=PAGE_BG, foreground=MUTED)
        style.configure("Field.TLabel", background=PAGE_BG, foreground=MUTED)
        style.configure("TCheckbutton", background=PAGE_BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", PAGE_BG)])
        style.configure(
            "TEntry",
            fieldbackground=SURFACE,
            bordercolor=BORDER,
            borderwidth=1,
            relief="flat",
            padding=6,
        )
        style.map("TEntry", bordercolor=[("focus", ACCENT)])

    def _build_ui(self) -> None:
        top = ttk.Frame(self._root)
        top.pack(fill="x", padx=16, pady=(14, 8))
        brand = ttk.Frame(top)
        brand.pack(side="left")
        logo = tk.Canvas(brand, width=26, height=26, bg=PAGE_BG, highlightthickness=0, bd=0)
        logo.pack(side="left")
        _draw_logo(logo, 26)
        ttk.Label(brand, text="Condense Agent", style="Title.TLabel").pack(side="left", padx=(8, 0))
        RoundedButton(
            top, "⚙", self._open_settings, variant="icon", padx=8, pady=5, font=("", 12)
        ).pack(side="right")

        self._path_var = tk.StringVar()
        ttk.Label(
            self._root,
            textvariable=self._path_var,
            style="Path.TLabel",
            justify="left",
            wraplength=400,
        ).pack(fill="x", anchor="w", padx=16, pady=(2, 6))

        self._status = tk.StringVar(value="idle")
        ttk.Label(self._root, textvariable=self._status, style="Status.TLabel").pack(
            anchor="w", padx=16, pady=(0, 8)
        )

        btns = ttk.Frame(self._root)
        btns.pack(fill="x", padx=16, pady=(2, 16))
        RoundedButton(btns, "Sync now", self._sync_now, variant="primary").pack(side="left")
        self._pause_btn = RoundedButton(btns, "Pause", self._toggle_pause, min_width=72)
        self._pause_btn.pack(side="left", padx=(8, 0))
        RoundedButton(btns, "Add folder…", self._add_folder).pack(side="right")

    def _folders_summary(self) -> str:
        paths = self._cfg.watch_paths
        if not paths:
            return "No folders yet — “Add folder…” or open ⚙ Settings"
        if len(paths) == 1:
            return f"Watching: {paths[0]}"
        return f"Watching {len(paths)} folders:\n  " + "\n  ".join(paths)

    def _refresh_path_label(self) -> None:
        self._path_var.set(self._folders_summary())

    # --- lifecycle: (re)build client + watcher from current config ----------------

    def _restart(self) -> None:
        """Rebuild the client and watcher for the current config, then do a full sync."""
        self._managed = set()  # config changed — don't carry over the old managed set
        self._stop_watching()
        if self._client is not None:
            self._client.close()
            self._client = None
        if not self._cfg.configured:
            self._status.set("Not configured — open ⚙ Settings")
            return
        self._client = SiftClient(self._cfg.engine_url, self._cfg.token)
        if not self._paused:
            self._start_watching()
        self._request_sync()

    def _start_watching(self) -> None:
        try:
            self._watcher = Watcher(
                self._cfg.watch_paths, self._on_fs_change, recursive=self._cfg.recursive
            )
            self._watcher.start()
        except Exception as exc:  # bad path, backend failure — show it, stay alive
            self._status.set(f"watch error: {exc}")
            self._watcher = None

    def _stop_watching(self) -> None:
        if self._watcher is not None:
            try:
                self._watcher.stop()
            finally:
                self._watcher = None

    # --- sync loop (single-flight, coalescing) ------------------------------------

    def _on_fs_change(self) -> None:
        self._request_sync()  # called on the watcher's timer thread

    def _sync_now(self) -> None:
        self._request_sync()

    def _request_sync(self) -> None:
        if self._client is None:
            return
        with self._sync_lock:
            if self._syncing:
                self._pending = True
                return
            self._syncing = True
        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self) -> None:
        while True:
            self._ui(lambda: self._status.set("syncing…"))
            client, cfg = self._client, self._cfg
            if client is None:
                summary = Summary(error="not configured")
            else:
                summary = sync(
                    client,
                    cfg.watch_paths,
                    cfg.includes(),
                    tenant=cfg.tenant,
                    delete_removed=cfg.delete_removed,
                    managed=self._managed,
                )
                self._managed = set(summary.managed)
            self._ui(lambda s=summary: self._status.set(s.line()))
            with self._sync_lock:
                if self._pending:
                    self._pending = False
                    continue
                self._syncing = False
                return

    def _ui(self, fn) -> None:
        """Run ``fn`` on the Tk main thread (safe to call from any thread)."""
        self._root.after(0, fn)

    # --- controls -----------------------------------------------------------------

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._stop_watching()
            self._pause_btn.set_text("Resume")
            self._status.set("paused")
        else:
            self._pause_btn.set_text("Pause")
            if self._cfg.configured:
                self._start_watching()
                self._request_sync()

    def _add_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Add a folder to watch")
        if not chosen or chosen in self._cfg.watch_paths:
            return
        self._cfg.watch_paths.append(chosen)
        save(self._cfg)
        self._refresh_path_label()
        self._restart()

    # --- settings dialog ----------------------------------------------------------

    def _open_settings(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("Condense Agent — Settings")
        win.configure(bg=PAGE_BG)
        win.transient(self._root)
        win.grab_set()
        frm = ttk.Frame(win, padding=18)
        frm.pack(fill="both", expand=True)

        url = tk.StringVar(value=self._cfg.engine_url)
        token = tk.StringVar(value=self._cfg.token)
        exts = tk.StringVar(value=", ".join(self._cfg.include_exts))
        tenant = tk.StringVar(value=self._cfg.tenant)
        recursive = tk.BooleanVar(value=self._cfg.recursive)
        delete_removed = tk.BooleanVar(value=self._cfg.delete_removed)

        def field(label: str, var: tk.StringVar, *, secret: bool = False) -> None:
            r = ttk.Frame(frm)
            r.pack(fill="x", pady=5)
            ttk.Label(r, text=label, style="Field.TLabel", width=13).pack(side="left")
            ttk.Entry(r, textvariable=var, show="•" if secret else "").pack(
                side="left", fill="x", expand=True
            )

        field("Engine URL", url)
        field("Bearer token", token, secret=True)

        # --- watched folders list (add / remove) ---
        ttk.Label(frm, text="Folders", style="Field.TLabel").pack(anchor="w", pady=(10, 2))
        list_row = ttk.Frame(frm)
        list_row.pack(fill="both", expand=True)
        folders = tk.Listbox(
            list_row,
            height=4,
            activestyle="none",
            bg=SURFACE,
            fg=TEXT_H,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            selectbackground=ACCENT,
            selectforeground="white",
        )
        folders.pack(side="left", fill="both", expand=True)
        for p in self._cfg.watch_paths:
            folders.insert("end", p)

        fbtns = ttk.Frame(list_row)
        fbtns.pack(side="left", fill="y", padx=(8, 0))

        def add_folder() -> None:
            chosen = filedialog.askdirectory(title="Add a folder to watch")
            if chosen and chosen not in folders.get(0, "end"):
                folders.insert("end", chosen)

        def remove_folder() -> None:
            for i in reversed(folders.curselection()):
                folders.delete(i)

        RoundedButton(fbtns, "Add…", add_folder, padx=12, pady=5).pack(fill="x")
        RoundedButton(fbtns, "Remove", remove_folder, padx=12, pady=5).pack(fill="x", pady=(6, 0))

        field("Extensions", exts)
        field("Tenant", tenant)
        ttk.Checkbutton(frm, text="Watch subfolders (recursive)", variable=recursive).pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Checkbutton(
            frm, text="Delete from index when a file is removed locally", variable=delete_removed
        ).pack(anchor="w")

        def on_save() -> None:
            self._cfg.engine_url = url.get().strip().rstrip("/")
            self._cfg.token = token.get().strip()
            self._cfg.watch_paths = list(folders.get(0, "end"))
            self._cfg.tenant = tenant.get().strip() or "default"
            self._cfg.recursive = recursive.get()
            self._cfg.delete_removed = delete_removed.get()
            self._cfg.include_exts = [e.strip() for e in exts.get().split(",") if e.strip()]
            save(self._cfg)
            win.destroy()
            self._refresh_path_label()
            self._restart()

        actions = ttk.Frame(frm)
        actions.pack(fill="x", pady=(18, 0))
        RoundedButton(actions, "Save", on_save, variant="primary").pack(side="right")
        RoundedButton(actions, "Cancel", win.destroy).pack(side="right", padx=(0, 8))

    # --- shutdown -----------------------------------------------------------------

    def _on_close(self) -> None:
        self._stop_watching()
        if self._client is not None:
            self._client.close()
        self._root.destroy()


def main() -> int:
    """Launch the agent window. Returns a process exit code."""
    if _TK_ERROR is not None:
        sys.stderr.write(f"{_TK_HINT}\n\n(import error: {_TK_ERROR})\n")
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no display available
        sys.stderr.write(f"Condense Agent cannot start its UI: {exc}\n")
        return 1
    AgentApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
