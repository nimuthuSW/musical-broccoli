"""Run tsh in a pseudo-terminal and type submitted scores into it.

The director keeps using tsh in their own terminal as normal: everything they
type goes to tsh and everything tsh prints comes back. Submitted scores are
queued and only typed in when the director isn't halfway through a line and
hasn't pressed a key for a moment, so the two never get mixed together.
"""

import fcntl
import os
import pty
import queue
import signal
import struct
import sys
import termios
import threading
import time
import tty


class Tsh:
    def __init__(self, argv, cwd, interactive=True, idle_seconds=1.0, line_delay=0.3):
        self.argv = argv
        self.cwd = cwd
        self.interactive = interactive and sys.stdin.isatty()
        self.idle_seconds = idle_seconds
        self.line_delay = line_delay
        self.pid = None
        self.fd = None
        self.output = bytearray()  # recent tsh output, for tests and debugging
        self._queue = queue.Queue()
        self._lock = threading.Lock()  # held while typing or forwarding keys
        self._typed = 0  # characters the director has typed on the current line
        self._last_key = 0.0
        self._saved_tty = None

    def start(self):
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(self.cwd)
                os.execvp(self.argv[0], self.argv)
            finally:
                os._exit(127)
        self.pid, self.fd = pid, fd
        threading.Thread(target=self._pump_output, daemon=True).start()
        threading.Thread(target=self._inject_loop, daemon=True).start()
        if self.interactive:
            self._sync_window_size()
            signal.signal(signal.SIGWINCH, lambda *_: self._sync_window_size())
            self._saved_tty = termios.tcgetattr(0)
            tty.setraw(0)
            threading.Thread(target=self._pump_keys, daemon=True).start()

    def submit(self, lines):
        """Queue lines to be typed into tsh, each followed by Enter."""
        self._queue.put(list(lines))

    def wait(self):
        """Block until tsh exits; restore the terminal; return its exit status."""
        _, status = os.waitpid(self.pid, 0)
        if self._saved_tty is not None:
            termios.tcsetattr(0, termios.TCSADRAIN, self._saved_tty)
        return os.waitstatus_to_exitcode(status)

    def _pump_output(self):
        while True:
            try:
                data = os.read(self.fd, 4096)
            except OSError:
                return
            if not data:
                return
            self.output += data
            del self.output[:-65536]
            if self.interactive:
                os.write(1, data)

    def _pump_keys(self):
        while True:
            data = os.read(0, 1024)
            if not data:
                return
            with self._lock:
                os.write(self.fd, data)
                self._last_key = time.monotonic()
                for b in data:
                    if b in (0x0d, 0x0a, 0x03, 0x15):  # Enter, Ctrl-C, Ctrl-U
                        self._typed = 0
                    elif b in (0x7f, 0x08):  # Backspace
                        self._typed = max(0, self._typed - 1)
                    elif b >= 0x20:
                        self._typed += 1

    def _director_busy(self):
        return self._typed > 0 or time.monotonic() - self._last_key < self.idle_seconds

    def _inject_loop(self):
        while True:
            lines = self._queue.get()
            while True:
                with self._lock:
                    if not self._director_busy():
                        for line in lines:
                            os.write(self.fd, line.encode() + b"\r")
                            time.sleep(self.line_delay)
                        break
                time.sleep(0.2)

    def _sync_window_size(self):
        size = fcntl.ioctl(0, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)
