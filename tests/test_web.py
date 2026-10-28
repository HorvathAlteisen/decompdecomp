"""The web mode (`decomp --web`): the app's own page in a browser on the same computer (a dev container reached
from VS Code's browser), without the mistakes that took the old browser tab away (n-delic/decompdecomp#7, #21):
the window's secret never reaches a browser, a link in the history or a log lets nobody in, and a cookie is this
app's alone."""

import pytest
from starlette.testclient import TestClient

from decompnet.app import window
from decompnet.app.engine import RomNetwork
from decompnet.app.server import build

PORT, SECRET = 6498, "s3cret-for-web-tests"
BASE = f"http://127.0.0.1:{PORT}"
DECOMP = {"User-Agent": f"{window.TOKEN_AGENT}{SECRET}", "X-Decomp": "1"}  # `decomp` itself (cli._call)
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/140 Electron/39 Code/1.125"}


def _app(home, web):
    (home / ".decomp").mkdir(parents=True, exist_ok=True)
    net = RomNetwork(home / ".decomp" / "decomp.db", home)
    mcp, _, security, _ = build(net, home / ".decomp", PORT, SECRET, web=web)
    return mcp.streamable_http_app(transport_security=security, host="127.0.0.1")


@pytest.fixture(scope="module")
def web_app(tmp_path_factory):
    return _app(tmp_path_factory.mktemp("web"), web=True)


def _browser(app, base=BASE):
    return TestClient(app, base_url=base, headers=BROWSER)


def _link(app) -> str:
    """A login link, asked for the way `decomp --web` asks the running app."""
    r = TestClient(app, base_url=BASE).post("/api/web-login", headers=DECOMP, json={})
    assert r.status_code == 200
    return r.json()["url"]


