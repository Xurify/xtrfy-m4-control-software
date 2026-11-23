"""Local backend for the M4 app: owns the HID connection and serves the web UI on 127.0.0.1."""
import base64
import uuid
import subprocess
import sys
import traceback
import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from compx import Compx, ProtocolError, PID_WIRED
from history import History, DIR as DATA_DIR, SRC_APP, SRC_MOUSE, SRC_OFFLINE, SRC_RESTORE
from m4config import (Config, BUTTON_ACTIONS, PROFILE_LEN, PAGE_LEN, MACRO_START, MACRO_LEN,
                      REGIONS, describe_changes, read_profile, write_diff, validate_backup, button_label, dpi_snap)

PORT = 47813
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PREFS = os.path.join(DATA_DIR, "prefs.json")
SETUPS = os.path.join(DATA_DIR, "setups.json")
# The mouse exactly as this app first found it, so "Your original settings" can always put it back.
ORIGINAL = os.path.join(DATA_DIR, "original.m4")
LOG = os.path.join(DATA_DIR, "helper.log")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STARTUP_LINK = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup",
                            "Xtrfy M4 helper.lnk")


def log_error(where):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {where}\n{traceback.format_exc()}\n")
    except OSError:
        pass


def pythonw():
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return exe if os.path.isfile(exe) else sys.executable


def set_autostart(on):
    if not on:
        try:
            os.remove(STARTUP_LINK)
        except FileNotFoundError:
            pass
        return
    agent = os.path.join(APP_DIR, "xtrfy_m4_helper.pyw")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:M4_LINK);"
          "$s.TargetPath=$env:M4_EXE;$s.Arguments='\"'+$env:M4_AGENT+'\"';"
          "$s.WorkingDirectory=$env:M4_DIR;$s.Description='Keeps Xtrfy M4 auto lighting and history running';$s.Save()")
    env = dict(os.environ, M4_LINK=STARTUP_LINK, M4_EXE=pythonw(), M4_AGENT=agent, M4_DIR=APP_DIR)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, check=True,
                   creationflags=0x08000000, timeout=20)
LED_OFF = 4
LED_STATIC = 2
# Lowest brightness level that still drowns out the charging blink, found by testing on this mouse.
COVER_BRIGHTNESS = 2
SRC_AUTO = "Auto lighting"
SRC_FACTORY = "Factory reset"
OP_FACTORY_RESET = 0x09


def hexcolor(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def config_to_dict(c):
    return {
        "polling": c.polling, "stage_count": c.stage_count, "active_stage": c.active_stage, "lod": c.lod,
        "dpi": c.dpi, "colors": [hexcolor(x) for x in c.colors],
        "led_mode": c.led_mode, "led_color": hexcolor(c.led_color), "led_speed": c.led_speed,
        "led_brightness": c.led_brightness, "buttons": [button_label(b) for b in c.buttons],
        "debounce": c.debounce, "motion_sync": c.motion_sync, "sleep_s": c.sleep_s,
        "angle_snap": c.angle_snap, "ripple": c.ripple,
    }


class Prefs:
    def __init__(self):
        try:
            with open(PREFS, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PREFS, "w", encoding="utf-8") as f:
            json.dump(self.data, f)


class Setups:
    """Named copies of the mouse's settings, kept on this PC."""

    def __init__(self):
        try:
            with open(SETUPS, encoding="utf-8") as f:
                self.items = json.load(f)
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETUPS, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=1)

    def add(self, name, image):
        item = {"id": uuid.uuid4().hex[:10], "name": name.strip()[:40] or "Untitled", "image": image.hex(),
                "created": time.strftime("%Y-%m-%d %H:%M")}
        self.items.append(item)
        self._save()
        return item

    def get(self, sid):
        return next((x for x in self.items if x["id"] == sid), None)

    def update(self, sid, name=None, image=None):
        item = self.get(sid)
        if not item:
            raise KeyError("No such setup")
        if name is not None:
            item["name"] = name.strip()[:40] or item["name"]
        if image is not None:
            item["image"] = image.hex()
        self._save()

    def delete(self, sid):
        self.items = [x for x in self.items if x["id"] != sid]
        self._save()

    def summary(self, current):
        out = []
        for x in self.items:
            c = Config.parse(bytes.fromhex(x["image"]))
            out.append({"id": x["id"], "name": x["name"], "created": x["created"],
                        "active": current is not None and bytes.fromhex(x["image"]) == current,
                        "dpi": c.dpi[c.active_stage], "colour": hexcolor(c.colors[c.active_stage]),
                        "polling": c.polling})
        return out


