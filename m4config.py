"""Xtrfy M4 Wireless config memory (Compx firmware, PMW3370 layout).

Run directly for a CLI:  python m4config.py [show | backup FILE | restore FILE]
"""
import sys
from dataclasses import dataclass, field

PROFILE_LEN = 0xB5
STAGES = 8

A_POLL, A_STAGE_COUNT, A_ACTIVE, A_LOD = 0x00, 0x02, 0x04, 0x0A
A_DPI, A_COLORS, A_BUTTONS, A_LED = 0x0C, 0x2C, 0x60, 0xA0
A_DEBOUNCE, A_MOTION_SYNC, A_SLEEP, A_ANGLE_SNAP, A_RIPPLE = 0xA9, 0xAB, 0xAD, 0xAF, 0xB1

POLL_RATES = {1: 1000, 2: 500, 4: 250, 8: 125}
LOD_MM = {1: "1 mm", 2: "2 mm"}

LED_MODES = {0: "Spectrum flow", 1: "Breathing", 2: "Static", 3: "Neon", 4: "Off", 5: "Marquee",
             7: "Colour breathing"}
LED_HAS_COLOR = {1, 2, 5}
LED_HAS_SPEED = {0, 1, 3, 5, 7}
SPEED_STD = [0xFF, 0xE6, 0xD2, 0xBE, 0xAA, 0x96, 0x82, 0x6E, 0x46, 0x28]
BRI_STD = [0x2D, 0x32, 0x4B, 0x64, 0x7D, 0x96, 0xAF, 0xC8, 0xE1, 0xFF]
SPEED_FLOW = [0x0A, 0x09, 0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01]
BRI_FLOW = [0x48, 0x5C, 0x70, 0x84, 0x98, 0xAC, 0xC0, 0xD4, 0xE8, 0xFC]

BUTTON_ACTIONS = {
    "Left click": (0x01, 0x01, 0x00),
    "Right click": (0x01, 0x02, 0x00),
    "Middle click": (0x01, 0x04, 0x00),
    "Back": (0x01, 0x08, 0x00),
    "Forward": (0x01, 0x10, 0x00),
    "DPI cycle": (0x02, 0x01, 0x00),
    "DPI up": (0x02, 0x02, 0x00),
    "DPI down": (0x02, 0x03, 0x00),
    "Disabled": (0x00, 0x00, 0x00),
}
PHYSICAL_BUTTONS = ["Left button", "Right button", "Wheel click", "Side back", "Side forward", "DPI button"]

DPI_MIN, DPI_MAX = 50, 19000



def ck(*b):
    return (0x55 - sum(b)) & 0xFF


def get_pair(mem, a, default):
    v = mem[a]
    return v if mem[a + 1] == ck(v) else default


def put_pair(mem, a, v):
    mem[a], mem[a + 1] = v, ck(v)


def dpi_decode(code, flags):
    mul = flags & 0x0F
    base = 100 if mul & 2 else 50
    if mul & 1:
        base *= 2
    return (code + 1) * base


def dpi_snap(dpi):
    dpi = max(DPI_MIN, min(DPI_MAX, int(dpi)))
    step = 50 if dpi <= 10000 else 100
    return max(DPI_MIN, min(DPI_MAX, round(dpi / step) * step))


def dpi_encode(dpi):
    dpi = dpi_snap(dpi)
    # The PMW3370 table tops out at code 0xC7 in 50-step mode; above 10000 the firmware switches to 100-steps.
    if dpi <= 10000:
        return dpi // 50 - 1, 0x00
    return dpi // 100 - 1, 0x22


def level_of(raw, table):
    return table.index(raw) + 1 if raw in table else 6


