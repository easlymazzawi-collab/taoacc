"""
login_tab.py — Tab 1 Đăng nhập (refactor)
==========================================
Thay đổi chính so với bản gốc:
  - AccountRow KHÔNG còn tự tạo asyncio loop riêng (bản gốc mỗi row tạo
    1 loop + 1 thread, 30 acc = 30 loop → kill RAM + lag).
  - Mọi coroutine dùng chung SharedTaskRunner của app.
  - Bulk send / bulk login dùng asyncio.Semaphore để cap concurrent
    (tránh Telegram flood).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import math
import threading
import time
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneNumberInvalidError, FloodWaitError,
)
from opentele.api import UseCurrentSession
from opentele.tl import TelegramClient

from admin_channel import load_or_create_api


def sanitize_folder_name(name: str) -> str:
    if not name: return ""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or ""


# ────────────────────────────────────────────────────────────────────
class BulkPhoneDialog(ctk.CTkToplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.title("📥 Nhập SĐT hàng loạt")
        self.geometry("540x600")
        self.app = app
        self.transient(master); self.grab_set()

        ctk.CTkLabel(self, text="Mỗi dòng:  SĐT  hoặc  SĐT | 2FA",
                     font=ctk.CTkFont(size=13)).pack(pady=(12, 4))

        # ── Field 2FA chung (nhập 1 lần, áp cho mọi dòng không nhập riêng)
        fr2 = ctk.CTkFrame(self, fg_color="#1a2030", corner_radius=6)
        fr2.pack(fill="x", padx=12, pady=(4, 6))
        ctk.CTkLabel(fr2, text="🔒 2FA chung cho tất cả acc:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#ffcc66"
                     ).pack(side="left", padx=(10, 6), pady=8)
        self.common_2fa = ctk.CTkEntry(
            fr2, placeholder_text="(nếu không nhập sẽ để trống)",
            show="*", width=200)
        self.common_2fa.pack(side="left", padx=4, pady=8)

        self._show_2fa = False
        self.btn_eye = ctk.CTkButton(
            fr2, text="👁", width=36,
            command=self._toggle_show_2fa,
            fg_color="#444", hover_color="#555")
        self.btn_eye.pack(side="left", padx=4, pady=8)

        ctk.CTkLabel(
            self,
            text="• Dòng có '| pwd' riêng → dùng pwd đó (override)\n"
                 "• Dòng KHÔNG có '|' → tự áp 2FA chung ở trên",
            text_color="#888", font=ctk.CTkFont(size=10),
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 4))

        self.textbox = ctk.CTkTextbox(self, width=500, height=320)
        self.textbox.pack(padx=12, pady=4)
        self.textbox.insert("0.0",
            "+84912345678\n+84987654321\n+84111222333\n")

        ctk.CTkLabel(self, text="Phân cách: |  tab  hoặc  2 spaces",
                     text_color="gray", font=ctk.CTkFont(size=11)
                     ).pack(pady=(0, 4))
        btns = ctk.CTkFrame(self, fg_color="transparent"); btns.pack(pady=8)
        ctk.CTkButton(btns, text="📂 Load .txt", width=130,
                      command=self._load).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="✅ Áp dụng", width=110,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      command=self._apply).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Hủy", width=80,
                      fg_color="#666", hover_color="#555",
                      command=self.destroy).pack(side="left", padx=4)

    def _toggle_show_2fa(self):
        self._show_2fa = not self._show_2fa
        self.common_2fa.configure(show="" if self._show_2fa else "*")
        self.btn_eye.configure(text="🙈" if self._show_2fa else "👁")

    def _load(self):
        p = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not p: return
        try: content = open(p, encoding="utf-8").read()
        except UnicodeDecodeError: content = open(p, encoding="latin-1").read()
        self.textbox.delete("0.0", "end"); self.textbox.insert("0.0", content)

    def _apply(self):
        common = self.common_2fa.get().strip()
        content = self.textbox.get("0.0", "end").strip()
        entries = []
        used_common = 0
        for line in content.splitlines():
            line = line.strip()
            if not line: continue
            parts = re.split(r"\s*\|\s*|\t+|\s{2,}", line, maxsplit=1)
            phone = re.sub(r"[^\d+]", "", parts[0])
            line_twofa = parts[1].strip() if len(parts) > 1 else ""

            # Logic: dòng riêng override 2FA chung
            if line_twofa:
                twofa = line_twofa
            elif common:
                twofa = common
                used_common += 1
            else:
                twofa = ""

            if phone and (phone.startswith("+") or len(phone) >= 9):
                if not phone.startswith("+"): phone = "+" + phone
                entries.append((phone, twofa))
        if not entries:
            messagebox.showwarning("Trống", "Không tìm thấy SĐT hợp lệ!"); return

        info = f"Đã import {len(entries)} SĐT"
        if used_common:
            info += f"\n  → {used_common} dòng dùng 2FA chung"
        n_specific = sum(1 for _, t in entries if t) - used_common
        if n_specific:
            info += f"\n  → {n_specific} dòng có 2FA riêng"
        messagebox.showinfo("OK", info)

        self.app.apply_bulk_entries(entries)
        self.destroy()


class BulkCodeDialog(ctk.CTkToplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.title("📝 Nhập mã code hàng loạt")
        self.geometry("560x560")
        self.app = app
        self.transient(master); self.grab_set()
        ctk.CTkLabel(self, text="Nhập mã code cho từng acc",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12, 2))
        ctk.CTkLabel(self,
            text="• 1 mã/dòng → điền theo thứ tự\n"
                 "• +84xxx | 12345 → khớp theo SĐT\n"
                 "• +84xxx | 12345 | 2fapwd → khớp + 2FA",
            text_color="gray", font=ctk.CTkFont(size=11),
            justify="left").pack(pady=(0, 6), padx=12, anchor="w")

        existing = [f"  #{i:02d}  {row.phone.get().strip()}"
                    + (f"   [code: {row.code.get().strip()}]" if row.code.get().strip() else "")
                    for i, row in enumerate(app.rows, 1)
                    if row.phone.get().strip()]
        if existing:
            ctk.CTkLabel(self, text="SĐT hiện có:",
                         text_color="#888", font=ctk.CTkFont(size=11)
                         ).pack(anchor="w", padx=14)
            ref = ctk.CTkTextbox(self, width=520, height=80,
                                 font=ctk.CTkFont(size=11), fg_color="#222")
            ref.pack(padx=12, pady=(0, 6))
            ref.insert("0.0", "\n".join(existing))
            ref.configure(state="disabled")
        self.textbox = ctk.CTkTextbox(self, width=520, height=240)
        self.textbox.pack(padx=12, pady=8)
        btns = ctk.CTkFrame(self, fg_color="transparent"); btns.pack(pady=8)
        ctk.CTkButton(btns, text="📂 Load .txt", width=130,
                      command=self._load).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="✅ Áp dụng", width=110,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      command=self._apply).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Hủy", width=80,
                      fg_color="#666", hover_color="#555",
                      command=self.destroy).pack(side="left", padx=4)

    def _load(self):
        p = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not p: return
        try: content = open(p, encoding="utf-8").read()
        except UnicodeDecodeError: content = open(p, encoding="latin-1").read()
        self.textbox.delete("0.0", "end"); self.textbox.insert("0.0", content)

    def _apply(self):
        content = self.textbox.get("0.0", "end").strip()
        parsed = []
        for line in content.splitlines():
            line = line.strip()
            if not line: continue
            parts = re.split(r"\s*\|\s*|\t+|\s{2,}", line)
            if len(parts) == 1:
                code = re.sub(r"\D", "", parts[0])
                if code: parsed.append((None, code, ""))
            else:
                phone = re.sub(r"[^\d+]", "", parts[0])
                if phone and not phone.startswith("+"): phone = "+" + phone
                code = re.sub(r"\D", "", parts[1])
                twofa = parts[2].strip() if len(parts) > 2 else ""
                if code:
                    parsed.append((phone if phone else None, code, twofa))
        if not parsed:
            messagebox.showwarning("Trống", "Không tìm thấy code hợp lệ!"); return
        self.app.apply_bulk_codes(parsed)
        self.destroy()


# ────────────────────────────────────────────────────────────────────
class AccountRow(ctk.CTkFrame):
    """
    Một dòng acc trong tab Login. KHÔNG còn tự tạo loop — submit
    coroutine vào SharedTaskRunner của app.
    """

    def __init__(self, master, index, app, **kw):
        super().__init__(master, **kw)
        self.index = index
        self.app = app
        self.client = None
        self.phone_code_hash = None
        self.current_folder = None
        self._build()

    def _build(self):
        r1 = ctk.CTkFrame(self, fg_color="transparent")
        r1.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(r1, text=f"#{self.index:02d}", width=35,
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(r1, text="Folder:").pack(side="left", padx=(8, 2))
        self.folder = ctk.CTkEntry(r1, placeholder_text=f"acc_{self.index:02d}", width=140)
        self.folder.pack(side="left", padx=2)
        ctk.CTkLabel(r1, text="Ghi chú:").pack(side="left", padx=(8, 2))
        self.note = ctk.CTkEntry(r1, placeholder_text="tên/username", width=160)
        self.note.pack(side="left", padx=2)
        ctk.CTkLabel(r1, text="SĐT:").pack(side="left", padx=(8, 2))
        self.phone = ctk.CTkEntry(r1, placeholder_text="+84...", width=150)
        self.phone.pack(side="left", padx=2)

        r2 = ctk.CTkFrame(self, fg_color="transparent")
        r2.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(r2, text="    ", width=35).pack(side="left", padx=4)
        ctk.CTkLabel(r2, text="Code:").pack(side="left", padx=(8, 2))
        self.code = ctk.CTkEntry(r2, placeholder_text="12345", width=80)
        self.code.pack(side="left", padx=2)
        ctk.CTkLabel(r2, text="2FA:").pack(side="left", padx=(8, 2))
        self.twofa = ctk.CTkEntry(r2, placeholder_text="(nếu có)", width=120, show="*")
        self.twofa.pack(side="left", padx=2)
        self.btn_send = ctk.CTkButton(r2, text="📩 Gửi mã", width=90,
                                       command=self._on_send)
        self.btn_send.pack(side="left", padx=(8, 2))
        self.btn_login = ctk.CTkButton(r2, text="🔐 Đăng nhập", width=120,
                                        command=self._on_login, state="disabled",
                                        fg_color="#1f6feb", hover_color="#1158c7")
        self.btn_login.pack(side="left", padx=2)
        self.status = ctk.CTkLabel(r2, text="⏸  Sẵn sàng",
                                    text_color="gray", anchor="w")
        self.status.pack(side="left", padx=10, fill="x", expand=True)

    def _set_status(self, t, c="white"):
        self.after(0, lambda: self.status.configure(text=t, text_color=c))

    def _set_btn(self, b, s):
        self.after(0, lambda: b.configure(state=s))

    def _set_folder_field(self, name):
        def upd():
            self.folder.delete(0, "end"); self.folder.insert(0, name)
        self.after(0, upd)

    def _initial_folder_name(self):
        n = self.folder.get().strip()
        return n if n else f"acc_{self.index:02d}"

    # ---- Submit qua SharedTaskRunner ----
    def _submit(self, coro, on_err=None):
        def err_handler(e):
            if on_err: on_err(e)
            else:
                self._set_status(f"❌ {str(e)[:60]}", "red")
        self.app.runner.submit(
            f"login_row_{self.index}", coro,
            on_error=err_handler)

    def _on_send(self):
        base = self.app.base_folder.get().strip()
        if not base:
            messagebox.showerror("Lỗi", "Chưa chọn thư mục gốc!"); return
        ph = self.phone.get().strip()
        if not ph:
            messagebox.showerror("Lỗi", "Chưa nhập SĐT!"); return
        self.btn_send.configure(state="disabled")
        self._set_status("⏳ Đang gửi mã...", "#ffcc00")

        def on_err(e):
            if isinstance(e, FloodWaitError):
                self._set_status(f"❌ Flood {e.seconds}s", "red")
            elif isinstance(e, PhoneNumberInvalidError):
                self._set_status("❌ SĐT sai", "red")
            else:
                self._set_status(f"❌ {str(e)[:60]}", "red")
            self._set_btn(self.btn_send, "normal")

        self._submit(self._async_send(ph, base), on_err=on_err)

    async def _async_send(self, phone, base):
        folder = Path(base) / self._initial_folder_name()
        folder.mkdir(parents=True, exist_ok=True)
        self.current_folder = folder

        api = load_or_create_api(folder)
        self.client = TelegramClient(str(folder / "_telethon"), api=api)
        await self.client.connect()
        if await self.client.is_user_authorized():
            self._set_status("✅ Session sẵn, lưu tdata...", "#00cc66")
            await self._finish_login(); return
        sent = await self.client.send_code_request(phone)
        self.phone_code_hash = sent.phone_code_hash
        self._set_status("📩 Đã gửi → nhập Code rồi nhấn Đăng nhập", "#22aaff")
        self._set_btn(self.btn_login, "normal")
        self._set_btn(self.btn_send, "normal")

    def _on_login(self):
        c = self.code.get().strip()
        if not c:
            messagebox.showerror("Lỗi", "Chưa nhập code!"); return
        self.btn_login.configure(state="disabled")
        self._set_status("⏳ Đang đăng nhập...", "#ffcc00")

        def on_err(e):
            self._set_status(f"❌ {str(e)[:60]}", "red")
            self._set_btn(self.btn_login, "normal")

        self._submit(self._async_login(c), on_err=on_err)

    async def _async_login(self, code):
        phone = self.phone.get().strip()
        twofa = self.twofa.get().strip()
        try:
            await self.client.sign_in(phone=phone, code=code,
                                      phone_code_hash=self.phone_code_hash)
        except SessionPasswordNeededError:
            if not twofa:
                self._set_status("⚠ Acc bật 2FA — nhập password rồi bấm lại",
                                 "orange")
                self._set_btn(self.btn_login, "normal"); return
            try:
                await self.client.sign_in(password=twofa)
            except Exception as e:
                self._set_status(f"❌ 2FA sai: {str(e)[:40]}", "red")
                self._set_btn(self.btn_login, "normal"); return
        except PhoneCodeInvalidError:
            self._set_status("❌ Code sai", "red")
            self._set_btn(self.btn_login, "normal"); return
        await self._finish_login()

    async def _finish_login(self):
        me = None
        try:
            self._set_status("💾 Tạo tdata...", "#ffcc00")
            tdata = self.current_folder / "tdata"
            if tdata.exists():
                shutil.rmtree(tdata, ignore_errors=True)
            tdesk = await self.client.ToTDesktop(flag=UseCurrentSession)
            tdesk.SaveTData(str(tdata))
            me = await self.client.get_me()
        except Exception as e:
            self._set_status(f"⚠ Login OK nhưng tdata lỗi: {str(e)[:50]}", "orange")
        finally:
            try: await self.client.disconnect()
            except Exception: pass
        if me is None: return
        final = self._maybe_rename(me)
        self.current_folder = final
        self._maybe_copy_portable(final)
        uname = f"@{me.username}" if me.username else "(no @)"
        self._set_status(f"✅ {me.first_name or ''} {uname} → 📁 {final.name}", "#00cc66")

    def _maybe_rename(self, me):
        mode = self.app.naming_var.get()
        old = self.current_folder
        if mode == "manual": return old
        if mode == "username":
            target = me.username or me.first_name or f"acc_{self.index:02d}"
        elif mode == "firstname":
            target = me.first_name or me.username or f"acc_{self.index:02d}"
        elif mode == "prefix":
            prefix = self.app.prefix_entry.get().strip() or "acc"
            target = f"{prefix}_{self.index:02d}"
        else:
            return old
        target = sanitize_folder_name(target) or f"acc_{self.index:02d}"
        if target == old.name: return old
        new = old.parent / target
        cnt = 1
        while new.exists():
            new = old.parent / f"{target}_{cnt}"; cnt += 1
        try:
            old.rename(new)
            self._set_folder_field(new.name)
            return new
        except Exception as e:
            print(f"Rename lỗi: {e}")
            return old

    def _maybe_copy_portable(self, folder):
        src = self.app.portable_src.get().strip()
        if not src or not os.path.isdir(src): return
        try:
            for item in os.listdir(src):
                if item.lower() == "tdata": continue
                s = os.path.join(src, item)
                d = os.path.join(str(folder), item)
                if os.path.isdir(s):
                    if not os.path.exists(d): shutil.copytree(s, d)
                else:
                    if not os.path.exists(d): shutil.copy2(s, d)
        except Exception as e:
            print(f"Copy portable lỗi: {e}")


# ────────────────────────────────────────────────────────────────────
class LoginTab:
    """Tab Đăng nhập + Bulk + Tile windows."""

    def __init__(self, parent, app):
        self.app = app
        self.parent = parent
        self.rows = []
        self._build()

    def _build(self):
        cfg = ctk.CTkFrame(self.parent)
        cfg.pack(fill="x", padx=10, pady=(10, 4))

        r1 = ctk.CTkFrame(cfg, fg_color="transparent")
        r1.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r1, text="Telegram Portable (tùy chọn):", width=200,
                     anchor="w").pack(side="left")
        self.app.portable_src = ctk.CTkEntry(r1, placeholder_text="Folder chứa Telegram.exe")
        self.app.portable_src.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(r1, text="Chọn...", width=80,
                      command=self._pick_portable).pack(side="left")
        self.app.cfg.bind_entry(self.app.portable_src, "portable_src", "")

        r2 = ctk.CTkFrame(cfg, fg_color="transparent")
        r2.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r2, text="Tên folder sau login:", width=200,
                     anchor="w").pack(side="left")
        self.app.naming_var = ctk.StringVar(value="username")
        for txt, val in [("@username", "username"), ("Tên hiển thị", "firstname"),
                          ("Prefix:", "prefix")]:
            ctk.CTkRadioButton(r2, text=txt, variable=self.app.naming_var,
                               value=val).pack(side="left", padx=4)
        self.app.prefix_entry = ctk.CTkEntry(r2, placeholder_text="vd: client", width=120)
        self.app.prefix_entry.pack(side="left", padx=2)
        ctk.CTkRadioButton(r2, text="Giữ nguyên",
                           variable=self.app.naming_var, value="manual"
                           ).pack(side="left", padx=8)
        self.app.cfg.bind_var(self.app.naming_var, "naming_var", "username")
        self.app.cfg.bind_entry(self.app.prefix_entry, "prefix_entry", "")

        r3 = ctk.CTkFrame(cfg, fg_color="transparent"); r3.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r3, text="Số acc:", width=200, anchor="w").pack(side="left")
        self.num = ctk.CTkEntry(r3, width=60); self.num.insert(0, "5")
        self.num.pack(side="left", padx=2)
        ctk.CTkButton(r3, text="📋 Tạo bảng", width=110,
                      command=self._gen).pack(side="left", padx=4)
        ctk.CTkButton(r3, text="📥 Nhập SĐT hàng loạt", width=180,
                      fg_color="#aa44cc", hover_color="#8833aa",
                      command=self._open_bulk_phone).pack(side="left", padx=4)
        ctk.CTkButton(r3, text="🔒 Áp 2FA cho hết", width=160,
                      fg_color="#ffcc66", hover_color="#e0b850",
                      text_color="#000",
                      command=self._apply_common_2fa).pack(side="left", padx=4)
        ctk.CTkButton(r3, text="🗑 Xóa hết", width=90,
                      fg_color="#cc3333", hover_color="#aa2222",
                      command=self._clear).pack(side="left", padx=4)
        self.app.cfg.bind_entry(self.num, "num_acc", "5")

        r4 = ctk.CTkFrame(cfg, fg_color="transparent"); r4.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r4, text="Bulk login:", width=200, anchor="w").pack(side="left")
        ctk.CTkButton(r4, text="📩 Gửi mã TẤT CẢ", width=160,
                      fg_color="#dd8822", hover_color="#bb6f1c",
                      command=self._send_all).pack(side="left", padx=3)
        ctk.CTkButton(r4, text="📝 Nhập mã hàng loạt", width=170,
                      fg_color="#aa44cc", hover_color="#8833aa",
                      command=self._open_bulk_code).pack(side="left", padx=3)
        ctk.CTkButton(r4, text="🔐 Đăng nhập TẤT CẢ", width=170,
                      fg_color="#1f6feb", hover_color="#1158c7",
                      command=self._login_all).pack(side="left", padx=3)

        r5 = ctk.CTkFrame(cfg, fg_color="transparent"); r5.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r5, text="Mở Telegram:", width=200, anchor="w").pack(side="left")
        ctk.CTkButton(r5, text="🪟 Mở tất cả + chia màn hình", width=240,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      command=self._launch_and_tile).pack(side="left", padx=3)
        ctk.CTkButton(r5, text="❌ Đóng tất cả tab", width=160,
                      fg_color="#cc3333", hover_color="#aa2222",
                      command=self.app.close_all_tabs).pack(side="left", padx=3)

        self.scroll = ctk.CTkScrollableFrame(self.parent,
                                             label_text="📒 Danh sách tài khoản")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def _pick_portable(self):
        p = filedialog.askdirectory(title="Chọn folder Telegram Portable")
        if p:
            self.app.portable_src.delete(0, "end")
            self.app.portable_src.insert(0, p)
            self.app.cfg.set("portable_src", p)

    def _gen(self):
        try:
            n = int(self.num.get())
            if n < 1 or n > 200: raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số acc 1–200!"); return
        self._clear()
        for _ in range(n): self._add_row()

    def _add_row(self):
        r = AccountRow(self.scroll, len(self.rows) + 1, self.app)
        r.pack(fill="x", pady=4)
        self.rows.append(r)
        return r

    def _clear(self):
        for r in self.rows: r.destroy()
        self.rows = []

    def _open_bulk_phone(self):
        BulkPhoneDialog(self.parent.winfo_toplevel(), self)

    def _open_bulk_code(self):
        if not self.rows:
            messagebox.showinfo("Trống", "Chưa có dòng nào!"); return
        BulkCodeDialog(self.parent.winfo_toplevel(), self)

    def apply_bulk_entries(self, entries):
        while len(self.rows) < len(entries): self._add_row()
        for i, (phone, twofa) in enumerate(entries):
            row = self.rows[i]
            row.phone.delete(0, "end"); row.phone.insert(0, phone)
            if twofa:
                row.twofa.delete(0, "end"); row.twofa.insert(0, twofa)
        self.num.delete(0, "end"); self.num.insert(0, str(len(self.rows)))
        # Dialog đã hiển thị thông báo chi tiết trước khi gọi method này

    def _apply_common_2fa(self):
        """Popup nhập 1 password 2FA, fill vào tất cả row đang trống 2FA."""
        if not self.rows:
            messagebox.showinfo("Trống",
                "Chưa có row nào!\nBấm '📋 Tạo bảng' hoặc nhập bulk trước."); return

        # Đếm row có / không có 2FA
        empty_rows = [r for r in self.rows if not r.twofa.get().strip()]
        has_2fa = len(self.rows) - len(empty_rows)
        if not empty_rows:
            messagebox.showinfo("OK",
                f"Tất cả {len(self.rows)} row đã có 2FA rồi."); return

        # Mini dialog
        dlg = ctk.CTkToplevel(self.parent.winfo_toplevel())
        dlg.title("🔒 Áp 2FA chung")
        dlg.geometry("440x260")
        dlg.transient(self.parent.winfo_toplevel())
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="🔒 Áp 2FA cho tất cả acc trống",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(pady=(15, 6))
        ctk.CTkLabel(
            dlg,
            text=f"Có {len(self.rows)} row tổng:\n"
                 f"  • {has_2fa} đã có 2FA riêng (giữ nguyên)\n"
                 f"  • {len(empty_rows)} đang trống → áp 2FA này",
            text_color="#aaa", justify="left",
            font=ctk.CTkFont(size=11)
        ).pack(padx=15, pady=4, anchor="w")

        ctk.CTkLabel(dlg, text="2FA password:",
                     anchor="w").pack(fill="x", padx=15, pady=(8, 2))
        pwd_var = ctk.StringVar()
        ent = ctk.CTkEntry(dlg, textvariable=pwd_var, show="*", width=400)
        ent.pack(padx=15, pady=2)
        ent.focus()

        # Toggle hiện/ẩn
        show_var = ctk.BooleanVar(value=False)
        def _toggle():
            ent.configure(show="" if show_var.get() else "*")
        ctk.CTkCheckBox(dlg, text="Hiện password",
                        variable=show_var, command=_toggle,
                        font=ctk.CTkFont(size=11)
                        ).pack(padx=15, pady=4, anchor="w")

        # Buttons
        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(pady=(10, 15))

        def _do_apply():
            pwd = pwd_var.get().strip()
            if not pwd:
                messagebox.showwarning("Trống", "Chưa nhập password!"); return
            for row in empty_rows:
                row.twofa.delete(0, "end")
                row.twofa.insert(0, pwd)
            dlg.destroy()
            messagebox.showinfo("OK",
                f"Đã áp 2FA cho {len(empty_rows)} acc.\n"
                f"({has_2fa} acc đã có 2FA riêng, giữ nguyên)")

        ctk.CTkButton(bf, text="✅ Áp dụng", width=120,
                      fg_color="#22aa55", hover_color="#1c8d44",
                      command=_do_apply).pack(side="left", padx=6)
        ctk.CTkButton(bf, text="Hủy", width=80,
                      fg_color="#666", hover_color="#555",
                      command=dlg.destroy).pack(side="left", padx=6)

        # Enter = apply
        ent.bind("<Return>", lambda e: _do_apply())

    def apply_bulk_codes(self, parsed):
        matched_phone = matched_order = unmatched = skipped = 0
        empty_rows = [r for r in self.rows if not r.code.get().strip()]
        order_idx = 0
        for phone, code, twofa in parsed:
            target = None
            if phone:
                for row in self.rows:
                    if row.phone.get().strip() == phone:
                        if row.code.get().strip():
                            skipped += 1; continue
                        target = row; break
                if target: matched_phone += 1
                else:
                    if not any(r.phone.get().strip() == phone for r in self.rows):
                        unmatched += 1
            else:
                if order_idx < len(empty_rows):
                    target = empty_rows[order_idx]
                    order_idx += 1; matched_order += 1
                else: unmatched += 1
            if target:
                target.code.delete(0, "end"); target.code.insert(0, code)
                if twofa:
                    target.twofa.delete(0, "end"); target.twofa.insert(0, twofa)
        msg = ["Đã điền code:"]
        if matched_phone: msg.append(f"  • Khớp SĐT: {matched_phone}")
        if matched_order: msg.append(f"  • Theo thứ tự: {matched_order}")
        if skipped: msg.append(f"  • Skip (đã có code): {skipped}")
        if unmatched: msg.append(f"  • Không khớp: {unmatched}")
        messagebox.showinfo("Xong", "\n".join(msg))

    def _send_all(self):
        base = self.app.base_folder.get().strip()
        if not base:
            messagebox.showerror("Lỗi", "Chưa chọn thư mục gốc!"); return
        targets = [r for r in self.rows
                   if r.phone.get().strip() and r.client is None]
        if not targets:
            messagebox.showinfo("Trống", "Không có dòng hợp lệ."); return
        for i, row in enumerate(targets):
            self.app.root.after(i * 500, row._on_send)
        messagebox.showinfo("Đang gửi", f"Queue {len(targets)} acc.")

    def _login_all(self):
        targets = []
        for row in self.rows:
            if not row.code.get().strip(): continue
            if row.client is None: continue
            try:
                if str(row.btn_login.cget("state")) == "disabled":
                    continue
            except Exception: continue
            targets.append(row)
        if not targets:
            messagebox.showinfo("Trống", "Không có dòng sẵn sàng login."); return
        for i, row in enumerate(targets):
            self.app.root.after(i * 300, row._on_login)
        messagebox.showinfo("Đang login", f"Queue {len(targets)} acc.")

    def _launch_and_tile(self):
        base = self.app.base_folder.get().strip()
        if not base or not os.path.isdir(base):
            messagebox.showerror("Lỗi", "Thư mục gốc không hợp lệ!"); return
        folders = [s for s in Path(base).iterdir()
                   if s.is_dir() and (s / "Telegram.exe").exists()]
        if not folders:
            messagebox.showinfo("Không tìm thấy",
                "Không có Telegram.exe trong folder con."); return
        if not messagebox.askyesno("Xác nhận",
            f"Mở {len(folders)} Telegram.exe và chia lưới?"):
            return
        threading.Thread(target=self._tile_thread, args=(folders,),
                         daemon=True).start()

    def _tile_thread(self, folders):
        try: import pygetwindow as gw
        except ImportError:
            self.app.root.after(0, lambda: messagebox.showerror(
                "Thiếu lib", "pip install pygetwindow")); return

        existing = set()
        try:
            for w in gw.getAllWindows():
                if "Telegram" in (getattr(w, "title", "") or ""):
                    existing.add(w._hWnd)
        except Exception: pass

        self.app.set_status(f"🚀 Đang mở {len(folders)} Telegram...")
        pid_to_folder = {}
        for folder in folders:
            try:
                proc = subprocess.Popen([str(folder / "Telegram.exe")],
                                        cwd=str(folder))
                pid_to_folder[proc.pid] = folder.name
            except Exception as e:
                print(f"Launch lỗi {folder}: {e}")
            time.sleep(0.4)

        self.app.set_status("⏳ Chờ Telegram load...")
        new_windows = []
        for attempt in range(15):
            time.sleep(1)
            new_windows = []
            try:
                for w in gw.getAllWindows():
                    if "Telegram" not in (getattr(w, "title", "") or ""):
                        continue
                    if w._hWnd in existing: continue
                    pid = self.app.get_window_pid(w._hWnd)
                    folder_name = pid_to_folder.get(pid, "?")
                    if folder_name == "?":
                        for ppid, fname in pid_to_folder.items():
                            if pid and abs(pid - ppid) < 100:
                                folder_name = fname; break
                    new_windows.append((w, pid, folder_name))
                if len(new_windows) >= len(folders):
                    break
            except Exception as e:
                print(f"Enum lỗi: {e}")

        if not new_windows:
            self.app.root.after(0, lambda: messagebox.showwarning(
                "Không thấy", "Đã launch nhưng chưa thấy cửa sổ.")); return

        self.app.window_manager.clear()
        for w, pid, fname in new_windows:
            self.app.window_manager.add(w._hWnd, pid, fname)

        wx, wy, ww, wh = self.app.get_work_area()
        GAP = 4
        n = len(new_windows)
        cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
        cell_w = (ww - GAP * (cols + 1)) // cols
        cell_h = (wh - GAP * (rows + 1)) // rows

        ok = 0
        for i, (w, pid, fname) in enumerate(new_windows):
            r, c = i // cols, i % cols
            x = wx + GAP + c * (cell_w + GAP)
            y = wy + GAP + r * (cell_h + GAP)
            try:
                if getattr(w, "isMinimized", False): w.restore()
                if getattr(w, "isMaximized", False): w.restore()
                self.app.set_window_pos(w._hWnd, x, y, cell_w, cell_h)
                ok += 1
            except Exception as e:
                print(f"Tile lỗi {i}: {e}")

        try: self.app.sync_tab.count_label.configure(text=f"{ok} tab")
        except Exception: pass

        self.app.root.after(0, lambda: messagebox.showinfo(
            "Xong", f"Đã mở + tile {ok}/{n} cửa sổ ({cols}×{rows})\n"
                    f"💡 Tab '🔄 Đồng bộ' để gửi text đồng bộ."))
        self.app.set_status(f"✅ Track {ok} tab", "#00cc66")
