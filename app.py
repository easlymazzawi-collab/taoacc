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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

IS_WINDOWS = platform.system() == "Windows"
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
CONFIG_FILE = BASE_DIR / "tg_tool_config.json"

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
app = FastAPI(title="Multi-Telegram Tool v8")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _startup():
    _load_config()
    if not TELETHON_OK:
        log("error", f"⚠️ Telethon/opentele chưa cài: {_import_err}")
        log("info", "👉 Chạy: pip install telethon opentele pygetwindow pywin32")
    else:
        log("ok", "✅ Multi-Telegram Tool v8 đã sẵn sàng!")
    log("info", f"🌐 Giao diện: http://localhost:8899")


# ── Static files ──
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


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
