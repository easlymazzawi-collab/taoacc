"""
admin_channel.py v6
Module Admin & Channel — đã fix nhiều bugs:
- API per-account lưu vào api.json để Telegram không flag (reuse mỗi lần)
- is_member fix cho cả Chat và Channel
- export_chatlist_link có option xử lý kênh private
- Logging chi tiết
"""

import asyncio
import inspect
import json
import random
import re
import string
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest, EditAdminRequest, InviteToChannelRequest,
    GetParticipantRequest as ChGetParticipantRequest,
)
from telethon.tl.functions.messages import (
    EditChatAdminRequest, ExportChatInviteRequest,
    GetDialogFiltersRequest, MigrateChatRequest,
    UpdateDialogFilterRequest,
)
from telethon.tl.types import (
    ChatAdminRights, Chat, Channel, ChannelParticipantAdmin,
    ChannelParticipantCreator,
)
from telethon.errors import (
    ChatAdminRequiredError, UserNotParticipantError,
    UserPrivacyRestrictedError, FloodWaitError,
    UserAdminInvalidError, ChatNotModifiedError,
)

try:
    from telethon.errors import FreshChangeAdminsForbiddenError
except ImportError:
    FreshChangeAdminsForbiddenError = None


# ──────────────────────────────────────────────
#  AUTO-DETECT QUYỀN
# ──────────────────────────────────────────────
def _supported_rights():
    sig = inspect.signature(ChatAdminRights.__init__)
    return {p for p in sig.parameters if p != "self"}


SUPPORTED = _supported_rights()


def make_rights(is_broadcast=False, full=True):
    group_full = dict(
        change_info=True, delete_messages=True, ban_users=True,
        invite_users=True, pin_messages=True, add_admins=True,
        manage_call=True, manage_topics=True, anonymous=False,
        other=True,
    )
    group_safe = dict(
        change_info=True, delete_messages=True, ban_users=True,
        invite_users=True, pin_messages=True, manage_call=True,
    )
    channel_full = dict(
        change_info=True, post_messages=True, edit_messages=True,
        delete_messages=True, ban_users=True, invite_users=True,
        pin_messages=True, add_admins=True, manage_call=True,
        post_stories=True, edit_stories=True, delete_stories=True,
        other=True,
    )
    channel_safe = dict(
        change_info=True, post_messages=True, edit_messages=True,
        delete_messages=True, ban_users=True, invite_users=True,
        pin_messages=True, manage_call=True,
    )
    if is_broadcast:
        wanted = channel_full if full else channel_safe
    else:
        wanted = group_full if full else group_safe
    filtered = {k: v for k, v in wanted.items() if k in SUPPORTED}
    return ChatAdminRights(**filtered)


def random_channel_name(prefix="vip_"):
    suffix = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    return prefix + suffix


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


# ──────────────────────────────────────────────
#  API PERSISTENCE — quan trọng để acc không bị flag
# ──────────────────────────────────────────────
def load_or_create_api(folder: Path):
    """
    Đọc/tạo api.json trong folder acc, để mỗi lần connect dùng lại API_ID/HASH cũ.
    Nếu chưa có, generate Telegram Desktop-style API và lưu lại.
    """
    from opentele.api import API
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
    # Generate mới và lưu
    api = API.TelegramDesktop.Generate()
    try:
        # Lưu các attr quan trọng
        data = {}
        for k in ("api_id", "api_hash", "device_model", "system_version",
                  "app_version", "lang_code", "system_lang_code"):
            v = getattr(api, k, None)
            if v is not None:
                data[k] = v
        api_file.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    except Exception:
        pass
    return api


# ──────────────────────────────────────────────
#  AUTO-DETECT ACCOUNTS
# ──────────────────────────────────────────────
def detect_sessions(base_folder: str):
    base = Path(base_folder)
    if not base.is_dir():
        return []
    found = []
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        sess = sub / "_telethon.session"
        if sess.exists():
            found.append((sub.name, str(sub / "_telethon")))
    return found


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


