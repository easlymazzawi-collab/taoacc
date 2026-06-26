"""
admin_tab.py — Tab Admin & Channel (refactor)
==============================================
Bản gốc 1300 dòng, copy-paste pattern per_acc 8 lần. Bản này ~600 dòng
nhờ dùng PerAccountRunner + AccountListView từ account_panel.py.

Logic backend (admin_channel.py) giữ nguyên 100% — chỉ refactor UI layer.
"""

from __future__ import annotations

import asyncio
import csv
import os
import re
import time
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from telethon import TelegramClient as PlainTelegramClient
from opentele.tl import TelegramClient

from admin_channel import (
    detect_sessions, load_accounts_txt, load_or_create_api,
    parse_usernames, parse_chat_inputs,
    run_promote_batch, create_channels_one, get_folder_channels,
    get_admin_channels, create_or_update_folder, promote_one,
    export_chatlist_link, join_chatlist_link, delete_account,
    create_public_channels_batch, title_of,
)

from account_panel import AccountListView, PerAccountRunner


class AdminTab:
    def __init__(self, parent_frame, app):
        self.app = app
        self.parent = parent_frame
        self.run_records = []
        self._loaded_folders = {}
        self._build()

    # ════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ════════════════════════════════════════════════════════════════
    def _build(self):
        # ── Section: Acc selector
        sec1 = ctk.CTkFrame(self.parent)
        sec1.pack(fill="x", padx=10, pady=(10, 6))
        head = ctk.CTkFrame(sec1, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(head, text="👥 Tài khoản",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(head, text="🔍 Quét lại", width=100,
                      command=self._scan).pack(side="right", padx=2)

        self.acc_list = AccountListView(sec1, height=160)
        self.acc_list.pack(fill="x", padx=8, pady=(0, 8))

        # ── Section: Cài đặt + thanh điều khiển
        sec2 = ctk.CTkFrame(self.parent)
        sec2.pack(fill="x", padx=10, pady=6)
        cfg = ctk.CTkFrame(sec2, fg_color="transparent")
        cfg.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(cfg, text="⚙️ Chế độ:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        self.run_mode = ctk.StringVar(value="parallel")
        ctk.CTkRadioButton(cfg, text="Song song", variable=self.run_mode,
                           value="parallel").pack(side="left", padx=4)
        ctk.CTkRadioButton(cfg, text="Tuần tự", variable=self.run_mode,
                           value="serial").pack(side="left", padx=4)
        ctk.CTkLabel(cfg, text="  Delay (s):").pack(side="left", padx=(15, 2))
        self.delay_entry = ctk.CTkEntry(cfg, width=60)
        self.delay_entry.insert(0, "0.5")
        self.delay_entry.pack(side="left")
        ctk.CTkLabel(cfg, text="  Max song song:").pack(side="left", padx=(15, 2))
        self.max_parallel = ctk.CTkEntry(cfg, width=50)
        self.max_parallel.insert(0, "8")
        self.max_parallel.pack(side="left")

        # Nút STOP + status
        self.btn_stop = ctk.CTkButton(
            cfg, text="⏹ DỪNG", width=90,
            fg_color="#cc3333", hover_color="#aa2222",
            command=self._stop_running, state="disabled")
        self.btn_stop.pack(side="right", padx=4)

        self.lbl_running = ctk.CTkLabel(cfg, text="", text_color="#888")
        self.lbl_running.pack(side="right", padx=4)

        # Bind config save
        self.app.cfg.bind_var(self.run_mode, "admin_run_mode", "parallel")
        self.app.cfg.bind_entry(self.delay_entry, "admin_delay", "0.5")
        self.app.cfg.bind_entry(self.max_parallel, "admin_max_parallel", "8")

        # ── Section: Tabview
        sec3 = ctk.CTkFrame(self.parent)
        sec3.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        tabs = ctk.CTkTabview(sec3, height=420)
        tabs.pack(fill="both", expand=True, padx=6, pady=6)

        # Đăng ký các sub-tab — list[(label, build_fn)]
        sub_tabs = [
            ("🏗️ Tạo channel",     self._build_create),
            ("🌐 Tạo kênh public",  self._build_create_public),
            ("👮 Cấp admin",        self._build_promote),
            ("📂 Theo Folder TG",   self._build_folder),
            ("📁 Auto Folder",      self._build_autofolder),
            ("👥 Auto-promote",     self._build_auto_promote),
            ("🎯 Dồn về acc tổng",  self._build_master),
            ("🗑️ Xóa account",      self._build_delete),
        ]
        for name, fn in sub_tabs:
            tabs.add(name)
            fn(tabs.tab(name))

        # Bind tab vừa chọn → save
        try:
            tabs._segmented_button.configure(
                command=lambda v: (
                    tabs._segmented_button_callback(v),
                    self.app.cfg.set("admin_sub_tab", v),
                ))
            last = self.app.cfg.get("admin_sub_tab")
            if last and last in [s[0] for s in sub_tabs]:
                tabs.set(last)
        except Exception: pass

    # ════════════════════════════════════════════════════════════════
    #  SUB-TAB BUILDERS (gọn — chỉ field, action button có 1 chỗ)
    # ════════════════════════════════════════════════════════════════
    def _add_action_button(self, parent, text, color, hover, command):
        ctk.CTkButton(parent, text=text, height=42,
                      fg_color=color, hover_color=hover,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=command).pack(fill="x", padx=10, pady=(4, 8))

    def _add_desc(self, parent, text, color="#aaa"):
        ctk.CTkLabel(parent, text=text, justify="left",
                     text_color=color, font=ctk.CTkFont(size=11)
                     ).pack(anchor="w", padx=12, pady=(8, 4))

    # ---- 1. Tạo channel ----
    def _build_create(self, frame):
        self._add_desc(frame,
            "Tạo channel/megagroup PRIVATE (chỉ có invite link, không @username)")
        self._add_action_button(frame, "🚀 BẮT ĐẦU TẠO CHANNEL",
            "#22aa55", "#1c8d44", self._run_create)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(g, text="Số channel/acc:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.cc_amount = ctk.CTkEntry(g, width=80); self.cc_amount.insert(0, "1")
        self.cc_amount.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(g, text="Prefix tên:").grid(row=0, column=2, sticky="w", padx=(20, 4), pady=4)
        self.cc_prefix = ctk.CTkEntry(g, width=120); self.cc_prefix.insert(0, "vip_")
        self.cc_prefix.grid(row=0, column=3, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(g, text="Mô tả:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.cc_about = ctk.CTkEntry(g, width=400); self.cc_about.insert(0, "VIP Channel")
        self.cc_about.grid(row=1, column=1, columnspan=3, sticky="we", padx=4, pady=4)
        self.cc_megagroup = ctk.CTkCheckBox(g, text="Tạo Megagroup")
        self.cc_megagroup.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        self.cc_save_links = ctk.CTkCheckBox(g, text="Lưu link vào channels.txt")
        self.cc_save_links.select()
        self.cc_save_links.grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        g.columnconfigure(1, weight=1)

        # Bind save
        cfg = self.app.cfg
        cfg.bind_entry(self.cc_amount, "cc_amount", "1")
        cfg.bind_entry(self.cc_prefix, "cc_prefix", "vip_")
        cfg.bind_entry(self.cc_about, "cc_about", "VIP Channel")

    # ---- 2. Tạo kênh public ----
    def _build_create_public(self, frame):
        self._add_desc(frame,
            "Tạo kênh CÔNG KHAI (có @username, ai cũng tìm được):\n"
            "  • Username = prefix + suffix tự sinh (retry nếu trùng)\n"
            "  • Có thể upload ảnh kênh + welcome message")
        self._add_action_button(frame, "🌐 BẮT ĐẦU TẠO KÊNH PUBLIC",
            "#0288d1", "#01579b", self._run_create_public)

        scroll = ctk.CTkScrollableFrame(frame, height=280)
        scroll.pack(fill="both", expand=True, padx=10, pady=4)
        g = ctk.CTkFrame(scroll, fg_color="transparent")
        g.pack(fill="x", pady=4)
        row = 0

        ctk.CTkLabel(g, text="Số kênh/acc:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        self.cp_amount = ctk.CTkEntry(g, width=80); self.cp_amount.insert(0, "1")
        self.cp_amount.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        self.cp_megagroup = ctk.CTkCheckBox(g, text="Tạo Megagroup")
        self.cp_megagroup.grid(row=row, column=2, columnspan=2, sticky="w", padx=20, pady=4)
        row += 1

        ctk.CTkLabel(g, text="Tên kênh:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        self.cp_title = ctk.CTkEntry(g, width=440,
            placeholder_text="vd: My VIP Channel  hoặc  Channel #{n}")
        self.cp_title.insert(0, "VIP Channel #{n}")
        self.cp_title.grid(row=row, column=1, columnspan=3, sticky="we", padx=4, pady=4)
        row += 1
        ctk.CTkLabel(g, text="({n} = số thứ tự)",
            text_color="gray", font=ctk.CTkFont(size=11)
            ).grid(row=row, column=1, columnspan=3, sticky="w", padx=4, pady=(0, 4))
        row += 1

        self.cp_same_title = ctk.CTkCheckBox(g,
            text="✋ Giữ nguyên tên cho TẤT CẢ kênh (không thêm số)")
        self.cp_same_title.grid(row=row, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        row += 1

        ctk.CTkLabel(g, text="Mô tả:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        self.cp_about = ctk.CTkEntry(g, width=440)
        self.cp_about.insert(0, "Welcome to my channel!")
        self.cp_about.grid(row=row, column=1, columnspan=3, sticky="we", padx=4, pady=4)
        row += 1

        ctk.CTkLabel(g, text="Username prefix:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        self.cp_uprefix = ctk.CTkEntry(g, width=180)
        self.cp_uprefix.insert(0, "vip")
        self.cp_uprefix.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(g, text="→ @prefix + suffix",
                     text_color="gray").grid(row=row, column=2, columnspan=2,
                                             sticky="w", padx=10, pady=4)
        row += 1

        ctk.CTkLabel(g, text="Suffix:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sf = ctk.CTkFrame(g, fg_color="transparent")
        sf.grid(row=row, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.cp_suffix_mode = ctk.StringVar(value="random_3")
        for txt, val in [("+1 ký tự", "random_1"), ("+2 ký tự", "random_2"),
                          ("+3 ký tự", "random_3"),
                          ("Lộn xộn (5-8 + có thể có _)", "chaos")]:
            ctk.CTkRadioButton(sf, text=txt, variable=self.cp_suffix_mode,
                               value=val).pack(side="left", padx=4)
        row += 1

        ctk.CTkLabel(g, text="Ảnh kênh:").grid(row=row, column=0, sticky="w", padx=4, pady=4)
        self.cp_photo_path = ctk.CTkEntry(g, width=340,
            placeholder_text="(không bắt buộc)")
        self.cp_photo_path.grid(row=row, column=1, columnspan=2, sticky="we", padx=4, pady=4)
        ctk.CTkButton(g, text="📁 Chọn", width=80,
                      command=self._pick_channel_photo
                      ).grid(row=row, column=3, sticky="w", padx=4, pady=4)
        row += 1

        ctk.CTkLabel(g, text="Welcome:").grid(row=row, column=0, sticky="nw", padx=4, pady=4)
        self.cp_welcome = ctk.CTkTextbox(g, width=440, height=70)
        self.cp_welcome.grid(row=row, column=1, columnspan=3, sticky="we", padx=4, pady=4)
        row += 1

        self.cp_save_links = ctk.CTkCheckBox(g,
            text="Lưu vào public_channels.txt")
        self.cp_save_links.select()
        self.cp_save_links.grid(row=row, column=0, columnspan=4, sticky="w", padx=4, pady=8)
        g.columnconfigure(1, weight=1)

        cfg = self.app.cfg
        cfg.bind_entry(self.cp_amount, "cp_amount", "1")
        cfg.bind_entry(self.cp_title, "cp_title", "VIP Channel #{n}")
        cfg.bind_entry(self.cp_about, "cp_about", "Welcome to my channel!")
        cfg.bind_entry(self.cp_uprefix, "cp_uprefix", "vip")
        cfg.bind_var(self.cp_suffix_mode, "cp_suffix_mode", "random_3")
        cfg.bind_entry(self.cp_photo_path, "cp_photo_path", "")
        cfg.bind_textbox(self.cp_welcome, "cp_welcome", "")

    def _pick_channel_photo(self):
        p = filedialog.askopenfilename(
            title="Chọn ảnh",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.webp"), ("All", "*.*")])
        if p:
            self.cp_photo_path.delete(0, "end")
            self.cp_photo_path.insert(0, p)
            self.app.cfg.set("cp_photo_path", p)

    # ---- 3. Cấp admin ----
    def _build_promote(self, frame):
        self._add_desc(frame, "Cấp admin cho username vào danh sách kênh chỉ định.")
        self._add_action_button(frame, "🚀 BẮT ĐẦU CẤP ADMIN",
            "#1f6feb", "#1158c7", self._run_promote)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="both", expand=True, padx=10, pady=4)
        ctk.CTkLabel(g, text="Username:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ctk.CTkButton(g, text="📂 Load .txt", width=100,
                      command=lambda: self._load_into(self.pr_users)
                      ).grid(row=0, column=1, sticky="e", padx=4, pady=2)
        self.pr_users = ctk.CTkTextbox(g, height=60)
        self.pr_users.grid(row=1, column=0, columnspan=2, sticky="we", padx=4, pady=2)
        ctk.CTkLabel(g, text="Channel/link:").grid(row=2, column=0, sticky="w", padx=4, pady=(8, 2))
        ctk.CTkButton(g, text="📂 Load channels.txt", width=160,
                      command=lambda: self._load_into(self.pr_chans, "channels.txt")
                      ).grid(row=2, column=1, sticky="e", padx=4, pady=(8, 2))
        self.pr_chans = ctk.CTkTextbox(g, height=60)
        self.pr_chans.grid(row=3, column=0, columnspan=2, sticky="we", padx=4, pady=2)
        opt = ctk.CTkFrame(g, fg_color="transparent")
        opt.grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=6)
        self.pr_full_var = ctk.StringVar(value="full")
        ctk.CTkRadioButton(opt, text="Full quyền", variable=self.pr_full_var,
                           value="full").pack(side="left", padx=4)
        ctk.CTkRadioButton(opt, text="Safe", variable=self.pr_full_var,
                           value="safe").pack(side="left", padx=4)
        g.columnconfigure(0, weight=1)

        cfg = self.app.cfg
        cfg.bind_textbox(self.pr_users, "pr_users", "")
        cfg.bind_textbox(self.pr_chans, "pr_chans", "")
        cfg.bind_var(self.pr_full_var, "pr_full", "full")

    # ---- 4. Theo Folder TG ----
    def _build_folder(self, frame):
        self._add_desc(frame, "Cấp admin cho username trong tất cả kênh thuộc 1 Folder TG.")
        self._add_action_button(frame, "🚀 BẮT ĐẦU CẤP ADMIN THEO FOLDER",
            "#aa44cc", "#8833aa", self._run_folder)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(row, text="📥 Tải folder", command=self._load_folders
                      ).pack(side="left", padx=4)
        self.fold_var = ctk.StringVar(value="(chưa tải)")
        self.fold_menu = ctk.CTkOptionMenu(row, variable=self.fold_var,
                                           values=["(chưa tải)"], width=300)
        self.fold_menu.pack(side="left", padx=4)

        ctk.CTkLabel(frame, text="Username:").pack(anchor="w", padx=12, pady=(8, 2))
        urow = ctk.CTkFrame(frame, fg_color="transparent")
        urow.pack(fill="x", padx=10)
        ctk.CTkButton(urow, text="📂 Load .txt", width=100,
                      command=lambda: self._load_into(self.fd_users)
                      ).pack(side="right", padx=4)
        self.fd_users = ctk.CTkTextbox(frame, height=60)
        self.fd_users.pack(fill="x", padx=12, pady=4)
        self.fd_full_var = ctk.StringVar(value="full")
        opt = ctk.CTkFrame(frame, fg_color="transparent")
        opt.pack(anchor="w", padx=12, pady=4)
        ctk.CTkRadioButton(opt, text="Full quyền", variable=self.fd_full_var,
                           value="full").pack(side="left", padx=4)
        ctk.CTkRadioButton(opt, text="Safe", variable=self.fd_full_var,
                           value="safe").pack(side="left", padx=4)

        cfg = self.app.cfg
        cfg.bind_textbox(self.fd_users, "fd_users", "")
        cfg.bind_var(self.fd_full_var, "fd_full", "full")

    # ---- 5. Auto Folder ----
    def _build_autofolder(self, frame):
        self._add_desc(frame,
            "Tự gom tất cả kênh acc đang admin vào 1 folder filter trong TG.")
        self._add_action_button(frame, "🚀 TẠO FOLDER CHO MỖI ACC",
            "#dd8822", "#bb6f1c", self._run_autofolder)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(g, text="Tên folder:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.af_name = ctk.CTkEntry(g, width=200)
        self.af_name.insert(0, "My Channels")
        self.af_name.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(g, text="(folder trùng tên sẽ CẬP NHẬT)",
                     text_color="gray", font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=2, sticky="w", padx=10, pady=4)

        self.app.cfg.bind_entry(self.af_name, "af_name", "My Channels")

    # ---- 6. Auto-promote ----
    def _build_auto_promote(self, frame):
        self._add_desc(frame,
            "Trên mỗi acc đã chọn:\n"
            "  1. Quét tất cả kênh acc đó đang admin\n"
            "  2. Mời các username (nếu chưa member) → Cấp admin")
        self._add_action_button(frame, "🚀 BẮT ĐẦU AUTO-PROMOTE",
            "#16a085", "#117a65", self._run_auto_promote)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="both", expand=True, padx=10, pady=4)
        ctk.CTkLabel(g, text="Username cần cấp admin:"
                     ).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ctk.CTkButton(g, text="📂 Load .txt", width=100,
                      command=lambda: self._load_into(self.ap_users)
                      ).grid(row=0, column=1, sticky="e", padx=4, pady=2)
        self.ap_users = ctk.CTkTextbox(g, height=80)
        self.ap_users.grid(row=1, column=0, columnspan=2, sticky="we", padx=4, pady=2)

        opt = ctk.CTkFrame(g, fg_color="transparent")
        opt.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=6)
        self.ap_full_var = ctk.StringVar(value="full")
        ctk.CTkRadioButton(opt, text="Full quyền", variable=self.ap_full_var,
                           value="full").pack(side="left", padx=4)
        ctk.CTkRadioButton(opt, text="Safe", variable=self.ap_full_var,
                           value="safe").pack(side="left", padx=4)

        opt2 = ctk.CTkFrame(g, fg_color="transparent")
        opt2.grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        self.ap_skip_self = ctk.CTkCheckBox(opt2,
            text="Bỏ qua nếu username trùng với chính acc")
        self.ap_skip_self.select()
        self.ap_skip_self.pack(side="left", padx=4)
        g.columnconfigure(0, weight=1)

        cfg = self.app.cfg
        cfg.bind_textbox(self.ap_users, "ap_users", "")
        cfg.bind_var(self.ap_full_var, "ap_full", "full")

    # ---- 7. Dồn về acc tổng ----
    def _build_master(self, frame):
        self._add_desc(frame,
            "CHATLIST: acc phụ tạo folder + cấp admin acc tổng → export link\n"
            "→ Acc tổng tự JOIN qua link → folder hiện ngay.")
        self._add_action_button(frame, "🎯 BẮT ĐẦU DỒN VỀ ACC TỔNG",
            "#cc3366", "#aa2952", self._run_master)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(g, text="Acc tổng:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.mt_master_var = ctk.StringVar(value="(bấm 🔄 để load)")
        self.mt_master_menu = ctk.CTkOptionMenu(g, variable=self.mt_master_var,
                                                values=["(chưa load)"], width=240)
        self.mt_master_menu.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkButton(g, text="🔄 Load từ acc đã chọn", width=180,
                      command=self._refresh_master_dropdown
                      ).grid(row=0, column=2, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(g, text="Folder tổng:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.mt_folder = ctk.CTkEntry(g, width=240); self.mt_folder.insert(0, "All Managed")
        self.mt_folder.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(g, text="Folder phụ:").grid(row=1, column=2, sticky="w", padx=(15, 4), pady=4)
        self.mt_subfolder = ctk.CTkEntry(g, width=180); self.mt_subfolder.insert(0, "ToShare")
        self.mt_subfolder.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        opt = ctk.CTkFrame(g, fg_color="transparent")
        opt.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        self.mt_full_var = ctk.StringVar(value="full")
        ctk.CTkRadioButton(opt, text="Full quyền", variable=self.mt_full_var,
                           value="full").pack(side="left", padx=4)
        ctk.CTkRadioButton(opt, text="Safe", variable=self.mt_full_var,
                           value="safe").pack(side="left", padx=4)

        opt2 = ctk.CTkFrame(g, fg_color="transparent")
        opt2.grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        self.mt_promote_first = ctk.CTkCheckBox(opt2, text="Cấp admin acc tổng trước")
        self.mt_promote_first.select(); self.mt_promote_first.pack(side="left", padx=4)
        self.mt_save_links = ctk.CTkCheckBox(opt2, text="Lưu chatlist_links.txt")
        self.mt_save_links.select(); self.mt_save_links.pack(side="left", padx=20)
        self.mt_auto_join = ctk.CTkCheckBox(opt2, text="Acc tổng tự JOIN")
        self.mt_auto_join.select(); self.mt_auto_join.pack(side="left", padx=20)

        cfg = self.app.cfg
        cfg.bind_entry(self.mt_folder, "mt_folder", "All Managed")
        cfg.bind_entry(self.mt_subfolder, "mt_subfolder", "ToShare")
        cfg.bind_var(self.mt_full_var, "mt_full", "full")

    # ---- 8. Xóa account ----
    def _build_delete(self, frame):
        ctk.CTkLabel(frame,
            text="⚠️  XÓA TÀI KHOẢN VĨNH VIỄN — KHÔNG THỂ UNDO ⚠️",
            text_color="#ff6666",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        self._add_action_button(frame, "🗑️ XÓA TẤT CẢ ACC ĐÃ CHỌN",
            "#cc1818", "#990000", self._run_delete)

        g = ctk.CTkFrame(frame, fg_color="transparent")
        g.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(g, text="Lý do (tùy chọn):").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.del_reason = ctk.CTkEntry(g, width=400,
            placeholder_text="vd: Không sử dụng nữa")
        self.del_reason.grid(row=0, column=1, sticky="we", padx=4, pady=4)

        ctk.CTkLabel(g, text="Gõ chính xác chữ DELETE để xác nhận:",
                     text_color="#ffaa44").grid(row=1, column=0, columnspan=2,
                                                sticky="w", padx=4, pady=(12, 2))
        self.del_confirm = ctk.CTkEntry(g, width=200,
            placeholder_text='Gõ "DELETE"',
            font=ctk.CTkFont(weight="bold"))
        self.del_confirm.grid(row=2, column=0, sticky="w", padx=4, pady=4)
        g.columnconfigure(1, weight=1)

        self.del_understand = ctk.CTkCheckBox(frame,
            text="Tôi hiểu acc bị xóa KHÔNG THỂ KHÔI PHỤC",
            text_color="#ffaa44")
        self.del_understand.pack(anchor="w", padx=14, pady=(4, 4))

    # ════════════════════════════════════════════════════════════════
    #  HELPERS
    # ════════════════════════════════════════════════════════════════
    def _load_into(self, textbox, default_filename=None):
        path = None
        if default_filename and Path(default_filename).exists():
            if messagebox.askyesno("Hỏi", f"Load file '{default_filename}'?"):
                path = default_filename
        if not path:
            path = filedialog.askopenfilename(
                filetypes=[("Text", "*.txt"), ("All", "*.*")])
            if not path: return
        try: content = open(path, encoding="utf-8").read()
        except UnicodeDecodeError: content = open(path, encoding="latin-1").read()
        textbox.delete("0.0", "end")
        textbox.insert("0.0", content)

    def _scan(self):
        base = self.app.base_folder.get().strip()
        sessions = detect_sessions(base) if base else []
        accs_txt = load_accounts_txt("accounts.txt")
        self.acc_list.set_accounts(sessions, accs_txt)
        if not sessions and not accs_txt:
            self.log("info", "(không thấy acc — login Tab 1 trước hoặc tạo accounts.txt)")

    def log(self, level, msg):
        """Forward log lên LogBus."""
        self.app.log_bus.write(level, msg)

    def _get_delay(self):
        try: return max(0.0, float(self.delay_entry.get().strip()))
        except (ValueError, AttributeError): return 0.5

    def _get_max_parallel(self):
        try: return max(1, int(self.max_parallel.get().strip()))
        except (ValueError, AttributeError): return 8

    def _get_selected(self):
        sel = self.acc_list.get_selected()
        if not sel:
            messagebox.showinfo("Trống", "Chưa chọn acc nào!")
            return None
        return sel

    async def _make_client(self, kind, label, payload):
        self.log("info", f"  🔌 [{label}] kết nối...")
        if kind == "session_folder":
            name, sess_path = payload
            session_path = Path(sess_path)
            folder = session_path.parent
            api = load_or_create_api(folder)
            client = TelegramClient(sess_path, api=api)
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(f"{label}: session chưa authorized")
            self.log("info", f"  ✓ [{label}] OK")
            return client
        else:
            api_id, api_hash, phone = payload
            client = PlainTelegramClient(f"session_{phone}", api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(f"{phone}: chưa authorized")
            self.log("info", f"  ✓ [{label}] OK")
            return client

    def _make_runner(self):
        return PerAccountRunner(
            make_client=self._make_client,
            log=self.log,
            badge_setter=lambda l, t, c: self.parent.after(
                0, lambda: self.acc_list.set_badge(l, t, c)),
        )

    def _run_async(self, name, coro_factory, busy="", done=""):
        """Submit coro qua AsyncBridge — disable buttons + show stop btn."""
        self.acc_list.clear_badges()
        self.btn_stop.configure(state="normal")
        self.lbl_running.configure(text=f"⏳ {name}...")
        self._current_tid = None

        def _final(_=None):
            self.btn_stop.configure(state="disabled")
            self.lbl_running.configure(text="")

        self._current_tid = self.app.bridge.run(
            name=name, coro=coro_factory(),
            busy_msg=busy, done_msg=done, on_done=_final)

        # AsyncBridge tự log error, ta poll để reset UI khi task dừng
        # (dù do done, error, hay cancel)
        self.parent.after(200, self._poll_done)

    def _poll_done(self):
        if not getattr(self, "_current_tid", None):
            return
        tid = self._current_tid
        running = tid in self.app.runner.running_tasks()
        if running:
            self.parent.after(500, self._poll_done)
        else:
            self.btn_stop.configure(state="disabled")
            self.lbl_running.configure(text="")
            self._current_tid = None

    def _stop_running(self):
        if not messagebox.askyesno("Dừng?",
            "Hủy task đang chạy?\n(Đã ghi vào Telegram thì không undo được)"):
            return
        n = self.app.runner.cancel_all()
        self.log("info", f"⏹ Đã yêu cầu hủy {n} task")

    # ════════════════════════════════════════════════════════════════
    #  RUN HANDLERS — gọn nhờ PerAccountRunner
    # ════════════════════════════════════════════════════════════════
    def _run_create(self):
        sel = self._get_selected()
        if not sel: return
        try: amount = int(self.cc_amount.get().strip())
        except ValueError: messagebox.showerror("Lỗi", "Số channel sai!"); return

        prefix = self.cc_prefix.get().strip() or "vip_"
        about = self.cc_about.get().strip() or "Channel"
        megagroup = bool(self.cc_megagroup.get())
        save_links = bool(self.cc_save_links.get())
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()

        runner = self._make_runner()
        all_links = []

        async def do_one(client, label):
            links = await create_channels_one(
                client, amount, prefix, about, megagroup, delay,
                log_cb=self.log)
            for l in links:
                all_links.append((label, l))
                self.run_records.append({"acc": label, "result": "ok", "data": l})
            return len(links)

        async def task():
            await runner.execute("Tạo channel", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)
            if save_links and all_links:
                try:
                    with open("channels.txt", "a", encoding="utf-8") as f:
                        for label, l in all_links:
                            f.write(l + "\n")
                    self.log("ok", f"💾 Ghi {len(all_links)} link → channels.txt")
                except Exception as e:
                    self.log("error", f"Lưu file lỗi: {e}")

        self._run_async("Tạo channel", task,
                        busy="🏗️ Đang tạo channel...",
                        done="✅ Hoàn tất tạo channel")

    def _run_create_public(self):
        sel = self._get_selected()
        if not sel: return
        try: amount = int(self.cp_amount.get().strip())
        except ValueError: messagebox.showerror("Lỗi", "Số kênh sai!"); return

        title = self.cp_title.get().strip()
        if not title: messagebox.showerror("Lỗi", "Chưa nhập tên!"); return

        uprefix = self.cp_uprefix.get().strip()
        if not uprefix or not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", uprefix):
            messagebox.showerror("Lỗi",
                "Username prefix: bắt đầu bằng chữ, chỉ a-z 0-9 _"); return

        about = self.cp_about.get().strip() or "Channel"
        suffix_mode = self.cp_suffix_mode.get()
        photo_path = self.cp_photo_path.get().strip() or None
        if photo_path and not os.path.isfile(photo_path):
            messagebox.showerror("Lỗi", f"Không thấy ảnh:\n{photo_path}"); return
        welcome = self.cp_welcome.get("0.0", "end").strip() or None
        megagroup = bool(self.cp_megagroup.get())
        same_title = bool(self.cp_same_title.get())
        save_links = bool(self.cp_save_links.get())
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()

        runner = self._make_runner()
        all_results = []

        async def do_one(client, label):
            res = await create_public_channels_batch(
                client, amount, title, about, uprefix,
                suffix_mode=suffix_mode, photo_path=photo_path,
                welcome_msg=welcome, delay=delay, megagroup=megagroup,
                same_title=same_title, log_cb=self.log)
            for r in res:
                all_results.append((label, r))
                self.run_records.append({
                    "acc": label, "result": "ok",
                    "data": f"{r['title']} | @{r['username']} | {r['public_link']}"})
            return len(res)

        async def task():
            await runner.execute("Tạo kênh public", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)
            if save_links and all_results:
                try:
                    with open("public_channels.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n# === {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                        for label, r in all_results:
                            f.write(f"# {label}: {r['title']}\n")
                            if r.get("public_link"): f.write(f"{r['public_link']}\n")
                            if r.get("invite_link"): f.write(f"{r['invite_link']}\n")
                            f.write("\n")
                    self.log("ok", f"💾 Lưu {len(all_results)} kênh → public_channels.txt")
                except Exception as e:
                    self.log("error", f"Lưu lỗi: {e}")

        self._run_async("Tạo kênh public", task,
                        busy="🌐 Đang tạo public...", done="✅ Hoàn tất")

    def _run_promote(self):
        sel = self._get_selected()
        if not sel: return
        usernames = parse_usernames(self.pr_users.get("0.0", "end"))
        chan_inputs = parse_chat_inputs(self.pr_chans.get("0.0", "end"))
        if not usernames or not chan_inputs:
            messagebox.showerror("Lỗi", "Cần username + channel!"); return

        full = self.pr_full_var.get() == "full"
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()
        runner = self._make_runner()

        async def do_one(client, label):
            channels = []
            for c in chan_inputs:
                try:
                    ent = await client.get_entity(c)
                    channels.append(ent)
                except Exception as e:
                    self.log("error", f"     ⚠ '{c}': {e}")
            if not channels: return None
            stats = await run_promote_batch(
                client, channels, usernames, delay, full=full, log_cb=self.log)
            self.log("info", f"  📊 [{label}] {stats}")
            self.run_records.append({"acc": label, "result": "stats", "data": str(stats)})
            return stats

        async def task():
            await runner.execute("Cấp admin", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)

        self._run_async("Cấp admin", task,
                        busy="👮 Đang cấp admin...", done="✅ Hoàn tất")

    def _load_folders(self):
        sel = self._get_selected()
        if not sel: return
        acc = sel[0]

        async def task():
            kind, label, payload = acc
            self.log("info", f"📥 Tải folder TG của: {label}")
            try:
                client = await self._make_client(kind, label, payload)
            except Exception as e:
                self.log("error", f"  ❌ {e}"); return
            try:
                folders = await get_folder_channels(client)
                self._loaded_folders = folders
                names = list(folders.keys()) or ["(không có folder)"]
                self.log("info", "  Folder: " + ", ".join(
                    f"{n}({len(folders.get(n, []))})" for n in names))

                def upd():
                    self.fold_menu.configure(values=names)
                    self.fold_var.set(names[0])
                self.parent.after(0, upd)
            finally:
                try: await client.disconnect()
                except Exception: pass

        self._run_async("Tải folder", task,
                        busy="📥 Tải folder...", done="✅ OK")

    def _run_folder(self):
        sel = self._get_selected()
        if not sel: return
        fname = self.fold_var.get()
        if fname not in self._loaded_folders:
            messagebox.showerror("Lỗi", "Chưa tải folder! Bấm 📥 trước."); return
        usernames = parse_usernames(self.fd_users.get("0.0", "end"))
        if not usernames: messagebox.showerror("Lỗi", "Chưa nhập username!"); return

        full = self.fd_full_var.get() == "full"
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()
        runner = self._make_runner()

        async def do_one(client, label):
            channels = await get_folder_channels(client, fname)
            if not channels:
                self.log("info", f"  (acc {label} không có kênh trong '{fname}')")
                return None
            stats = await run_promote_batch(
                client, channels, usernames, delay, full=full, log_cb=self.log)
            self.run_records.append({"acc": label, "result": "stats", "data": str(stats)})
            return stats

        async def task():
            await runner.execute(f"Cấp admin theo folder '{fname}'", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)

        self._run_async(f"Theo folder", task,
                        busy="📂 Đang chạy...", done="✅ Hoàn tất")

    def _run_autofolder(self):
        sel = self._get_selected()
        if not sel: return
        folder_name = self.af_name.get().strip() or "My Channels"
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()
        delay = self._get_delay()
        runner = self._make_runner()

        async def do_one(client, label):
            channels = await get_admin_channels(client, log_cb=self.log)
            if not channels:
                self.log("info", f"  (acc {label} không admin kênh nào)")
                return None
            fid = await create_or_update_folder(
                client, folder_name, channels, log_cb=self.log)
            self.run_records.append({
                "acc": label, "result": "ok",
                "data": f"folder_id={fid}, channels={len(channels)}"})
            return fid

        async def task():
            await runner.execute(f"Auto folder '{folder_name}'", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)

        self._run_async("Auto folder", task,
                        busy="📁 Đang tạo...", done="✅ Hoàn tất")

    def _run_auto_promote(self):
        sel = self._get_selected()
        if not sel: return
        usernames = parse_usernames(self.ap_users.get("0.0", "end"))
        if not usernames: messagebox.showerror("Lỗi", "Chưa nhập username!"); return

        full = self.ap_full_var.get() == "full"
        skip_self = bool(self.ap_skip_self.get())
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()
        runner = self._make_runner()

        async def do_one(client, label):
            me = await client.get_me()
            my_un = (me.username or "").lower()
            actual = [u for u in usernames
                      if not (skip_self and u.lower() == my_un)]
            if not actual:
                self.log("info", "  (không còn user sau skip self)")
                return None
            channels = await get_admin_channels(client, log_cb=self.log)
            if not channels:
                self.log("info", f"  (acc không admin kênh nào)")
                return None
            stats = await run_promote_batch(
                client, channels, actual, delay, full=full, log_cb=self.log)
            self.run_records.append({"acc": label, "result": "stats", "data": str(stats)})
            return stats

        async def task():
            await runner.execute("Auto-promote", sel, do_one,
                                  mode=mode, delay=delay, max_concurrent=max_p)

        self._run_async("Auto-promote", task,
                        busy="👥 Đang chạy...", done="✅ Hoàn tất")

    def _refresh_master_dropdown(self):
        sel = self.acc_list.get_selected()
        if not sel:
            messagebox.showinfo("Trống", "Chưa chọn acc!"); return
        labels = [a[1] for a in sel]
        self.mt_master_menu.configure(values=labels)
        self.mt_master_var.set(labels[0])
        self.log("info", f"🔄 Đã load {len(labels)} acc vào dropdown")

    def _ask_private_handling(self):
        dlg = ctk.CTkToplevel(self.parent)
        dlg.title("Kênh private")
        dlg.geometry("520x300")
        dlg.transient(self.parent.winfo_toplevel()); dlg.grab_set()
        result = {"choice": None}

        ctk.CTkLabel(dlg, text="🔒 Kênh private xử lý sao?",
                     font=ctk.CTkFont(size=12)
                     ).pack(padx=15, pady=(15, 10), anchor="w")

        for text, val, color, hover in [
            ("⏭ SKIP — bỏ qua (an toàn)", "skip", "#1f6feb", "#1158c7"),
            ("🔗 EXPORT — tự gen invite", "export", "#dd8822", "#bb6f1c"),
            ("🌐 ALL — để Telegram tự reject", "all", "#aa44cc", "#8833aa"),
        ]:
            ctk.CTkButton(dlg, text=text, width=480, anchor="w",
                          fg_color=color, hover_color=hover,
                          command=lambda v=val: (result.update(choice=v), dlg.destroy())
                          ).pack(padx=15, pady=4)
        ctk.CTkButton(dlg, text="❌ Hủy", width=480, anchor="w",
                      fg_color="#666", hover_color="#555",
                      command=dlg.destroy).pack(padx=15, pady=(10, 15))
        dlg.wait_window()
        return result["choice"]

    def _run_master(self):
        sel = self._get_selected()
        if not sel: return
        master_label = self.mt_master_var.get()
        if master_label.startswith("("):
            messagebox.showerror("Lỗi", "Chưa chọn acc tổng (bấm 🔄)!"); return

        private_handling = self._ask_private_handling()
        if not private_handling: return

        master_acc = None
        slave_accs = []
        for acc in sel:
            if acc[1] == master_label: master_acc = acc
            else: slave_accs.append(acc)
        if master_acc is None:
            messagebox.showerror("Lỗi", "Không thấy acc tổng!"); return
        if not slave_accs:
            messagebox.showerror("Lỗi", "Cần ≥1 acc phụ!"); return

        folder_name = self.mt_folder.get().strip() or "All Managed"
        sub_folder = self.mt_subfolder.get().strip() or "ToShare"
        full = self.mt_full_var.get() == "full"
        promote_first = bool(self.mt_promote_first.get())
        save_links = bool(self.mt_save_links.get())
        auto_join = bool(self.mt_auto_join.get())
        delay = self._get_delay()
        mode = self.run_mode.get()
        max_p = self._get_max_parallel()

        runner = self._make_runner()
        all_links = []

        async def task():
            # Phase 1: Connect master
            self.log("info", "\n🔍 Phase 1: Kết nối acc tổng...")
            try:
                m_kind, m_label, m_payload = master_acc
                master_client = await self._make_client(m_kind, m_label, m_payload)
                me = await master_client.get_me()
                if not me.username:
                    self.log("error", "❌ Acc tổng chưa có username!"); return
                master_username = me.username
                self.log("ok", f"  ✓ Acc tổng: @{master_username}")
            except Exception as e:
                self.log("error", f"  ❌ {e}"); return

            try:
                # Phase 2: acc phụ
                async def do_slave(client, label):
                    self.log("info", "  ▶ B1: Quét kênh đang admin...")
                    channels = await get_admin_channels(client, log_cb=self.log)
                    if not channels:
                        self.log("info", f"  (không admin kênh nào)")
                        return None

                    if promote_first:
                        self.log("info", f"\n  ▶ B2: Cấp admin @{master_username}...")
                        for ch in channels:
                            try:
                                await promote_one(client, ch, master_username,
                                                  full=full, log_cb=self.log)
                            except Exception as e:
                                self.log("error", f"     💥 {e}")
                            await asyncio.sleep(delay)

                    self.log("info", f"\n  ▶ B3: Folder '{sub_folder}'...")
                    fid = await create_or_update_folder(
                        client, sub_folder, channels, log_cb=self.log)

                    self.log("info", "\n  ▶ B4: Export chatlist link...")
                    url = await export_chatlist_link(
                        client, fid, channels,
                        link_title=f"{label}-{sub_folder}",
                        private_handling=private_handling, log_cb=self.log)
                    if url:
                        all_links.append((label, url, len(channels)))
                        self.run_records.append({
                            "acc": label, "result": "ok",
                            "data": f"{url} ({len(channels)} kênh)"})
                    return url

                await runner.execute("Dồn về acc tổng (slaves)",
                                      slave_accs, do_slave,
                                      mode=mode, delay=delay,
                                      max_concurrent=max_p)

                if save_links and all_links:
                    self.log("info", f"\n💾 Lưu {len(all_links)} link...")
                    try:
                        with open("chatlist_links.txt", "a", encoding="utf-8") as f:
                            for label, url, cnt in all_links:
                                f.write(f"# {label} ({cnt} kênh)\n{url}\n\n")
                        self.log("ok", "  ✓ OK")
                    except Exception as e:
                        self.log("error", f"  ❌ {e}")

                if auto_join and all_links:
                    self.log("info", f"\n🚪 Acc tổng join {len(all_links)} link...")
                    total_joined = 0
                    for label, url, cnt in all_links:
                        success, joined = await join_chatlist_link(
                            master_client, url, log_cb=self.log)
                        if success: total_joined += joined
                        await asyncio.sleep(delay)
                    self.log("ok", f"\n  📊 Đã join {total_joined} kênh mới")

                    self.log("info", f"\n  ▶ Tạo folder tổng '{folder_name}'...")
                    await asyncio.sleep(2)
                    final_channels = await get_admin_channels(master_client, log_cb=self.log)
                    if final_channels:
                        await create_or_update_folder(
                            master_client, folder_name, final_channels,
                            log_cb=self.log)
            finally:
                try: await master_client.disconnect()
                except Exception: pass

        self._run_async("Dồn về acc tổng", task,
                        busy="🎯 Đang chạy...", done="✅ Hoàn tất")

    def _run_delete(self):
        sel = self._get_selected()
        if not sel: return
        if self.del_confirm.get().strip() != "DELETE":
            messagebox.showerror("Chưa xác nhận", 'Phải gõ "DELETE" (in hoa)!'); return
        if not self.del_understand.get():
            messagebox.showerror("Chưa xác nhận", "Phải tick ô hiểu hậu quả!"); return

        labels = [a[1] for a in sel]
        preview = "\n".join(f"  • {l}" for l in labels[:10])
        if len(labels) > 10:
            preview += f"\n  ... và {len(labels) - 10} acc khác"
        if not messagebox.askyesno(
            "⚠️ XÁC NHẬN CUỐI",
            f"XÓA VĨNH VIỄN {len(sel)} TÀI KHOẢN:\n\n{preview}\n\n"
            f"KHÔNG THỂ UNDO. Tiếp tục?",
            icon="warning"):
            return

        reason = self.del_reason.get().strip()
        self.del_confirm.delete(0, "end")
        self.del_understand.deselect()

        runner = self._make_runner()

        async def do_one(client, label):
            success = await delete_account(client, reason=reason, log_cb=self.log)
            self.run_records.append({
                "acc": label,
                "result": "deleted" if success else "error",
                "data": f"reason: {reason}"})
            return success

        async def task():
            # Luôn tuần tự khi xóa
            await runner.execute(f"XÓA {len(sel)} ACC", sel, do_one,
                                  mode="serial", delay=0.5)
            self.log("info", "💡 Bấm 🔍 Quét lại để cập nhật danh sách acc")

        self._run_async("XÓA ACC", task,
                        busy="🗑️ Đang xóa...", done="✅ Hoàn tất xóa")

    # ════════════════════════════════════════════════════════════════
    #  EXPORT
    # ════════════════════════════════════════════════════════════════
    def export_csv(self):
        if not self.run_records:
            messagebox.showinfo("Trống", "Chưa có dữ liệu!"); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["acc", "result", "data"])
            w.writeheader(); w.writerows(self.run_records)
        messagebox.showinfo("Xong", f"Đã ghi {len(self.run_records)} dòng")
