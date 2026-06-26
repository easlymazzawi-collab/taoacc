"""
account_panel.py — chọn acc (nhẹ) + per-account runner chung
=============================================================
Trước: AdminTab có 8 sub-tab, mỗi cái viết lại pattern `per_acc(acc)`
hàng trăm dòng giống nhau. File main.py 2400 dòng phần lớn copy-paste.

Sau: PerAccountRunner gom pattern này thành 1 helper:
    runner.run(name, sel_accounts, do_one=async_handler, ...)
nhận callback xử lý 1 acc — phần connect/disconnect/log/gather tự lo.

AccountListView dùng tk.Checkbutton thay CTkCheckBox để fix lag khi
30+ acc trong scroll frame (GitHub CustomTkinter issue #1461, #2690).
"""

from __future__ import annotations

import asyncio
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Awaitable, Callable, Optional

import customtkinter as ctk


# ────────────────────────────────────────────────────────────────────
class AccountListView(ctk.CTkFrame):
    """
    Danh sách acc dạng checklist NHẸ (dùng tk.Checkbutton, không phải CTk).
    Hỗ trợ:
      - Hiển thị nhóm theo source (session_folder, accounts_txt)
      - Filter search-as-you-type
      - Select all / none / invert
      - Hiển thị status từng acc (badge nhỏ)
    """

    BG_DARK   = "#202020"
    BG_GROUP  = "#2a2a2a"
    FG_TEXT   = "#e0e0e0"
    FG_GROUP  = "#888888"
    SEL_BG    = "#1f6feb"

    def __init__(self, master, height=180, **kw):
        super().__init__(master, **kw)
        self._items = []           # list dict: var, kind, label, payload, badge
        self._build(height)

    def _build(self, height):
        # Toolbar: search + select buttons
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=4, pady=(4, 2))

        ctk.CTkLabel(bar, text="🔎").pack(side="left", padx=(4, 2))
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self._apply_filter())
        ent = ctk.CTkEntry(bar, textvariable=self.var_search,
                           placeholder_text="filter...", width=160)
        ent.pack(side="left", padx=2)

        ctk.CTkButton(bar, text="✓ Tất cả", width=70,
                      command=lambda: self._set_all(True)).pack(side="right", padx=2)
        ctk.CTkButton(bar, text="✗ Bỏ", width=60,
                      command=lambda: self._set_all(False)).pack(side="right", padx=2)
        ctk.CTkButton(bar, text="⇌ Đảo", width=60,
                      command=self._invert).pack(side="right", padx=2)

        self.lbl_count = ctk.CTkLabel(bar, text="0/0", text_color="#888")
        self.lbl_count.pack(side="right", padx=8)

        # Canvas + scrollbar — tự xây bằng tk thay vì CTkScrollableFrame
        # → nhanh hơn nhiều khi nhồi 30+ checkbox
        wrap = ctk.CTkFrame(self, fg_color=self.BG_DARK, corner_radius=4)
        wrap.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._canvas = tk.Canvas(wrap, bg=self.BG_DARK,
                                 highlightthickness=0, height=height)
        self._canvas.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        sb.pack(side="right", fill="y", pady=2)
        self._canvas.configure(yscrollcommand=sb.set)

        self._inner = tk.Frame(self._canvas, bg=self.BG_DARK)
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfigure(self._win, width=e.width))

        # Mouse wheel scroll
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-e.delta / 120), "units"))

    def _set_all(self, val):
        for it in self._items:
            if it.get("visible", True):
                it["var"].set(1 if val else 0)
        self._update_count()

    def _invert(self):
        for it in self._items:
            if it.get("visible", True):
                it["var"].set(0 if it["var"].get() else 1)
        self._update_count()

    def _apply_filter(self):
        q = self.var_search.get().strip().lower()
        for it in self._items:
            text = it["label"].lower() + " " + str(it.get("kind", "")).lower()
            match = (q in text) if q else True
            it["visible"] = match
            try:
                if match: it["row"].pack(fill="x", padx=4, pady=0)
                else: it["row"].pack_forget()
            except Exception: pass
        self._update_count()

    def _update_count(self):
        total = len(self._items)
        sel = sum(1 for it in self._items if it["var"].get())
        self.lbl_count.configure(text=f"{sel}/{total}")

    # ---- public API ----
    def clear(self):
        for it in self._items:
            try: it["row"].destroy()
            except Exception: pass
        # Xóa các label group còn lại
        for w in list(self._inner.winfo_children()):
            try: w.destroy()
            except Exception: pass
        self._items = []
        self._update_count()

    def set_accounts(self, sessions: list, accounts_txt: list):
        """
        sessions: [(name, session_path), ...]
        accounts_txt: [(api_id, api_hash, phone), ...]
        """
        self.clear()
        if sessions:
            self._add_group_label(f"📁 Folder ({len(sessions)} acc)")
            for name, sess in sessions:
                self._add_item("session_folder", name, (name, sess))
        if accounts_txt:
            self._add_group_label(f"📄 accounts.txt ({len(accounts_txt)} acc)")
            for api_id, api_hash, phone in accounts_txt:
                self._add_item("accounts_txt", phone, (api_id, api_hash, phone))
        self._update_count()

    def _add_group_label(self, text):
        lbl = tk.Label(self._inner, text=text,
                       bg=self.BG_DARK, fg=self.FG_GROUP,
                       font=("Segoe UI", 9), anchor="w")
        lbl.pack(fill="x", padx=8, pady=(8, 2))

    def _add_item(self, kind, label, payload):
        var = tk.IntVar(value=1)
        row = tk.Frame(self._inner, bg=self.BG_DARK)
        row.pack(fill="x", padx=4, pady=0)

        icon = "📂" if kind == "session_folder" else "📱"
        cb = tk.Checkbutton(
            row, text=f"  {icon}  {label}", variable=var,
            bg=self.BG_DARK, fg=self.FG_TEXT,
            activebackground=self.BG_DARK, activeforeground="#ffffff",
            selectcolor="#3a3a3a",      # màu nền của ô tick khi được chọn
            font=("Segoe UI", 10), anchor="w",
            highlightthickness=0, bd=0,
            command=self._update_count,
        )
        cb.pack(side="left", fill="x", expand=True)

        badge = tk.Label(row, text="", bg=self.BG_DARK, fg="#888",
                         font=("Segoe UI", 9))
        badge.pack(side="right", padx=4)

        self._items.append({
            "var": var, "kind": kind, "label": label, "payload": payload,
            "row": row, "badge": badge, "visible": True,
        })

    def set_badge(self, label, text, color="#888"):
        """Đặt status badge cho acc theo label."""
        for it in self._items:
            if it["label"] == label:
                try:
                    it["badge"].configure(text=text, fg=color)
                except Exception: pass
                return

    def clear_badges(self):
        for it in self._items:
            try: it["badge"].configure(text="")
            except Exception: pass

    def get_selected(self) -> list:
        """Trả về [(kind, label, payload), ...]"""
        return [(it["kind"], it["label"], it["payload"])
                for it in self._items if it["var"].get()]

    def get_all_labels(self) -> list:
        return [it["label"] for it in self._items]