@dataclass
class Config:
    polling: int = 1000
    stage_count: int = 5
    active_stage: int = 0
    lod: int = 1
    dpi: list = field(default_factory=lambda: [400] * STAGES)
    colors: list = field(default_factory=lambda: [(255, 255, 255)] * STAGES)
    led_mode: int = 2
    led_color: tuple = (255, 255, 255)
    led_speed: int = 6
    led_brightness: int = 6
    buttons: list = field(default_factory=lambda: [None] * len(PHYSICAL_BUTTONS))
    debounce: int = 4
    motion_sync: bool = False
    sleep_s: int = 60
    angle_snap: bool = False
    ripple: bool = False

    @classmethod
    def parse(cls, mem):
        c = cls()
        c.polling = POLL_RATES.get(get_pair(mem, A_POLL, 1), 1000)
        c.stage_count = max(1, min(STAGES, get_pair(mem, A_STAGE_COUNT, 5)))
        c.active_stage = min(c.stage_count - 1, get_pair(mem, A_ACTIVE, 0))
        c.lod = get_pair(mem, A_LOD, 1)
        c.dpi = [dpi_decode(mem[A_DPI + 4 * i], mem[A_DPI + 4 * i + 2]) for i in range(STAGES)]
        c.colors = [tuple(mem[A_COLORS + 4 * i:A_COLORS + 4 * i + 3]) for i in range(STAGES)]
        mode = mem[A_LED]
        c.led_mode = mode if mode in LED_MODES else 2
        c.led_color = tuple(mem[A_LED + 1:A_LED + 4])
        flow = c.led_mode == 0
        c.led_speed = level_of(mem[A_LED + 4], SPEED_FLOW if flow else SPEED_STD)
        c.led_brightness = level_of(mem[A_LED + 5], BRI_FLOW if flow else BRI_STD)
        c.buttons = [tuple(mem[A_BUTTONS + 4 * i:A_BUTTONS + 4 * i + 3]) for i in range(len(PHYSICAL_BUTTONS))]
        c.debounce = get_pair(mem, A_DEBOUNCE, 4)
        c.motion_sync = bool(get_pair(mem, A_MOTION_SYNC, 0))
        c.sleep_s = get_pair(mem, A_SLEEP, 6) * 10
        c.angle_snap = bool(get_pair(mem, A_ANGLE_SNAP, 0))
        c.ripple = bool(get_pair(mem, A_RIPPLE, 0))
        return c

    def apply(self, mem):
        """Return a copy of `mem` with this config written in; bytes this tool doesn't model stay untouched."""
        m = bytearray(mem)
        put_pair(m, A_POLL, {v: k for k, v in POLL_RATES.items()}[self.polling])
        put_pair(m, A_STAGE_COUNT, self.stage_count)
        put_pair(m, A_ACTIVE, min(self.active_stage, self.stage_count - 1))
        put_pair(m, A_LOD, self.lod)
        for i in range(STAGES):
            code, flags = dpi_encode(self.dpi[i])
            m[A_DPI + 4 * i:A_DPI + 4 * i + 4] = bytes([code, code, flags, ck(code, code, flags)])
            r, g, b = self.colors[i]
            m[A_COLORS + 4 * i:A_COLORS + 4 * i + 4] = bytes([r, g, b, ck(r, g, b)])
        flow = self.led_mode == 0
        speed = (SPEED_FLOW if flow else SPEED_STD)[self.led_speed - 1]
        bri = (BRI_FLOW if flow else BRI_STD)[self.led_brightness - 1]
        led = [self.led_mode, *self.led_color, speed, bri]
        m[A_LED:A_LED + 7] = bytes(led + [ck(*led)])
        for i, rec in enumerate(self.buttons):
            if rec is not None:
                m[A_BUTTONS + 4 * i:A_BUTTONS + 4 * i + 4] = bytes([*rec, ck(*rec)])
        put_pair(m, A_DEBOUNCE, max(0, min(30, self.debounce)))
        put_pair(m, A_MOTION_SYNC, int(self.motion_sync))
        put_pair(m, A_SLEEP, max(1, min(0xFF, round(self.sleep_s / 10))))
        put_pair(m, A_ANGLE_SNAP, int(self.angle_snap))
        put_pair(m, A_RIPPLE, int(self.ripple))
        return bytes(m)


def read_profile(dev):
    return dev.read(0, PROFILE_LEN)


def write_diff(dev, old, new):
    """Write only the 10-byte chunks that changed. Returns how many chunks were written."""
    n = 0
    for a in range(0, min(len(old), len(new)), 10):
        if old[a:a + 10] != new[a:a + 10]:
            dev.write(a, new[a:a + 10])
            n += 1
    return n


def validate_backup(data):
    if len(data) < PROFILE_LEN:
        raise ValueError(f"backup too short ({len(data)} bytes, need {PROFILE_LEN})")
    pairs = (A_POLL, A_STAGE_COUNT, A_ACTIVE, A_DEBOUNCE, A_SLEEP)
    if any(data[a + 1] != ck(data[a]) for a in pairs):
        raise ValueError("backup checksums don't match; not an Xtrfy M4 profile")
    return bytes(data[:PROFILE_LEN])


def button_label(rec):
    for name, r in BUTTON_ACTIONS.items():
        if tuple(rec) == r:
            return name
    return "Special ({:02X} {:02X} {:02X})".format(*rec)


PAGE_LEN = 0x100
MACRO_START, MACRO_LEN = 0x100, 0x200

# (start, length, name, category) covering the whole 256-byte settings page.
REGIONS = [
    (0x00, 2, "Polling rate", "Sensor"),
    (0x02, 2, "DPI stage count", "DPI"),
    (0x04, 2, "Active DPI stage", "DPI"),
    (0x06, 4, "Unidentified", "Unknown"),
    (0x0A, 2, "Lift-off distance", "Sensor"),
    (0x0C, 32, "DPI stage values (8 × 4)", "DPI"),
    (0x2C, 32, "DPI stage colours (8 × 4)", "DPI"),
    (0x4C, 20, "DPI indicator effect", "DPI"),
    (0x60, 64, "Button assignments (16 slots × 4)", "Buttons"),
    (0xA0, 7, "RGB lighting", "Lighting"),
    (0xA7, 2, "Unidentified", "Unknown"),
    (0xA9, 2, "Click debounce", "Sensor"),
    (0xAB, 2, "Motion sync", "Sensor"),
    (0xAD, 2, "Sleep timer", "Power"),
    (0xAF, 2, "Angle snapping", "Sensor"),
    (0xB1, 2, "Ripple control", "Sensor"),
    (0xB3, 2, "LED off while moving", "Lighting"),
    (PROFILE_LEN, PAGE_LEN - PROFILE_LEN, "Free space", "Free"),
]


