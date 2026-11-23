"""Background helper: talks to the mouse with no window, so auto lighting and history keep working."""
import time

import server

from overlay import DpiPopup

try:
    server.serve()
    server.APP.mouse.popup = DpiPopup()
except OSError:
    raise SystemExit  # another copy already owns the port
while True:
    time.sleep(3600)