# ────────────────────────────────────────────────────────────────────
#  PerAccountRunner — pattern run-per-acc dùng chung
# ────────────────────────────────────────────────────────────────────
class PerAccountRunner:
    """
    Gói lại pattern 'for each acc: connect → do_one → disconnect' để
    không phải copy-paste 8 lần ở AdminTab.

        runner = PerAccountRunner(make_client, log, badge_setter)
        async def do_one(client, acc_label):
            ...
        result = await runner.execute(
            name="cấp admin",
            accounts=[(kind, label, payload), ...],
            do_one=do_one,
            mode="parallel" | "serial",
            delay=0.5,
        )
    """

    def __init__(self, make_client, log, badge_setter=None):
        """
        make_client: async fn(kind, label, payload) -> client
        log: callable(level, msg)
        badge_setter: callable(label, text, color) — set badge ở UI list
        """
        self.make_client = make_client
        self.log = log
        self.set_badge = badge_setter or (lambda *_a, **_k: None)

    async def execute(self, name: str, accounts: list,
                      do_one: Callable[[object, str], Awaitable],
                      mode: str = "parallel",
                      delay: float = 0.5,
                      max_concurrent: int = 8):
        total = len(accounts)
        done = [0]
        results = []
        self.log("info", f"\n{'='*55}")
        self.log("info", f"▶ {name}: {total} acc | Mode: {mode}")
        self.log("info", "="*55)

        sem = asyncio.Semaphore(max_concurrent if mode == "parallel" else 1)

        async def per(kind, label, payload):
            async with sem:
                self.log("info", f"\n📱 [{done[0]+1}/{total}] {label}")
                self.set_badge(label, "⏳", "#ffcc00")
                client = None
                try:
                    client = await self.make_client(kind, label, payload)
                except BaseException as e:
                    self.log("error", f"  ❌ {label}: connect lỗi — {e}")
                    self.set_badge(label, "❌", "#ff5555")
                    done[0] += 1
                    return {"label": label, "ok": False, "error": str(e)}

                try:
                    r = await do_one(client, label)
                    results.append({"label": label, "ok": True, "result": r})
                    self.set_badge(label, "✓", "#00cc66")
                except asyncio.CancelledError:
                    self.set_badge(label, "⏹", "#ffaa44")
                    raise
                except BaseException as e:
                    import traceback
                    self.log("error", f"  💥 [{label}]: {type(e).__name__}: {e}")
                    self.log("error", traceback.format_exc())
                    self.set_badge(label, "✗", "#ff5555")
                    results.append({"label": label, "ok": False, "error": str(e)})
                finally:
                    try:
                        if client: await client.disconnect()
                    except Exception: pass
                    done[0] += 1
                    self.log("info", f"  ✓ [{label}] xong ({done[0]}/{total})")
                    if delay > 0:
                        await asyncio.sleep(delay)

        if mode == "serial":
            for kind, label, payload in accounts:
                await per(kind, label, payload)
        else:
            await asyncio.gather(
                *(per(k, lb, pl) for k, lb, pl in accounts),
                return_exceptions=False)

        ok_n = sum(1 for r in results if r["ok"])
        self.log("info", f"\n✅ {name} XONG — {ok_n}/{total} OK\n")
        return results