# ──────────────────────────────────────────────
#  IS_MEMBER / IS_ADMIN — fix cho cả Chat
# ──────────────────────────────────────────────
async def is_member(client, channel, user):
    """Đúng cho cả Channel và Chat cũ."""
    try:
        if isinstance(channel, Channel):
            try:
                await client(ChGetParticipantRequest(channel, user))
                return True
            except Exception:
                return False
        elif isinstance(channel, Chat):
            # Chat cũ — duyệt participants
            try:
                full = await client.get_participants(channel)
                user_id = user.id if hasattr(user, "id") else user
                return any(p.id == user_id for p in full)
            except Exception:
                return False
        return False
    except Exception:
        return False


async def is_admin(client, channel, user):
    try:
        if isinstance(channel, Channel):
            try:
                p = await client(ChGetParticipantRequest(channel, user))
                return isinstance(
                    p.participant,
                    (ChannelParticipantAdmin, ChannelParticipantCreator),
                )
            except Exception:
                return False
        return False
    except Exception:
        return False


# ──────────────────────────────────────────────
#  PROMOTE
# ──────────────────────────────────────────────
async def promote_one(client, channel, username, full=True, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)

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
                await client(EditChatAdminRequest(
                    chat_id=channel.id, user_id=user, is_admin=True,
                ))
                log("ok", f"  ✅ @{username} → {title}")
                return "ok"
            except Exception as e:
                log("error", f"  ❌ @{username}: {e}")
                return "error"

        is_broadcast = getattr(channel, "broadcast", False)
        log("info", f"     → @{username}: kiểm tra member...")
        member = await is_member(client, channel, user)
        if not member:
            log("info", f"     → @{username}: chưa vào, đang mời...")
            try:
                await client(InviteToChannelRequest(channel, [user]))
                log("info", f"     ✓ Đã mời")
            except UserPrivacyRestrictedError:
                log("privacy", f"  🔒 @{username}: privacy chặn")
                return "privacy"
            except Exception as e:
                log("not_member", f"  ❌ @{username}: chưa vào — {e}")
                return "not_member"
        else:
            log("info", f"     ✓ Đã là member")

        if await is_admin(client, channel, user):
            log("skip", f"  ⏭️  @{username}: đã là admin")
            return "skip"

        rights = make_rights(is_broadcast=is_broadcast, full=full)
        try:
            log("info", f"     → @{username}: gửi EditAdminRequest...")
            await client(EditAdminRequest(
                channel=channel, user_id=user,
                admin_rights=rights, rank="",
            ))
            log("ok", f"  ✅ @{username} → {title}")
            return "ok"
        except ChatAdminRequiredError:
            log("no_perm", f"  🚫 @{username}: account không có quyền cấp admin trong {title}")
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
                log("fresh", f"  ⏳ @{username}: account mới, chờ Telegram cho phép")
                return "fresh"
            log("error", f"  💥 @{username}: {type(e).__name__} — {e}")
            return "error"
    except Exception as e:
        log("error", f"  💥 @{username}: {type(e).__name__} — {e}")
        return "error"


async def run_promote_batch(client, channels, usernames, delay, full=True, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)
    stats = dict(ok=0, skip=0, fresh=0, no_perm=0,
                 not_member=0, privacy=0, invalid=0, error=0)
    log("info", f"  ▶ {len(channels)} kênh × {len(usernames)} user "
                f"= {len(channels)*len(usernames)} thao tác")
    for ci, ch in enumerate(channels, 1):
        log("info", f"\n  📣 [{ci}/{len(channels)}] {title_of(ch)}")
        for ui, u in enumerate(usernames, 1):
            log("info", f"    [user {ui}/{len(usernames)}]")
            res = await promote_one(client, ch, u, full=full, log_cb=log_cb)
            stats[res] = stats.get(res, 0) + 1
            await asyncio.sleep(delay)
    return stats


