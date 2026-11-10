"""The GUI's page, for the app's own window only (its user agent carries the per-launch secret: window.py), its
assets, and the health check `decomp` asks to find a running app and its version.
"""

from __future__ import annotations

import mimetypes
import secrets

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ... import __version__, hostenv
from .. import edition, window
from ..support import static_file
from . import App

# what the browser tab of 1.0.2 and older shows after updating into this version
OLD_PAGE = ("<!doctype html><meta charset=utf-8><title>decompdecomp</title>"
            "<body style='font:16px/1.5 system-ui;background:#0b0c0e;color:#e8e6e1;padding:3rem;max-width:46rem'>")
OLD_PAGE_LINUX = ("decompdecomp now opens in a window of its own (it just did, if it was updated): you can close this one. "
                  "Next time, use its app icon or run <code>decomp</code>.")
OLD_PAGE_WINDOWS = ("<p><b>This version of decompdecomp doesn't run on Windows.</b> Windows comes back in 1.0.4. Your projects "
                    "are safe, and update checks are now off, so 1.0.2 won't update itself again.</p>"
                    "<p>Go back to 1.0.2: in PowerShell, run</p><pre style='white-space:pre-wrap'>"
                    + hostenv.WSL_GO_BACK + "</pre><p>then start decompdecomp as before.</p>")

SIGN_IN = "Sign in with the link <code>decomp --web</code> prints: run it again for a new one."
LOGIN_SPENT = ("This login link has been used or is too old. Run <code>decomp --web</code> again for a new one.")


def register(app: App) -> None:
    mcp, build_id, web_login = app.mcp, app.build_id, app.web_login

    @mcp.custom_route("/", methods=["GET"])
    async def index(request: Request) -> Response:
        if not app.host_ok(request):
            return JSONResponse({"error": "bad host"}, status_code=403)
        if not app.admitted(request) and web_login is not None:  # signed out, or the app restarted since
            return HTMLResponse(OLD_PAGE + SIGN_IN, status_code=401)
        if not app.admitted(request):
            return HTMLResponse(OLD_PAGE + (OLD_PAGE_WINDOWS if hostenv.in_old_windows_install() else OLD_PAGE_LINUX), status_code=401)
        return HTMLResponse(static_file("index.html").decode(), headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/api/web-login", methods=["POST"])
    async def web_login_link(request: Request) -> Response:
        """A one-time login link, for `decomp --web` to print (weblogin.py)."""
        if (bad := app.guard(request, write=True)) is not None:
            return bad
        if not secrets.compare_digest(window.request_token(request), app.secret):  # a signed-in browser isn't `decomp`
            return JSONResponse({"error": "only `decomp --web` hands out login links"}, status_code=401)
        if web_login is None:
            return JSONResponse({"error": "decompdecomp isn't running in the web mode: start it with `decomp --web`"},
                                status_code=404)
        return JSONResponse({"url": f"http://127.0.0.1:{app.port}/login?code={web_login.new_code()}"})

    @mcp.custom_route("/login", methods=["GET"])
    async def login(request: Request) -> Response:
        """A one-time link from `decomp --web` becomes this browser's session; the code leaves the address bar."""
        if not app.host_ok(request):
            return JSONResponse({"error": "bad host"}, status_code=403)
        if web_login is None:
            return Response(status_code=404)
        session = web_login.redeem(request.query_params.get("code", ""))
        if session is None:
            return HTMLResponse(OLD_PAGE + LOGIN_SPENT, status_code=401)
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(web_login.cookie, session, httponly=True, samesite="strict", path="/")
        return r

    @mcp.custom_route("/assets/{name:path}", methods=["GET"])
    async def asset(request: Request) -> Response:
        if not app.host_ok(request):
            return Response(status_code=403)
        name = request.path_params["name"]
        data = static_file(name)
        if data is None:
            return Response(status_code=404)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return Response(data, media_type=ctype, headers={"Cache-Control": "no-cache"})

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "app": "decomp-wtf", "edition": edition.NAME, "version": __version__,
                             "build": build_id})