def test_a_login_link_lets_the_browser_in_and_then_only_its_cookie_counts(web_app):
    browser = _browser(web_app)
    assert browser.get("/api/state").status_code == 401
    r = browser.get(_link(web_app), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"  # the code leaves the address bar at once
    assert browser.get("/").status_code == 200
    assert browser.get("/api/state").status_code == 200


def test_a_login_link_works_once_so_the_history_or_a_log_lets_nobody_in(web_app):
    link = _link(web_app)
    assert _browser(web_app).get(link, follow_redirects=False).status_code == 303
    later = _browser(web_app)  # whoever finds the link afterwards: in the history, a log, a shell's scrollback
    r = later.get(link, follow_redirects=False)
    assert r.status_code == 401 and not r.cookies
    assert later.get("/api/state").status_code == 401


def test_a_login_link_nobody_used_is_worthless_after_two_minutes(web_app, monkeypatch):
    from decompnet.app import weblogin

    now = [1000.0]
    monkeypatch.setattr(weblogin, "clock", lambda: now[0])
    link = _link(web_app)
    now[0] += 121
    assert _browser(web_app).get(link, follow_redirects=False).status_code == 401
    fresh = _link(web_app)
    now[0] += 119
    assert _browser(web_app).get(fresh, follow_redirects=False).status_code == 303


def test_the_browsers_cookie_is_this_apps_alone_and_never_the_windows_secret(web_app):
    r = _browser(web_app).get(_link(web_app), follow_redirects=False)
    cookie = r.headers["set-cookie"]
    name, value = cookie.split(";")[0].split("=", 1)
    assert str(PORT) in name  # the installed app (6464) and a development copy (6474) never overwrite each other's
    assert value and SECRET not in cookie
    assert "httponly" in cookie.lower() and "samesite=strict" in cookie.lower()
    for old in ({"decomp_live": SECRET}, {name: SECRET}):  # the secret itself, as the 1.0.2 tab sent it
        sent = "; ".join(f"{k}={v}" for k, v in old.items())
        assert _browser(web_app).get("/api/state", headers={"Cookie": sent}).status_code == 401


def test_a_code_in_any_other_address_opens_nothing(web_app):
    """The old tab took its secret from ?k= on any page: here only /login reads a code, and turns it into a cookie."""
    code = _link(web_app).split("code=")[1]
    browser = _browser(web_app)
    for path in (f"/?code={code}", f"/api/state?code={code}", f"/?k={SECRET}"):
        assert browser.get(path, follow_redirects=False).status_code == 401


def test_the_desktop_app_has_no_browser_sign_in(tmp_path):
    desktop = _app(tmp_path, web=False)
    assert TestClient(desktop, base_url=BASE).post("/api/web-login", headers=DECOMP, json={}).status_code == 404
    assert _browser(desktop).get("/login?code=anything", follow_redirects=False).status_code == 404
    assert TestClient(desktop, base_url=BASE, headers=DECOMP).get("/api/state").status_code == 200  # its window


def test_a_forwarded_port_works_and_another_hosts_name_never_does(web_app):
    """VS Code forwards the container's port to whatever port is free on the user's computer, so the browser's Host
    names another port; a web page that rebinds its own name to 127.0.0.1 names its own host, and gets nothing."""
    forwarded = _browser(web_app, base="http://localhost:16498")
    code = _link(web_app).split("code=")[1]
    assert forwarded.get(f"/login?code={code}", follow_redirects=False).status_code == 303
    assert forwarded.get("/api/state").status_code == 200
    rebound = _browser(web_app, base="http://attacker.example:16498")
    rebound.cookies.update(forwarded.cookies)
    assert rebound.get("/api/state").status_code == 403
    assert rebound.get(f"/login?code={_link(web_app).split('code=')[1]}", follow_redirects=False).status_code == 403


def test_a_signed_in_browser_still_needs_the_pages_header_to_change_anything(web_app):
    """Another site's form can post to localhost with the cookie (SameSite aside); it can't add a header without
    the app's say-so (CORS), so writes keep asking for X-Decomp as they did for the window."""
    browser = _browser(web_app)
    browser.get(_link(web_app))
    assert browser.post("/api/log", json={"message": "from a form"}).status_code == 403
    assert browser.post("/api/log", json={"message": "from the page"}, headers={"X-Decomp": "1"}).status_code == 200


def test_only_decomp_hands_out_login_links_not_a_signed_in_browser(web_app):
    browser = _browser(web_app)
    browser.get(_link(web_app))
    assert browser.post("/api/web-login", json={}, headers={"X-Decomp": "1"}).status_code == 401



def test_a_browser_that_isnt_signed_in_is_told_how_to_sign_in(web_app):
    """After a restart (an update) the browser's session is gone: its page says how to get a new link, not that the
    app opens in a window."""
    page = _browser(web_app).get("/")
    assert page.status_code == 401 and "decomp --web" in page.text and "window of its own" not in page.text


# --- `decomp --web` itself, as a process of its own -------------------------------------------------------------

def _start(tmp_path, *args, env_extra=None):
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k not in ("DECOMP_WINDOW", "DECOMP_WEB")}  # no window by default
    env.update(DECOMP_HOME=str(tmp_path / "home"), HOME=str(tmp_path), DECOMP_PORT=str(CLI_PORT), **(env_extra or {}))
    return subprocess.Popen([sys.executable, "-m", "decompnet.app.cli", *args], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _login_line(proc, seconds=60):
    import select
    import time

    seen, end = [], time.time() + seconds
    while time.time() < end:
        if proc.poll() is not None and not select.select([proc.stdout], [], [], 0)[0]:
            break
        if select.select([proc.stdout], [], [], 0.2)[0]:
            line = proc.stdout.readline()
            seen.append(line)
            if "/login?code=" in line:
                return line.strip().split()[-1], "".join(seen)
    raise AssertionError("no login link:\n" + "".join(seen))


CLI_PORT = 6597


@pytest.fixture
def web_process(tmp_path):
    proc = _start(tmp_path, "--web")
    try:
        yield proc, tmp_path
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def test_decomp_web_starts_without_a_window_and_prints_a_link_never_the_secret(web_process):
    import json

    import httpx

    proc, tmp = web_process
    link, said = _login_line(proc)
    secret = json.loads((tmp / "home" / ".decomp" / "server.json").read_text())["secret"]
    assert secret not in said
    with httpx.Client(base_url=f"http://127.0.0.1:{CLI_PORT}", headers=BROWSER) as browser:
        assert browser.get(link, follow_redirects=True).status_code == 200  # signed in, on the page
        assert browser.get("/api/state").status_code == 200


def test_running_decomp_web_again_prints_a_fresh_link_to_the_running_app(web_process):
    import httpx

    proc, tmp = web_process
    first, _ = _login_line(proc)
    again = _start(tmp, "--web")
    second, _ = _login_line(again)
    assert again.wait(timeout=30) == 0 and second != first
    with httpx.Client(base_url=f"http://127.0.0.1:{CLI_PORT}", headers=BROWSER) as browser:
        assert browser.get(second, follow_redirects=True).status_code == 200


def test_after_restarting_into_an_update_it_is_still_in_the_web_mode(tmp_path):
    """updates.restart becomes the new version with `--port` alone and this process's environment: what --web set
    there (DECOMP_WEB) must bring it back without a window and with a link, or a server is left with neither."""
    import json

    port = CLI_PORT + 1
    restart = json.dumps({"port": port, "secret": "kept-across-the-update", "window": False})
    proc = _start(tmp_path, "--port", str(port), env_extra={"DECOMP_WEB": "1", "DECOMP_RESTART": restart})
    try:
        link, said = _login_line(proc)
        assert f"127.0.0.1:{port}/login?code=" in link and "kept-across-the-update" not in said
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def test_the_web_mode_answers_on_this_computer_only(web_process):
    """Meant for a browser on the same computer (VS Code tunnels to the container's localhost): nothing listens on
    the container's or server's other addresses, so a published port or a neighbour on the network gets nothing."""
    import socket

    proc, _ = web_process
    _login_line(proc)
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # (no packet is sent: this only picks the address other machines see)
        address = probe.getsockname()[0]
    except OSError:
        address = ""
    finally:
        probe.close()
    if not address or address.startswith("127."):
        pytest.skip("this computer has no address besides its own loopback")
    with pytest.raises(OSError):
        socket.create_connection((address, CLI_PORT), timeout=2).close()
