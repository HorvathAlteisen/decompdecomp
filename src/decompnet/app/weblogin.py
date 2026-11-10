"""The web mode's sign-in (`decomp --web`): the app's page in a browser on the same computer, such as VS Code's
browser in a dev container, where no window can carry the secret in its user agent.

The old browser tab was taken away for good reasons (n-delic/decompdecomp#7, #21), and this mode keeps clear of
each: the window's secret never reaches a browser (`decomp` asks the running app for a link, server.json stays
the user's own file); a link is a one-time code, so the history or a log that kept it lets nobody in; and the
browser's cookie carries a session of its own, under a name of this port's, so two apps on one computer never
overwrite each other's.
"""

from __future__ import annotations

import secrets
import threading
import time

COOKIE_PREFIX = "decomp_web_"
CODE_SECONDS = 120  # long enough to click the link `decomp --web` printed, too short to matter in a log
clock = time.monotonic
LOCAL_NAMES = ("localhost", "127.0.0.1", "[::1]")


def local_host(host: str) -> bool:
    """A Host header naming this computer itself, on any port (a forwarded one, in the web mode)."""
    name, _, port = host.rpartition(":") if not host.endswith("]") else (host, "", "")
    if not name:
        name, port = host, ""
    return name in LOCAL_NAMES and (port == "" or port.isdigit())


class WebLogin:
    """One-time codes `decomp` hands out, and the browser sessions they turn into."""

    def __init__(self, port: int):
        self.port = port
        self.cookie = f"{COOKIE_PREFIX}{port}"
        self._codes: dict[str, float] = {}  # code: when it stops working
        self._sessions: set[str] = set()
        self._lock = threading.Lock()

    def new_code(self) -> str:
        code = secrets.token_urlsafe(24)
        with self._lock:
            self._codes = {c: end for c, end in self._codes.items() if end > clock()}  # spent ones go
            self._codes[code] = clock() + CODE_SECONDS
        return code

    def redeem(self, code: str) -> str | None:
        """A new session for a code that's still good, or None."""
        with self._lock:
            end = self._codes.pop(code, None)
            if end is None or end <= clock():
                return None
            session = secrets.token_urlsafe(32)
            self._sessions.add(session)
            return session

    def admits(self, request) -> bool:
        """Whether the request carries one of this app's browser sessions."""
        given = request.cookies.get(self.cookie, "")
        with self._lock:
            return bool(given) and any(secrets.compare_digest(given, s) for s in self._sessions)
