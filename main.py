"""
Multi-Telegram Login Tool v7
============================
Refactor lớn từ v6:
  - Tách thành các module (core_runtime, account_panel, login_tab, admin_tab, sync_tab)
  - 1 event loop chung (SharedTaskRunner) — không còn 30 loop song song
  - LogBus batched — fix UI đơ khi log dày đặc
  - Auto save/load config — không phải gõ lại setting
  - Nút STOP cho task đang chạy
  - Acc list dùng tk.Checkbutton — nhanh hơn 10x CTk

Cài: pip install customtkinter telethon opentele pygetwindow pywin32
Chạy: python main.py
"""

from __future__ import annotations

import os
import ctypes
import math
import time
from ctypes import wintypes
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core_runtime import LogBus, SharedTaskRunner, ConfigStore, AsyncBridge
from login_tab import LoginTab
from admin_tab import AdminTab
from sync_tab import SyncTab, WindowManager


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ────────────────────────────────────────────────────────────────────
class FloatingLogWindow(ctk.CTkToplevel):
    """Cửa sổ log riêng — không bị tab che."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("📜 Log realtime")
        self.geometry("960x440")
        self.minsize(500, 200)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(head, text="📜 Log realtime",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        # Filter
        ctk.CTkLabel(head, text="Filter:").pack(side="left", padx=(20, 4))
        self.var_filter = ctk.StringVar(value="all")
        opt = ctk.CTkOptionMenu(head, variable=self.var_filter,
                                values=["all", "ok+error", "error only", "info+ok"],
                                width=120, command=self._on_filter_change)
        opt.pack(side="left", padx=2)

        self._topmost_btn = ctk.CTkButton(head, text="📌 Pin", width=80,
                                          command=self._toggle_topmost)
        self._topmost_btn.pack(side="right", padx=2)
        ctk.CTkButton(head, text="🗑 Xóa", width=70,
                      command=self._clear).pack(side="right", padx=2)
        ctk.CTkButton(head, text="💾 Save", width=70,
                      command=self._save).pack(side="right", padx=2)

        self.log_box = ctk.CTkTextbox(self,
                                       font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._topmost = False

        # Bind bus → widget
        self.app.log_bus.attach_widget(self.log_box)

    def _on_filter_change(self, val):
        mapping = {
            "all": None,
            "ok+error": {"ok", "error", "no_perm", "invalid", "fresh", "privacy"},
            "error only": {"error", "no_perm", "invalid"},
            "info+ok": {"info", "ok"},
        }
        self.app.log_bus.set_filter(mapping.get(val))

    def _toggle_topmost(self):
        self._topmost = not self._topmost
        self.attributes("-topmost", self._topmost)
        self._topmost_btn.configure(
            text="📌 Pin: ON" if self._topmost else "📌 Pin",
            fg_color="#22aa55" if self._topmost else None)

    def _on_close(self):
        self.withdraw()

    def _clear(self):
        self.app.log_bus.clear()

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log", "*.log *.txt"), ("All", "*.*")])
        if not path: return
        lines = self.app.log_bus.export_lines()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("OK", f"Đã lưu {len(lines)} dòng")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def show(self):
        self.deiconify(); self.lift()


# ────────────────────────────────────────────────────────────────────
class App:
    """Multi-Telegram tool — entry."""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Multi-Telegram Tool v7")
        self.root.geometry("1300x920")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Core services
        self.cfg = ConfigStore(
            Path(__file__).parent / "tg_tool_config.json",
            tk_root=self.root)
        self.log_bus = LogBus(self.root)
        self.runner = SharedTaskRunner().start()
        self.bridge = AsyncBridge(self.runner, self.log_bus,
                                   on_status=self.set_status)

        # State
        self.window_manager = WindowManager()
        self.log_window = None

        self._build()
        self.log_bus.attach_status_setter(self.set_status)

    def ensure_log_window(self):
        if self.log_window is None or not self.log_window.winfo_exists():
            self.log_window = FloatingLogWindow(self.root, self)
        else:
            try: self.log_window.deiconify()
            except Exception: pass

    def _build(self):
        # Header
        header = ctk.CTkFrame(self.root)
        header.pack(fill="x", padx=12, pady=(12, 4))
        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(top, text="🚀 Multi-Telegram Tool v7",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        # Indicator running tasks
        self.lbl_runner = ctk.CTkLabel(top, text="", text_color="#888")
        self.lbl_runner.pack(side="left", padx=20)
        self._poll_runner_status()

        ctk.CTkButton(top, text="📜 Mở log", width=110,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      command=self.ensure_log_window).pack(side="right", padx=4)
        ctk.CTkButton(top, text="⏹ Hủy hết", width=110,
                      fg_color="#cc3333", hover_color="#aa2222",
                      command=self._cancel_all).pack(side="right", padx=4)

        ctk.CTkLabel(header, text="Thư mục gốc:").pack(anchor="w", padx=10, pady=(4, 0))
        prow = ctk.CTkFrame(header, fg_color="transparent")
        prow.pack(fill="x", padx=10, pady=(0, 8))
        self.base_folder = ctk.CTkEntry(prow, placeholder_text="Nơi lưu folder các acc")
        self.base_folder.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(prow, text="Chọn...", width=80,
                      command=self._pick_base).pack(side="left", padx=2)
        self.cfg.bind_entry(self.base_folder, "base_folder", "")

        # Tabs
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.tabs.add("🔐 Đăng nhập")
        self.tabs.add("🛠️ Admin & Channel")
        self.tabs.add("🔄 Đồng bộ tab")

        self.login_tab = LoginTab(self.tabs.tab("🔐 Đăng nhập"), self)
        self.admin_tab = AdminTab(self.tabs.tab("🛠️ Admin & Channel"), self)
        self.sync_tab = SyncTab(self.tabs.tab("🔄 Đồng bộ tab"), self)

        # Restore last active tab
        last = self.cfg.get("last_tab")
        if last in ["🔐 Đăng nhập", "🛠️ Admin & Channel", "🔄 Đồng bộ tab"]:
            try: self.tabs.set(last)
            except Exception: pass
        # Save tab change
        try:
            orig = self.tabs._segmented_button._command
            def _wrap(v):
                self.cfg.set("last_tab", v)
                if orig: orig(v)
            self.tabs._segmented_button.configure(command=_wrap)
        except Exception: pass

        # Status bar
        self.status_bar = ctk.CTkLabel(
            self.root, text="⏸ Sẵn sàng", anchor="w",
            fg_color="#1a1a1a", text_color="#88ccff",
            font=ctk.CTkFont(family="Consolas", size=12), height=26)
        self.status_bar.pack(fill="x", side="bottom", padx=0, pady=0)

    def set_status(self, text, color="#88ccff"):
        try:
            self.root.after(0, lambda: self.status_bar.configure(
                text=f" {text}", text_color=color))
        except Exception: pass

    def _poll_runner_status(self):
        try:
            n = self.runner.running_count()
            if n > 0:
                self.lbl_runner.configure(text=f"⚙ {n} task chạy",
                                           text_color="#ffaa44")
            else:
                self.lbl_runner.configure(text="", text_color="#888")
        except Exception: pass
        self.root.after(1000, self._poll_runner_status)

    def _cancel_all(self):
        n = self.runner.running_count()
        if n == 0:
            messagebox.showinfo("Trống", "Không có task nào đang chạy."); return
        if not messagebox.askyesno("Hủy?",
            f"Hủy {n} task đang chạy? Thao tác đã gửi tới Telegram\n"
            f"không thể undo, chỉ cancel phần CHƯA gửi."):
            return
        cancelled = self.runner.cancel_all()
        self.log_bus.write("info", f"⏹ Đã yêu cầu hủy {cancelled} task")

    def _pick_base(self):
        p = filedialog.askdirectory(title="Chọn thư mục gốc")
        if p:
            self.base_folder.delete(0, "end")
            self.base_folder.insert(0, p)
            self.cfg.set("base_folder", p)

    def _on_close(self):
        self.cfg.save()
        try: self.log_bus.stop()
        except Exception: pass
        try: self.runner.shutdown()
        except Exception: pass
        self.root.destroy()

    # ──── Win API helpers (chia sẻ cho login_tab + sync_tab) ────
    @staticmethod
    def get_window_pid(hwnd):
        try:
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(
                hwnd, ctypes.byref(pid))
            return pid.value
        except Exception: return 0

    @staticmethod
    def get_work_area():
        try:
            rect = wintypes.RECT()
            ok = ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0)
            if ok:
                return (rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top)
        except Exception: pass
        try:
            from screeninfo import get_monitors
            mon = get_monitors()[0]
            return (mon.x, mon.y, mon.width, mon.height - 48)
        except Exception:
            return (0, 0, 1920, 1032)

    @staticmethod
    def set_window_pos(hwnd, x, y, w, h):
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, flags)

    def close_all_tabs(self):
        items = self.window_manager.get_alive()
        if not items:
            messagebox.showinfo("Trống", "Không có tab nào!"); return
        if not messagebox.askyesno("Xác nhận",
            f"Đóng {len(items)} tab Telegram?"): return
        WM_CLOSE = 0x0010
        sent = 0
        for hwnd, pid, name in items:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                sent += 1
            except Exception: pass
        time.sleep(1.5)
        survivors = self.window_manager.get_alive()
        try: self.sync_tab.count_label.configure(text=f"{len(survivors)} tab")
        except Exception: pass
        msg = f"Đã đóng {sent}/{len(items)} tab."
        if survivors:
            msg += f"\n⚠ {len(survivors)} tab còn (có thể đang hỏi save)."
        self.set_status(f"✅ Đóng {sent - len(survivors)}/{sent} tab", "#00cc66")
        messagebox.showinfo("Xong", msg)

    def run(self):
        # Auto mở log window 1 lần khi start (ẩn ngay)
        self.ensure_log_window()
        self.log_window.withdraw()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
