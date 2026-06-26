"""
Multi-Telegram Tool v8 — Web Interface
=======================================
Gộp toàn bộ logic từ v7 (6 file) thành 1 file backend.
Giao diện HTML đẹp, mở trình duyệt tự động, chạy bằng double-click.

Cài: pip install fastapi uvicorn[standard] sse-starlette telethon opentele pygetwindow pywin32
Chạy: python app.py   hoặc   start.bat
"""

from __future__ import annotations

import asyncio
import inspect
import json
import math
import os
import platform
import queue
import random
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

IS_WINDOWS = platform.system() == "Windows"
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "tg_tool_config.json"

# ── Embedded HTML — toàn bộ giao diện nhúng thẳng vào app.py ──
# Không cần tạo folder static/ riêng.
# Nếu muốn tùy chỉnh giao diện, tạo file static/index.html (sẽ ưu tiên dùng).
_EMBEDDED_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-Telegram Tool v8</title>
<style>
:root{--bg:#0d1117;--bg2:#161b22;--bg3:#1c2128;--bg4:#21262d;--border:#30363d;--border2:#3d444d;--accent:#2563eb;--accent-h:#1d4ed8;--green:#16a34a;--green-h:#15803d;--red:#dc2626;--red-h:#b91c1c;--amber:#d97706;--amber-h:#b45309;--purple:#7c3aed;--purple-h:#6d28d9;--text:#e6edf3;--text2:#8b949e;--text3:#6e7681;--ok:#3fb950;--err:#f85149;--warn:#e3b341;--info:#58a6ff;--skip:#6e7681;--radius:8px;--radius-lg:12px;--shadow:0 4px 20px rgba(0,0,0,.4);--sidebar-w:220px;--log-w:380px}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font:14px/1.5 'Segoe UI',system-ui,sans-serif;overflow:hidden;height:100vh;display:flex;flex-direction:column}
.header{background:var(--bg2);border-bottom:1px solid var(--border);padding:10px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0;z-index:10}
.logo{font-size:16px;font-weight:700;background:linear-gradient(135deg,#58a6ff,#a371f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;white-space:nowrap}
.header-folder{flex:1;display:flex;align-items:center;gap:6px}
.header-folder label{color:var(--text2);font-size:12px;white-space:nowrap}
.header-folder input{flex:1;background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:5px 10px;border-radius:6px;font-size:12px}
.header-folder input:focus{outline:none;border-color:var(--accent)}
.task-badge{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:4px 10px;font-size:12px;color:var(--text2);white-space:nowrap;transition:.2s}
.task-badge.running{color:var(--warn);border-color:var(--warn);background:rgba(227,179,65,.1)}
.layout{display:flex;flex:1;overflow:hidden}
.sidebar{width:var(--sidebar-w);background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
.nav-section{padding:12px 8px 4px;color:var(--text3);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em}
.nav-item{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:6px;cursor:pointer;margin:2px 6px;color:var(--text2);font-size:13px;transition:.15s;user-select:none}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:rgba(37,99,235,.2);color:var(--info);font-weight:500}
.nav-item .icon{font-size:15px;width:20px;text-align:center}
.sidebar-bottom{margin-top:auto;padding:12px 8px;border-top:1px solid var(--border)}
.version-tag{font-size:11px;color:var(--text3);text-align:center}
.main{flex:1;overflow:hidden;display:flex;flex-direction:column}
.tab-content{display:none;flex:1;overflow-y:auto;padding:16px;flex-direction:column;gap:12px}
.tab-content.active{display:flex}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden}
.card-header{padding:10px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--bg3)}
.card-header h3{font-size:13px;font-weight:600;color:var(--text)}
.card-body{padding:12px 14px}
.form-group{display:flex;flex-direction:column;gap:4px}
label.lbl{font-size:12px;color:var(--text2)}
input[type=text],input[type=number],input[type=password],select,textarea{background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;font-family:inherit;transition:border-color .15s}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
input[type=number]{width:80px}
textarea{resize:vertical;min-height:80px}
select{cursor:pointer}
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:6px;border:none;cursor:pointer;font-size:13px;font-weight:500;font-family:inherit;transition:.15s;white-space:nowrap}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover:not(:disabled){background:var(--accent-h)}
.btn-success{background:var(--green);color:#fff}
.btn-success:hover:not(:disabled){background:var(--green-h)}
.btn-danger{background:var(--red);color:#fff}
.btn-danger:hover:not(:disabled){background:var(--red-h)}
.btn-warn{background:var(--amber);color:#fff}
.btn-warn:hover:not(:disabled){background:var(--amber-h)}
.btn-purple{background:var(--purple);color:#fff}
.btn-purple:hover:not(:disabled){background:var(--purple-h)}
.btn-ghost{background:var(--bg3);border:1px solid var(--border);color:var(--text2)}
.btn-ghost:hover:not(:disabled){background:var(--bg4);color:var(--text);border-color:var(--border2)}
.btn-sm{padding:4px 10px;font-size:12px}
.btn-lg{padding:10px 20px;font-size:14px;width:100%;justify-content:center}
.radio-group{display:flex;gap:4px;flex-wrap:wrap}
.radio-opt{display:flex;align-items:center;gap:6px;padding:5px 10px;background:var(--bg3);border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;transition:.15s}
.radio-opt:hover{border-color:var(--border2)}
.radio-opt input[type=radio]{accent-color:var(--accent)}
.radio-opt.checked{border-color:var(--accent);background:rgba(37,99,235,.12);color:var(--info)}
input[type=checkbox]{accent-color:var(--accent);cursor:pointer}
.login-config{display:flex;flex-direction:column;gap:8px}
.login-config .row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.login-config label{font-size:12px;color:var(--text2);width:170px;flex-shrink:0}
.accounts-table-wrap{flex:1;overflow:auto}
.accounts-table{width:100%;border-collapse:collapse;font-size:12px}
.accounts-table th{background:var(--bg3);padding:7px 8px;text-align:left;font-weight:600;color:var(--text2);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:2;white-space:nowrap}
.accounts-table td{padding:5px 6px;border-bottom:1px solid var(--border);vertical-align:middle}
.accounts-table tr:hover td{background:rgba(255,255,255,.02)}
.accounts-table input{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 7px;border-radius:4px;font-size:12px;width:100%}
.accounts-table input:focus{outline:none;border-color:var(--accent)}
.accounts-table input.phone-field{width:130px}
.accounts-table input.code-field{width:70px}
.accounts-table input.twofa-field{width:110px}
.accounts-table input.folder-field{width:120px}
.accounts-table input.note-field{width:130px}
.status-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:12px;font-size:11px;white-space:nowrap}
.status-badge.ready{background:rgba(110,118,129,.15);color:var(--text3)}
.status-badge.sending{background:rgba(227,179,65,.15);color:var(--warn)}
.status-badge.code_sent{background:rgba(88,166,255,.15);color:var(--info)}
.status-badge.logging_in{background:rgba(88,166,255,.15);color:var(--info)}
.status-badge.need_2fa{background:rgba(227,179,65,.2);color:var(--warn)}
.status-badge.done{background:rgba(63,185,80,.15);color:var(--ok)}
.status-badge.error{background:rgba(248,81,73,.15);color:var(--err)}
.status-badge.warn{background:rgba(227,179,65,.15);color:var(--warn)}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.dot.pulse{animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.admin-layout{display:flex;gap:12px;flex:1;overflow:hidden;min-height:0}
.admin-left{width:260px;flex-shrink:0;display:flex;flex-direction:column;gap:10px;overflow-y:auto}
.admin-right{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
.acc-list-wrap{flex:1;overflow:auto;max-height:240px}
.acc-checkbox-list{display:flex;flex-direction:column;gap:2px}
.acc-check-item{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:5px;cursor:pointer}
.acc-check-item:hover{background:var(--bg3)}
.acc-check-item label{cursor:pointer;font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.search-box{background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:5px 10px;border-radius:6px;font-size:12px;width:100%}
.search-box:focus{outline:none;border-color:var(--accent)}
.sub-tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px}
.sub-tab{padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;background:var(--bg3);border:1px solid var(--border);color:var(--text2);transition:.15s;white-space:nowrap}
.sub-tab:hover{border-color:var(--border2);color:var(--text)}
.sub-tab.active{background:rgba(37,99,235,.2);border-color:var(--accent);color:var(--info)}
.sub-panel{display:none}
.sub-panel.active{display:flex;flex-direction:column;gap:10px}
.sync-windows-list{display:flex;flex-direction:column;gap:3px;max-height:160px;overflow:auto}
.window-item{display:flex;align-items:center;gap:8px;padding:5px 8px;background:var(--bg3);border-radius:5px;font-size:12px}
.window-item .wname{flex:1;color:var(--text);overflow:hidden;text-overflow:ellipsis}
.window-item .winfo{color:var(--text3);font-size:11px}
.log-panel{width:var(--log-w);border-left:1px solid var(--border);display:flex;flex-direction:column;background:var(--bg2);flex-shrink:0;transition:width .25s}
.log-panel.collapsed{width:36px}
.log-header{padding:8px 10px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:6px;background:var(--bg3);flex-shrink:0}
.log-header .log-title{font-size:12px;font-weight:600;color:var(--text2);flex:1;white-space:nowrap;overflow:hidden}
.log-header select{background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:2px 6px;border-radius:4px;font-size:11px}
.log-body{flex:1;overflow-y:auto;padding:6px;font-family:'Consolas','Courier New',monospace;font-size:11.5px;line-height:1.5}
.log-line{padding:1px 4px;border-radius:3px;word-break:break-all}
.log-line:hover{background:rgba(255,255,255,.04)}
.log-line.ok{color:var(--ok)}
.log-line.error{color:var(--err)}
.log-line.fresh,.log-line.warn{color:var(--warn)}
.log-line.no_perm,.log-line.not_member,.log-line.privacy,.log-line.invalid{color:#f0883e}
.log-line.skip{color:var(--skip)}
.log-line.info{color:var(--info)}
.log-line .ts{color:var(--text3);font-size:10px;margin-right:4px}
.log-toggle{cursor:pointer;padding:4px;border-radius:4px;background:none;border:none;color:var(--text2);font-size:14px;transition:.15s}
.log-toggle:hover{background:var(--bg4);color:var(--text)}
#toast-container{position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none}
.toast{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;font-size:13px;min-width:240px;max-width:360px;box-shadow:var(--shadow);pointer-events:all;display:flex;align-items:flex-start;gap:8px;animation:slideIn .2s ease}
.toast.ok{border-color:var(--ok)}
.toast.error{border-color:var(--err)}
.toast.warn{border-color:var(--warn)}
.toast-icon{font-size:15px}
.toast-msg{flex:1;line-height:1.4}
@keyframes slideIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
@keyframes fadeOut{from{opacity:1}to{opacity:0;transform:translateX(20px)}}
.text-sm{font-size:11px;color:var(--text3)}
.flex{display:flex}
.gap-2{gap:6px}
.items-center{align-items:center}
.flex-1{flex:1}
.mt-2{margin-top:6px}
.mt-3{margin-top:12px}
.bold{font-weight:600}
.empty-state{text-align:center;padding:24px;color:var(--text3);font-size:12px}
.cols-2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.w-full{width:100%}
</style>
</head>
<body>
<div class="header">
  <div class="logo">&#x1F680; Multi-Telegram Tool v8</div>
  <div class="header-folder">
    <label>Thu muc goc:</label>
    <input id="base-folder" type="text" placeholder="Chon thu muc luu tai khoan...">
    <button class="btn btn-ghost btn-sm" onclick="browseFolder()">&#x1F4C1; Chon</button>
  </div>
  <div id="task-badge" class="task-badge">&#x2699; 0 task</div>
  <button class="btn btn-danger btn-sm" onclick="cancelAll()">&#x23F9; Huy het</button>
  <button class="btn btn-ghost btn-sm" onclick="clearLog()">&#x1F5D1; Xoa log</button>
</div>
<div class="layout">
  <aside class="sidebar">
    <div class="nav-section">Chuc nang</div>
    <div class="nav-item active" onclick="switchTab('login')" id="nav-login"><span class="icon">&#x1F510;</span> Dang nhap</div>
    <div class="nav-item" onclick="switchTab('admin')" id="nav-admin"><span class="icon">&#x1F6E0;&#xFE0F;</span> Admin &amp; Channel</div>
    <div class="nav-item" onclick="switchTab('sync')" id="nav-sync"><span class="icon">&#x1F504;</span> Dong bo Tab</div>
    <div class="sidebar-bottom"><div class="version-tag">v8 &middot; Web Interface</div></div>
  </aside>
  <div class="main">
    <!-- TAB LOGIN -->
    <div id="tab-login" class="tab-content active">
      <div class="card">
        <div class="card-header"><h3>&#x2699;&#xFE0F; Cau hinh dang nhap</h3></div>
        <div class="card-body">
          <div class="login-config">
            <div class="row">
              <label class="lbl">Telegram Portable (tuy chon):</label>
              <input id="portable-src" type="text" style="flex:1" placeholder="Folder chua Telegram.exe">
              <button class="btn btn-ghost btn-sm" onclick="browsePortable()">&#x1F4C1; Chon</button>
            </div>
            <div class="row">
              <label class="lbl">Ten folder sau login:</label>
              <div class="radio-group">
                <label class="radio-opt checked"><input type="radio" name="naming" value="username" checked onchange="updateNaming(this)"> @username</label>
                <label class="radio-opt"><input type="radio" name="naming" value="firstname" onchange="updateNaming(this)"> Ten hien thi</label>
                <label class="radio-opt"><input type="radio" name="naming" value="prefix" onchange="updateNaming(this)"> Prefix:</label>
                <input id="prefix-entry" type="text" placeholder="vd: client" style="width:100px">
                <label class="radio-opt"><input type="radio" name="naming" value="manual" onchange="updateNaming(this)"> Giu nguyen</label>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3>&#x1F4D2; Danh sach tai khoan</h3>
          <div class="flex gap-2 items-center">
            <label class="lbl">So acc:</label>
            <input id="num-acc" type="number" value="5" min="1" max="200" style="width:65px">
            <button class="btn btn-ghost btn-sm" onclick="genRows()">&#x1F4CB; Tao bang</button>
            <button class="btn btn-purple btn-sm" onclick="openBulkPhone()">&#x1F4E5; Nhap SDT</button>
            <button class="btn btn-warn btn-sm" onclick="openApply2FA()">&#x1F512; Ap 2FA</button>
            <button class="btn btn-danger btn-sm" onclick="clearRows()">&#x1F5D1; Xoa het</button>
          </div>
        </div>
        <div class="card-body" style="padding:6px 14px 8px">
          <div class="flex gap-2 items-center" style="flex-wrap:wrap;margin-bottom:8px">
            <button class="btn btn-warn btn-sm" onclick="sendAll()">&#x1F4E9; Gui ma TAT CA</button>
            <button class="btn btn-purple btn-sm" onclick="openBulkCode()">&#x1F4DD; Nhap code</button>
            <button class="btn btn-primary btn-sm" onclick="loginAll()">&#x1F510; Dang nhap TAT CA</button>
            <button class="btn btn-success btn-sm" onclick="launchTile()">&#x1FA9F; Mo + chia man hinh</button>
            <button class="btn btn-danger btn-sm" onclick="closeAllTabs()">&#x274C; Dong tat ca tab</button>
          </div>
        </div>
        <div class="accounts-table-wrap" style="max-height:420px;overflow:auto;border-top:1px solid var(--border)">
          <table class="accounts-table">
            <thead><tr>
              <th style="width:36px">#</th><th>Folder</th><th>Ghi chu</th><th>SDT</th>
              <th>Code</th><th>2FA</th><th style="width:175px">Hanh dong</th><th>Trang thai</th>
            </tr></thead>
            <tbody id="accounts-tbody">
              <tr><td colspan="8" class="empty-state">Chua co dong nao &middot; Bam "Tao bang" de bat dau</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <!-- TAB ADMIN -->
    <div id="tab-admin" class="tab-content">
      <div class="admin-layout">
        <div class="admin-left">
          <div class="card" style="flex:1">
            <div class="card-header">
              <h3>&#x1F465; Tai khoan</h3>
              <button class="btn btn-ghost btn-sm" onclick="scanAccounts()">&#x1F50D; Quet</button>
            </div>
            <div class="card-body" style="padding:8px">
              <input class="search-box" id="admin-search" placeholder="&#x1F50D; Tim acc..." oninput="filterAccList(this.value)" style="margin-bottom:6px">
              <div class="flex gap-2" style="margin-bottom:6px;flex-wrap:wrap">
                <button class="btn btn-ghost btn-sm" style="flex:1" onclick="selectAll()">&#x2713; Tat ca</button>
                <button class="btn btn-ghost btn-sm" style="flex:1" onclick="selectNone()">&#x2715; Bo</button>
                <button class="btn btn-ghost btn-sm" style="flex:1" onclick="selectInvert()">&#x2195; Dao</button>
              </div>
              <div class="acc-list-wrap"><div class="acc-checkbox-list" id="acc-checkbox-list"><div class="empty-state">Bam Quet de tai danh sach</div></div></div>
              <div id="acc-selected-count" class="text-sm mt-2">0 acc duoc chon</div>
            </div>
          </div>
          <div class="card">
            <div class="card-body" style="padding:10px">
              <div class="form-group" style="gap:8px">
                <div class="flex gap-2 items-center">
                  <span class="lbl">Che do:</span>
                  <label class="radio-opt checked" id="r-parallel"><input type="radio" name="run-mode" value="parallel" checked onchange="updateRunMode()"> Song song</label>
                  <label class="radio-opt" id="r-serial"><input type="radio" name="run-mode" value="serial" onchange="updateRunMode()"> Tuan tu</label>
                </div>
                <div class="flex gap-2 items-center" style="flex-wrap:wrap">
                  <span class="lbl">Delay (s):</span><input id="run-delay" type="number" value="0.5" min="0" step="0.1" style="width:70px">
                  <span class="lbl">Max:</span><input id="run-max" type="number" value="8" min="1" style="width:60px">
                </div>
                <button class="btn btn-danger btn-sm w-full" onclick="cancelAll()">&#x23F9; DUNG TAT CA</button>
              </div>
            </div>
          </div>
        </div>
        <div class="admin-right">
          <div class="sub-tabs">
            <div class="sub-tab active" onclick="switchSubTab('create-ch')" id="st-create-ch">&#x1F3D7;&#xFE0F; Tao channel</div>
            <div class="sub-tab" onclick="switchSubTab('create-pub')" id="st-create-pub">&#x1F310; Kenh public</div>
            <div class="sub-tab" onclick="switchSubTab('promote')" id="st-promote">&#x1F46E; Cap admin</div>
            <div class="sub-tab" onclick="switchSubTab('folder-prom')" id="st-folder-prom">&#x1F4C2; Theo Folder TG</div>
            <div class="sub-tab" onclick="switchSubTab('auto-folder')" id="st-auto-folder">&#x1F4C1; Auto Folder</div>
            <div class="sub-tab" onclick="switchSubTab('auto-promote')" id="st-auto-promote">&#x1F465; Auto-promote</div>
            <div class="sub-tab" onclick="switchSubTab('consolidate')" id="st-consolidate">&#x1F3AF; Don ve acc tong</div>
            <div class="sub-tab" onclick="switchSubTab('delete-acc')" id="st-delete-acc">&#x1F5D1;&#xFE0F; Xoa account</div>
          </div>
          <!-- Sub 1: Tao channel -->
          <div class="sub-panel active" id="sp-create-ch"><div class="card">
            <div class="card-header"><h3>&#x1F3D7;&#xFE0F; Tao Channel / Group rieng tu</h3></div>
            <div class="card-body">
              <div class="cols-2">
                <div class="form-group"><label class="lbl">So kenh moi acc</label><input id="ch-amount" type="number" value="1" min="1"></div>
                <div class="form-group"><label class="lbl">Prefix ten kenh</label><input id="ch-prefix" type="text" value="vip_" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Mo ta (about)</label><input id="ch-about" type="text" placeholder="Mo ta kenh..." style="width:100%"></div>
                <div class="form-group"><label class="lbl">Delay giua kenh (s)</label><input id="ch-delay" type="number" value="1" min="0" step="0.5"></div>
              </div>
              <div class="flex gap-2 items-center mt-2">
                <label class="radio-opt checked"><input type="radio" name="ch-type" value="false" checked> Channel</label>
                <label class="radio-opt"><input type="radio" name="ch-type" value="true"> Megagroup</label>
              </div>
              <div class="text-sm mt-2">Link invite luu vao <code>channels.txt</code></div>
              <button class="btn btn-success btn-lg mt-3" onclick="runCreateChannels()">&#x25B6; TAO CHANNEL</button>
            </div>
          </div></div>
          <!-- Sub 2: Kenh public -->
          <div class="sub-panel" id="sp-create-pub"><div class="card">
            <div class="card-header"><h3>&#x1F310; Tao Kenh Cong Khai (co @username)</h3></div>
            <div class="card-body">
              <div class="cols-2">
                <div class="form-group"><label class="lbl">So kenh moi acc</label><input id="pub-amount" type="number" value="1" min="1"></div>
                <div class="form-group"><label class="lbl">Ten kenh (dung {n} danh so)</label><input id="pub-title" type="text" value="Kenh {n}" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Username prefix</label><input id="pub-uname" type="text" value="channel" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Suffix mode</label>
                  <select id="pub-suffix" style="width:100%">
                    <option value="random_3">random_3 (3 ky tu)</option>
                    <option value="random_2">random_2 (2 ky tu)</option>
                    <option value="random_1">random_1 (1 ky tu)</option>
                    <option value="chaos">chaos (5-8 ky tu)</option>
                  </select>
                </div>
                <div class="form-group"><label class="lbl">Mo ta (about)</label><input id="pub-about" type="text" placeholder="Mo ta kenh..." style="width:100%"></div>
                <div class="form-group"><label class="lbl">Delay giua kenh (s)</label><input id="pub-delay" type="number" value="2" min="0" step="0.5"></div>
                <div class="form-group"><label class="lbl">Anh kenh (duong dan file)</label><input id="pub-photo" type="text" placeholder="D:\hinh.jpg" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Welcome message</label><input id="pub-welcome" type="text" placeholder="Tin nhan dau tien..." style="width:100%"></div>
              </div>
              <button class="btn btn-success btn-lg mt-3" onclick="runCreatePublic()">&#x25B6; TAO KENH PUBLIC</button>
            </div>
          </div></div>
          <!-- Sub 3: Cap admin -->
          <div class="sub-panel" id="sp-promote"><div class="card">
            <div class="card-header"><h3>&#x1F46E; Cap Admin cho User</h3></div>
            <div class="card-body">
              <div class="cols-2">
                <div class="form-group"><label class="lbl">Danh sach kenh</label><textarea id="prom-channels" rows="4" placeholder="@channel1&#10;t.me/channel2"></textarea></div>
                <div class="form-group"><label class="lbl">Username can cap admin</label><textarea id="prom-users" rows="4" placeholder="@user1&#10;user2"></textarea></div>
              </div>
              <div class="flex gap-2 items-center mt-2"><label><input type="checkbox" id="prom-full" checked> Toan quyen admin</label></div>
              <div class="text-sm mt-2">Load tu channels.txt: <button class="btn btn-ghost btn-sm" onclick="loadChannelsTxt()">&#x1F4C2; Tai</button></div>
              <button class="btn btn-success btn-lg mt-3" onclick="runPromote()">&#x25B6; CAP ADMIN</button>
            </div>
          </div></div>
          <!-- Sub 4: Folder promote -->
          <div class="sub-panel" id="sp-folder-prom"><div class="card">
            <div class="card-header"><h3>&#x1F4C2; Cap Admin Theo Folder Telegram</h3></div>
            <div class="card-body">
              <div class="cols-2">
                <div class="form-group"><label class="lbl">Ten folder Telegram</label><input id="fp-folder" type="text" placeholder="Ten folder trong TG" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Username can cap admin</label><textarea id="fp-users" rows="3" placeholder="@user1&#10;user2"></textarea></div>
              </div>
              <div class="flex gap-2 items-center mt-2"><label><input type="checkbox" id="fp-full" checked> Toan quyen admin</label></div>
              <button class="btn btn-success btn-lg mt-3" onclick="runFolderPromote()">&#x25B6; CAP ADMIN THEO FOLDER</button>
            </div>
          </div></div>
          <!-- Sub 5: Auto Folder -->
          <div class="sub-panel" id="sp-auto-folder"><div class="card">
            <div class="card-header"><h3>&#x1F4C1; Gom kenh admin vao Folder TG</h3></div>
            <div class="card-body">
              <div class="form-group"><label class="lbl">Ten folder muon tao/cap nhat</label><input id="af-name" type="text" value="Admin Channels" style="width:100%"></div>
              <div class="text-sm mt-2">Tool quet tat ca kenh acc dang la admin, gom vao 1 folder TG</div>
              <button class="btn btn-success btn-lg mt-3" onclick="runAutoFolder()">&#x25B6; AUTO FOLDER</button>
            </div>
          </div></div>
          <!-- Sub 6: Auto promote -->
          <div class="sub-panel" id="sp-auto-promote"><div class="card">
            <div class="card-header"><h3>&#x1F465; Cap Admin vao Tat Ca Kenh Dang Admin</h3></div>
            <div class="card-body">
              <div class="form-group"><label class="lbl">Username can cap admin</label><textarea id="ap-users" rows="3" placeholder="@user1&#10;user2&#10;user3"></textarea></div>
              <div class="flex gap-2 items-center mt-2"><label><input type="checkbox" id="ap-full" checked> Toan quyen admin</label></div>
              <button class="btn btn-success btn-lg mt-3" onclick="runAutoPromote()">&#x25B6; AUTO-PROMOTE</button>
            </div>
          </div></div>
          <!-- Sub 7: Consolidate -->
          <div class="sub-panel" id="sp-consolidate"><div class="card">
            <div class="card-header"><h3>&#x1F3AF; Don Kenh Ve Acc Tong qua Chatlist Link</h3></div>
            <div class="card-body">
              <div class="cols-2">
                <div class="form-group"><label class="lbl">Acc tong (folder name)</label><input id="cons-master" type="text" placeholder="vd: master_acc" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Ten folder TG de export</label><input id="cons-folder" type="text" value="Master" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Tieu de chatlist link</label><input id="cons-title" type="text" value="My Folder" style="width:100%"></div>
                <div class="form-group"><label class="lbl">Kenh private</label>
                  <select id="cons-private" style="width:100%">
                    <option value="skip">Bo qua (skip)</option>
                    <option value="export">Export invite truoc</option>
                    <option value="all">Dua tat ca vao</option>
                  </select>
                </div>
              </div>
              <div class="text-sm mt-2">Chatlist links luu vao <code>chatlist_links.txt</code></div>
              <button class="btn btn-success btn-lg mt-3" onclick="runConsolidate()">&#x25B6; DON VE ACC TONG</button>
            </div>
          </div></div>
          <!-- Sub 8: Delete -->
          <div class="sub-panel" id="sp-delete-acc"><div class="card" style="border-color:var(--red)">
            <div class="card-header" style="border-color:var(--red);background:rgba(220,38,38,.1)">
              <h3 style="color:var(--err)">&#x1F5D1;&#xFE0F; Xoa Account Vinh Vien</h3>
            </div>
            <div class="card-body">
              <div style="background:rgba(220,38,38,.1);border:1px solid var(--red);border-radius:6px;padding:10px;margin-bottom:12px">
                <div class="bold" style="color:var(--err)">&#x26A0;&#xFE0F; CANH BAO</div>
                <div class="text-sm" style="color:var(--err);margin-top:4px">Thao tac nay XOA VINH VIEN tai khoan Telegram. KHONG THE UNDO.</div>
              </div>
              <div class="form-group"><label class="lbl">Ly do xoa (tuy chon)</label><input id="del-reason" type="text" placeholder="Khong can thiet nua..." style="width:100%"></div>
              <div class="flex gap-2 items-center mt-2" style="background:rgba(220,38,38,.1);padding:8px;border-radius:6px">
                <input type="checkbox" id="del-confirm1"><label for="del-confirm1" style="cursor:pointer;font-size:12px">Toi hieu hanh dong nay KHONG THE HOAN TAC</label>
              </div>
              <div class="flex gap-2 items-center mt-2" style="background:rgba(220,38,38,.1);padding:8px;border-radius:6px">
                <input type="checkbox" id="del-confirm2"><label for="del-confirm2" style="cursor:pointer;font-size:12px">Toi da backup du lieu can thiet</label>
              </div>
              <button class="btn btn-danger btn-lg mt-3" onclick="runDeleteAccounts()">&#x1F5D1;&#xFE0F; XOA ACCOUNT (KHONG THE UNDO)</button>
            </div>
          </div></div>
        </div>
      </div>
    </div>
    <!-- TAB SYNC -->
    <div id="tab-sync" class="tab-content">
      <div class="card">
        <div class="card-header"><h3>&#x1F5A5;&#xFE0F; Tab Telegram dang theo doi</h3></div>
        <div class="card-body">
          <div class="text-sm" style="margin-bottom:8px;color:var(--text3)">Chi thao tac tren tab Telegram do tool tu mo. Tab khac tren may KHONG bi dung vao.</div>
          <div class="flex gap-2 items-center" style="margin-bottom:10px;flex-wrap:wrap">
            <span class="bold" id="sync-count">0 tab</span>
            <button class="btn btn-ghost btn-sm" onclick="refreshWindows()">&#x1F504; Cap nhat</button>
            <button class="btn btn-ghost btn-sm" onclick="showWindowList()">&#x1F4CB; Xem danh sach</button>
          </div>
          <div class="sync-windows-list" id="sync-windows-list">
            <div class="empty-state">Chua co tab nao &middot; Vao Tab Dang nhap &#x2192; Mo + chia man hinh</div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>&#x270D;&#xFE0F; Gui Text Dong Bo Toi Tat Ca Tab</h3></div>
        <div class="card-body">
          <div class="text-sm" style="margin-bottom:8px;color:var(--text3)">Tool focus tung tab, paste, Enter (neu chon). Dam bao tab TG dang o o chat.</div>
          <textarea id="sync-text" rows="5" class="w-full" placeholder="Nhap noi dung gui...">Hello world!</textarea>
          <div class="flex gap-2 items-center mt-2" style="flex-wrap:wrap">
            <label><input type="checkbox" id="sync-enter" checked> Nhan Enter (gui luon)</label>
            <span class="lbl" style="margin-left:12px">Delay giua tab (s):</span>
            <input type="number" id="sync-delay" value="0.3" min="0" step="0.1" style="width:70px">
          </div>
          <button class="btn btn-success btn-lg mt-3" onclick="broadcastText()">&#x1F4E4; GUI DONG BO TOI TAT CA TAB</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>&#x1F3DB;&#xFE0F; Dieu Khien Cua So</h3></div>
        <div class="card-body">
          <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            <button class="btn btn-primary" onclick="retileWindows()">&#x1FA9F; Re-tile (xep luoi)</button>
            <button class="btn btn-ghost" onclick="bringToFront()">&#x1F4CD; Dua len tren</button>
            <button class="btn btn-danger" onclick="closeAllTabs()">&#x274C; DONG TAT CA TAB</button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <!-- Log panel -->
  <div class="log-panel" id="log-panel">
    <div class="log-header">
      <span class="log-title" id="log-title">&#x1F4DC; Log</span>
      <select id="log-filter" onchange="filterLog(this.value)">
        <option value="all">Tat ca</option>
        <option value="ok,error">OK + Loi</option>
        <option value="error">Chi loi</option>
        <option value="info,ok">Info + OK</option>
      </select>
      <button class="log-toggle" onclick="clearLog()" title="Xoa log">&#x1F5D1;</button>
      <button class="log-toggle" onclick="saveLog()" title="Luu log">&#x1F4BE;</button>
      <button class="log-toggle" id="log-collapse-btn" onclick="toggleLog()">&#x25C4;</button>
    </div>
    <div class="log-body" id="log-body"></div>
  </div>
</div>
<div id="toast-container"></div>
<div id="modal-overlay" onclick="closeModal()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000"></div>
<div id="modal" style="display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--bg2);border:1px solid var(--border);border-radius:12px;z-index:1001;width:560px;max-width:95vw;max-height:90vh;overflow-y:auto;box-shadow:var(--shadow)">
  <div class="card-header" style="border-radius:12px 12px 0 0"><h3 id="modal-title"></h3><button class="log-toggle" onclick="closeModal()">&#x2715;</button></div>
  <div id="modal-body" style="padding:16px"></div>
</div>
<script>
let ws=null,rows=[],adminAccounts=[],selectedAdminAccs=new Set(),trackedWindows=[],logFilter='all',logCollapsed=false,rowCounter=0,config={};
function connectWS(){
  ws=new WebSocket(`ws://${location.host}/ws`);
  ws.onopen=()=>console.log('WS ok');
  ws.onmessage=(e)=>{const m=JSON.parse(e.data);handleWsMessage(m)};
  ws.onclose=()=>setTimeout(connectWS,2000);
  ws.onerror=()=>ws.close();
}
function handleWsMessage(m){
  switch(m.type){
    case 'log':appendLog(m.data);break;
    case 'log_clear':document.getElementById('log-body').innerHTML='';break;
    case 'task_count':updateTaskBadge(m.data);break;
    case 'config':config=m.data;applyConfig(config);break;
    case 'login_rows':m.data.forEach(r=>updateRowStatus(r));break;
    case 'row_status':updateRowStatus(m.data);break;
    case 'row_folder':updateRowFolder(m.data);break;
    case 'windows':updateWindowList(m.data);break;
  }
}
async function api(method,url,body){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body!==undefined)opts.body=JSON.stringify(body);
  const r=await fetch(url,opts);return r.json();
}
const get=(url)=>api('GET',url);
const post=(url,body)=>api('POST',url,body);
function applyConfig(cfg){
  if(cfg.base_folder)document.getElementById('base-folder').value=cfg.base_folder;
  if(cfg.portable_src)document.getElementById('portable-src').value=cfg.portable_src;
  if(cfg.naming_mode)document.querySelectorAll('[name="naming"]').forEach(r=>{r.checked=r.value===cfg.naming_mode;r.closest('.radio-opt')?.classList.toggle('checked',r.checked)});
  if(cfg.prefix_entry)document.getElementById('prefix-entry').value=cfg.prefix_entry;
  if(cfg.sync_text)document.getElementById('sync-text').value=cfg.sync_text;
  if(cfg.sync_delay)document.getElementById('sync-delay').value=cfg.sync_delay;
}
function saveConfig(extra={}){
  const cfg={base_folder:document.getElementById('base-folder').value,portable_src:document.getElementById('portable-src').value,naming_mode:document.querySelector('[name="naming"]:checked')?.value||'username',prefix_entry:document.getElementById('prefix-entry').value,sync_text:document.getElementById('sync-text').value,sync_delay:document.getElementById('sync-delay').value,...extra};
  post('/api/config',cfg);
}
document.addEventListener('DOMContentLoaded',()=>{document.getElementById('base-folder').addEventListener('change',()=>saveConfig())});
async function browseFolder(){const r=await post('/api/browse-folder',{});if(r.path){document.getElementById('base-folder').value=r.path;saveConfig();}}
async function browsePortable(){const r=await post('/api/browse-folder',{});if(r.path)document.getElementById('portable-src').value=r.path;}
function switchTab(id){document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(el=>el.classList.remove('active'));document.getElementById('tab-'+id).classList.add('active');document.getElementById('nav-'+id).classList.add('active');saveConfig({last_tab:id});}
function switchSubTab(id){document.querySelectorAll('.sub-tab').forEach(el=>el.classList.remove('active'));document.querySelectorAll('.sub-panel').forEach(el=>el.classList.remove('active'));document.getElementById('st-'+id).classList.add('active');document.getElementById('sp-'+id).classList.add('active');}
function appendLog(entry){
  const levels=logFilter==='all'?null:logFilter.split(',');
  if(levels&&!levels.includes(entry.level))return;
  const body=document.getElementById('log-body');
  const line=document.createElement('div');
  line.className='log-line '+(entry.level||'info');
  line.dataset.level=entry.level||'info';
  line.innerHTML=`<span class="ts">${entry.ts}</span>${escHtml(entry.msg)}`;
  body.appendChild(line);
  if(body.children.length>3000)body.removeChild(body.firstChild);
  body.scrollTop=body.scrollHeight;
}
function filterLog(val){logFilter=val;document.querySelectorAll('.log-line').forEach(el=>{const lvl=el.dataset.level||'info';el.style.display=(val==='all'||val.split(',').includes(lvl))?'':'none'});}
function clearLog(){post('/api/logs/clear',{});}
function saveLog(){const lines=Array.from(document.querySelectorAll('.log-line')).map(el=>el.textContent).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines],{type:'text/plain'}));a.download=`tg-log-${Date.now()}.txt`;a.click();}
function toggleLog(){logCollapsed=!logCollapsed;document.getElementById('log-panel').classList.toggle('collapsed',logCollapsed);document.getElementById('log-collapse-btn').textContent=logCollapsed?'\u25BA':'\u25C4';document.getElementById('log-title').style.display=logCollapsed?'none':'';}
function updateTaskBadge(n){const el=document.getElementById('task-badge');el.textContent=`\u2699 ${n} task`;el.classList.toggle('running',n>0);}
async function cancelAll(){const r=await post('/api/tasks/cancel-all',{});toast(`Da yeu cau huy ${r.cancelled} task`,'warn');}
function makeRowId(){return 'row_'+(++rowCounter);}
function genRows(){const n=parseInt(document.getElementById('num-acc').value)||5;clearRows();for(let i=0;i<n;i++)addRow();}
function addRow(data={}){
  const id=data.id||makeRowId();
  const row={id,folder:data.folder||'',note:data.note||'',phone:data.phone||'',code:data.code||'',twofa:data.twofa||'',status:data.status||'ready',status_text:data.status_text||'\u23F8 San sang'};
  rows.push(row);renderRow(row);syncRowsToServer();return row;
}
function renderRow(row){
  const tbody=document.getElementById('accounts-tbody');
  const empty=tbody.querySelector('[colspan]');if(empty)empty.parentElement.remove();
  const idx=rows.indexOf(row)+1;
  const tr=document.createElement('tr');tr.id='tr-'+row.id;
  tr.innerHTML=`<td style="color:var(--text3)">${idx}</td>
    <td><input class="folder-field" type="text" placeholder="acc_${idx}" value="${escAttr(row.folder)}" oninput="rowField('${row.id}','folder',this.value)"></td>
    <td><input class="note-field" type="text" placeholder="ghi chu" value="${escAttr(row.note)}" oninput="rowField('${row.id}','note',this.value)"></td>
    <td><input class="phone-field" type="text" placeholder="+84..." value="${escAttr(row.phone)}" oninput="rowField('${row.id}','phone',this.value)"></td>
    <td><input class="code-field" type="text" placeholder="12345" value="${escAttr(row.code)}" oninput="rowField('${row.id}','code',this.value)"></td>
    <td><input class="twofa-field" type="password" placeholder="(neu co)" oninput="rowField('${row.id}','twofa',this.value)"></td>
    <td style="white-space:nowrap">
      <button class="btn btn-warn btn-sm" onclick="sendCode('${row.id}')">&#x1F4E9; Gui ma</button>
      <button class="btn btn-primary btn-sm" onclick="signIn('${row.id}')">&#x1F510; Login</button>
    </td>
    <td id="status-${row.id}"><span class="status-badge ${row.status}"><span class="dot"></span>${escHtml(row.status_text)}</span></td>`;
  tbody.appendChild(tr);
}
function rowField(id,field,val){const row=rows.find(r=>r.id===id);if(row)row[field]=val;}
function clearRows(){rows=[];document.getElementById('accounts-tbody').innerHTML='<tr><td colspan="8" class="empty-state">Chua co dong nao &middot; Bam "Tao bang" de bat dau</td></tr>';}
function updateRowStatus(data){
  const row=rows.find(r=>r.id===data.id);
  if(row){row.status=data.status;row.status_text=data.text||data.status_text||'';}
  const el=document.getElementById('status-'+data.id);if(!el)return;
  const pulse=['sending','logging_in'].includes(data.status);
  el.innerHTML=`<span class="status-badge ${data.status}"><span class="dot ${pulse?'pulse':''}"></span>${escHtml(data.text||data.status_text||data.status)}</span>`;
}
function updateRowFolder(data){const row=rows.find(r=>r.id===data.id);if(row)row.folder=data.folder;const tr=document.getElementById('tr-'+data.id);if(tr){const inp=tr.querySelector('.folder-field');if(inp)inp.value=data.folder;}}
function syncRowsToServer(){post('/api/login/rows/sync',{rows:rows.map(r=>({...r}))});}
async function sendCode(rowId){
  const row=rows.find(r=>r.id===rowId);if(!row)return;
  const r=await post(`/api/login/send-code/${rowId}`,{base_folder:document.getElementById('base-folder').value,phone:row.phone,folder:row.folder||('acc_'+rowId)});
  if(!r.ok)toast(r.msg,'error');
}
async function signIn(rowId){
  const row=rows.find(r=>r.id===rowId);if(!row)return;
  const tr=document.getElementById('tr-'+rowId);
  const twofaInput=tr?.querySelector('.twofa-field');
  const r=await post(`/api/login/sign-in/${rowId}`,{base_folder:document.getElementById('base-folder').value,code:row.code,twofa:twofaInput?.value||'',naming_mode:document.querySelector('[name="naming"]:checked')?.value||'username',prefix:document.getElementById('prefix-entry').value,portable_src:document.getElementById('portable-src').value});
  if(!r.ok)toast(r.msg,'error');
}
async function sendAll(){
  const base=document.getElementById('base-folder').value;
  if(!base){toast('Chua chon thu muc goc!','error');return;}
  syncRowsToServer();
  const r=await post('/api/login/send-all',{base_folder:base,rows});
  toast(`Queue gui ma ${r.count} acc`,'info');
}
async function loginAll(){
  syncRowsToServer();
  const targets=rows.filter(r=>r.code&&r.status==='code_sent');
  if(!targets.length){toast('Khong co acc san sang login','warn');return;}
  for(const row of targets)await signIn(row.id);
  toast(`Da queue login ${targets.length} acc`,'info');
}
function openBulkPhone(){showModal('Nhap SDT Hang Loat',`
  <div class="form-group"><label class="lbl">2FA chung (tuy chon)</label><input id="bulk-common-2fa" type="password" placeholder="(de trong neu khong co)" style="width:100%"></div>
  <div class="form-group mt-2"><label class="lbl">Moi dong: SDT hoac SDT | 2FA</label><textarea id="bulk-phones" rows="10" style="width:100%;font-family:monospace" placeholder="+84912345678\n+84987654321 | password2FA"></textarea></div>
  <div class="flex gap-2 mt-3"><button class="btn btn-success" onclick="applyBulkPhones()">Ap dung</button><button class="btn btn-ghost" onclick="closeModal()">Huy</button></div>`);}
function applyBulkPhones(){
  const common2fa=document.getElementById('bulk-common-2fa').value.trim();
  const text=document.getElementById('bulk-phones').value.trim();
  const entries=[];
  for(const line of text.split('\n')){const l=line.trim();if(!l)continue;const parts=l.split(/\s*\|\s*|\t+|\s{2,}/);let phone=parts[0].replace(/[^\d+]/g,'');if(!phone.startsWith('+'))phone='+'+phone;const twofa=parts[1]?.trim()||common2fa||'';if(phone.length>=9)entries.push({phone,twofa});}
  if(!entries.length){toast('Khong tim thay SDT hop le!','error');return;}
  clearRows();entries.forEach(e=>addRow({phone:e.phone,twofa:e.twofa}));closeModal();toast(`Da import ${entries.length} SDT`,'ok');
}
function openBulkCode(){
  if(!rows.length){toast('Chua co dong nao!','warn');return;}
  const ref=rows.filter(r=>r.phone).map((r,i)=>`#${String(i+1).padStart(2,'0')} ${r.phone}${r.code?' ['+r.code+']':''}`).join('\n');
  showModal('Nhap Code Hang Loat',`
    <div class="text-sm" style="margin-bottom:6px">1 code/dong theo thu tu | SDT|code khop SDT | SDT|code|2FA</div>
    ${ref?`<textarea readonly rows="3" style="width:100%;font-size:11px;font-family:monospace;background:var(--bg3);color:var(--text3)">${escHtml(ref)}</textarea>`:''}
    <textarea id="bulk-codes" rows="8" style="width:100%;margin-top:8px;font-family:monospace" placeholder="12345\n+84912345678 | 54321\n+84987654321 | 11111 | 2fapwd"></textarea>
    <div class="flex gap-2 mt-3"><button class="btn btn-success" onclick="applyBulkCodes()">Ap dung</button><button class="btn btn-ghost" onclick="closeModal()">Huy</button></div>`);
}
function applyBulkCodes(){
  const text=document.getElementById('bulk-codes').value.trim();const parsed=[];
  for(const line of text.split('\n')){const l=line.trim();if(!l)continue;const parts=l.split(/\s*\|\s*|\t+|\s{2,}/);if(parts.length===1){const code=parts[0].replace(/\D/g,'');if(code)parsed.push({phone:null,code,twofa:''});}else{let phone=parts[0].replace(/[^\d+]/g,'');if(!phone.startsWith('+'))phone='+'+phone;const code=parts[1]?.replace(/\D/g,'');const twofa=parts[2]?.trim()||'';if(code)parsed.push({phone,code,twofa});}}
  if(!parsed.length){toast('Khong tim thay code!','error');return;}
  let byPhone=0,byOrder=0,orderIdx=0;const emptyCodeRows=rows.filter(r=>!r.code);
  for(const p of parsed){let target=null;if(p.phone){target=rows.find(r=>r.phone===p.phone&&!r.code);if(target)byPhone++;}else{if(orderIdx<emptyCodeRows.length){target=emptyCodeRows[orderIdx++];byOrder++;}}if(target){target.code=p.code;if(p.twofa)target.twofa=p.twofa;const tr=document.getElementById('tr-'+target.id);if(tr){const ci=tr.querySelector('.code-field');if(ci)ci.value=p.code;}}}
  closeModal();toast(`Da dien code: ${byPhone} khop SDT, ${byOrder} theo thu tu`,'ok');
}
function openApply2FA(){
  if(!rows.length){toast('Chua co dong nao!','warn');return;}
  const empty=rows.filter(r=>!r.twofa);
  showModal('Ap 2FA Chung',`
    <div class="text-sm" style="margin-bottom:10px">${rows.length} row tong, ${rows.length-empty.length} da co 2FA, <strong>${empty.length}</strong> dang trong</div>
    <div class="form-group"><label class="lbl">2FA Password</label><input id="apply-2fa-pwd" type="password" placeholder="Nhap password..." style="width:100%" autofocus></div>
    <div class="flex gap-2 items-center mt-2"><input type="checkbox" id="show-2fa-pwd" onchange="document.getElementById('apply-2fa-pwd').type=this.checked?'text':'password'"><label for="show-2fa-pwd">Hien password</label></div>
    <div class="flex gap-2 mt-3"><button class="btn btn-success" onclick="doApply2FA()">Ap dung cho ${empty.length} acc</button><button class="btn btn-ghost" onclick="closeModal()">Huy</button></div>`);
  setTimeout(()=>document.getElementById('apply-2fa-pwd')?.focus(),100);
}
function doApply2FA(){const pwd=document.getElementById('apply-2fa-pwd').value.trim();if(!pwd){toast('Chua nhap password!','error');return;}let count=0;for(const row of rows){if(!row.twofa){row.twofa=pwd;count++;}}closeModal();toast(`Da ap 2FA cho ${count} acc`,'ok');}
async function launchTile(){const base=document.getElementById('base-folder').value;if(!base){toast('Chua chon thu muc goc!','error');return;}toast('Dang mo Telegram...','info');const r=await post('/api/sync/launch-tile',{base_folder:base});if(r.ok)toast(`Dang mo ${r.count} Telegram...`,'info');else toast(r.msg||'Loi','error');}
async function closeAllTabs(){const r=await post('/api/sync/close-all',{});if(r.ok)toast(`Da dong ${r.closed} tab (${r.survivors} con lai)`,'ok');else toast(r.msg||'Loi','error');refreshWindows();}
function updateNaming(radio){document.querySelectorAll('.radio-opt').forEach(el=>{const inp=el.querySelector('input[type=radio][name="naming"]');if(inp)el.classList.toggle('checked',inp.checked)});}
function updateRunMode(){document.querySelectorAll('[name="run-mode"]').forEach(r=>{r.closest('.radio-opt')?.classList.toggle('checked',r.checked)});}
async function scanAccounts(){const base=document.getElementById('base-folder').value;if(!base){toast('Chua chon thu muc goc!','error');return;}const r=await get(`/api/admin/scan?base_folder=${encodeURIComponent(base)}`);adminAccounts=r.accounts||[];renderAccList(adminAccounts);toast(`Tim thay ${adminAccounts.length} acc`,'info');}
function renderAccList(accs){const el=document.getElementById('acc-checkbox-list');if(!accs.length){el.innerHTML='<div class="empty-state">Khong tim thay session nao</div>';return;}el.innerHTML=accs.map(acc=>`<label class="acc-check-item"><input type="checkbox" onchange="toggleAcc('${acc.name}',this.checked)" ${selectedAdminAccs.has(acc.name)?'checked':''}><span title="${escAttr(acc.name)}">${escHtml(acc.name)}</span></label>`).join('');updateSelectedCount();}
function filterAccList(q){const f=adminAccounts.filter(a=>a.name.toLowerCase().includes(q.toLowerCase()));renderAccList(f);}
function toggleAcc(name,checked){if(checked)selectedAdminAccs.add(name);else selectedAdminAccs.delete(name);updateSelectedCount();}
function selectAll(){adminAccounts.forEach(a=>selectedAdminAccs.add(a.name));renderAccList(adminAccounts);}
function selectNone(){selectedAdminAccs.clear();renderAccList(adminAccounts);}
function selectInvert(){adminAccounts.forEach(a=>{if(selectedAdminAccs.has(a.name))selectedAdminAccs.delete(a.name);else selectedAdminAccs.add(a.name)});renderAccList(adminAccounts);}
function updateSelectedCount(){document.getElementById('acc-selected-count').textContent=`${selectedAdminAccs.size} acc duoc chon`;}
function getAdminParams(){return{base_folder:document.getElementById('base-folder').value,selected:Array.from(selectedAdminAccs),mode:document.querySelector('[name="run-mode"]:checked')?.value||'parallel',delay:parseFloat(document.getElementById('run-delay').value)||0.5,max_parallel:parseInt(document.getElementById('run-max').value)||8};}
function checkAdminReady(){if(!document.getElementById('base-folder').value){toast('Chua chon thu muc goc!','error');return false;}if(!selectedAdminAccs.size){toast('Chua chon acc nao!','warn');return false;}return true;}
async function runCreateChannels(){if(!checkAdminReady())return;const r=await post('/api/admin/create-channels',{...getAdminParams(),amount:parseInt(document.getElementById('ch-amount').value)||1,prefix:document.getElementById('ch-prefix').value,about:document.getElementById('ch-about').value,megagroup:document.querySelector('[name="ch-type"]:checked')?.value==='true',delay:parseFloat(document.getElementById('ch-delay').value)||1});toast(r.ok?'Da bat dau tao channel...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runCreatePublic(){if(!checkAdminReady())return;const r=await post('/api/admin/create-public-channels',{...getAdminParams(),amount:parseInt(document.getElementById('pub-amount').value)||1,title:document.getElementById('pub-title').value,about:document.getElementById('pub-about').value,username_prefix:document.getElementById('pub-uname').value,suffix_mode:document.getElementById('pub-suffix').value,photo_path:document.getElementById('pub-photo').value,welcome_msg:document.getElementById('pub-welcome').value,delay:parseFloat(document.getElementById('pub-delay').value)||2});toast(r.ok?'Da bat dau tao kenh public...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runPromote(){if(!checkAdminReady())return;const r=await post('/api/admin/promote',{...getAdminParams(),channels:document.getElementById('prom-channels').value,usernames:document.getElementById('prom-users').value,full_rights:document.getElementById('prom-full').checked});toast(r.ok?'Da bat dau cap admin...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runFolderPromote(){if(!checkAdminReady())return;const r=await post('/api/admin/folder-promote',{...getAdminParams(),folder_name:document.getElementById('fp-folder').value,usernames:document.getElementById('fp-users').value,full_rights:document.getElementById('fp-full').checked});toast(r.ok?'Da bat dau cap admin...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runAutoFolder(){if(!checkAdminReady())return;const r=await post('/api/admin/auto-folder',{...getAdminParams(),folder_name:document.getElementById('af-name').value});toast(r.ok?'Da bat dau auto folder...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runAutoPromote(){if(!checkAdminReady())return;const r=await post('/api/admin/auto-promote',{...getAdminParams(),usernames:document.getElementById('ap-users').value,full_rights:document.getElementById('ap-full').checked});toast(r.ok?'Da bat dau auto-promote...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runConsolidate(){if(!checkAdminReady())return;const r=await post('/api/admin/consolidate',{...getAdminParams(),master_acc:document.getElementById('cons-master').value,folder_name:document.getElementById('cons-folder').value,link_title:document.getElementById('cons-title').value,private_handling:document.getElementById('cons-private').value});toast(r.ok?'Da bat dau don ve acc tong...':(r.detail||'Loi'),r.ok?'info':'error');}
async function runDeleteAccounts(){if(!checkAdminReady())return;const c1=document.getElementById('del-confirm1').checked;const c2=document.getElementById('del-confirm2').checked;if(!c1||!c2){toast('Vui long xac nhan ca 2 checkbox!','error');return;}if(!confirm(`XOA VINH VIEN ${selectedAdminAccs.size} account? KHONG THE UNDO!`))return;const r=await post('/api/admin/delete-accounts',{...getAdminParams(),reason:document.getElementById('del-reason').value});toast(r.ok?`Da bat dau xoa ${selectedAdminAccs.size} account...`:(r.detail||'Loi'),r.ok?'warn':'error');}
async function loadChannelsTxt(){const base=document.getElementById('base-folder').value;if(!base){toast('Chua chon thu muc goc!','error');return;}try{const resp=await fetch(`/api/read-file?path=${encodeURIComponent(base+'\\channels.txt')}`);if(resp.ok){const text=await resp.text();document.getElementById('prom-channels').value=text;toast('Da tai channels.txt','ok');}else toast('Khong tim thay channels.txt','warn');}catch{toast('Loi tai file','error');}}
async function refreshWindows(){const r=await get('/api/sync/windows');updateWindowList(r.windows||[]);}
function updateWindowList(windows){trackedWindows=windows;const el=document.getElementById('sync-windows-list');const count=document.getElementById('sync-count');count.textContent=`${windows.length} tab`;if(!windows.length){el.innerHTML='<div class="empty-state">Chua co tab nao</div>';return;}el.innerHTML=windows.map(w=>`<div class="window-item"><span class="wname">&#x1F4F1; ${escHtml(w.name)}</span><span class="winfo">PID: ${w.pid}</span></div>`).join('');}
function showWindowList(){if(!trackedWindows.length){toast('Khong co tab nao','warn');return;}showModal('Danh Sach Tab',`<pre style="font-size:12px;color:var(--text);line-height:1.6">${escHtml(trackedWindows.map((w,i)=>`${String(i+1).padStart(2,'0')}. ${w.name}  PID:${w.pid}`).join('\n'))}</pre><button class="btn btn-ghost mt-3" onclick="closeModal()">Dong</button>`);}
async function broadcastText(){const text=document.getElementById('sync-text').value;if(!text.trim()){toast('Noi dung trong!','error');return;}const r=await post('/api/sync/broadcast',{text,delay:parseFloat(document.getElementById('sync-delay').value)||0.3,press_enter:document.getElementById('sync-enter').checked});if(r.ok)toast(`Dang gui toi ${r.count} tab...`,'info');else toast(r.msg||'Loi','error');}
async function retileWindows(){const r=await post('/api/sync/retile',{});toast(r.ok?'Da re-tile cua so':(r.msg||'Loi'),r.ok?'ok':'error');}
async function bringToFront(){const r=await post('/api/sync/bring-front',{});toast(r.ok?`Da dua ${r.count} tab len tren`:(r.msg||'Loi'),r.ok?'ok':'error');}
function showModal(title,html){document.getElementById('modal-title').textContent=title;document.getElementById('modal-body').innerHTML=html;document.getElementById('modal-overlay').style.display='block';document.getElementById('modal').style.display='block';}
function closeModal(){document.getElementById('modal-overlay').style.display='none';document.getElementById('modal').style.display='none';}
function toast(msg,type='info'){const icons={ok:'\u2705',error:'\u274C',warn:'\u26A0\uFE0F',info:'\u2139\uFE0F'};const el=document.createElement('div');el.className='toast '+(type==='ok'?'ok':type==='error'?'error':type==='warn'?'warn':'');el.innerHTML=`<span class="toast-icon">${icons[type]||'\u2139\uFE0F'}</span><span class="toast-msg">${escHtml(msg)}</span>`;document.getElementById('toast-container').appendChild(el);setTimeout(()=>{el.style.animation='fadeOut .3s ease forwards';setTimeout(()=>el.remove(),300)},3500);}
function escHtml(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function escAttr(s){return String(s||'').replace(/"/g,'&quot;');}
document.addEventListener('DOMContentLoaded',()=>{
  connectWS();
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
  setInterval(async()=>{const r=await get('/api/tasks');updateTaskBadge(r.count||0);},3000);
});
</script>
</body>
</html>"""


def _load_html() -> str:
    ext = BASE_DIR / "static" / "index.html"
    if ext.exists():
        try:
            return ext.read_text(encoding="utf-8")
        except Exception:
            pass
    return _EMBEDDED_HTML

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
_config: dict = {}
_config_lock = threading.Lock()


def _load_config():
    global _config
    if CONFIG_FILE.exists():
        try:
            _config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            _config = {}


def _save_config():
    with _config_lock:
        try:
            tmp = CONFIG_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(_config, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(CONFIG_FILE)
        except Exception:
            pass


def cfg_get(key, default=None):
    return _config.get(key, default)


def cfg_set(key, value):
    _config[key] = value
    _save_config()


# ══════════════════════════════════════════════════════════
#  LOG SYSTEM (WebSocket broadcast)
# ══════════════════════════════════════════════════════════
LOG_COLORS = {
    "ok": "#00cc66",
    "error": "#ff5555",
    "fresh": "#ffaa44",
    "no_perm": "#ff5555",
    "not_member": "#ff8844",
    "privacy": "#ff8844",
    "invalid": "#ff8844",
    "skip": "#888888",
    "info": "#88ccff",
    "warn": "#ffcc44",
}

log_buffer: deque = deque(maxlen=5000)
_ws_clients: List[WebSocket] = []
_ws_lock = asyncio.Lock()


def _sync_log(level: str, msg: str):
    """Thread-safe log — usable from any thread."""
    entry = {"level": level, "msg": msg,
             "color": LOG_COLORS.get(level, "#88ccff"),
             "ts": time.strftime("%H:%M:%S")}
    log_buffer.append(entry)
    # Schedule broadcast on the main event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(
                lambda e=entry: asyncio.ensure_future(_broadcast_log(e)))
    except Exception:
        pass


async def _broadcast_log(entry: dict):
    dead = []
    async with _ws_lock:
        for ws in _ws_clients:
            try:
                await ws.send_json({"type": "log", "data": entry})
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                _ws_clients.remove(ws)
            except ValueError:
                pass


async def _broadcast(payload: dict):
    dead = []
    async with _ws_lock:
        for ws in _ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                _ws_clients.remove(ws)
            except ValueError:
                pass


log = _sync_log  # shorthand


# ══════════════════════════════════════════════════════════
#  BACKGROUND TASK RUNNER
# ══════════════════════════════════════════════════════════
_bg_tasks: Dict[str, asyncio.Task] = {}
_task_counter = 0


def _submit(name: str, coro) -> str:
    global _task_counter
    _task_counter += 1
    tid = f"{name}#{_task_counter}"

    async def _wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            log("info", f"⏹ Task '{name}' đã hủy")
        except Exception as e:
            import traceback
            log("error", f"💥 Task '{name}' lỗi: {type(e).__name__}: {e}")
            log("error", traceback.format_exc())
        finally:
            _bg_tasks.pop(tid, None)
            asyncio.ensure_future(_broadcast({"type": "task_count",
                                              "data": len(_bg_tasks)}))

    loop = asyncio.get_event_loop()
    task = loop.create_task(_wrapper(), name=tid)
    _bg_tasks[tid] = task
    asyncio.ensure_future(_broadcast({"type": "task_count", "data": len(_bg_tasks)}))
    return tid


def _cancel_all():
    cancelled = 0
    for task in list(_bg_tasks.values()):
        if task.cancel():
            cancelled += 1
    return cancelled


# ══════════════════════════════════════════════════════════
#  TELETHON / OPENTELE HELPERS  (từ admin_channel.py)
# ══════════════════════════════════════════════════════════
try:
    from telethon import TelegramClient as _PlainClient
    from telethon.tl.functions.channels import (
        CreateChannelRequest, EditAdminRequest, InviteToChannelRequest,
        GetParticipantRequest as ChGetParticipantRequest,
        UpdateUsernameRequest, EditPhotoRequest,
    )
    from telethon.tl.functions.messages import (
        EditChatAdminRequest, ExportChatInviteRequest,
        GetDialogFiltersRequest, MigrateChatRequest,
        UpdateDialogFilterRequest,
    )
    from telethon.tl.types import (
        ChatAdminRights, Chat, Channel, ChannelParticipantAdmin,
        ChannelParticipantCreator, InputChatUploadedPhoto,
    )
    from telethon.errors import (
        ChatAdminRequiredError, UserNotParticipantError,
        UserPrivacyRestrictedError, FloodWaitError,
        UserAdminInvalidError, ChatNotModifiedError,
        SessionPasswordNeededError, PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        UsernameInvalidError, UsernameOccupiedError,
        ChannelsAdminPublicTooMuchError,
    )
    try:
        from telethon.errors import FreshChangeAdminsForbiddenError
    except ImportError:
        FreshChangeAdminsForbiddenError = None
    try:
        from telethon.errors import UsernamePurchaseAvailableError
    except ImportError:
        UsernamePurchaseAvailableError = None
    from opentele.api import API, UseCurrentSession
    from opentele.tl import TelegramClient
    TELETHON_OK = True
except ImportError as _e:
    TELETHON_OK = False
    _import_err = str(_e)


def _supported_rights():
    try:
        sig = inspect.signature(ChatAdminRights.__init__)
        return {p for p in sig.parameters if p != "self"}
    except Exception:
        return set()


def make_rights(is_broadcast=False, full=True):
    group_full = dict(change_info=True, delete_messages=True, ban_users=True,
                      invite_users=True, pin_messages=True, add_admins=True,
                      manage_call=True, manage_topics=True, anonymous=False, other=True)
    group_safe = dict(change_info=True, delete_messages=True, ban_users=True,
                      invite_users=True, pin_messages=True, manage_call=True)
    channel_full = dict(change_info=True, post_messages=True, edit_messages=True,
                        delete_messages=True, ban_users=True, invite_users=True,
                        pin_messages=True, add_admins=True, manage_call=True,
                        post_stories=True, edit_stories=True, delete_stories=True, other=True)
    channel_safe = dict(change_info=True, post_messages=True, edit_messages=True,
                        delete_messages=True, ban_users=True, invite_users=True,
                        pin_messages=True, manage_call=True)
    wanted = (channel_full if full else channel_safe) if is_broadcast else (
              group_full if full else group_safe)
    supported = _supported_rights()
    filtered = {k: v for k, v in wanted.items() if k in supported}
    return ChatAdminRights(**filtered)


def random_channel_name(prefix="vip_"):
    return prefix + "".join(random.choices(string.ascii_letters + string.digits, k=8))


def parse_usernames(raw):
    return [u.strip().lstrip("@") for u in raw.replace(",", " ").split() if u.strip()]


def parse_chat_inputs(raw):
    out = []
    for item in raw.replace(",", " ").split():
        item = item.strip()
        if "t.me/" in item:
            item = item.split("t.me/")[-1].split("/")[0]
        if item:
            out.append(item)
    return out


def title_of(ch):
    return getattr(ch, "title", str(ch))


def load_or_create_api(folder: Path):
    api_file = folder / "api.json"
    if api_file.exists():
        try:
            data = json.loads(api_file.read_text(encoding="utf-8"))
            api = API.TelegramDesktop()
            for k, v in data.items():
                if hasattr(api, k):
                    setattr(api, k, v)
            return api
        except Exception:
            pass
    api = API.TelegramDesktop.Generate()
    try:
        data = {}
        for k in ("api_id", "api_hash", "device_model", "system_version",
                  "app_version", "lang_code", "system_lang_code"):
            v = getattr(api, k, None)
            if v is not None:
                data[k] = v
        api_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return api


def detect_sessions(base_folder: str):
    base = Path(base_folder)
    if not base.is_dir():
        return []
    return [(sub.name, str(sub / "_telethon"))
            for sub in sorted(base.iterdir())
            if sub.is_dir() and (sub / "_telethon.session").exists()]


def load_accounts_txt(path="accounts.txt"):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 3:
                try:
                    out.append((int(parts[0]), parts[1], ":".join(parts[2:])))
                except ValueError:
                    continue
    return out


async def is_member(client, channel, user):
    try:
        if isinstance(channel, Channel):
            try:
                await client(ChGetParticipantRequest(channel, user))
                return True
            except Exception:
                return False
        elif isinstance(channel, Chat):
            full = await client.get_participants(channel)
            user_id = user.id if hasattr(user, "id") else user
            return any(p.id == user_id for p in full)
        return False
    except Exception:
        return False


async def is_admin(client, channel, user):
    try:
        if isinstance(channel, Channel):
            p = await client(ChGetParticipantRequest(channel, user))
            return isinstance(p.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except Exception:
        pass
    return False


async def promote_one(client, channel, username, full=True):
    title = title_of(channel)
    log("info", f"     → @{username}: resolve user...")
    try:
        user = await client.get_entity(username)
    except Exception as e:
        log("error", f"  ❌ @{username}: không tìm được user — {e}")
        return "error"
    try:
        if isinstance(channel, Chat):
            log("info", f"     → @{username}: chat cũ, thử migrate...")
            try:
                await client(MigrateChatRequest(chat_id=channel.id))
                channel = await client.get_entity(channel.id)
            except Exception:
                pass
            try:
                await client(EditChatAdminRequest(chat_id=channel.id, user_id=user, is_admin=True))
                log("ok", f"  ✅ @{username} → {title}")
                return "ok"
            except Exception as e:
                log("error", f"  ❌ @{username}: {e}")
                return "error"
        is_broadcast = getattr(channel, "broadcast", False)
        member = await is_member(client, channel, user)
        if not member:
            try:
                await client(InviteToChannelRequest(channel, [user]))
                log("info", f"     ✓ Đã mời")
            except UserPrivacyRestrictedError:
                log("privacy", f"  🔒 @{username}: privacy chặn")
                return "privacy"
            except Exception as e:
                log("not_member", f"  ❌ @{username}: chưa vào — {e}")
                return "not_member"
        if await is_admin(client, channel, user):
            log("skip", f"  ⏭️  @{username}: đã là admin")
            return "skip"
        rights = make_rights(is_broadcast=is_broadcast, full=full)
        try:
            await client(EditAdminRequest(channel=channel, user_id=user, admin_rights=rights, rank=""))
            log("ok", f"  ✅ @{username} → {title}")
            return "ok"
        except ChatAdminRequiredError:
            log("no_perm", f"  🚫 @{username}: không có quyền")
            return "no_perm"
        except UserAdminInvalidError:
            log("invalid", f"  ⛔ @{username}: không thể cấp")
            return "invalid"
        except UserNotParticipantError:
            log("not_member", f"  ❌ @{username}: chưa là member")
            return "not_member"
        except FloodWaitError as e:
            log("error", f"  ⏳ Flood {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return "error"
        except ChatNotModifiedError:
            log("skip", f"  ⏭️  @{username}: không thay đổi")
            return "skip"
        except Exception as e:
            if FreshChangeAdminsForbiddenError and isinstance(e, FreshChangeAdminsForbiddenError):
                log("fresh", f"  ⏳ @{username}: account mới")
                return "fresh"
            log("error", f"  💥 @{username}: {type(e).__name__} — {e}")
            return "error"
    except Exception as e:
        log("error", f"  💥 @{username}: {type(e).__name__} — {e}")
        return "error"


async def get_folder_channels(client, folder_name=None):
    res = await client(GetDialogFiltersRequest())
    filters = getattr(res, "filters", res)
    folders = {}
    for f in filters:
        title = getattr(f, "title", None)
        if title is None:
            continue
        title_text = getattr(title, "text", title)
        channels = []
        for peer in (getattr(f, "include_peers", []) or []):
            try:
                channels.append(await client.get_entity(peer))
            except Exception:
                pass
        folders[title_text] = channels
    return folders if folder_name is None else folders.get(folder_name, [])


async def get_admin_channels(client):
    me = await client.get_me()
    log("info", f"     → Quét dialogs của @{me.username or me.first_name}...")
    admin_channels = []
    total = 0
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        if not isinstance(ent, Channel):
            continue
        total += 1
        try:
            p = await client(ChGetParticipantRequest(ent, me))
            if isinstance(p.participant, (ChannelParticipantCreator, ChannelParticipantAdmin)):
                admin_channels.append(ent)
        except Exception:
            pass
    log("info", f"     ✓ Quét {total} channel, đang admin {len(admin_channels)}")
    return admin_channels


async def create_or_update_folder(client, folder_name, channels):
    log("info", "     → Lấy danh sách filter hiện có...")
    res = await client(GetDialogFiltersRequest())
    existing = getattr(res, "filters", res)
    target_id = None
    used_ids = set()
    for f in existing:
        fid = getattr(f, "id", None)
        if fid is not None:
            used_ids.add(fid)
        title_obj = getattr(f, "title", None)
        if title_obj is None:
            continue
        title_text = getattr(title_obj, "text", title_obj)
        if title_text == folder_name:
            target_id = fid
    if target_id is None:
        for cand in range(2, 256):
            if cand not in used_ids:
                target_id = cand
                break
    include_peers = []
    for ch in channels:
        try:
            include_peers.append(await client.get_input_entity(ch))
        except Exception:
            pass
    try:
        from telethon.tl.types import TextWithEntities
        title_obj = TextWithEntities(text=folder_name, entities=[])
    except ImportError:
        title_obj = folder_name
    from telethon.tl.types import DialogFilter
    sig = inspect.signature(DialogFilter.__init__)
    kwargs = dict(id=target_id, title=title_obj, pinned_peers=[],
                  include_peers=include_peers, exclude_peers=[])
    for k in ("contacts", "non_contacts", "groups", "broadcasts",
              "bots", "exclude_muted", "exclude_read", "exclude_archived"):
        if k in sig.parameters:
            kwargs[k] = False
    if "emoticon" in sig.parameters:
        kwargs["emoticon"] = "📁"
    flt = DialogFilter(**kwargs)
    await client(UpdateDialogFilterRequest(id=target_id, filter=flt))
    log("ok", f"     ✅ Folder '{folder_name}' (id={target_id}) — {len(include_peers)} kênh")
    return target_id


async def export_chatlist_link(client, folder_id, channels, link_title="My Folder",
                               private_handling="skip"):
    try:
        from telethon.tl.functions.chatlists import ExportChatlistInviteRequest
        from telethon.tl.types import InputChatlistDialogFilter
    except ImportError:
        log("error", "❌ Telethon < 1.29 — không hỗ trợ chatlist")
        return None
    valid_peers = []
    for ch in channels:
        try:
            peer = await client.get_input_entity(ch)
            valid_peers.append(peer)
        except Exception as e:
            log("error", f"     ⚠️ Bỏ qua {title_of(ch)}: {e}")
    if not valid_peers:
        log("error", "❌ Không peer nào hợp lệ")
        return None
    try:
        result = await client(ExportChatlistInviteRequest(
            chatlist=InputChatlistDialogFilter(filter_id=folder_id),
            title=link_title, peers=valid_peers,
        ))
        url = result.invite.url
        log("ok", f"     ✅ {url}")
        return url
    except Exception as e:
        log("error", f"❌ Export lỗi: {type(e).__name__} — {e}")
        return None


async def join_chatlist_link(client, url):
    try:
        from telethon.tl.functions.chatlists import (
            CheckChatlistInviteRequest, JoinChatlistInviteRequest,
        )
    except ImportError:
        log("error", "❌ Telethon < 1.29")
        return False, 0
    m = re.search(r"addlist[/=]([A-Za-z0-9_\-]+)", url)
    if not m:
        log("error", f"❌ Không parse slug: {url}")
        return False, 0
    slug = m.group(1)
    try:
        info = await client(CheckChatlistInviteRequest(slug=slug))
        peers = getattr(info, "peers", []) or []
        already = getattr(info, "already_peers", []) or []
        log("info", f"     ℹ️  {len(peers)} kênh mới (đã có {len(already)})")
        if not peers:
            return True, 0
        await client(JoinChatlistInviteRequest(slug=slug, peers=peers))
        log("ok", f"     ✅ Đã join {len(peers)} kênh")
        return True, len(peers)
    except Exception as e:
        log("error", f"❌ Join lỗi: {type(e).__name__} — {e}")
        return False, 0


def _gen_username_suffix(mode):
    chars = string.ascii_lowercase + string.digits
    if mode == "random_1":
        return "".join(random.choices(chars, k=1))
    elif mode == "random_2":
        return "".join(random.choices(chars, k=2))
    elif mode == "random_3":
        return "".join(random.choices(chars, k=3))
    n = random.randint(5, 8)
    s = "".join(random.choices(chars, k=n))
    if random.random() < 0.3 and len(s) > 3:
        pos = random.randint(1, len(s) - 1)
        s = s[:pos] + "_" + s[pos:]
    return s


async def create_public_channel(client, title, about, username_prefix,
                                suffix_mode="random_3", photo_path=None,
                                welcome_msg=None, megagroup=False, max_retries=10):
    log("info", f"  → Tạo channel '{title}'...")
    try:
        result = await client(CreateChannelRequest(title=title, about=about, megagroup=megagroup))
        ch = result.chats[0]
        log("info", f"     ✓ id={ch.id}")
    except FloodWaitError as e:
        log("error", f"⏳ Flood {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return None
    except Exception as e:
        log("error", f"❌ {type(e).__name__}: {e}")
        return None
    final_username = None
    base = re.sub(r"[^a-zA-Z0-9_]", "", username_prefix)
    if base:
        for _ in range(max_retries):
            suffix = _gen_username_suffix(suffix_mode)
            candidate = f"{base}{suffix}"[:32]
            try:
                ok = await client(UpdateUsernameRequest(channel=ch, username=candidate))
                if ok:
                    final_username = candidate
                    log("ok", f"     ✅ Username: @{candidate}")
                    break
            except (UsernameOccupiedError, UsernameInvalidError):
                continue
            except Exception:
                if UsernamePurchaseAvailableError and isinstance(Exception, UsernamePurchaseAvailableError):
                    continue
                if ChannelsAdminPublicTooMuchError and isinstance(Exception, ChannelsAdminPublicTooMuchError):
                    break
                continue
            await asyncio.sleep(0.3)
    if photo_path and Path(photo_path).exists():
        try:
            file = await client.upload_file(photo_path)
            await client(EditPhotoRequest(channel=ch, photo=InputChatUploadedPhoto(file=file)))
            log("ok", "     ✅ Đã set ảnh")
        except Exception as e:
            log("warn", f"⚠️ Lỗi set ảnh: {e}")
    if welcome_msg:
        try:
            await client.send_message(ch, welcome_msg)
            log("ok", "     ✅ Đã gửi welcome")
        except Exception as e:
            log("warn", f"⚠️ Lỗi gửi msg: {e}")
    invite_link = None
    try:
        invite = await client(ExportChatInviteRequest(ch))
        invite_link = invite.link
    except Exception:
        pass
    return {
        "channel_id": ch.id,
        "title": title,
        "username": final_username,
        "public_link": f"https://t.me/{final_username}" if final_username else None,
        "invite_link": invite_link,
    }


async def delete_account_api(client, reason=""):
    try:
        from telethon.tl.functions.account import DeleteAccountRequest
    except ImportError:
        log("error", "❌ Telethon không hỗ trợ DeleteAccountRequest")
        return False
    try:
        me = await client.get_me()
        ident = f"@{me.username}" if me.username else f"id={me.id}"
        log("info", f"⚠️ Sẽ xóa: {me.first_name or ''} {ident}")
    except Exception as e:
        log("error", f"❌ Không lấy được info: {e}")
        return False
    try:
        sig = inspect.signature(DeleteAccountRequest.__init__)
        if "reason" in sig.parameters:
            await client(DeleteAccountRequest(reason=reason))
        else:
            await client(DeleteAccountRequest())
        log("ok", f"✅ Đã xóa account")
        return True
    except Exception as e:
        log("error", f"❌ Xóa lỗi: {type(e).__name__} — {e}")
        return False


def sanitize_folder_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or ""


# ══════════════════════════════════════════════════════════
#  LOGIN SESSION STATE
# ══════════════════════════════════════════════════════════
class LoginRow:
    def __init__(self, row_id: str):
        self.id = row_id
        self.folder = ""
        self.note = ""
        self.phone = ""
        self.code = ""
        self.twofa = ""
        self.client = None
        self.phone_code_hash = None
        self.current_folder: Optional[Path] = None
        self.status = "ready"
        self.status_text = "⏸ Sẵn sàng"

    def to_dict(self):
        return {
            "id": self.id,
            "folder": self.folder,
            "note": self.note,
            "phone": self.phone,
            "code": self.code,
            "twofa": "",  # never send password back
            "status": self.status,
            "status_text": self.status_text,
        }

    async def set_status(self, status: str, text: str):
        self.status = status
        self.status_text = text
        await _broadcast({"type": "row_status",
                          "data": {"id": self.id, "status": status, "text": text}})


login_rows: Dict[str, LoginRow] = {}


def get_or_create_row(row_id: str) -> LoginRow:
    if row_id not in login_rows:
        login_rows[row_id] = LoginRow(row_id)
    return login_rows[row_id]


# ══════════════════════════════════════════════════════════
#  WINDOWS API HELPERS
# ══════════════════════════════════════════════════════════
tracked_windows: List[tuple] = []  # (hwnd, pid, folder_name)


def _get_work_area():
    if not IS_WINDOWS:
        return (0, 0, 1920, 1040)
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        if ok:
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    return (0, 0, 1920, 1040)


def _set_window_pos(hwnd, x, y, w, h):
    if not IS_WINDOWS:
        return
    import ctypes
    flags = 0x0004 | 0x0010 | 0x0040
    ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, flags)


def _get_window_pid(hwnd):
    if not IS_WINDOWS:
        return 0
    import ctypes
    from ctypes import wintypes
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_alive_windows():
    if not IS_WINDOWS:
        return tracked_windows
    import ctypes
    alive = [(h, p, n) for h, p, n in tracked_windows
             if ctypes.windll.user32.IsWindow(h)]
    tracked_windows.clear()
    tracked_windows.extend(alive)
    return alive


# ══════════════════════════════════════════════════════════
#  PER-ACCOUNT RUNNER
# ══════════════════════════════════════════════════════════
async def _connect_account(folder_name: str, base_folder: str):
    """Connect a Telethon client for admin operations."""
    folder = Path(base_folder) / folder_name
    sess_file = str(folder / "_telethon")
    api = load_or_create_api(folder)
    client = TelegramClient(sess_file, api=api)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(f"Account {folder_name} chưa đăng nhập")
    return client


async def _run_per_account(
    base_folder: str,
    selected: List[str],
    op_coro_factory,
    mode: str = "parallel",
    delay: float = 0.5,
    max_parallel: int = 8,
):
    """Run an operation across multiple accounts."""
    sem = asyncio.Semaphore(max_parallel if mode == "parallel" else 1)
    stats = {"ok": 0, "skip": 0, "error": 0}
    total = len(selected)

    async def _do_one(i, folder_name):
        async with sem:
            log("info", f"\n[{i}/{total}] 🔌 Kết nối {folder_name}...")
            try:
                client = await _connect_account(folder_name, base_folder)
                try:
                    result = await op_coro_factory(client, folder_name)
                    stats[result if result in stats else "ok"] += 1
                finally:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
            except Exception as e:
                log("error", f"  ❌ {folder_name}: {e}")
                stats["error"] += 1
            if delay > 0 and mode == "serial":
                await asyncio.sleep(delay)

    if mode == "parallel":
        tasks = [_do_one(i + 1, name) for i, name in enumerate(selected)]
        await asyncio.gather(*tasks)
    else:
        for i, name in enumerate(selected):
            await _do_one(i + 1, name)
            if delay > 0:
                await asyncio.sleep(delay)

    log("ok", f"✅ Xong: {stats}")
    return stats


# ══════════════════════════════════════════════════════════
#  FASTAPI APP
# ══════════════════════════════════════════════════════════
@asynccontextmanager
async def _lifespan(app_instance: FastAPI):
    """Startup / shutdown với lifespan (thay on_event deprecated)."""
    _load_config()
    if not TELETHON_OK:
        log("error", f"⚠️ Telethon/opentele chưa cài đầy đủ")
        log("info", "👉 Chạy: pip install telethon opentele pygetwindow pywin32")
    else:
        log("ok", "✅ Multi-Telegram Tool v8 đã sẵn sàng!")
    log("info", "🌐 Giao diện: http://localhost:8899")
    yield  # ← app chạy ở đây
    # Shutdown: không cần dọn dẹp đặc biệt


app = FastAPI(title="Multi-Telegram Tool v8", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def index():
    """Serve giao diện HTML — ưu tiên static/index.html, fallback sang bản nhúng."""
    return HTMLResponse(_load_html())


# ── WebSocket log stream ──
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    async with _ws_lock:
        _ws_clients.append(ws)
    # Send buffered logs
    for entry in list(log_buffer):
        try:
            await ws.send_json({"type": "log", "data": entry})
        except Exception:
            break
    # Send current state
    try:
        await ws.send_json({"type": "task_count", "data": len(_bg_tasks)})
        await ws.send_json({"type": "config", "data": _config})
        rows_data = [r.to_dict() for r in login_rows.values()]
        await ws.send_json({"type": "login_rows", "data": rows_data})
        windows = [{"hwnd": h, "pid": p, "name": n} for h, p, n in tracked_windows]
        await ws.send_json({"type": "windows", "data": windows})
    except Exception:
        pass
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        pass
    finally:
        async with _ws_lock:
            try:
                _ws_clients.remove(ws)
            except ValueError:
                pass


# ══════════════════════════════════════════════════════════
#  CONFIG API
# ══════════════════════════════════════════════════════════
@app.get("/api/config")
async def api_get_config():
    return JSONResponse(_config)


@app.post("/api/config")
async def api_set_config(request: Request):
    data = await request.json()
    _config.update(data)
    _save_config()
    return {"ok": True}


@app.post("/api/browse-folder")
async def api_browse_folder():
    """Open native folder picker dialog (Windows only)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        path = filedialog.askdirectory(title="Chọn thư mục")
        root.destroy()
        return {"path": path or ""}
    except Exception as e:
        return {"path": "", "error": str(e)}


@app.post("/api/browse-file")
async def api_browse_file(request: Request):
    data = await request.json()
    filetypes = data.get("filetypes", [("All", "*.*")])
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        path = filedialog.askopenfilename(title="Chọn file", filetypes=filetypes)
        root.destroy()
        return {"path": path or ""}
    except Exception as e:
        return {"path": "", "error": str(e)}


# ══════════════════════════════════════════════════════════
#  TASKS API
# ══════════════════════════════════════════════════════════
@app.get("/api/tasks")
async def api_tasks():
    return {"count": len(_bg_tasks), "tasks": list(_bg_tasks.keys())}


@app.post("/api/tasks/cancel-all")
async def api_cancel_all():
    n = _cancel_all()
    log("info", f"⏹ Đã yêu cầu hủy {n} task")
    return {"cancelled": n}


@app.get("/api/logs")
async def api_logs():
    return {"logs": list(log_buffer)}


@app.post("/api/logs/clear")
async def api_logs_clear():
    log_buffer.clear()
    await _broadcast({"type": "log_clear"})
    return {"ok": True}


# ══════════════════════════════════════════════════════════
#  LOGIN API
# ══════════════════════════════════════════════════════════
@app.get("/api/login/rows")
async def api_login_rows():
    return [r.to_dict() for r in login_rows.values()]


@app.post("/api/login/rows/sync")
async def api_login_rows_sync(request: Request):
    """Sync rows from frontend (create/update)."""
    data = await request.json()
    rows_data = data.get("rows", [])
    for rd in rows_data:
        row = get_or_create_row(rd["id"])
        row.folder = rd.get("folder", row.folder)
        row.note = rd.get("note", row.note)
        row.phone = rd.get("phone", row.phone)
        row.code = rd.get("code", row.code)
        if rd.get("twofa"):
            row.twofa = rd["twofa"]
    # Remove rows not in the list
    ids = {rd["id"] for rd in rows_data}
    to_del = [k for k in login_rows if k not in ids]
    for k in to_del:
        row = login_rows.pop(k)
        if row.client:
            try:
                await row.client.disconnect()
            except Exception:
                pass
    return {"ok": True}


@app.post("/api/login/send-code/{row_id}")
async def api_send_code(row_id: str, request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    phone = data.get("phone", "")
    folder_name = data.get("folder", "") or f"acc_{row_id}"

    if not base:
        return JSONResponse({"ok": False, "msg": "Chưa chọn thư mục gốc"}, status_code=400)
    if not phone:
        return JSONResponse({"ok": False, "msg": "Chưa nhập SĐT"}, status_code=400)

    row = get_or_create_row(row_id)
    row.phone = phone
    row.folder = folder_name

    async def _do():
        await row.set_status("sending", "⏳ Đang gửi mã...")
        folder = Path(base) / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        row.current_folder = folder
        try:
            api = load_or_create_api(folder)
            row.client = TelegramClient(str(folder / "_telethon"), api=api)
            await row.client.connect()
            if await row.client.is_user_authorized():
                await row.set_status("code_sent", "✅ Session sẵn sàng → Đăng nhập ngay")
                log("ok", f"[{folder_name}] Session sẵn")
                return
            sent = await row.client.send_code_request(phone)
            row.phone_code_hash = sent.phone_code_hash
            await row.set_status("code_sent", "📩 Đã gửi mã → nhập Code rồi nhấn Đăng nhập")
            log("ok", f"[{folder_name}] Đã gửi mã đến {phone}")
        except FloodWaitError as e:
            await row.set_status("error", f"❌ Flood {e.seconds}s")
            log("error", f"[{folder_name}] Flood {e.seconds}s")
        except PhoneNumberInvalidError:
            await row.set_status("error", "❌ SĐT không hợp lệ")
        except Exception as e:
            await row.set_status("error", f"❌ {str(e)[:60]}")
            log("error", f"[{folder_name}] {e}")

    _submit(f"send_code_{row_id}", _do())
    return {"ok": True}


@app.post("/api/login/sign-in/{row_id}")
async def api_sign_in(row_id: str, request: Request):
    data = await request.json()
    code = data.get("code", "")
    twofa = data.get("twofa", "")
    naming_mode = data.get("naming_mode", "username")
    prefix = data.get("prefix", "acc")
    portable_src = data.get("portable_src", "")
    base_folder = data.get("base_folder", cfg_get("base_folder", ""))

    if not code:
        return JSONResponse({"ok": False, "msg": "Chưa nhập code"}, status_code=400)

    row = login_rows.get(row_id)
    if not row or not row.client:
        return JSONResponse({"ok": False, "msg": "Chưa gửi mã. Bấm 'Gửi mã' trước."}, status_code=400)

    row.code = code
    if twofa:
        row.twofa = twofa

    async def _do():
        await row.set_status("logging_in", "⏳ Đang đăng nhập...")
        try:
            await row.client.sign_in(phone=row.phone, code=code,
                                     phone_code_hash=row.phone_code_hash)
        except SessionPasswordNeededError:
            if not row.twofa:
                await row.set_status("need_2fa", "⚠ Acc bật 2FA — nhập password rồi bấm lại")
                return
            try:
                await row.client.sign_in(password=row.twofa)
            except Exception as e:
                await row.set_status("error", f"❌ 2FA sai: {str(e)[:40]}")
                return
        except PhoneCodeInvalidError:
            await row.set_status("error", "❌ Code sai")
            return
        except Exception as e:
            await row.set_status("error", f"❌ {str(e)[:60]}")
            return
        # Export tdata
        await row.set_status("logging_in", "💾 Tạo tdata...")
        me = None
        try:
            tdata = row.current_folder / "tdata"
            if tdata.exists():
                shutil.rmtree(tdata, ignore_errors=True)
            tdesk = await row.client.ToTDesktop(flag=UseCurrentSession)
            tdesk.SaveTData(str(tdata))
            me = await row.client.get_me()
        except Exception as e:
            await row.set_status("warn", f"⚠ Login OK nhưng tdata lỗi: {str(e)[:50]}")
        finally:
            try:
                await row.client.disconnect()
            except Exception:
                pass
        if me is None:
            return
        # Rename folder
        old = row.current_folder
        if naming_mode == "username":
            target = me.username or me.first_name or row.folder
        elif naming_mode == "firstname":
            target = me.first_name or me.username or row.folder
        elif naming_mode == "prefix":
            target = f"{prefix}_{row_id}"
        else:
            target = old.name
        target = sanitize_folder_name(target) or old.name
        if target != old.name:
            new = old.parent / target
            cnt = 1
            while new.exists():
                new = old.parent / f"{target}_{cnt}"
                cnt += 1
            try:
                old.rename(new)
                row.current_folder = new
                row.folder = new.name
                await _broadcast({"type": "row_folder",
                                  "data": {"id": row_id, "folder": new.name}})
            except Exception:
                pass
        # Copy portable
        if portable_src and os.path.isdir(portable_src):
            dest = row.current_folder
            for item in os.listdir(portable_src):
                if item.lower() == "tdata":
                    continue
                s = os.path.join(portable_src, item)
                d = os.path.join(str(dest), item)
                try:
                    if os.path.isdir(s) and not os.path.exists(d):
                        shutil.copytree(s, d)
                    elif os.path.isfile(s) and not os.path.exists(d):
                        shutil.copy2(s, d)
                except Exception:
                    pass
        uname = f"@{me.username}" if me.username else "(no @)"
        await row.set_status("done", f"✅ {me.first_name or ''} {uname} → {row.current_folder.name}")
        log("ok", f"✅ {me.first_name or ''} {uname} đăng nhập thành công")

    _submit(f"sign_in_{row_id}", _do())
    return {"ok": True}


@app.post("/api/login/send-all")
async def api_send_all(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    rows_data = data.get("rows", [])
    count = 0
    valid_rows = []
    for rd in rows_data:
        phone = rd.get("phone", "").strip()
        if not phone:
            continue
        row_id = rd["id"]
        row = get_or_create_row(row_id)
        row.phone = phone
        row.folder = rd.get("folder", "") or f"acc_{row_id}"
        valid_rows.append((row_id, phone, row.folder))
        count += 1

    async def _bulk_send():
        for i, (row_id, phone, folder_name) in enumerate(valid_rows):
            if i > 0:
                await asyncio.sleep(0.5)
            await _do_send_code(row_id, base, phone, folder_name)

    if valid_rows:
        _submit("send_all", _bulk_send())
    return {"ok": True, "count": count}


async def _do_send_code(row_id, base, phone, folder_name):
    row = login_rows.get(row_id)
    if not row:
        return
    await row.set_status("sending", "⏳ Đang gửi mã...")
    folder = Path(base) / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    row.current_folder = folder
    try:
        api_obj = load_or_create_api(folder)
        row.client = TelegramClient(str(folder / "_telethon"), api=api_obj)
        await row.client.connect()
        if await row.client.is_user_authorized():
            await row.set_status("code_sent", "✅ Session sẵn")
            return
        sent = await row.client.send_code_request(phone)
        row.phone_code_hash = sent.phone_code_hash
        await row.set_status("code_sent", "📩 Đã gửi mã")
    except Exception as e:
        await row.set_status("error", f"❌ {str(e)[:50]}")


# ══════════════════════════════════════════════════════════
#  ADMIN API
# ══════════════════════════════════════════════════════════
@app.get("/api/admin/scan")
async def api_admin_scan(base_folder: str = ""):
    bf = base_folder or cfg_get("base_folder", "")
    if not bf:
        return {"accounts": []}
    sessions = detect_sessions(bf)
    return {"accounts": [{"name": name, "path": path} for name, path in sessions]}


@app.post("/api/admin/create-channels")
async def api_create_channels(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    amount = int(data.get("amount", 1))
    prefix = data.get("prefix", "vip_")
    about = data.get("about", "")
    megagroup = data.get("megagroup", False)
    delay = float(data.get("delay", 1.0))

    async def _task():
        log("info", f"▶ Tạo channel: {len(selected)} acc × {amount} kênh")
        all_links = []
        for folder_name in selected:
            log("info", f"\n📌 {folder_name}")
            try:
                client = await _connect_account(folder_name, base)
                links = []
                try:
                    for i in range(amount):
                        name = random_channel_name(prefix)
                        log("info", f"  → [{i+1}/{amount}] Tạo '{name}'...")
                        try:
                            result = await client(CreateChannelRequest(
                                title=name, about=about, megagroup=megagroup))
                            ch = result.chats[0]
                            invite = await client(ExportChatInviteRequest(ch))
                            link = invite.link
                            links.append(link)
                            log("ok", f"  ✅ {name} → {link}")
                        except FloodWaitError as e:
                            log("error", f"  ⏳ Flood {e.seconds}s")
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            log("error", f"  ❌ {e}")
                        if i < amount - 1:
                            await asyncio.sleep(delay)
                finally:
                    await client.disconnect()
                all_links.extend(links)
                out = Path(base) / "channels.txt"
                with open(out, "a", encoding="utf-8") as f:
                    f.write("\n".join(links) + "\n")
            except Exception as e:
                log("error", f"❌ {folder_name}: {e}")
        log("ok", f"✅ Tổng: {len(all_links)} kênh")

    _submit("create_channels", _task())
    return {"ok": True}


@app.post("/api/admin/create-public-channels")
async def api_create_public_channels(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    amount = int(data.get("amount", 1))
    title_template = data.get("title", "Kênh {n}")
    about = data.get("about", "")
    username_prefix = data.get("username_prefix", "channel")
    suffix_mode = data.get("suffix_mode", "random_3")
    photo_path = data.get("photo_path", "")
    welcome_msg = data.get("welcome_msg", "")
    megagroup = data.get("megagroup", False)
    delay = float(data.get("delay", 2.0))

    async def _task():
        log("info", f"▶ Tạo kênh public: {len(selected)} acc × {amount} kênh")
        all_results = []
        for folder_name in selected:
            log("info", f"\n📌 {folder_name}")
            try:
                client = await _connect_account(folder_name, base)
                try:
                    for i in range(amount):
                        actual_title = title_template.replace("{n}", str(i+1)).replace("{i}", str(i+1))
                        log("info", f"\n  📣 [{i+1}/{amount}] {actual_title}")
                        result = await create_public_channel(
                            client, actual_title, about, username_prefix,
                            suffix_mode=suffix_mode, photo_path=photo_path or None,
                            welcome_msg=welcome_msg or None, megagroup=megagroup)
                        if result:
                            all_results.append(result)
                            link = result.get("public_link") or result.get("invite_link", "")
                            out = Path(base) / "public_channels.txt"
                            with open(out, "a", encoding="utf-8") as f:
                                f.write(link + "\n")
                        if i < amount - 1:
                            await asyncio.sleep(delay)
                finally:
                    await client.disconnect()
            except Exception as e:
                log("error", f"❌ {folder_name}: {e}")
        log("ok", f"✅ Tổng: {len(all_results)} kênh public")

    _submit("create_public_channels", _task())
    return {"ok": True}


@app.post("/api/admin/promote")
async def api_promote(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    channels_raw = data.get("channels", "")
    usernames_raw = data.get("usernames", "")
    full_rights = data.get("full_rights", True)
    delay = float(data.get("delay", 0.5))
    mode = data.get("mode", "parallel")
    max_parallel = int(data.get("max_parallel", 8))

    async def _task():
        channels_list = parse_chat_inputs(channels_raw)
        usernames_list = parse_usernames(usernames_raw)
        log("info", f"▶ Cấp admin: {len(selected)} acc, {len(channels_list)} kênh, "
                    f"{len(usernames_list)} user")
        stats = {"ok": 0, "skip": 0, "error": 0, "no_perm": 0,
                 "not_member": 0, "privacy": 0, "invalid": 0, "fresh": 0}

        async def _op(client, folder_name):
            channels = []
            for c in channels_list:
                try:
                    channels.append(await client.get_entity(c))
                except Exception as e:
                    log("error", f"  ❌ Không resolve {c}: {e}")
            for ci, ch in enumerate(channels, 1):
                log("info", f"  📣 [{ci}/{len(channels)}] {title_of(ch)}")
                for u in usernames_list:
                    res = await promote_one(client, ch, u, full=full_rights)
                    stats[res] = stats.get(res, 0) + 1
                    await asyncio.sleep(delay)
            return "ok"

        sem = asyncio.Semaphore(max_parallel if mode == "parallel" else 1)

        async def _do_one(folder_name):
            async with sem:
                try:
                    client = await _connect_account(folder_name, base)
                    try:
                        await _op(client, folder_name)
                    finally:
                        await client.disconnect()
                except Exception as e:
                    log("error", f"❌ {folder_name}: {e}")

        if mode == "parallel":
            await asyncio.gather(*[_do_one(n) for n in selected])
        else:
            for n in selected:
                await _do_one(n)
        log("ok", f"✅ Kết quả: {stats}")

    _submit("promote", _task())
    return {"ok": True}


@app.post("/api/admin/folder-promote")
async def api_folder_promote(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    folder_name = data.get("folder_name", "")
    usernames_raw = data.get("usernames", "")
    full_rights = data.get("full_rights", True)
    delay = float(data.get("delay", 0.5))

    async def _task():
        usernames_list = parse_usernames(usernames_raw)
        log("info", f"▶ Cấp admin theo Folder '{folder_name}': {len(selected)} acc")

        async def _op(client, folder_nm):
            channels = await get_folder_channels(client, folder_name)
            log("info", f"  📂 {len(channels)} kênh trong folder '{folder_name}'")
            for ch in channels:
                for u in usernames_list:
                    await promote_one(client, ch, u, full=full_rights)
                    await asyncio.sleep(delay)
            return "ok"

        await _run_per_account(base, selected, _op)

    _submit("folder_promote", _task())
    return {"ok": True}


@app.post("/api/admin/auto-folder")
async def api_auto_folder(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    folder_name = data.get("folder_name", "Admin Channels")

    async def _task():
        log("info", f"▶ Auto Folder '{folder_name}': {len(selected)} acc")

        async def _op(client, folder_nm):
            channels = await get_admin_channels(client)
            log("info", f"  📂 {len(channels)} kênh admin")
            await create_or_update_folder(client, folder_name, channels)
            return "ok"

        await _run_per_account(base, selected, _op)

    _submit("auto_folder", _task())
    return {"ok": True}


@app.post("/api/admin/auto-promote")
async def api_auto_promote(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    usernames_raw = data.get("usernames", "")
    full_rights = data.get("full_rights", True)
    delay = float(data.get("delay", 0.5))

    async def _task():
        usernames_list = parse_usernames(usernames_raw)
        log("info", f"▶ Auto-promote {len(usernames_list)} user vào {len(selected)} acc")

        async def _op(client, folder_name):
            channels = await get_admin_channels(client)
            log("info", f"  📂 {len(channels)} kênh admin")
            for ch in channels:
                for u in usernames_list:
                    await promote_one(client, ch, u, full=full_rights)
                    await asyncio.sleep(delay)
            return "ok"

        await _run_per_account(base, selected, _op)

    _submit("auto_promote", _task())
    return {"ok": True}


@app.post("/api/admin/consolidate")
async def api_consolidate(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    master_acc = data.get("master_acc", "")
    folder_name = data.get("folder_name", "Master")
    link_title = data.get("link_title", "My Folder")
    private_handling = data.get("private_handling", "skip")

    async def _task():
        log("info", f"▶ Dồn về acc tổng '{master_acc}': {len(selected)} acc")
        chatlist_links = []

        async def _op(client, folder_nm):
            channels = await get_admin_channels(client)
            log("info", f"  📂 {len(channels)} kênh admin")
            fid = await create_or_update_folder(client, folder_name, channels)
            url = await export_chatlist_link(client, fid, channels,
                                            link_title=link_title,
                                            private_handling=private_handling)
            if url:
                chatlist_links.append(url)
            return "ok"

        await _run_per_account(base, selected, _op)

        if chatlist_links and master_acc:
            log("info", f"\n▶ Acc tổng '{master_acc}' join {len(chatlist_links)} chatlist...")
            try:
                client = await _connect_account(master_acc, base)
                try:
                    for url in chatlist_links:
                        ok, n = await join_chatlist_link(client, url)
                        log("ok" if ok else "error",
                            f"  {'✅' if ok else '❌'} {url} — {n} kênh")
                        await asyncio.sleep(1.0)
                finally:
                    await client.disconnect()
            except Exception as e:
                log("error", f"❌ Acc tổng lỗi: {e}")
        links_out = Path(base) / "chatlist_links.txt"
        with open(links_out, "a", encoding="utf-8") as f:
            f.write("\n".join(chatlist_links) + "\n")
        log("ok", f"✅ Xong. {len(chatlist_links)} chatlist link")

    _submit("consolidate", _task())
    return {"ok": True}


@app.post("/api/admin/delete-accounts")
async def api_delete_accounts(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    selected = data.get("selected", [])
    reason = data.get("reason", "")

    async def _task():
        log("warn", f"⚠️ XÓA {len(selected)} account — KHÔNG THỂ UNDO!")

        async def _op(client, folder_name):
            ok = await delete_account_api(client, reason=reason)
            return "ok" if ok else "error"

        await _run_per_account(base, selected, _op, mode="serial")

    _submit("delete_accounts", _task())
    return {"ok": True}


@app.get("/api/admin/folders")
async def api_admin_folders(base_folder: str = "", client_acc: str = ""):
    """Get Telegram folder list from an account."""
    bf = base_folder or cfg_get("base_folder", "")
    if not bf or not client_acc:
        return {"folders": []}
    try:
        client = await _connect_account(client_acc, bf)
        try:
            res = await client(GetDialogFiltersRequest())
            filters = getattr(res, "filters", res)
            folders = []
            for f in filters:
                title = getattr(f, "title", None)
                if title is None:
                    continue
                title_text = getattr(title, "text", title)
                folders.append(title_text)
            return {"folders": folders}
        finally:
            await client.disconnect()
    except Exception as e:
        return {"folders": [], "error": str(e)}


# ══════════════════════════════════════════════════════════
#  SYNC API (Windows only)
# ══════════════════════════════════════════════════════════
@app.get("/api/sync/windows")
async def api_sync_windows():
    alive = _get_alive_windows()
    return {"windows": [{"hwnd": h, "pid": p, "name": n} for h, p, n in alive]}


@app.post("/api/sync/broadcast")
async def api_sync_broadcast(request: Request):
    data = await request.json()
    text = data.get("text", "")
    delay = float(data.get("delay", 0.3))
    press_enter = bool(data.get("press_enter", True))
    if not text:
        return JSONResponse({"ok": False, "msg": "Nội dung trống"}, status_code=400)
    items = _get_alive_windows()
    if not items:
        return JSONResponse({"ok": False, "msg": "Không có tab nào"}, status_code=400)

    async def _task():
        log("info", f"📤 Gửi tới {len(items)} tab...")
        sent = 0
        for i, (hwnd, pid, name) in enumerate(items, 1):
            try:
                log("info", f"  [{i}/{len(items)}] {name}...")
                await asyncio.to_thread(_send_to_window, hwnd, text, press_enter)
                sent += 1
            except Exception as e:
                log("error", f"  ❌ {name}: {e}")
            if delay > 0:
                await asyncio.sleep(delay)
        log("ok", f"✅ Đã gửi {sent}/{len(items)}")

    _submit("broadcast", _task())
    return {"ok": True, "count": len(items)}


def _send_to_window(hwnd, text, press_enter):
    if not IS_WINDOWS:
        return
    import ctypes
    user32 = ctypes.windll.user32
    _set_clipboard_text(text)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    VK_CONTROL, VK_V, VK_RETURN = 0x11, 0x56, 0x0D
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


def _set_clipboard_text(text):
    if not IS_WINDOWS:
        return
    import ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    text_b = (text + "\0").encode("utf-16-le")
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(text_b))
    ptr = k32.GlobalLock(h)
    ctypes.memmove(ptr, text_b, len(text_b))
    k32.GlobalUnlock(h)
    u32.OpenClipboard(0)
    u32.EmptyClipboard()
    u32.SetClipboardData(CF_UNICODETEXT, h)
    u32.CloseClipboard()


@app.post("/api/sync/retile")
async def api_sync_retile():
    items = _get_alive_windows()
    if not items:
        return JSONResponse({"ok": False, "msg": "Không có tab nào"}, status_code=400)

    def _do():
        wx, wy, ww, wh = _get_work_area()
        GAP = 4
        n = len(items)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        cell_w = (ww - GAP * (cols + 1)) // cols
        cell_h = (wh - GAP * (rows + 1)) // rows
        ok = 0
        for i, (hwnd, pid, name) in enumerate(items):
            r, c = i // cols, i % cols
            x = wx + GAP + c * (cell_w + GAP)
            y = wy + GAP + r * (cell_h + GAP)
            try:
                _set_window_pos(hwnd, x, y, cell_w, cell_h)
                ok += 1
            except Exception:
                pass
        log("ok", f"✅ Re-tile {ok}/{n} tab")

    await asyncio.to_thread(_do)
    return {"ok": True}


@app.post("/api/sync/bring-front")
async def api_sync_bring_front():
    items = _get_alive_windows()
    if not IS_WINDOWS:
        return {"ok": False, "msg": "Chỉ hỗ trợ Windows"}
    import ctypes
    ok = 0
    for hwnd, pid, name in items:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            ok += 1
        except Exception:
            pass
    log("info", f"📍 Đưa {ok}/{len(items)} tab lên trên")
    return {"ok": True, "count": ok}


@app.post("/api/sync/close-all")
async def api_sync_close_all():
    items = _get_alive_windows()
    if not items:
        return {"ok": False, "msg": "Không có tab nào"}
    if not IS_WINDOWS:
        return {"ok": False, "msg": "Chỉ hỗ trợ Windows"}
    import ctypes
    WM_CLOSE = 0x0010
    sent = 0
    for hwnd, pid, name in items:
        try:
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            sent += 1
        except Exception:
            pass
    await asyncio.sleep(1.5)
    survivors = _get_alive_windows()
    log("ok", f"✅ Đã đóng {sent - len(survivors)}/{sent} tab")
    await _broadcast({"type": "windows",
                      "data": [{"hwnd": h, "pid": p, "name": n}
                               for h, p, n in survivors]})
    return {"ok": True, "closed": sent - len(survivors), "survivors": len(survivors)}


@app.get("/api/read-file")
async def api_read_file(path: str = ""):
    """Read a text file and return its contents."""
    if not path:
        return JSONResponse({"error": "No path"}, status_code=400)
    try:
        p = Path(path)
        if not p.exists():
            return JSONResponse({"error": "File not found"}, status_code=404)
        content = p.read_text(encoding="utf-8")
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/sync/launch-tile")
async def api_sync_launch_tile(request: Request):
    data = await request.json()
    base = data.get("base_folder", cfg_get("base_folder", ""))
    if not base or not os.path.isdir(base):
        return JSONResponse({"ok": False, "msg": "Thư mục không hợp lệ"}, status_code=400)

    folders = [s for s in Path(base).iterdir()
               if s.is_dir() and (s / "Telegram.exe").exists()]
    if not folders:
        return JSONResponse({"ok": False, "msg": "Không tìm thấy Telegram.exe"}, status_code=400)

    async def _task():
        import pygetwindow as gw
        existing = set()
        try:
            for w in gw.getAllWindows():
                if "Telegram" in (getattr(w, "title", "") or ""):
                    existing.add(w._hWnd)
        except Exception:
            pass
        log("info", f"🚀 Đang mở {len(folders)} Telegram...")
        pid_to_folder = {}
        for folder in folders:
            try:
                proc = subprocess.Popen([str(folder / "Telegram.exe")], cwd=str(folder))
                pid_to_folder[proc.pid] = folder.name
            except Exception as e:
                log("error", f"❌ Launch lỗi {folder}: {e}")
            await asyncio.sleep(0.4)
        log("info", "⏳ Chờ Telegram load...")
        new_windows = []
        for _ in range(15):
            await asyncio.sleep(1)
            new_windows = []
            try:
                for w in gw.getAllWindows():
                    if "Telegram" not in (getattr(w, "title", "") or ""):
                        continue
                    if w._hWnd in existing:
                        continue
                    pid = _get_window_pid(w._hWnd)
                    fname = pid_to_folder.get(pid, "?")
                    new_windows.append((w, pid, fname))
                if len(new_windows) >= len(folders):
                    break
            except Exception:
                pass
        if not new_windows:
            log("warn", "⚠️ Đã launch nhưng không thấy cửa sổ mới")
            return
        tracked_windows.clear()
        for w, pid, fname in new_windows:
            tracked_windows.append((w._hWnd, pid, fname))
        wx, wy, ww, wh = _get_work_area()
        GAP = 4
        n = len(new_windows)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        cell_w = (ww - GAP * (cols + 1)) // cols
        cell_h = (wh - GAP * (rows + 1)) // rows
        ok = 0
        for i, (w, pid, fname) in enumerate(new_windows):
            r, c = i // cols, i % cols
            x = wx + GAP + c * (cell_w + GAP)
            y = wy + GAP + r * (cell_h + GAP)
            try:
                _set_window_pos(w._hWnd, x, y, cell_w, cell_h)
                ok += 1
            except Exception:
                pass
        await _broadcast({"type": "windows",
                          "data": [{"hwnd": h, "pid": p, "name": nm}
                                   for h, p, nm in tracked_windows]})
        log("ok", f"✅ Track {ok} tab ({cols}×{rows})")

    _submit("launch_tile", _task())
    return {"ok": True, "count": len(folders)}


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════
def _open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8899")


if __name__ == "__main__":
    print("=" * 60)
    print("  Multi-Telegram Tool v8 — Web Interface")
    print("=" * 60)
    print("  Đang khởi động server...")
    print("  Trình duyệt sẽ mở tự động tại: http://localhost:8899")
    print("  Nhấn Ctrl+C để thoát")
    print("=" * 60)
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8899, log_level="warning")
