"""Compx (VID 25A7) vendor protocol: 17-byte feature report 0x08 out, input report 0x09 back."""
import time
from winhid import find, HidDevice

VID = 0x25A7
PID_WIRED = 0xFA92
PID_RECEIVER = 0xFA99

OP_CONNECT_STATUS = 0x03
OP_BATTERY = 0x04
OP_WRITE = 0x07
OP_READ = 0x08
OP_EVENT = 0x0A


def checksum(b):
    return (0x55 - sum(b)) & 0xFF


def frame(op, addr=0, data=b"", length=None):
    data = bytes(data)
    n = len(data) if length is None else length
    b = bytes([0x08, op, 0x00, (addr >> 8) & 0xFF, addr & 0xFF, n]) + data.ljust(10, b"\0")
    return b + bytes([checksum(b)])


class ProtocolError(Exception):
    pass


class Compx:
    def __init__(self, pid):
        infos = {d.usage_page: d for d in find(VID, pid)}
        if 0xFF02 not in infos or 0xFF01 not in infos:
            raise ProtocolError(f"25A7:{pid:04X} not present")
        self.pid = pid
        self.wired = pid == PID_WIRED
        self.cmd = HidDevice(infos[0xFF02].path)
        self.rsp = HidDevice(infos[0xFF01].path)
        self.events = []
        self.drain()

    @classmethod
    def open_any(cls):
        """Prefer the cable: the receiver can only reach the mouse while it is awake."""
        for pid in (PID_WIRED, PID_RECEIVER):
            try:
                return cls(pid)
            except (ProtocolError, OSError):
                continue
        return None

    def close(self):
        self.cmd.close()
        self.rsp.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _keep_event(self, r):
        if r and len(r) >= 17 and r[1] == OP_EVENT:
            self.events.append(r)

    def drain(self):
        while True:
            r = self.rsp.read(17, timeout_ms=1)
            if not r:
                return
            self._keep_event(r)

    def pop_events(self):
        self.drain()
        ev, self.events = self.events, []
        return ev

    def transact(self, op, addr=0, data=b"", length=None, timeout=0.4, retries=3):
        req = frame(op, addr, data, length)
        for _ in range(retries):
            self.drain()
            self.cmd.set_feature(req)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                r = self.rsp.read(17, timeout_ms=max(1, int((deadline - time.monotonic()) * 1000)))
                if not r or len(r) < 17:
                    continue
                if r[1] != op:
                    self._keep_event(r)
                    continue
                if op in (OP_READ, OP_WRITE) and (r[3], r[4]) != (req[3], req[4]):
                    continue
                if checksum(r[:16]) != r[16]:
                    continue
                return r
            time.sleep(0.03)
        raise ProtocolError(f"no reply to op 0x{op:02X} addr 0x{addr:04X}")

    def read(self, addr, n):
        out = bytearray()
        while n > 0:
            k = min(10, n)
            r = self.transact(OP_READ, addr, length=k)
            if r[2] != 0:
                raise ProtocolError(f"read 0x{addr:04X} status 0x{r[2]:02X}")
            out += r[6:6 + k]
            addr += k
            n -= k
        return bytes(out)

    def write(self, addr, data):
        data = bytes(data)
        for i in range(0, len(data), 10):
            r = self.transact(OP_WRITE, addr + i, data[i:i + 10])
            if r[2] != 0:
                raise ProtocolError(f"write 0x{addr + i:04X} status 0x{r[2]:02X}")

    def mouse_online(self):
        return self.wired or self.transact(OP_CONNECT_STATUS)[6] == 1

    def battery(self):
        r = self.transact(OP_BATTERY)
        return r[6], bool(r[7])
