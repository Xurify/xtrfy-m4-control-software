"""Opens the M4 app window, starting the background helper first if it isn't running."""
import ctypes
import json
import os
import re
import subprocess
import time
import urllib.request

import webview

import server
from history import DIR as DATA_DIR

URL = f"http://127.0.0.1:{server.PORT}/"
MANUAL_URL = "https://cherryxtrfy.com/wp/wp-content/uploads/2021/12/Xtrfy-M4-RGB-Wireless-Quick-Start-Guide-20211206.pdf"
HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "web", "assets", "app.ico")
START_MENU_LINK = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs", "Xtrfy M4.lnk")

# Without its own ID, Windows groups this window under Python and shows Python's icon in the taskbar.
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Xtrfy.M4.Settings")


def set_window_icon():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Xtrfy M4")
    if not hwnd:
        return
    for which, size in ((0, 16), (1, 32)):  # ICON_SMALL, ICON_BIG
        h = user32.LoadImageW(None, ICON, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        if h:
            user32.SendMessageW(hwnd, 0x80, which, h)  # WM_SETICON


def ensure_start_menu_entry():
    # Rewrite the shortcuts whenever the app folder changes, so moving the app never leaves dead links.
    marker = os.path.join(DATA_DIR, "install-path.txt")
    try:
        with open(marker, encoding="utf-8") as f:
            same = f.read() == HERE
    except OSError:
        same = False
    if same and os.path.isfile(START_MENU_LINK):
        return
    if os.path.isfile(server.STARTUP_LINK):
        server.set_autostart(True)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(HERE)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:M4_LINK);$s.TargetPath=$env:M4_EXE;"
          "$s.Arguments='\"'+$env:M4_APP+'\"';$s.WorkingDirectory=$env:M4_DIR;$s.IconLocation=$env:M4_ICON;"
          "$s.Description='Settings for the Xtrfy M4 Wireless mouse';$s.Save()")
    env = dict(os.environ, M4_LINK=START_MENU_LINK, M4_EXE=server.pythonw(), M4_APP=os.path.abspath(__file__),
               M4_DIR=HERE, M4_ICON=ICON)
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, timeout=20,
                       creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError):
        pass


def helper_running():
    try:
        with urllib.request.urlopen(URL + "api/ping", timeout=1) as r:
            return json.load(r).get("app") == "xtrfy-m4"
    except (OSError, ValueError):
        return False


def start_helper():
    subprocess.Popen([server.pythonw(), os.path.join(HERE, "xtrfy_m4_helper.pyw")], cwd=HERE,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    for _ in range(40):
        if helper_running():
            return
        time.sleep(0.25)


class Api:
    """Functions the page can call through window.pywebview.api."""

    def save_backup(self):
        with urllib.request.urlopen(URL, timeout=5) as r:
            token = re.search(rb'm4-token" content="([^"]+)', r.read()).group(1).decode()
        req = urllib.request.Request(URL + "api/backup", headers={"X-Token": token})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        path = window.create_file_dialog(webview.FileDialog.SAVE, save_filename="xtrfy-m4-backup.m4",
                                         file_types=("M4 backup (*.m4)", "All files (*.*)"))
        if not path:
            return None
        path = path[0] if isinstance(path, (list, tuple)) else path
        with open(path, "wb") as f:
            f.write(data)
        return os.path.basename(path)

    def open_manual(self):
        os.startfile(MANUAL_URL)


if not helper_running():
    start_helper()
ensure_start_menu_entry()
window = webview.create_window("Xtrfy M4", URL, js_api=Api(), width=1280, height=860, min_size=(960, 640),
                               background_color="#0C0E11")
window.events.shown += set_window_icon
webview.start(gui="edgechromium", private_mode=False, storage_path=os.path.join(DATA_DIR, "webview"))
