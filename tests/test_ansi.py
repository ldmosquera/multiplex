import fcntl
import os
import struct
import sys
import termios

import pytest

from multiplex import ansi


def _set_winsize(fd, cols, rows):
    # struct winsize is (row, col, xpixel, ypixel)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


class _Pty:
    """A pty pair. Point sys.stdout at .file (via monkeypatch) to test get_size()."""

    def __init__(self):
        self.master, self.slave = os.openpty()
        self.file = os.fdopen(self.slave, "w")

    def resize(self, cols, rows):
        _set_winsize(self.slave, cols, rows)

    def close(self):
        self.file.close()
        os.close(self.master)


@pytest.fixture
def pty():
    p = _Pty()
    try:
        yield p
    finally:
        p.close()


def test_get_size_tracks_live_tty_and_ignores_stale_env(pty, monkeypatch):
    """The core regression.

    COLUMNS/LINES are frozen at a "startup" size that differs from the live
    tty. get_size() must report the live tty size and follow resizes, NOT the
    (stale) env values. With the old easyansi/shutil-based implementation this
    returned the env values and broke redraws until the terminal was resized
    back to the original dimensions.
    """
    # sys.stdout must be the pty slave; do it via monkeypatch so it survives
    # pytest's fd-level capture (a plain assignment in a fixture gets clobbered).
    monkeypatch.setattr(sys, "stdout", pty.file)
    # env vars, as exported by some shells/terminals, frozen at a startup size
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("LINES", "24")

    # live tty starts at a different size than the env vars
    pty.resize(100, 30)
    assert ansi.get_size() == (100, 30)

    # simulate the user resizing the terminal; env stays frozen at 80x24
    pty.resize(60, 20)
    assert ansi.get_size() == (60, 20)

    # ...and resizing larger also tracks the live size
    pty.resize(120, 40)
    assert ansi.get_size() == (120, 40)


def test_get_size_without_env_tracks_live_tty(pty, monkeypatch):
    """Sanity: with no COLUMNS/LINES set, the live size is reported (unchanged path)."""
    monkeypatch.setattr(sys, "stdout", pty.file)
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)

    pty.resize(90, 28)
    assert ansi.get_size() == (90, 28)

    pty.resize(50, 15)
    assert ansi.get_size() == (50, 15)


def test_get_size_falls_back_when_stdout_is_not_a_tty(monkeypatch):
    """When stdout is not a tty, fall back to the previous easyansi behavior
    (which honors COLUMNS/LINES) rather than raising."""
    read_fd, write_fd = os.pipe()
    monkeypatch.setattr(sys, "stdout", os.fdopen(write_fd, "w"))
    monkeypatch.setenv("COLUMNS", "81")
    monkeypatch.setenv("LINES", "25")

    assert ansi.get_size() == (81, 25)
    os.close(read_fd)