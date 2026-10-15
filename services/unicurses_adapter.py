"""curses-shaped wrapper around Uni-Curses for Windows.

The dashboard calls the stdlib curses window API. Uni-Curses exposes the same
ideas as functions and a module-level screen pointer, and it loads a bundled
PDCurses DLL through ctypes, so it works on Python versions that have no
windows-curses wheel.
"""
from __future__ import annotations


class UniCursesError(Exception):
    """Stand-in for curses.error."""


class _UniWindow:
    def __init__(self, uc):
        self._uc = uc

    def keypad(self, flag: bool) -> None:
        self._uc.keypad(self._uc.stdscr, bool(flag))

    def nodelay(self, flag: bool) -> None:
        self._uc.nodelay(self._uc.stdscr, bool(flag))

    def getch(self) -> int:
        return int(self._uc.getch())

    def getmaxyx(self):
        return self._uc.getmaxyx(self._uc.stdscr)

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self._uc.mvaddstr(y, x, str(text), attr)

    def clear(self) -> None:
        self._uc.clear()

    def erase(self) -> None:
        self._uc.erase()

    def refresh(self) -> None:
        self._uc.refresh()

    def clrtoeol(self) -> None:
        self._uc.clrtoeol()


class UniCursesAPI:
    """Object the dashboard can use in place of the curses module."""

    error = UniCursesError

    def __init__(self, uc) -> None:
        self._uc = uc
        self.A_NORMAL = uc.A_NORMAL
        self.A_BOLD = uc.A_BOLD
        self.A_UNDERLINE = uc.A_UNDERLINE
        self.KEY_RESIZE = uc.KEY_RESIZE
        self.COLOR_BLACK = uc.COLOR_BLACK
        self.COLOR_RED = uc.COLOR_RED
        self.COLOR_GREEN = uc.COLOR_GREEN
        self.COLOR_YELLOW = uc.COLOR_YELLOW
        self.COLOR_BLUE = uc.COLOR_BLUE
        self.COLOR_MAGENTA = uc.COLOR_MAGENTA
        self.COLOR_CYAN = uc.COLOR_CYAN
        self.COLOR_WHITE = uc.COLOR_WHITE
        # PDCurses here is a 16-color console. The dashboard falls back when
        # COLORS is below 256.
        self.COLORS = 16
        self.COLOR_PAIRS = 256

    def _check(self, result) -> None:
        if result == self._uc.ERR:
            raise UniCursesError("curses call failed")

    def initscr(self) -> _UniWindow:
        self._uc.initscr()
        return _UniWindow(self._uc)

    def noecho(self) -> None:
        self._check(self._uc.noecho())

    def echo(self) -> None:
        self._check(self._uc.echo())

    def cbreak(self) -> None:
        self._check(self._uc.cbreak())

    def nocbreak(self) -> None:
        self._check(self._uc.nocbreak())

    def curs_set(self, visibility: int) -> None:
        self._uc.curs_set(visibility)

    def endwin(self) -> None:
        self._uc.endwin()

    def has_colors(self) -> bool:
        return bool(self._uc.has_colors())

    def start_color(self) -> None:
        self._check(self._uc.start_color())

    def use_default_colors(self) -> None:
        self._check(self._uc.use_default_colors())

    def init_pair(self, pair_id: int, fg: int, bg: int) -> None:
        self._check(self._uc.init_pair(pair_id, fg, bg))

    def color_pair(self, pair_id: int) -> int:
        return int(self._uc.color_pair(pair_id))


def load_unicurses() -> UniCursesAPI:
    import unicurses
    return UniCursesAPI(unicurses)
