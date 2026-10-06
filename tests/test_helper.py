"""Unit tests for src/helper/helper.py (no DSM required).

Run:  python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "src", "helper", "helper.py")

VAR = tempfile.mkdtemp(prefix="torrserver-var-")
os.environ["TORRSERVER_DSM_VAR"] = VAR

spec = importlib.util.spec_from_file_location("helper", HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeTorrServer:
    """Mimics TorrServer's /settings: 'set' replaces the whole object."""

    def __init__(self, status=200):
        self.state = {
            "CacheSize": 134217728,
            "UseDisk": True,
            "TorrentsSavePath": "/old",
            "ConnectionsLimit": 50,
        }
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append(body)
                if status != 200:
                    self.send_response(status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if body["action"] == "get":
                    out = json.dumps(outer.state).encode()
                else:
                    outer.state.clear()
                    outer.state.update(body["sets"])
                    out = b""
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Base(unittest.TestCase):
    def setUp(self):
        for name in os.listdir(VAR):
            path = os.path.join(VAR, name)
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        # Deterministic, closed HTTPS port so only the HTTP endpoint matters.
        h.write_file(h.HTTPS_PORT_FILE, str(free_port()))
        h._PRIVILEGE_CACHE["time"] = 0.0


class CachePathTests(Base):
    def test_set_preserves_other_settings(self):
        ts = FakeTorrServer()
        self.addCleanup(ts.close)
        status, _ = h.set_cache_path("/volume1/TS/Cache", ts.port)
        self.assertEqual(status, "applied")
        self.assertEqual(ts.state["CacheSize"], 134217728)
        self.assertTrue(ts.state["UseDisk"])
        self.assertEqual(ts.state["ConnectionsLimit"], 50)
        self.assertEqual(ts.state["TorrentsSavePath"], "/volume1/TS/Cache")
        self.assertEqual([c["action"] for c in ts.calls], ["get", "set"])

    def test_unchanged_value_sends_no_set(self):
        ts = FakeTorrServer()
        self.addCleanup(ts.close)
        h.set_cache_path("/x", ts.port)
        ts.calls.clear()
        h.set_cache_path("/x", ts.port)
        self.assertEqual([c["action"] for c in ts.calls], ["get"])

    def test_key_case_is_respected(self):
        ts = FakeTorrServer()
        self.addCleanup(ts.close)
        ts.state.clear()
        ts.state.update({"torrentsSavePath": "/x", "CacheSize": 1})
        h.set_cache_path("/y", ts.port)
        self.assertEqual(ts.state.get("torrentsSavePath"), "/y")
        self.assertNotIn("TorrentsSavePath", ts.state)

    def test_redirect_is_not_success(self):
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(307)
                self.send_header("Location", "https://127.0.0.1:1/")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        ok, _data, reachable = h.torrserver_request({"action": "get"}, srv.server_address[1])
        self.assertFalse(ok)
        self.assertTrue(reachable)

    def test_not_running_is_queued_then_applied(self):
        status, _ = h.set_cache_path("/volume1/TS/Cache", free_port())
        self.assertEqual(status, "pending")
        self.assertEqual(h.read_file(h.CACHE_PENDING_FILE), "/volume1/TS/Cache")

        ts = FakeTorrServer()
        self.addCleanup(ts.close)
        h.write_file(h.PORT_FILE, str(ts.port))
        self.assertTrue(h.apply_pending_cache_path())
        self.assertEqual(ts.state["TorrentsSavePath"], "/volume1/TS/Cache")
        self.assertEqual(ts.state["ConnectionsLimit"], 50)
        self.assertFalse(os.path.exists(h.CACHE_PENDING_FILE))

    def test_server_error_is_not_queued(self):
        ts = FakeTorrServer(status=500)
        self.addCleanup(ts.close)
        status, _ = h.set_cache_path("/x", ts.port)
        self.assertEqual(status, "error")
        self.assertFalse(os.path.exists(h.CACHE_PENDING_FILE))


class AccountTests(Base):
    def test_other_accounts_kept_and_primary_first(self):
        h.write_file(h.ACCS_FILE, json.dumps({"alice": "pw1", "kid": "pw2"}))
        h.save_account("bob", "pw3", previous_username="alice")
        accounts = json.load(open(h.ACCS_FILE))
        self.assertEqual(accounts, {"bob": "pw3", "kid": "pw2"})
        self.assertEqual(next(iter(accounts)), "bob")

    def test_file_mode_is_0600(self):
        h.save_account("bob", "pw")
        self.assertEqual(os.stat(h.ACCS_FILE).st_mode & 0o777, 0o600)

    def test_username_validation(self):
        self.assertTrue(h.valid_username("bob"))
        self.assertFalse(h.valid_username("a:b"))
        self.assertFalse(h.valid_username("a\nb"))
        self.assertFalse(h.valid_username(""))

    def test_volume_path_validation(self):
        self.assertTrue(h.valid_volume_path("/volume1/certs/a.pem"))
        self.assertFalse(h.valid_volume_path("/volume1/../etc/shadow"))
        self.assertFalse(h.valid_volume_path("/etc/shadow"))


class SaveSettingsTests(Base):
    BASE = dict(port="8090", torrserver_dir="/volume1/TS", https="0",
                https_port="8091", ssl_mode="self", auth="0")

    def setUp(self):
        super().setUp()
        self.ts = FakeTorrServer()
        self.addCleanup(self.ts.close)
        self.patches = {
            "has_privileged_access": lambda use_cache=True: True,
            "prepare_torrserver_directory": lambda d: (True, ""),
            "get_dsm_certificates": lambda: [],
            "cache_browser_path": lambda p: p,
            "is_port_in_use": lambda n, allowed_ports=None: False,
            "get_port": lambda: self.ts.port,
        }
        self.saved = {k: getattr(h, k) for k in self.patches}
        for k, v in self.patches.items():
            setattr(h, k, v)
        self.addCleanup(lambda: [setattr(h, k, v) for k, v in self.saved.items()])

    def save(self, **overrides):
        data = dict(self.BASE, **overrides)
        return h.save_settings({k: [v] for k, v in data.items()})

    def test_valid_save_writes_files(self):
        ok, message = self.save()
        self.assertTrue(ok, message)
        self.assertEqual(h.read_file(h.PORT_FILE), "8090")
        self.assertEqual(h.read_file(h.TORRSERVER_DIR_FILE), "/volume1/TS")

    def test_rejected_input_writes_nothing(self):
        cases = [
            dict(torrserver_dir="/volume1/My Data"),
            dict(auth="1", username="a:b", password="x"),
            dict(auth="1", username="u", password=""),
            dict(port="80"),
            dict(ssl_mode="manual", ssl_cert="/volume1/../etc/shadow", ssl_key="/volume1/k"),
        ]
        h.os.unlink(h.HTTPS_PORT_FILE)
        for case in cases:
            ok, message = self.save(**case)
            self.assertFalse(ok, case)
        self.assertFalse(os.path.exists(h.PORT_FILE))

    def test_busy_https_port_only_matters_when_https_on(self):
        h.is_port_in_use = lambda n, allowed_ports=None: n == 8091
        self.assertTrue(self.save()[0])
        self.assertFalse(self.save(https="1")[0])

    def test_saves_when_torrserver_is_down(self):
        self.ts.close()
        h.get_port = lambda: free_port()
        ok, message = self.save()
        self.assertTrue(ok, message)
        self.assertEqual(h.read_file(h.CACHE_PENDING_FILE), "/volume1/TS/Cache")


class LogRotationTests(Base):
    def test_both_logs_rotated(self):
        old = h.LOG_MAX_SIZE
        h.LOG_MAX_SIZE = 100
        self.addCleanup(lambda: setattr(h, "LOG_MAX_SIZE", old))
        for path in h.ROTATED_LOGS:
            with open(path, "w") as f:
                f.write("x" * 500)
        h.rotate_log_if_needed()
        for path in h.ROTATED_LOGS:
            self.assertEqual(os.path.getsize(path), 0)
            self.assertTrue(os.path.exists(path + ".1"))

    def test_log_names_whitelisted(self):
        self.assertIsNone(h.get_log_path("../../etc/passwd"))
        self.assertIn("service.log", h.LOG_FILES)


class LocalizeTests(Base):
    def setUp(self):
        super().setUp()
        h.write_file(h.LANGUAGE_FILE, "ru")

    def test_text_and_safe_attributes_are_translated(self):
        out = h.localize_html('<span>Status</span><input placeholder="Browse">')
        self.assertIn("<span>Статус</span>", out)
        self.assertIn('placeholder="Обзор"', out)

    def test_user_values_and_identifiers_are_untouched(self):
        page = (
            '<input name="torrserver_dir" value="/volume1/Browse/Status">'
            '<a href="./Status" id="Browse">x</a>'
            '<button onclick="openTorrServerBrowser()">Browse</button>'
            '<script>function openTorrServerBrowser(){ var a = "Browse"; }</script>'
            '<img src="data:image/png;base64,AAACPUAAA">'
            '<style>.Status{content:"Browse"}</style>'
        )
        out = h.localize_html(page)
        self.assertIn('value="/volume1/Browse/Status"', out)
        self.assertIn('href="./Status" id="Browse"', out)
        self.assertIn('onclick="openTorrServerBrowser()"', out)
        self.assertIn("function openTorrServerBrowser()", out)
        self.assertIn(">Обзор</button>", out)           # visible text is translated
        self.assertIn('var a = "Обзор"', out)           # JS string literal is translated
        self.assertIn("data:image/png;base64,AAACPUAAA", out)
        self.assertIn('.Status{content:"Browse"}', out)

    def test_markup_keys_are_translated(self):
        key = next(k for k in h.load_locale("en") if "<b>" in k)
        out = h.localize_html("<p>" + key + "</p>")
        self.assertNotIn(key, out)

    def test_english_is_identity(self):
        h.write_file(h.LANGUAGE_FILE, "en")
        page = '<span>Status</span><input value="Browse">'
        self.assertEqual(h.localize_html(page), page)


class HttpTests(Base):
    @classmethod
    def setUpClass(cls):
        # These tests are about request handling, so act as a logged-in admin.
        cls._orig_check = h.check_dsm_session
        h.check_dsm_session = lambda cookie, token, ip, host="": ("admin", "")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), h.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        h.check_dsm_session = cls._orig_check
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, path, method="GET", data=None, headers=None):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=data,
            method=method, headers=headers or {})
        opener = urllib.request.build_opener(h._NoRedirect())
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def raw(self, payload):
        with socket.create_connection(("127.0.0.1", self.port)) as s:
            s.settimeout(3)
            s.sendall(payload)
            return s.recv(200).split(b"\r\n")[0].decode()

    def test_helper_binds_loopback_only(self):
        self.assertEqual(h.HOST, "127.0.0.1")

    def test_host_header_is_sanitised(self):
        original = h.main_page
        h.main_page = lambda host: "HOST=" + host
        self.addCleanup(lambda: setattr(h, "main_page", original))
        self.assertIn("HOST=nas.local", self.request("/", headers={"Host": "nas.local:5001"})[1])
        self.assertIn("HOST=[fe80::1]", self.request("/", headers={"Host": "[fe80::1]:5001"})[1])
        body = self.request("/", headers={"Host": '"><script>alert(1)</script>'})[1]
        self.assertNotIn("<script>", body)

    def test_csrf_origin_checks(self):
        form = b"language=ru"
        host = {"Host": "nas.local"}
        self.assertEqual(self.request("/language", "POST", form, host)[0], 403)
        self.assertEqual(self.request("/language", "POST", form, dict(host, Origin="https://evil.example"))[0], 403)
        self.assertEqual(self.request("/language", "POST", form, dict(host, Origin="null"))[0], 403)
        self.assertEqual(self.request("/language", "POST", form, dict(host, Origin="https://nas.local:5001"))[0], 302)
        self.assertEqual(self.request("/language", "POST", form, dict(host, Referer="https://nas.local/x"))[0], 302)

    def test_body_limits(self):
        headers = {"Host": "a", "Origin": "http://a"}
        self.assertEqual(self.request("/language", "POST", b"a" * (h.MAX_POST_BYTES + 1), headers)[0], 413)
        self.assertTrue(self.raw(b"POST /language HTTP/1.1\r\nHost: a\r\nOrigin: http://a\r\nContent-Length: abc\r\n\r\n").endswith("400 Bad Request"))
        self.assertTrue(self.raw(b"POST /language HTTP/1.1\r\nHost: a\r\nOrigin: http://a\r\nContent-Length: -5\r\n\r\n").endswith("400 Bad Request"))

    def test_log_name_whitelist(self):
        self.assertEqual(self.request("/read-log?name=../../etc/passwd")[0], 400)


