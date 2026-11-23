"""Minimal Windows HID access via ctypes (hid.dll / setupapi.dll), no third-party deps."""
import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass, field

hid = ctypes.WinDLL("hid")
setupapi = ctypes.WinDLL("setupapi")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE = ctypes.c_void_p(-1).value
DIGCF_PRESENT = 0x2
DIGCF_DEVICEINTERFACE = 0x10
HIDP_STATUS_SUCCESS = 0x00110000
WAIT_OBJECT_0 = 0
ERROR_IO_PENDING = 997


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT), ("ProductID", wt.USHORT), ("VersionNumber", wt.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT),
        ("NumberInputButtonCaps", wt.USHORT), ("NumberInputValueCaps", wt.USHORT), ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT), ("NumberOutputDataIndices", wt.USHORT),
        ("NumberFeatureButtonCaps", wt.USHORT), ("NumberFeatureValueCaps", wt.USHORT), ("NumberFeatureDataIndices", wt.USHORT),
    ]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
        ("BitField", wt.USHORT), ("LinkCollection", wt.USHORT), ("LinkUsage", wt.USHORT), ("LinkUsagePage", wt.USHORT),
        ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
        ("BitSize", wt.USHORT), ("ReportCount", wt.USHORT), ("Reserved2", wt.USHORT * 5),
        ("UnitsExp", wt.ULONG), ("Units", wt.ULONG), ("LogicalMin", ctypes.c_long), ("LogicalMax", ctypes.c_long),
        ("PhysicalMin", ctypes.c_long), ("PhysicalMax", ctypes.c_long),
        ("UsageMin", wt.USHORT), ("UsageMax", wt.USHORT), ("StringMin", wt.USHORT), ("StringMax", wt.USHORT),
        ("DesignatorMin", wt.USHORT), ("DesignatorMax", wt.USHORT), ("DataIndexMin", wt.USHORT), ("DataIndexMax", wt.USHORT),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wt.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
kernel32.CreateFileW.restype = wt.HANDLE
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(OVERLAPPED)]
kernel32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(OVERLAPPED)]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.POINTER(OVERLAPPED), ctypes.POINTER(wt.DWORD), wt.BOOL]
kernel32.CancelIo.argtypes = [wt.HANDLE]
for fn in ("HidD_GetAttributes", "HidD_GetPreparsedData", "HidD_FreePreparsedData", "HidD_GetFeature",
           "HidD_SetFeature", "HidD_SetOutputReport", "HidD_GetInputReport", "HidD_GetProductString",
           "HidD_GetManufacturerString", "HidD_GetSerialNumberString"):
    getattr(hid, fn).argtypes = None
hid.HidD_GetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_SetOutputReport.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetInputReport.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
for fn in ("HidD_GetProductString", "HidD_GetManufacturerString", "HidD_GetSerialNumberString"):
    getattr(hid, fn).argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(wt.USHORT), ctypes.c_void_p]
hid.HidP_GetValueCaps.restype = ctypes.c_long


def _hid_guid():
    g = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(g))
    return g


def enumerate_paths():
    g = _hid_guid()
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    paths, i = [], 0
    try:
        while True:
            data = SP_DEVICE_INTERFACE_DATA()
            data.cbSize = ctypes.sizeof(data)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(data)):
                break
            i += 1
            need = wt.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(data), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(data), buf, need, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return paths


@dataclass
class HidInfo:
    path: str
    vid: int = 0
    pid: int = 0
    usage_page: int = 0
    usage: int = 0
    in_len: int = 0
    out_len: int = 0
    feat_len: int = 0
    product: str = ""
    report_ids: dict = field(default_factory=dict)


def _open(path, access=GENERIC_READ | GENERIC_WRITE, flags=0):
    h = kernel32.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, flags, None)
    return None if h in (None, INVALID_HANDLE) else h


