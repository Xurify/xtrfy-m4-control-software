"""On-screen DPI indicator shown by the background helper when the DPI button is pressed."""
import ctypes
import ctypes.wintypes as wt
import queue
import threading

GWL_EXSTYLE = -20
# Click-through, never takes focus, no taskbar button.
EX_STYLE = 0x00080000 | 0x00000020 | 0x08000000 | 0x00000080
SHOW_MS, FADE_STEPS = 1300, 10


class DpiPopup:
    def __init__(self):
        self.q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def show(self, dpi, colour, stage, count):
        self.q.put((dpi, colour, stage, count))

    def _run(self):
        import tkinter as tk
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass
        root = tk.Tk()
        root.withdraw()
        self.win = None
        self.hide_job = None

        def poll():
            try:
                while True:
                    self._present(tk, root, *self.q.get_nowait())
            except queue.Empty:
                pass
            root.after(80, poll)

        root.after(80, poll)
        root.mainloop()

    def _present(self, tk, root, dpi, colour, stage, count):
        scale = root.winfo_fpixels("1i") / 96
        w, h = int(232 * scale), int(64 * scale)
        if self.win is None:
            self.win = tk.Toplevel(root)
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.configure(bg="#16181c")
            self.canvas = tk.Canvas(self.win, width=w, height=h, bg="#16181c", highlightthickness=0)
            self.canvas.pack()
            self.win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | EX_STYLE)
            # Windows 11 rounded corners (DWMWA_WINDOW_CORNER_PREFERENCE = round); ignored on Windows 10.
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        c = self.canvas
        c.delete("all")
        r = int(7 * scale)
        cx, cy = int(28 * scale), h // 2
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=colour, outline="")
        c.create_text(int(48 * scale), cy - int(1 * scale), text=f"{dpi:,}", anchor="w", fill="#e9ebee",
                      font=("Segoe UI Semibold", 20))
        c.create_text(w - int(18 * scale), cy - int(8 * scale), text="DPI", anchor="e", fill="#8d939b", font=("Segoe UI", 10))
        c.create_text(w - int(18 * scale), cy + int(10 * scale), text=f"Stage {stage} of {count}", anchor="e",
                      fill="#5f656d", font=("Segoe UI", 9))
        area = wt.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA
        x = area.left + (area.right - area.left - w) // 2
        y = area.bottom - h - int(56 * scale)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.attributes("-alpha", 0.96)
        self.win.deiconify()
        self.win.lift()
        if self.hide_job:
            self.win.after_cancel(self.hide_job)
        self.hide_job = self.win.after(SHOW_MS, lambda: self._fade(FADE_STEPS))

    def _fade(self, n):
        if n <= 0:
            self.win.withdraw()
            self.hide_job = None
            return
        self.win.attributes("-alpha", 0.96 * n / FADE_STEPS)
        self.hide_job = self.win.after(18, lambda: self._fade(n - 1))