class AuthTests(Base):
    """DSM session check. A stub authenticate.cgi stands in for DSM's."""

    CGI_TEMPLATE = """#!/bin/sh
# Records what the helper passes in, then behaves like DSM's authenticate.cgi:
# prints the user only for the session cookie "id=GOOD" (plus token "TOK" when
# a token is required).
echo "cookie=$HTTP_COOKIE token=$HTTP_X_SYNO_TOKEN addr=$REMOTE_ADDR" >> "{log}"
case "$HTTP_COOKIE" in
  *id=GOOD*)
    if [ -n "{need_token}" ] && [ "$HTTP_X_SYNO_TOKEN" != "{need_token}" ]; then exit 0; fi
    echo "{user}" ;;
  *id=HEADERS*) printf 'Content-Type: text/plain\\n\\n{user}\\n' ;;
esac
"""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), h.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        super().setUp()
        h._AUTH_CACHE.clear()
        self.tmp = tempfile.mkdtemp(prefix="cgi-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "calls.log")
        self.saved = (h.AUTH_CGI_PATHS, h.is_dsm_admin, h.main_page)
        self.addCleanup(lambda: (setattr(h, "AUTH_CGI_PATHS", self.saved[0]),
                                 setattr(h, "is_dsm_admin", self.saved[1]),
                                 setattr(h, "main_page", self.saved[2])))
        h.main_page = lambda host: "SECRET-SETTINGS-PAGE"
        h.is_dsm_admin = lambda user: user == "admin"
        self.install_cgi(user="admin")

    def install_cgi(self, user="admin", need_token=""):
        path = os.path.join(self.tmp, "authenticate.cgi")
        with open(path, "w") as f:
            f.write(self.CGI_TEMPLATE.format(log=self.log, user=user, need_token=need_token))
        os.chmod(path, 0o755)
        h.AUTH_CGI_PATHS = (os.path.join(self.tmp, "missing.cgi"), path)
        h._AUTH_CACHE.clear()

    def get(self, path="/", headers=None, method="GET", data=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path),
                                     headers=dict({"Host": "nas.local"}, **(headers or {})),
                                     method=method, data=data)
        try:
            with urllib.request.build_opener(h._NoRedirect()).open(req, timeout=5) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), e.headers

    def calls(self):
        return open(self.log).read() if os.path.exists(self.log) else ""

    # ---- the bug that was reported: no login at all
    def test_no_cookie_gets_nothing(self):
        status, body, _ = self.get()
        self.assertEqual(status, 403)
        self.assertNotIn("SECRET-SETTINGS-PAGE", body)
        self.assertEqual(self.calls(), "")  # not even worth running the CGI

    def test_every_route_and_method_is_protected(self):
        for path in ("/", "/settings", "/logs", "/browse?path=/", "/read-log?name=TorrServer.log",
                     "/download-log?name=TorrServer.log", "/permissions", "/recommendations"):
            self.assertEqual(self.get(path)[0], 403, path)
        for path in ("/settings", "/restart", "/language"):
            status, _, _ = self.get(path, method="POST", data=b"x=1",
                                    headers={"Origin": "http://nas.local"})
            self.assertEqual(status, 403, path)

    def test_forged_cookie_is_rejected(self):
        self.assertEqual(self.get(headers={"Cookie": "id=FORGED"})[0], 403)

    def test_valid_admin_session_is_served(self):
        status, body, headers = self.get(headers={"Cookie": "id=GOOD"})
        self.assertEqual((status, body), (200, "SECRET-SETTINGS-PAGE"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])

    def test_non_admin_user_is_rejected(self):
        self.install_cgi(user="alice")
        self.assertEqual(self.get(headers={"Cookie": "id=GOOD"})[0], 403)

    def test_denial_page_leaks_nothing(self):
        _, body, _ = self.get()
        self.assertNotIn("authenticate", body.lower())
        self.assertNotIn("/usr/syno", body)

    # ---- fail closed
    def test_missing_cgi_fails_closed(self):
        h.AUTH_CGI_PATHS = (os.path.join(self.tmp, "nope.cgi"),)
        self.assertEqual(self.get(headers={"Cookie": "id=GOOD"})[0], 403)

    def test_crashing_cgi_fails_closed(self):
        path = os.path.join(self.tmp, "boom.cgi")
        with open(path, "w") as f:
            f.write("#!/bin/sh\nexit 3\n")
        os.chmod(path, 0o755)
        h.AUTH_CGI_PATHS = (path,)
        self.assertEqual(self.get(headers={"Cookie": "id=GOOD"})[0], 403)

    def test_hostile_cgi_output_is_not_trusted(self):
        self.assertEqual(h.parse_cgi_user("admin\n"), "admin")
        self.assertEqual(h.parse_cgi_user("admin\nroot"), "admin")      # first line only
        self.assertEqual(h.parse_cgi_user("DOMAIN\\\\bob"), "DOMAIN\\\\bob")
        for evil in ("", "   ", "../../etc", "<script>alert(1)</script>", "a:b", "x" * 200):
            self.assertEqual(h.parse_cgi_user(evil), "", repr(evil))

    # ---- what DSM's CGI actually receives
    def test_cookie_token_and_client_ip_reach_the_cgi(self):
        self.install_cgi(need_token="TOK")
        status, _, _ = self.get(headers={"Cookie": "id=GOOD", "X-SYNO-TOKEN": "TOK", "X-Real-IP": "192.168.1.50"})
        self.assertEqual(status, 200)
        self.assertIn("cookie=id=GOOD token=TOK addr=192.168.1.50", self.calls())

    def test_token_required_by_dsm_is_enforced(self):
        self.install_cgi(need_token="TOK")
        self.assertEqual(self.get(headers={"Cookie": "id=GOOD"})[0], 403)
        self.assertEqual(self.get(headers={"Cookie": "id=GOOD", "X-SYNO-TOKEN": "WRONG"})[0], 403)

    def test_cgi_that_prints_headers_first_is_understood(self):
        self.assertEqual(self.get(headers={"Cookie": "id=HEADERS"})[0], 200)

    def test_spoofed_ip_header_is_sanitised(self):
        self.get(headers={"Cookie": "id=GOOD", "X-Real-IP": "1.2.3.4; rm -rf /"})
        self.assertNotIn("rm -rf", self.calls())

    # ---- SynoToken hand-over from the DSM desktop iframe URL
    def test_token_in_url_becomes_cookie_and_clean_redirect(self):
        self.install_cgi(need_token="TOK")
        status, _, headers = self.get("/settings?SynoToken=TOK", headers={
            "Cookie": "id=GOOD", "X-Forwarded-Proto": "https"})
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "./settings")
        cookie = headers["Set-Cookie"]
        self.assertIn("TorrServerSynoToken=TOK", cookie)
        for flag in ("HttpOnly", "SameSite=Strict", "Secure", "Path=/webman/3rdparty/TorrServer/"):
            self.assertIn(flag, cookie)

    def test_wrong_token_in_url_is_denied_without_cookie(self):
        self.install_cgi(need_token="TOK")
        status, _, headers = self.get("/?SynoToken=WRONG", headers={"Cookie": "id=GOOD"})
        self.assertEqual(status, 403)
        self.assertIsNone(headers.get("Set-Cookie"))

    def test_token_cookie_authenticates_followup_requests(self):
        self.install_cgi(need_token="TOK")
        status, body, _ = self.get("/settings", headers={"Cookie": "id=GOOD; TorrServerSynoToken=TOK"})
        self.assertEqual(status, 200)

    def test_malformed_token_is_ignored(self):
        self.install_cgi(need_token="")
        self.get(headers={"Cookie": "id=GOOD", "X-SYNO-TOKEN": "a b;c"})
        self.assertIn("token= ", self.calls())

    # ---- caching
    def test_valid_sessions_are_cached_briefly(self):
        for _ in range(3):
            self.assertEqual(self.get(headers={"Cookie": "id=GOOD"})[0], 200)
        self.assertEqual(self.calls().count("\n"), 1)

    def test_denials_are_remembered_only_for_a_moment(self):
        # A user who has just logged in must not stay locked out.
        self.assertEqual(self.get(headers={"Cookie": "id=NEW"})[0], 403)
        now = time.monotonic()
        (expires, user, _reason), = h._AUTH_CACHE.values()
        self.assertEqual(user, "")
        self.assertLessEqual(expires - now, h.AUTH_DENIED_CACHE_SECONDS + 0.5)
        self.assertLess(h.AUTH_DENIED_CACHE_SECONDS, h.AUTH_CACHE_SECONDS)

    # ---- admin group membership
    def test_admin_group_membership(self):
        h.is_dsm_admin = self.saved[1]
        import grp, pwd
        real_grp, real_pwd, real_list = grp.getgrnam, pwd.getpwnam, os.getgrouplist
        group = type("G", (), {"gr_mem": ["root_like"], "gr_gid": 101})()
        entry = lambda gid: type("P", (), {"pw_gid": gid})()
        try:
            grp.getgrnam = lambda name: group
            pwd.getpwnam = lambda name: entry(100)
            os.getgrouplist = lambda name, gid: [100, 101] if name == "nested" else [100]
            self.assertTrue(h.is_dsm_admin("root_like"))        # listed member
            self.assertTrue(h.is_dsm_admin("nested"))           # member through NSS
            self.assertFalse(h.is_dsm_admin("alice"))
            pwd.getpwnam = lambda name: entry(101)
            self.assertTrue(h.is_dsm_admin("primary"))          # primary group
            grp.getgrnam = lambda name: (_ for _ in ()).throw(KeyError(name))
            self.assertFalse(h.is_dsm_admin("anyone"))          # no such group: fail closed
        finally:
            grp.getgrnam, pwd.getpwnam, os.getgrouplist = real_grp, real_pwd, real_list


if __name__ == "__main__":
    unittest.main()
