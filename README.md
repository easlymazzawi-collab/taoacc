# Multi-Telegram Tool v7 — Refactor

## Thay đổi chính so với v6

### 1. Fix UI đơ (3 nguyên nhân gốc)
- **LogBus batched** (`core_runtime.py`): log dồn vào queue, flush 1 nhịp/100ms.
  Trước đây mỗi dòng log gọi `after(0, write)` riêng → batch 1000 thao tác = 1000 event
  tk → main loop nghẹn. Test: submit 100 dòng chỉ 0.19ms.
- **SharedTaskRunner** (`core_runtime.py`): 1 event loop nền duy nhất cho cả app.
  Trước đây mỗi AccountRow + mỗi `_run_in_bg` tạo loop riêng → 30+ loop song song
  → GIL contention.
- **AccountListView** (`account_panel.py`): dùng `tk.Checkbutton` thay
  `CTkCheckBox` (nhanh hơn ~10x khi 30+ acc trong scroll frame —
  GitHub CustomTkinter issue #1461, #2690).

### 2. Code gọn hơn
- Tách `main.py` (2400 dòng) thành 6 module riêng:
  - `core_runtime.py` (361 dòng) — hạ tầng dùng chung
  - `account_panel.py` (294 dòng) — danh sách acc + PerAccountRunner
  - `admin_tab.py` (1079 dòng) — Tab Admin (giảm từ ~1300 dòng nhờ PerAccountRunner)
  - `login_tab.py` (660 dòng) — Tab Đăng nhập
  - `sync_tab.py` (249 dòng) — Tab Đồng bộ
  - `main.py` (322 dòng) — entry point
- `PerAccountRunner` gom pattern `for acc: connect → do_one → disconnect`
  vào 1 helper → 8 sub-tab gọi 1 dòng thay vì 50 dòng copy-paste mỗi cái.

### 3. Tính năng mới
- **Auto save/load config** (`ConfigStore`): mọi setting tự lưu vào
  `tg_tool_config.json`. Mở app lại không phải gõ lại base_folder, prefix,
  delay, các text box… Áp dụng cho cả 3 tab.
- **Nút ⏹ Hủy hết** ở header + Nút **⏹ DỪNG** trong Admin tab: cancel task
  đang chạy (đã ghi vào Telegram thì không undo được, chỉ hủy phần chưa
  gửi).
- **Filter log** (4 mức: all / ok+error / error only / info+ok) trong cửa sổ log.
- **Save log ra file** (.log/.txt) — nút 💾 trong log window.
- **Acc search/filter** + **select invert** + **count badge** trong danh sách acc.
- **Badge trạng thái per acc** (⏳ chạy, ✓ ok, ✗ lỗi, ⏹ hủy) hiện ngay trong
  danh sách khi đang chạy task.
- **Restore last active tab** — mở app lại đúng tab vừa dùng.
- **Indicator task đang chạy** ở header: `⚙ N task chạy` hiện realtime.

## Cấu trúc file

```
tg_tool_v7/
├── admin_channel.py   ← Backend logic Telethon (KHÔNG đổi, vẫn 832 dòng)
├── core_runtime.py    ← LogBus + SharedTaskRunner + ConfigStore + AsyncBridge
├── account_panel.py   ← AccountListView (nhanh) + PerAccountRunner
├── login_tab.py       ← Tab 1: Đăng nhập + Bulk + Tile windows
├── admin_tab.py       ← Tab 2: Admin & Channel (8 sub-tab)
├── sync_tab.py        ← Tab 3: Đồng bộ + WindowManager
└── main.py            ← Entry point
```

## Cài & chạy

```bash
pip install customtkinter telethon opentele pygetwindow pywin32
python main.py
```

## Test logic (đã verify)
- `SharedTaskRunner`: submit/cancel/cancel_all/shutdown đều OK
- `ConfigStore`: save/load JSON OK
- `LogBus`: batched flush + filter + export OK
- Syntax 6 file đều pass

## Lưu ý
- Config file `tg_tool_config.json` tự tạo cạnh main.py. Xóa file này để reset
  về mặc định.
- Khi đóng app sẽ tự save config + shutdown runner sạch.
- Trong Admin tab, ô **Max song song** mặc định 8 (semaphore giới hạn coroutine
  concurrent — tránh Telegram flood).
- Xóa account luôn chạy serial dù chọn parallel — an toàn hơn.