def region_at(addr):
    for start, n, name, cat in REGIONS:
        if start <= addr < start + n:
            return start, n, name, cat
    return None


def describe_changes(old_mem, new_mem):
    """Human-readable list of setting changes between two profile images."""
    if not old_mem or len(old_mem) < PROFILE_LEN or old_mem[:PROFILE_LEN] == new_mem[:PROFILE_LEN]:
        return []
    a, b = Config.parse(old_mem), Config.parse(new_mem)
    out = []

    def diff(label, x, y, fmt=str):
        if x != y:
            out.append(f"{label}: {fmt(x)} → {fmt(y)}")

    if a.active_stage != b.active_stage:
        out.append(f"Active DPI: stage {a.active_stage + 1} ({a.dpi[a.active_stage]}) → "
                   f"stage {b.active_stage + 1} ({b.dpi[b.active_stage]})")
    diff("Stages in cycle", a.stage_count, b.stage_count)
    for i in range(STAGES):
        diff(f"Stage {i + 1} DPI", a.dpi[i], b.dpi[i])
        diff(f"Stage {i + 1} colour", a.colors[i], b.colors[i], lambda c: "#%02X%02X%02X" % c)
    diff("Polling rate", a.polling, b.polling, lambda v: f"{v} Hz")
    diff("Lift-off distance", a.lod, b.lod, lambda v: LOD_MM.get(v, str(v)))
    diff("Debounce", a.debounce, b.debounce, lambda v: f"{v} ms")
    diff("Motion sync", a.motion_sync, b.motion_sync, lambda v: "on" if v else "off")
    diff("Angle snapping", a.angle_snap, b.angle_snap, lambda v: "on" if v else "off")
    diff("Ripple control", a.ripple, b.ripple, lambda v: "on" if v else "off")
    diff("Sleep timer", a.sleep_s, b.sleep_s, lambda v: f"{v} s")
    diff("Lighting effect", a.led_mode, b.led_mode, lambda v: LED_MODES.get(v, str(v)))
    diff("Lighting colour", a.led_color, b.led_color, lambda c: "#%02X%02X%02X" % c)
    diff("Lighting speed", a.led_speed, b.led_speed, lambda v: f"{v}/10")
    diff("Lighting brightness", a.led_brightness, b.led_brightness, lambda v: f"{v}/10")
    for name, x, y in zip(PHYSICAL_BUTTONS, a.buttons, b.buttons):
        diff(name, x, y, button_label)
    if not out:
        out.append("Internal setting bytes changed")
    return out


def _cli(argv):
    from compx import Compx
    dev = Compx.open_any()
    if not dev:
        sys.exit("Xtrfy M4 not found (cable or receiver).")
    with dev:
        if not dev.mouse_online():
            sys.exit("Receiver found, but the mouse is asleep or off. Move it and retry.")
        mem = read_profile(dev)
        cmd = argv[0] if argv else "show"
        if cmd == "backup":
            open(argv[1], "wb").write(mem)
            print(f"Saved {len(mem)} bytes to {argv[1]}")
        elif cmd == "restore":
            new = validate_backup(open(argv[1], "rb").read())
            print(f"Wrote {write_diff(dev, mem, new)} chunk(s)")
        else:
            c = Config.parse(mem)
            pct, chg = dev.battery()
            print(f"Connection   {'cable' if dev.wired else 'receiver'}   battery {pct}%{' (charging)' if chg else ''}")
            print(f"Polling      {c.polling} Hz   LOD {LOD_MM.get(c.lod, c.lod)}   debounce {c.debounce} ms")
            for i in range(c.stage_count):
                mark = "*" if i == c.active_stage else " "
                print(f" {mark} stage {i + 1}  {c.dpi[i]:>5} DPI  #{'%02X%02X%02X' % c.colors[i]}")
            print(f"LED          {LED_MODES[c.led_mode]}  #{'%02X%02X%02X' % c.led_color}  "
                  f"speed {c.led_speed}/10  brightness {c.led_brightness}/10")
            for name, rec in zip(PHYSICAL_BUTTONS, c.buttons):
                print(f"{name:13}{button_label(rec)}")
            print(f"Sleep {c.sleep_s}s   motion sync {c.motion_sync}   angle snap {c.angle_snap}   ripple {c.ripple}")


if __name__ == "__main__":
    _cli(sys.argv[1:])