class Mouse:
    """All HID traffic goes through here, serialised by one lock, so the poller and requests never interleave."""

    def __init__(self):
        self.lock = threading.RLock()
        self.changed = threading.Condition()
        self.dev = None
        self.mem = None
        self.tail = None
        self.status = "searching"
        self.battery = None
        self.version = 0
        self.history = History()
        self.prefs = Prefs()
        self.setups = Setups()
        self.popup = None
        # Settings changed while the mouse sleeps; written as soon as it wakes.
        self.queued = None
        self.last_online_check = 0.0
        self.last_battery = 0.0

    def bump(self):
        with self.changed:
            self.version += 1
            self.changed.notify_all()

    def state(self):
        with self.lock:
            s = {"version": self.version, "status": self.status, "autostart": os.path.isfile(STARTUP_LINK),
                 "connection": ("cable" if self.dev.wired else "receiver") if self.dev else None,
                 "battery": self.battery, "config": None}
            shown = self.current()
            if shown is not None and self.status in ("ready", "asleep"):
                s["config"] = config_to_dict(Config.parse(shown))
                s["queued"] = self.queued is not None
                original = self.original()
                s["is_original"] = shown == original
                if original:
                    oc = Config.parse(original)
                    s["original"] = {"dpi": oc.dpi[oc.active_stage], "led_mode": oc.led_mode, "led_color": hexcolor(oc.led_color)}
                s["last_led_mode"] = self.prefs.get("last_led_mode", 2)
                s["lights_off"] = bool(self.prefs.get("lights_off", False))
                s["charge_cover"] = bool(self.prefs.get("charge_cover", False))
                s["covering"] = s["lights_off"] and self._cover_wanted()
                s["dpi_popup"] = bool(self.prefs.get("dpi_popup", True))
                page = shown + (self.tail or b"\xff" * (PAGE_LEN - PROFILE_LEN))
                s["storage"] = {"page": page.hex(), "regions": REGIONS, "profile_len": PROFILE_LEN}
            s["setups"] = self.setups.summary(shown if self.status in ("ready", "asleep") else None)
            return s

    def original(self):
        try:
            with open(ORIGINAL, "rb") as f:
                data = f.read()
            return data if len(data) >= PROFILE_LEN else None
        except OSError:
            return None

    def current(self):
        """What the mouse holds, or will hold once queued changes are written."""
        return self.queued if self.queued is not None else self.mem

    def _go_to_sleep(self):
        if self.mem is None:
            seen = self.history.last_seen()
            self.mem = seen if seen and len(seen) >= PROFILE_LEN else None
        self.status = "asleep"

    def _drop(self, status="searching"):
        if self.dev:
            try:
                self.dev.close()
            except OSError:
                pass
        self.dev, self.mem, self.tail, self.battery = None, None, None, None
        self.status = status
        self.bump()

    def _load(self):
        self.mem = read_profile(self.dev)
        self.tail = self.dev.read(PROFILE_LEN, PAGE_LEN - PROFILE_LEN)
        if self.original() is None:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ORIGINAL, "wb") as f:
                f.write(self.mem)
        self._log(SRC_OFFLINE, self.history.last_seen(), self.mem)
        self.status = "ready"
        if self.queued is not None:
            queued, self.queued = self.queued, None
            self._write(queued, SRC_APP)
        self._read_battery()
        c = Config.parse(self.mem)
        ours = c.led_mode == LED_STATIC and c.led_brightness == COVER_BRIGHTNESS
        if c.led_mode == LED_OFF:
            self.prefs.set("lights_off", True)
        elif self.prefs.get("lights_off") and not ours:
            self.prefs.set("lights_off", False)
        self._auto_light()

    def _read_battery(self):
        try:
            pct, charging = self.dev.battery()
            self.battery = {"percent": pct, "charging": charging}
        except (ProtocolError, OSError):
            pass
        self.last_battery = time.monotonic()

    def _log(self, source, old, new):
        self.history.add(source, describe_changes(old, new))
        self.history.remember(new)

    def poll(self):
        with self.lock:
            try:
                now = time.monotonic()
                if not self.dev:
                    self.dev = Compx.open_any()
                    if not self.dev:
                        return
                    self.last_online_check = 0
                if self.dev.pop_events() and self.status == "ready":
                    fresh = read_profile(self.dev)
                    old, new = Config.parse(self.mem), Config.parse(fresh)
                    self._log(SRC_MOUSE, self.mem, fresh)
                    self.mem = fresh
                    if new.active_stage != old.active_stage and self.popup and self.prefs.get("dpi_popup", True):
                        i = new.active_stage
                        self.popup.show(new.dpi[i], hexcolor(new.colors[i]), i + 1, new.stage_count)
                    self.bump()
                if now - self.last_online_check > 3:
                    self.last_online_check = now
                    if not self.dev.wired:
                        # Once the cable is in, the mouse stops answering through the receiver.
                        try:
                            wired = Compx(PID_WIRED)
                        except (ProtocolError, OSError):
                            wired = None
                        if wired:
                            self.dev.close()
                            self.dev, self.status, self.mem = wired, "searching", None
                    online = self.dev.mouse_online()
                    if online and self.status != "ready":
                        self._load()
                        self.bump()
                    elif not online and self.status != "asleep":
                        self._go_to_sleep()
                        self._read_battery()
                        self.bump()
                # The charging flag drives auto lighting, so it's checked often only while that feature is in use.
                # Only fast over the cable: charging needs the cable, and polling over wireless could keep the mouse awake.
                fast = self.dev.wired and self.prefs.get("lights_off") and self.prefs.get("charge_cover")
                every = 5 if fast else 60
                if self.status == "ready" and now - self.last_battery > every:
                    before = self.battery
                    self._read_battery()
                    if self.battery != before:
                        self._auto_light()
                        self.bump()
            except (ProtocolError, OSError):
                self._drop()

    def run(self):
        while True:
            try:
                self.poll()
            except Exception:
                log_error("poll")
                self._drop()
                time.sleep(2)
            time.sleep(0.35 if self.dev else 1.5)

    def _cover_wanted(self):
        return bool(self.prefs.get("charge_cover") and self.battery and self.battery["charging"])

    def _lights_off_target(self, c):
        """With lights 'off', a faint static glow while charging hides the firmware's charging blink."""
        if self._cover_wanted():
            c.led_mode, c.led_brightness = LED_STATIC, COVER_BRIGHTNESS
        else:
            c.led_mode = LED_OFF

    def _auto_light(self):
        if self.status != "ready" or not self.prefs.get("lights_off"):
            return
        c = Config.parse(self.mem)
        before = (c.led_mode, c.led_brightness)
        self._lights_off_target(c)
        if (c.led_mode, c.led_brightness) != before:
            self._write(c.apply(self.mem), SRC_AUTO)

    def _write(self, new, source):
        if self.status == "asleep" and self.mem is not None:
            self.queued = new
            self.bump()
            return
        if self.status != "ready":
            raise ProtocolError("The mouse isn't connected")
        try:
            write_diff(self.dev, self.mem, new)
            check = read_profile(self.dev)
        except ProtocolError:
            # Over the receiver the mouse can doze off between status checks; finish the write when it wakes.
            if not self.dev.wired and not self.dev.mouse_online():
                self._go_to_sleep()
                self.queued = new
                self.bump()
                return
            raise
        self._log(source, self.mem, check)
        self.mem = check
        self.bump()
        if check != new[:len(check)]:
            raise ProtocolError("The mouse stored different values than requested")

    def update(self, changes):
        with self.lock:
            if self.current() is None:
                raise ProtocolError("The mouse isn't connected")
            c = Config.parse(self.current())
            if "autostart" in changes:
                set_autostart(bool(changes.pop("autostart")))
                if not changes:
                    self.bump()
                    return
            if "dpi_popup" in changes:
                self.prefs.set("dpi_popup", bool(changes.pop("dpi_popup")))
                if not changes:
                    self.bump()
                    return
            if "charge_cover" in changes:
                self.prefs.set("charge_cover", bool(changes.pop("charge_cover")))
            if "lights_on" in changes:
                if changes.pop("lights_on"):
                    self.prefs.set("lights_off", False)
                    c.led_mode = self.prefs.get("last_led_mode", 2)
                    c.led_brightness = self.prefs.get("last_led_brightness", c.led_brightness)
                elif not self.prefs.get("lights_off"):
                    if c.led_mode != LED_OFF:
                        self.prefs.set("last_led_mode", c.led_mode)
                        self.prefs.set("last_led_brightness", c.led_brightness)
                    self.prefs.set("lights_off", True)
            for k, v in changes.items():
                if k == "dpi":
                    c.dpi = [dpi_snap(x) for x in v]
                elif k == "colors":
                    c.colors = [rgb(x) for x in v]
                elif k == "led_color":
                    c.led_color = rgb(v)
                elif k == "buttons":
                    c.buttons = [BUTTON_ACTIONS.get(label, old) for label, old in zip(v, c.buttons)]
                elif k == "led_mode":
                    c.led_mode = int(v)
                    if c.led_mode != LED_OFF:
                        self.prefs.set("last_led_mode", c.led_mode)
                        self.prefs.set("lights_off", False)
                elif k in ("polling", "stage_count", "active_stage", "lod", "led_speed", "led_brightness",
                           "debounce", "sleep_s"):
                    setattr(c, k, int(v))
                elif k in ("motion_sync", "angle_snap", "ripple"):
                    setattr(c, k, bool(v))
            c.stage_count = max(1, min(8, c.stage_count))
            c.active_stage = max(0, min(c.stage_count - 1, c.active_stage))
            c.led_speed = max(1, min(10, c.led_speed))
            c.led_brightness = max(1, min(10, c.led_brightness))
            if self.prefs.get("lights_off"):
                self._lights_off_target(c)
            self._write(c.apply(self.current()), SRC_APP)

    def restore(self, image, source=SRC_RESTORE):
        with self.lock:
            self._write(validate_backup(image), source)
            self.prefs.set("lights_off", Config.parse(self.current()).led_mode == LED_OFF)
            self._auto_light()

    def save_setup(self, name, sid=None):
        with self.lock:
            if self.current() is None:
                raise ProtocolError("The mouse isn't connected")
            if sid:
                self.setups.update(sid, image=self.current())
            else:
                self.setups.add(name, self.current())
            self.bump()

    def apply_setup(self, sid):
        item = self.setups.get(sid)
        if not item:
            raise KeyError("No such setup")
        self.restore(bytes.fromhex(item["image"]), f"Setup: {item['name']}")

    def factory_reset(self):
        with self.lock:
            if self.status != "ready":
                raise ProtocolError("The mouse isn't connected")
            if not self.dev.wired:
                raise ProtocolError("Plug the USB cable into the mouse to reset it")
            r = self.dev.transact(OP_FACTORY_RESET, timeout=2.0)
            if r[2] != 0:
                raise ProtocolError(f"The mouse refused the reset (status {r[2]})")
            time.sleep(0.5)
            fresh = read_profile(self.dev)
            self.tail = self.dev.read(PROFILE_LEN, PAGE_LEN - PROFILE_LEN)
            self._log(SRC_FACTORY, self.mem, fresh)
            self.mem = fresh
            self.prefs.set("lights_off", Config.parse(fresh).led_mode == LED_OFF)
            self.bump()

    def backup(self):
        with self.lock:
            if self.current() is None:
                raise ProtocolError("The mouse isn't connected")
            return self.current()

    def scan_macros(self):
        with self.lock:
            if self.status != "ready":
                raise ProtocolError("Move the mouse to wake it, then scan again")
            data = self.dev.read(MACRO_START, MACRO_LEN)
        slots = [i + 1 for i in range(MACRO_LEN // 0x20) if any(b != 0xFF for b in data[i * 0x20:(i + 1) * 0x20])]
        return {"start": MACRO_START, "length": MACRO_LEN, "used_slots": slots,
                "used_bytes": sum(b != 0xFF for b in data)}


class App:
    def __init__(self):
        self.mouse = Mouse()
        self.token = secrets.token_urlsafe(24)
        self.clients = 0
        self.last_client_seen = time.monotonic()
        self.ever_connected = False


APP = App()


class Handler(BaseHTTPRequestHandler):
    server_version = "M4"

    def log_message(self, *a):
        pass

    def _host_ok(self):
        # Rejects DNS-rebinding: a hostile site resolving its own name to 127.0.0.1 sends a different Host header.
        return self.headers.get("Host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _authed(self):
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-Token", ""), APP.token)

    def _send(self, code, body=b"", ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        if path == "/api/ping":
            return self._send(200, {"app": "xtrfy-m4"})
        if path.startswith("/api/"):
            if not self._authed() and not (path == "/api/events" and self._token_param_ok()):
                return self._send(403, {"error": "forbidden"})
            if path == "/api/state":
                return self._send(200, APP.mouse.state())
            if path == "/api/history":
                return self._send(200, APP.mouse.history.entries())
            if path == "/api/backup":
                try:
                    data = APP.mouse.backup()
                except ProtocolError as e:
                    return self._send(409, {"error": str(e)})
                return self._send(200, data, "application/octet-stream",
                                  {"Content-Disposition": 'attachment; filename="xtrfy-m4-backup.m4"'})
            if path == "/api/events":
                return self._events()
            return self._send(404, {"error": "not found"})
        return self._static(path)

    def _token_param_ok(self):
        q = urlparse(self.path).query
        return any(p == f"token={APP.token}" for p in q.split("&"))

    def _static(self, path):
        if path == "/":
            path = "/index.html"
        full = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
        if not full.startswith(WEB) or not os.path.isfile(full):
            return self._send(404, "Not found", "text/plain")
        with open(full, "rb") as f:
            data = f.read()
        if path == "/index.html":
            data = data.replace(b"__TOKEN__", APP.token.encode())
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".svg"):
            ctype = "image/svg+xml"
        self._send(200, data, ctype, {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                                 "img-src 'self' data: blob:; frame-src 'self'; "
                                                                 "object-src 'self'"})

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        APP.clients += 1
        APP.ever_connected = True
        seen = -1
        try:
            while True:
                with APP.mouse.changed:
                    if APP.mouse.version == seen:
                        APP.mouse.changed.wait(15)
                if APP.mouse.version != seen:
                    s = APP.mouse.state()
                    seen = s["version"]
                    self.wfile.write(b"data: " + json.dumps(s).encode() + b"\n\n")
                else:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (ConnectionError, OSError):
            pass
        finally:
            APP.clients -= 1
            APP.last_client_seen = time.monotonic()

    def do_POST(self):
        if not self._authed():
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        try:
            if path == "/api/config":
                APP.mouse.update(json.loads(self._body() or b"{}"))
            elif path == "/api/setups":
                body = json.loads(self._body() or b"{}")
                APP.mouse.save_setup(body.get("name", ""), body.get("overwrite"))
            elif path == "/api/setups/apply":
                APP.mouse.apply_setup(json.loads(self._body())["id"])
            elif path == "/api/setups/rename":
                body = json.loads(self._body())
                APP.mouse.setups.update(body["id"], name=body["name"])
                APP.mouse.bump()
            elif path == "/api/factory-reset":
                APP.mouse.factory_reset()
            elif path == "/api/restore-original":
                original = APP.mouse.original()
                if original is None:
                    raise ProtocolError("No original settings have been saved yet")
                APP.mouse.restore(original)
            elif path == "/api/restore":
                APP.mouse.restore(base64.b64decode(json.loads(self._body())["data"]))
            elif path == "/api/macros/scan":
                return self._send(200, APP.mouse.scan_macros())
            else:
                return self._send(404, {"error": "not found"})
        except (ProtocolError, OSError) as e:
            return self._send(409, {"error": str(e)})
        except (ValueError, KeyError, TypeError) as e:
            return self._send(400, {"error": str(e)})
        return self._send(200, APP.mouse.state())

    def do_DELETE(self):
        if not self._authed():
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        if path == "/api/history":
            APP.mouse.history.clear()
            return self._send(200, [])
        if path.startswith("/api/setups/"):
            APP.mouse.setups.delete(path.rsplit("/", 1)[1])
            APP.mouse.bump()
            return self._send(200, APP.mouse.state())
        return self._send(404, {"error": "not found"})


def serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=APP.mouse.run, daemon=True).start()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


if __name__ == "__main__":
    serve()
    print(f"Serving on http://127.0.0.1:{PORT}/  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
