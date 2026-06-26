"""
sync_tab.py — Tab 3 Đồng bộ tab Telegram
=========================================
Track tab Telegram đã mở qua Tab 1, broadcast text qua nhiều tab cùng lúc.
"""

from __future__ import annotations

import math
import threading
import time
import ctypes

import customtkinter as ctk
from tkinter import messagebox


class WindowManager:
    """Track tab Telegram do tool tự mở. Match theo PID."""

    def __init__(self):
        self.tracked = []  # (hwnd, pid, folder_name)

    def clear(self):
        self.tracked = []

    def add(self, hwnd, pid, folder_name):
        self.tracked.append((hwnd, pid, folder_name))

    def remove_hwnd(self, hwnd):
        self.tracked = [t for t in self.tracked if t[0] != hwnd]

    def get_alive(self):
        try:
            alive = []
            for hwnd, pid, name in self.tracked:
                if ctypes.windll.user32.IsWindow(hwnd):
                    alive.append((hwnd, pid, name))
            self.tracked = alive
            return alive
        except Exception:
            return self.tracked

    def count(self):
        return len(self.get_alive())


class SyncTab:
    def __init__(self, parent, app):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        sec0 = ctk.CTkFrame(self.parent)
        sec0.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(sec0,
            text="Chỉ thao tác trên tab Telegram do tool tự mở (qua 🪟 Tab 1).\n"
                 "Tab khác trên máy KHÔNG bị đụng vào.",
            justify="left", text_color="#aaa",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=10, pady=8)

        sec_st = ctk.CTkFrame(self.parent)
        sec_st.pack(fill="x", padx=10, pady=6)
        row = ctk.CTkFrame(sec_st, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(row, text="Tab đang track:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        self.count_label = ctk.CTkLabel(row, text="0 tab",
                                         text_color="#88ccff",
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.count_label.pack(side="left", padx=4)
        ctk.CTkButton(row, text="🔄 Cập nhật", width=110,
                      command=self._refresh_count).pack(side="left", padx=4)
        ctk.CTkButton(row, text="📋 Xem danh sách", width=140,
                      command=self._show_list).pack(side="left", padx=4)

        sec1 = ctk.CTkFrame(self.parent)
        sec1.pack(fill="both", expand=True, padx=10, pady=6)
        ctk.CTkLabel(sec1, text="✍️ Gửi text đồng bộ tới tất cả tab",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(sec1,
            text="Tool focus từng tab → paste → Enter (nếu chọn).\n"
                 "Đảm bảo tab Telegram đang mở ở ô chat.",
            text_color="gray", font=ctk.CTkFont(size=11), justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 4))

        self.sync_text = ctk.CTkTextbox(sec1, height=120)
        self.sync_text.pack(fill="x", padx=10, pady=4)
        self.sync_text.insert("0.0", "Hello world!")
        self.app.cfg.bind_textbox(self.sync_text, "sync_text", "Hello world!")

        opt = ctk.CTkFrame(sec1, fg_color="transparent")
        opt.pack(fill="x", padx=10, pady=4)
        self.send_press_enter = ctk.CTkCheckBox(opt, text="Nhấn Enter (gửi luôn)")
        self.send_press_enter.select()
        self.send_press_enter.pack(side="left", padx=4)
        ctk.CTkLabel(opt, text="   Delay giữa tab (s):").pack(side="left", padx=(20, 2))
        self.sync_delay = ctk.CTkEntry(opt, width=60); self.sync_delay.insert(0, "0.3")
        self.sync_delay.pack(side="left")
        self.app.cfg.bind_entry(self.sync_delay, "sync_delay", "0.3")

        ctk.CTkButton(sec1, text="📤 GỬI ĐỒNG BỘ TỚI TẤT CẢ TAB", height=40,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._broadcast_text).pack(fill="x", padx=10, pady=(8, 12))

        sec2 = ctk.CTkFrame(self.parent)
        sec2.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(sec2, text="🎛️ Điều khiển cửa sổ",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(anchor="w", padx=10, pady=(8, 4))
        row = ctk.CTkFrame(sec2, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)
        ctk.CTkButton(row, text="🪟 Re-tile", width=130,
                      command=self._retile).pack(side="left", padx=3)
        ctk.CTkButton(row, text="📍 Đưa lên trên", width=140,
                      command=self._bring_to_front).pack(side="left", padx=3)
        ctk.CTkButton(row, text="❌ ĐÓNG TẤT CẢ TAB", width=180,
                      fg_color="#cc3333", hover_color="#aa2222",
                      command=self._close_all).pack(side="left", padx=3)

    def _refresh_count(self):
        n = self.app.window_manager.count()
        self.count_label.configure(text=f"{n} tab")
        self.app.log_bus.write("info", f"🔄 Hiện có {n} tab đang track")

    def _show_list(self):
        items = self.app.window_manager.get_alive()
        if not items:
            messagebox.showinfo("Trống",
                "Chưa có tab nào.\nVào Tab 1 → 🪟 Mở + chia màn hình."); return
        lines = [f"{i+1:02d}. hwnd={hwnd:#x} pid={pid}  {name}"
                 for i, (hwnd, pid, name) in enumerate(items)]
        messagebox.showinfo("Danh sách tab", "\n".join(lines))

    def _broadcast_text(self):
        text = self.sync_text.get("0.0", "end").rstrip("\n")
        if not text:
            messagebox.showerror("Lỗi", "Nội dung trống!"); return
        items = self.app.window_manager.get_alive()
        if not items:
            messagebox.showinfo("Trống", "Chưa có tab nào!"); return
        try: delay = max(0.0, float(self.sync_delay.get()))
        except: delay = 0.3
        press_enter = bool(self.send_press_enter.get())

        if not messagebox.askyesno("Xác nhận",
            f"Gửi tới {len(items)} tab Telegram?\n"
            f"Đảm bảo các tab đang ở ô chat."):
            return

        threading.Thread(target=self._th_broadcast,
                         args=(text, items, delay, press_enter),
                         daemon=True).start()

    def _th_broadcast(self, text, items, delay, press_enter):
        self.app.log_bus.write("info", f"📤 Gửi tới {len(items)} tab...")
        sent = 0
        for i, (hwnd, pid, name) in enumerate(items, 1):
            try:
                self.app.log_bus.write("info", f"  [{i}/{len(items)}] {name}...")
                self._send_to_window(hwnd, text, press_enter)
                sent += 1
            except Exception as e:
                self.app.log_bus.write("error", f"  ❌ {name}: {e}")
            time.sleep(delay)
        self.app.log_bus.write("ok", f"✅ Đã gửi {sent}/{len(items)}")

    def _send_to_window(self, hwnd, text, press_enter):
        user32 = ctypes.windll.user32
        self._set_clipboard(text)
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        VK_CONTROL = 0x11; VK_V = 0x56; VK_RETURN = 0x0D
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)
        if press_enter:
            user32.keybd_event(VK_RETURN, 0, 0, 0)
            user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)

    def _set_clipboard(self, text):
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.restype = ctypes.c_void_p
        text_b = (text + "\0").encode("utf-16-le")
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_b))
        ptr = kernel32.GlobalLock(h_mem)
        ctypes.memmove(ptr, text_b, len(text_b))
        kernel32.GlobalUnlock(h_mem)
        user32.OpenClipboard(0)
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        user32.CloseClipboard()

    def _retile(self):
        items = self.app.window_manager.get_alive()
        if not items:
            messagebox.showinfo("Trống", "Không có tab nào!"); return
        threading.Thread(target=self._th_retile, args=(items,),
                         daemon=True).start()

    def _th_retile(self, items):
        self.app.log_bus.write("info", f"🪟 Re-tile {len(items)} tab...")
        try: wx, wy, ww, wh = self.app.get_work_area()
        except Exception as e:
            self.app.log_bus.write("error", f"❌ {e}"); return
        GAP = 4
        n = len(items)
        cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
        cell_w = (ww - GAP * (cols + 1)) // cols
        cell_h = (wh - GAP * (rows + 1)) // rows
        ok = 0
        for i, (hwnd, pid, name) in enumerate(items):
            r, c = i // cols, i % cols
            x = wx + GAP + c * (cell_w + GAP)
            y = wy + GAP + r * (cell_h + GAP)
            try:
                self.app.set_window_pos(hwnd, x, y, cell_w, cell_h); ok += 1
            except Exception as e:
                self.app.log_bus.write("error", f"  ❌ {name}: {e}")
        self.app.log_bus.write("ok", f"✅ Re-tile xong {ok}/{n}")

    def _bring_to_front(self):
        items = self.app.window_manager.get_alive()
        if not items:
            messagebox.showinfo("Trống", "Không có tab!"); return
        ok = 0
        for hwnd, pid, name in items:
            try:
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.BringWindowToTop(hwnd); ok += 1
            except Exception: pass
        self.app.log_bus.write("info", f"📍 Đưa {ok}/{len(items)} tab lên trên")

    def _close_all(self):
        self.app.close_all_tabs()
        self._refresh_count()