def describe(path):
    # Access 0 lets us query attributes even on collections Windows holds exclusively (mouse/keyboard).
    h = _open(path, 0)
    if not h:
        return None
    try:
        info = HidInfo(path)
        a = HIDD_ATTRIBUTES()
        a.Size = ctypes.sizeof(a)
        hid.HidD_GetAttributes(h, ctypes.byref(a))
        info.vid, info.pid = a.VendorID, a.ProductID
        sbuf = ctypes.create_unicode_buffer(128)
        if hid.HidD_GetProductString(h, sbuf, ctypes.sizeof(sbuf)):
            info.product = sbuf.value
        pp = ctypes.c_void_p()
        if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            caps = HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(caps)) == HIDP_STATUS_SUCCESS:
                info.usage_page, info.usage = caps.UsagePage, caps.Usage
                info.in_len, info.out_len, info.feat_len = (caps.InputReportByteLength, caps.OutputReportByteLength,
                                                             caps.FeatureReportByteLength)
                for kind, n in ((0, caps.NumberInputValueCaps), (1, caps.NumberOutputValueCaps),
                                (2, caps.NumberFeatureValueCaps)):
                    if not n:
                        continue
                    arr = (HIDP_VALUE_CAPS * n)()
                    cnt = wt.USHORT(n)
                    if hid.HidP_GetValueCaps(kind, arr, ctypes.byref(cnt), pp) == HIDP_STATUS_SUCCESS:
                        name = ("input", "output", "feature")[kind]
                        for vc in arr[:cnt.value]:
                            info.report_ids.setdefault(name, []).append(
                                dict(id=vc.ReportID, bits=vc.BitSize, count=vc.ReportCount,
                                     usage=vc.UsageMin if vc.IsRange else vc.UsageMin))
            hid.HidD_FreePreparsedData(pp)
        return info
    finally:
        kernel32.CloseHandle(h)


class HidDevice:
    def __init__(self, path):
        self.path = path
        self.h = _open(path, GENERIC_READ | GENERIC_WRITE, FILE_FLAG_OVERLAPPED)
        if not self.h:
            raise OSError(f"cannot open {path}: winerr {ctypes.get_last_error()}")
        self.ev = kernel32.CreateEventW(None, True, False, None)

    def close(self):
        if self.h:
            kernel32.CloseHandle(self.h)
            kernel32.CloseHandle(self.ev)
            self.h = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def get_feature(self, report_id, length):
        buf = (ctypes.c_ubyte * length)()
        buf[0] = report_id
        if not hid.HidD_GetFeature(self.h, buf, length):
            raise OSError(f"GetFeature({report_id}) failed: winerr {ctypes.get_last_error()}")
        return bytes(buf)

    def set_feature(self, data: bytes):
        buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        if not hid.HidD_SetFeature(self.h, buf, len(data)):
            raise OSError(f"SetFeature failed: winerr {ctypes.get_last_error()}")

    def get_input_report(self, report_id, length):
        buf = (ctypes.c_ubyte * length)()
        buf[0] = report_id
        if not hid.HidD_GetInputReport(self.h, buf, length):
            raise OSError(f"GetInputReport({report_id}) failed: winerr {ctypes.get_last_error()}")
        return bytes(buf)

    def write(self, data: bytes, timeout_ms=1000):
        buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        ov = OVERLAPPED(hEvent=self.ev)
        kernel32.ResetEvent(self.ev)
        n = wt.DWORD()
        if not kernel32.WriteFile(self.h, buf, len(data), None, ctypes.byref(ov)):
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                raise OSError(f"WriteFile failed: winerr {ctypes.get_last_error()}")
            if kernel32.WaitForSingleObject(self.ev, timeout_ms) != WAIT_OBJECT_0:
                kernel32.CancelIo(self.h)
                raise TimeoutError("write timeout")
        kernel32.GetOverlappedResult(self.h, ctypes.byref(ov), ctypes.byref(n), False)
        return n.value

    def read(self, length, timeout_ms=200):
        buf = (ctypes.c_ubyte * length)()
        ov = OVERLAPPED(hEvent=self.ev)
        kernel32.ResetEvent(self.ev)
        n = wt.DWORD()
        if not kernel32.ReadFile(self.h, buf, length, None, ctypes.byref(ov)):
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                raise OSError(f"ReadFile failed: winerr {ctypes.get_last_error()}")
            if kernel32.WaitForSingleObject(self.ev, timeout_ms) != WAIT_OBJECT_0:
                kernel32.CancelIo(self.h)
                kernel32.GetOverlappedResult(self.h, ctypes.byref(ov), ctypes.byref(n), True)
                return None
        kernel32.GetOverlappedResult(self.h, ctypes.byref(ov), ctypes.byref(n), False)
        return bytes(buf[:n.value])


def find(vid, pid):
    out = []
    for p in enumerate_paths():
        if f"vid_{vid:04x}&pid_{pid:04x}" in p.lower():
            d = describe(p)
            if d:
                out.append(d)
    return out