# ──────────────────────────────────────────────
#  TẠO CHANNEL
# ──────────────────────────────────────────────
async def create_channels_one(client, amount, prefix, about, megagroup,
                              delay, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)
    kind = "megagroup" if megagroup else "channel"
    log("info", f"  ▶ Tạo {amount} {kind} (prefix='{prefix}')")
    links = []
    for i in range(amount):
        try:
            name = random_channel_name(prefix)
            log("info", f"  → [{i+1}/{amount}] Đang tạo '{name}'...")
            result = await client(CreateChannelRequest(
                title=name, about=about, megagroup=megagroup,
            ))
            ch = result.chats[0]
            log("info", f"     ✓ id={ch.id}, đang export invite link...")
            try:
                invite = await client(ExportChatInviteRequest(ch))
                link = invite.link
            except Exception as e:
                link = f"(no invite, id={ch.id})"
                log("info", f"     ⚠️ {e}")
            links.append(link)
            log("ok", f"  ✅ [{i+1}/{amount}] {name} → {link}")
        except FloodWaitError as e:
            log("error", f"  ⏳ Flood {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            log("error", f"  ❌ [{i+1}/{amount}] {type(e).__name__}: {e}")
        if i < amount - 1:
            await asyncio.sleep(delay)
    log("info", f"  ◀ Xong: {len(links)}/{amount}")
    return links


# ──────────────────────────────────────────────
#  FOLDER FILTER
# ──────────────────────────────────────────────
async def get_folder_channels(client, folder_name=None):
    res = await client(GetDialogFiltersRequest())
    filters = getattr(res, "filters", res)
    folders = {}
    for f in filters:
        title = getattr(f, "title", None)
        if title is None: continue
        title_text = getattr(title, "text", title)
        include_peers = getattr(f, "include_peers", []) or []
        channels = []
        for peer in include_peers:
            try:
                ent = await client.get_entity(peer)
                channels.append(ent)
            except Exception:
                continue
        folders[title_text] = channels
    if folder_name is None:
        return folders
    return folders.get(folder_name, [])


async def get_admin_channels(client, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)

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
            if isinstance(p.participant,
                          (ChannelParticipantCreator, ChannelParticipantAdmin)):
                admin_channels.append(ent)
        except Exception:
            continue
    log("info", f"     ✓ Quét {total} channel/group, đang admin {len(admin_channels)}")
    return admin_channels


async def create_or_update_folder(client, folder_name, channels, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    log("info", f"     → Lấy danh sách filter hiện có...")
    res = await client(GetDialogFiltersRequest())
    existing = getattr(res, "filters", res)

    target_id = None
    used_ids = set()
    for f in existing:
        fid = getattr(f, "id", None)
        if fid is not None:
            used_ids.add(fid)
        title_obj = getattr(f, "title", None)
        if title_obj is None: continue
        title_text = getattr(title_obj, "text", title_obj)
        if title_text == folder_name:
            target_id = fid
            log("info", f"     ℹ️  Folder '{folder_name}' đã tồn tại (id={fid}) — sẽ cập nhật")

    if target_id is None:
        for cand in range(2, 256):
            if cand not in used_ids:
                target_id = cand
                break
        log("info", f"     ℹ️  Tạo folder mới với id={target_id}")

    log("info", f"     → Convert {len(channels)} channels sang InputPeer...")
    include_peers = []
    skipped = 0
    for i, ch in enumerate(channels, 1):
        try:
            peer = await client.get_input_entity(ch)
            include_peers.append(peer)
            if i <= 5 or i == len(channels):
                log("info", f"        [{i}/{len(channels)}] ✓ {title_of(ch)}")
            elif i == 6:
                log("info", f"        ... ({len(channels) - 5} kênh khác)")
        except Exception as e:
            log("error", f"     ⚠️ Bỏ qua {title_of(ch)}: {e}")
            skipped += 1

    if skipped:
        log("info", f"     ⚠️  Bỏ qua {skipped} kênh do lỗi resolve")

    try:
        from telethon.tl.types import TextWithEntities
        title_obj = TextWithEntities(text=folder_name, entities=[])
    except ImportError:
        title_obj = folder_name

    from telethon.tl.types import DialogFilter
    sig = inspect.signature(DialogFilter.__init__)
    kwargs = dict(
        id=target_id, title=title_obj, pinned_peers=[],
        include_peers=include_peers, exclude_peers=[],
    )
    for k in ("contacts", "non_contacts", "groups", "broadcasts",
              "bots", "exclude_muted", "exclude_read", "exclude_archived"):
        if k in sig.parameters:
            kwargs[k] = False
    if "emoticon" in sig.parameters:
        kwargs["emoticon"] = "📁"

    flt = DialogFilter(**kwargs)
    log("info", f"     → Gửi UpdateDialogFilterRequest ({len(include_peers)} peer)...")
    await client(UpdateDialogFilterRequest(id=target_id, filter=flt))
    log("ok", f"     ✅ Folder '{folder_name}' (id={target_id}) — {len(include_peers)} kênh")
    return target_id


# ──────────────────────────────────────────────
#  CHATLIST INVITE
# ──────────────────────────────────────────────
async def channel_has_invite_link(client, channel):
    """Check kênh có invite link không (để biết private hay không)."""
    try:
        full = await client.get_entity(channel)
        username = getattr(full, "username", None)
        if username:
            return True
        # Channel private — thử lấy invite link đã có
        try:
            from telethon.tl.functions.messages import ExportChatInviteRequest as _E
            inv = await client(_E(channel))
            return inv is not None
        except Exception:
            return False
    except Exception:
        return False


async def export_chatlist_link(client, folder_id, channels, link_title="My Folder",
                              private_handling="skip", log_cb=None):
    """
    private_handling:
      'skip' — bỏ qua kênh không có invite, chỉ export những kênh public/đã có link
      'export' — generate invite link cho kênh chưa có (cần quyền admin với invite_users)
      'all' — đưa tất cả vào, để Telegram tự reject nếu cần
    """
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    try:
        from telethon.tl.functions.chatlists import ExportChatlistInviteRequest
        from telethon.tl.types import InputChatlistDialogFilter
    except ImportError:
        log("error", "     ❌ Telethon < 1.29 — không hỗ trợ chatlist")
        return None

    valid_peers = []
    skipped = 0
    for ch in channels:
        try:
            if private_handling == "skip":
                if not await channel_has_invite_link(client, ch):
                    skipped += 1
                    log("info", f"     ⏭ Skip private (không có invite): {title_of(ch)}")
                    continue
            elif private_handling == "export":
                # Thử generate invite link
                if not await channel_has_invite_link(client, ch):
                    try:
                        await client(ExportChatInviteRequest(ch))
                        log("info", f"     🔗 Đã tạo invite cho: {title_of(ch)}")
                    except Exception as e:
                        skipped += 1
                        log("error", f"     ⏭ Skip {title_of(ch)} (không tạo được invite): {e}")
                        continue
            # 'all' → không skip, để Telegram tự xử
            peer = await client.get_input_entity(ch)
            valid_peers.append(peer)
        except Exception as e:
            log("error", f"     ⚠️ Bỏ qua {title_of(ch)}: {e}")
            skipped += 1

    if not valid_peers:
        log("error", f"     ❌ Không peer nào hợp lệ (skipped {skipped})")
        return None

    log("info", f"     → Export chatlist link ({len(valid_peers)} peer, skipped {skipped})...")
    try:
        result = await client(ExportChatlistInviteRequest(
            chatlist=InputChatlistDialogFilter(filter_id=folder_id),
            title=link_title,
            peers=valid_peers,
        ))
        url = result.invite.url
        log("ok", f"     ✅ {url}")
        return url
    except Exception as e:
        log("error", f"     ❌ Export lỗi: {type(e).__name__} — {e}")
        return None


async def join_chatlist_link(client, url, log_cb=None):
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    try:
        from telethon.tl.functions.chatlists import (
            CheckChatlistInviteRequest, JoinChatlistInviteRequest,
        )
    except ImportError:
        log("error", "     ❌ Telethon < 1.29")
        return False, 0

    m = re.search(r"addlist[/=]([A-Za-z0-9_\-]+)", url)
    if not m:
        log("error", f"     ❌ Không parse slug: {url}")
        return False, 0
    slug = m.group(1)

    log("info", f"     → Check chatlist '{slug}'...")
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
        log("error", f"     ❌ Join lỗi: {type(e).__name__} — {e}")
        return False, 0


# ──────────────────────────────────────────────
#  TẠO KÊNH CÔNG KHAI (kèm username, ảnh, welcome msg)
# ──────────────────────────────────────────────
async def create_public_channel(
    client, title, about, username_prefix,
    suffix_mode="random_3",  # 'random_1' / 'random_2' / 'random_3' / 'chaos'
    photo_path=None,
    welcome_msg=None,
    megagroup=False,
    max_retries=10,
    log_cb=None,
):
    """
    Tạo 1 kênh công khai (có @username):
      1. CreateChannelRequest
      2. UpdateUsernameRequest với prefix + suffix sinh ra (retry nếu trùng)
      3. EditPhotoRequest nếu có photo_path
      4. SendMessageRequest welcome_msg

    suffix_mode:
      'random_1' / 'random_2' / 'random_3' — thêm N ký tự random sau prefix
      'chaos' — random hoàn toàn 5-8 ký tự sau prefix
    """
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    from telethon.tl.functions.channels import (
        UpdateUsernameRequest, EditPhotoRequest,
    )
    from telethon.tl.types import InputChatUploadedPhoto
    from telethon.errors import (
        UsernameInvalidError, UsernameOccupiedError,
        UsernamePurchaseAvailableError, ChannelsAdminPublicTooMuchError,
    )

    # B1: Tạo channel
    log("info", f"  → Tạo channel '{title}'...")
    try:
        result = await client(CreateChannelRequest(
            title=title, about=about, megagroup=megagroup,
        ))
        ch = result.chats[0]
        log("info", f"     ✓ Đã tạo, id={ch.id}")
    except FloodWaitError as e:
        log("error", f"     ⏳ Flood {e.seconds}s, chờ...")
        await asyncio.sleep(e.seconds)
        return None
    except Exception as e:
        log("error", f"     ❌ {type(e).__name__}: {e}")
        return None

    # B2: Set username với retry
    final_username = None
    base = re.sub(r"[^a-zA-Z0-9_]", "", username_prefix)  # username chỉ a-z, 0-9, _
    if not base:
        log("error", f"     ⚠️  Prefix không hợp lệ, bỏ qua set username")
    else:
        for attempt in range(max_retries):
            suffix = _gen_username_suffix(suffix_mode)
            candidate = f"{base}{suffix}"[:32]  # max 32 chars
            log("info", f"     → Thử username @{candidate}...")
            try:
                ok = await client(UpdateUsernameRequest(
                    channel=ch, username=candidate))
                if ok:
                    final_username = candidate
                    log("ok", f"     ✅ Username: @{candidate}")
                    break
            except UsernameOccupiedError:
                log("info", f"     ⚠️  @{candidate} đã có người dùng, thử khác...")
                continue
            except UsernameInvalidError:
                log("error", f"     ❌ @{candidate} sai format")
                continue
            except UsernamePurchaseAvailableError:
                log("info", f"     ⚠️  @{candidate} cần mua, thử khác...")
                continue
            except ChannelsAdminPublicTooMuchError:
                log("error", f"     🚫 Acc đạt giới hạn channel public — cần xóa kênh public cũ")
                break
            except FloodWaitError as e:
                log("error", f"     ⏳ Flood {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log("error", f"     ❌ {type(e).__name__}: {e}")
                continue
            await asyncio.sleep(0.3)

        if not final_username:
            log("error", f"     ⚠️  Không set được username sau {max_retries} lần thử")

    # B3: Set ảnh
    if photo_path:
        try:
            log("info", f"     → Upload ảnh: {Path(photo_path).name}...")
            file = await client.upload_file(photo_path)
            await client(EditPhotoRequest(
                channel=ch, photo=InputChatUploadedPhoto(file=file)))
            log("ok", f"     ✅ Đã set ảnh kênh")
        except Exception as e:
            log("error", f"     ⚠️ Lỗi set ảnh: {type(e).__name__} — {e}")

    # B4: Gửi welcome message
    if welcome_msg:
        try:
            log("info", f"     → Gửi welcome message...")
            await client.send_message(ch, welcome_msg)
            log("ok", f"     ✅ Đã gửi welcome")
        except Exception as e:
            log("error", f"     ⚠️ Lỗi gửi msg: {type(e).__name__} — {e}")

    # B5: Lấy invite link (kênh public thì link là t.me/{username}, fallback dùng invite)
    public_link = f"https://t.me/{final_username}" if final_username else None
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
        "public_link": public_link,
        "invite_link": invite_link,
    }


def _gen_username_suffix(mode):
    """Sinh suffix theo mode."""
    chars = string.ascii_lowercase + string.digits
    if mode == "random_1":
        return "".join(random.choices(chars, k=1))
    elif mode == "random_2":
        return "".join(random.choices(chars, k=2))
    elif mode == "random_3":
        return "".join(random.choices(chars, k=3))
    elif mode == "chaos":
        # Random 5-8 ký tự, có thể chèn _ giữa
        n = random.randint(5, 8)
        s = "".join(random.choices(chars, k=n))
        # 30% chèn 1 dấu _
        if random.random() < 0.3 and len(s) > 3:
            pos = random.randint(1, len(s) - 1)
            s = s[:pos] + "_" + s[pos:]
        return s
    return "".join(random.choices(chars, k=3))


async def create_public_channels_batch(
    client, amount, title_template, about, username_prefix,
    suffix_mode="random_3", photo_path=None, welcome_msg=None,
    delay=1.0, megagroup=False, same_title=False, log_cb=None,
):
    """Tạo nhiều kênh public liên tiếp.

    same_title=True: tất cả kênh dùng nguyên title_template, không thêm số.
    same_title=False: nếu có {n} thì thay bằng số, nếu không thì append số khi amount>1.
    """
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    log("info", f"  ▶ Tạo {amount} kênh public với prefix '{username_prefix}'")
    results = []
    for i in range(amount):
        if same_title:
            actual_title = title_template
        elif "{n}" in title_template or "{i}" in title_template:
            actual_title = title_template.replace("{n}", str(i + 1)).replace("{i}", str(i + 1))
        elif amount > 1:
            actual_title = f"{title_template} {i + 1}"
        else:
            actual_title = title_template

        log("info", f"\n  📣 [{i+1}/{amount}] {actual_title}")
        result = await create_public_channel(
            client, actual_title, about, username_prefix,
            suffix_mode=suffix_mode, photo_path=photo_path,
            welcome_msg=welcome_msg, megagroup=megagroup, log_cb=log_cb,
        )
        if result:
            results.append(result)
        if i < amount - 1:
            await asyncio.sleep(delay)
    log("info", f"  ◀ Xong: {len(results)}/{amount}")
    return results


async def delete_account(client, reason="", log_cb=None):
    """
    Xóa vĩnh viễn account đang đăng nhập.
    KHÔNG THỂ UNDO. Tương đương "Delete my account" trên mobile.
    """
    def log(level, msg):
        if log_cb: log_cb(level, msg)

    try:
        from telethon.tl.functions.account import DeleteAccountRequest
    except ImportError:
        log("error", "     ❌ Telethon không hỗ trợ DeleteAccountRequest")
        return False

    try:
        me = await client.get_me()
        ident = f"@{me.username}" if me.username else f"id={me.id}"
        name = me.first_name or ""
        log("info", f"     ⚠️  Sẽ xóa: {name} {ident} (id={me.id})")
    except Exception as e:
        log("error", f"     ❌ Không lấy được info: {e}")
        return False

    # DeleteAccountRequest chấp nhận tham số reason (string) ở Telethon mới
    try:
        import inspect
        sig = inspect.signature(DeleteAccountRequest.__init__)
        if "reason" in sig.parameters:
            await client(DeleteAccountRequest(reason=reason))
        else:
            await client(DeleteAccountRequest())
        log("ok", f"     ✅ Đã xóa account {ident}")
        return True
    except Exception as e:
        log("error", f"     ❌ Xóa lỗi: {type(e).__name__} — {e}")
        return False
