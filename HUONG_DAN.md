# 📘 Hướng dẫn Multi-Telegram Tool v7

## Tổng quan

Tool quản lý hàng loạt acc Telegram qua Telethon. Hỗ trợ login, tạo channel, cấp admin, gom kênh, đồng bộ thao tác.

**3 tab chính:**
- 🔐 **Đăng nhập** — login acc, tạo session/tdata
- 🛠️ **Admin & Channel** — 8 chức năng quản lý kênh
- 🔄 **Đồng bộ tab** — gửi text đồng bộ tới nhiều cửa sổ Telegram

---

## Cài đặt

```bash
pip install customtkinter telethon opentele pygetwindow pywin32
python main.py
```

**File cần có cùng folder:** `main.py`, `core_runtime.py`, `account_panel.py`, `admin_tab.py`, `login_tab.py`, `sync_tab.py`, `admin_channel.py`

**File tự sinh khi chạy:**
- `tg_tool_config.json` — lưu setting (auto)
- `channels.txt` / `public_channels.txt` / `chatlist_links.txt` — kết quả tạo kênh

---

## Setting chung (header trên cùng)

| Mục | Giải thích |
|---|---|
| **Thư mục gốc** | Nơi lưu folder mỗi acc (mỗi acc 1 folder con chứa `_telethon.session`, `api.json`, `tdata/`) |
| **📜 Mở log** | Bật cửa sổ log nổi (kéo đi đâu cũng được) |
| **⏹ Hủy hết** | Cancel mọi task đang chạy (đã ghi Telegram không undo, chỉ hủy phần chưa gửi) |
| **⚙ N task chạy** | Chỉ báo task đang chạy realtime ở góc header |

---

## 🔐 TAB 1: ĐĂNG NHẬP

### Setting riêng tab login

| Mục | Giải thích |
|---|---|
| **Telegram Portable** | (Tùy chọn) Folder chứa `Telegram.exe` portable. Tool sẽ copy các file (trừ `tdata`) vào folder mỗi acc → mỗi acc có 1 Telegram.exe riêng để mở |
| **Tên folder sau login** | Sau khi login xong, đổi tên folder thành: `@username` / `Tên hiển thị` / `Prefix_01` / `Giữ nguyên` |
| **Số acc** | Số dòng sẽ tạo khi bấm "📋 Tạo bảng" (1-200) |

### Các nút chức năng

#### 📋 Tạo bảng
Tạo N row trống để nhập acc thủ công.

#### 📥 Nhập SĐT hàng loạt
Paste danh sách SĐT 1 lần. **Có ô "🔒 2FA chung"** — nhập 1 lần, áp cho tất cả dòng không có 2FA riêng.

**Format:**
```
+84912345678                    ← dùng 2FA chung
+84987654321                    ← dùng 2FA chung
+84111222333 | otherpwd         ← override, dùng pwd riêng
```

#### 🔒 Áp 2FA cho hết
Nếu đã có danh sách row sẵn, bấm nút này → nhập password 1 lần → fill vào mọi row đang trống 2FA. Row đã có 2FA riêng giữ nguyên.

#### 📩 Gửi mã TẤT CẢ
Với mỗi row có SĐT chưa login, gửi yêu cầu code (queue cách nhau 0.5s).

#### 📝 Nhập mã hàng loạt
Sau khi Telegram gửi code SMS, paste danh sách code:
- **1 mã/dòng** → điền theo thứ tự vào row trống code
- **`+84xxx | 12345`** → khớp theo SĐT
- **`+84xxx | 12345 | 2fapwd`** → khớp + kèm 2FA

#### 🔐 Đăng nhập TẤT CẢ
Submit code cho mọi row đã có code. Tự tạo `tdata` folder + đổi tên folder theo setting.

#### 🪟 Mở tất cả + chia màn hình
Quét tất cả folder con của thư mục gốc, mở `Telegram.exe` cho mỗi folder, sắp xếp lưới trên màn hình. Match qua PID để biết cửa sổ nào của acc nào.

#### ❌ Đóng tất cả tab
Gửi `WM_CLOSE` tới mọi tab Telegram mà tool đã mở. Nếu tab đang hỏi "Save chat?" thì vẫn còn.

---

## 🛠️ TAB 2: ADMIN & CHANNEL

### Setting chung cho cả 8 sub-tab

| Mục | Giải thích |
|---|---|
| **👥 Tài khoản** | Danh sách acc. Bấm 🔍 Quét lại để load từ thư mục gốc + `accounts.txt` |
| **🔎 filter** | Search box — gõ để lọc acc trong danh sách |
| **✓ Tất cả / ✗ Bỏ / ⇌ Đảo** | Chọn nhanh |
| **Chế độ Song song / Tuần tự** | Song song = chạy nhiều acc cùng lúc (nhanh nhưng dễ flood); Tuần tự = từng acc một (an toàn hơn) |
| **Delay (s)** | Khoảng nghỉ giữa các thao tác (0.5s mặc định) |
| **Max song song** | Khi chế độ song song, giới hạn số acc chạy đồng thời (mặc định 8) — tránh Telegram flood |
| **⏹ DỪNG** | Hủy task đang chạy trong tab này |

**Badge bên cạnh mỗi acc khi chạy:**
- ⏳ vàng = đang chạy
- ✓ xanh = ok
- ✗ đỏ = lỗi
- ⏹ cam = bị hủy

---

### 🏗️ 1. Tạo channel (Private)

Tạo kênh/megagroup **không có @username**, chỉ có invite link.

| Field | Giải thích |
|---|---|
| Số channel/acc | Mỗi acc sẽ tạo bao nhiêu kênh |
| Prefix tên | Tên kênh = prefix + 8 ký tự random. VD: `vip_AbCd1234` |
| Mô tả | About của kênh |
| ☐ Tạo Megagroup | Tick = tạo group; bỏ tick = tạo channel broadcast |
| ☐ Lưu link vào channels.txt | Append invite link vào file để dùng cho chức năng "Cấp admin" sau |

**Output:** `channels.txt` chứa mỗi dòng 1 invite link `https://t.me/+xxxxx`.

---

### 🌐 2. Tạo kênh public

Tạo kênh **có @username** (search được). Có thể đính ảnh + welcome message.

| Field | Giải thích |
|---|---|
| Số kênh/acc | Mỗi acc tạo bao nhiêu kênh |
| ☐ Megagroup | Group public (có @username) thay vì channel |
| Tên kênh | Hỗ trợ `{n}` để chèn số thứ tự. VD: `Channel #{n}` → `Channel #1`, `Channel #2`... |
| ☐ Giữ nguyên tên cho TẤT CẢ | Tick = không thêm số dù tạo nhiều |
| Mô tả | About của kênh |
| Username prefix | Phần đầu username, chỉ `a-z 0-9 _`. VD: `vip` |
| Suffix | Phần đuôi auto:<br>• `+1` / `+2` / `+3 ký tự` random<br>• `Lộn xộn` 5-8 ký tự, có thể có `_` |
| Ảnh kênh | (Tùy chọn) Upload làm avatar |
| Welcome msg | (Tùy chọn) Post tin nhắn đầu tiên trong kênh |
| ☐ Lưu public_channels.txt | Lưu cả `https://t.me/@username` + invite link |

**Lưu ý:**
- Mỗi acc giới hạn ~10 kênh public, dùng nhiều quá sẽ bị `ChannelsAdminPublicTooMuchError`
- Tool tự retry username khi trùng (mặc định 10 lần)

---

### 👮 3. Cấp admin

Cấp quyền admin cho 1 hoặc nhiều username vào danh sách kênh chỉ định.

| Field | Giải thích |
|---|---|
| Username | Danh sách `@username`, cách nhau bằng space/comma/newline. Có thể load từ file. |
| Channel/link | Danh sách kênh — username `@chan` hoặc full link `https://t.me/...`. Có nút **📂 Load channels.txt** để load file đã tạo từ tab "Tạo channel". |
| Full quyền | Tất cả quyền admin (kể cả `add_admins`) |
| Safe | Không có `add_admins` — user chỉ là admin, không thể tự cấp admin khác |

**Cơ chế:**
1. Resolve từng kênh → entity
2. Với mỗi (kênh × user): mời nếu chưa member → gửi `EditAdminRequest`
3. Skip nếu đã là admin, log lỗi nếu privacy chặn / không có quyền

---

### 📂 4. Theo Folder TG

Giống "Cấp admin" nhưng kênh không gõ tay mà lấy tự động từ **folder trong Telegram** (folder filter mà acc đã tạo sẵn).

**Quy trình:**
1. Bấm **📥 Tải folder** → tool quét folder TG của acc đầu tiên trong list đã chọn
2. Chọn folder từ dropdown
3. Nhập username cần cấp admin → 🚀 chạy

**Áp dụng:** mỗi acc đã chọn sẽ cấp admin trong folder cùng tên của mình.

---

### 📁 5. Auto Folder

Tự gom **tất cả kênh acc đang admin** vào 1 folder filter trong Telegram (để acc dễ tìm).

| Field | Giải thích |
|---|---|
| Tên folder | Tên folder filter sẽ tạo trong Telegram |

**Logic:**
1. Quét hết dialog của acc → lọc những kênh acc đang là admin/creator
2. Tạo folder filter cùng tên (hoặc cập nhật nếu đã có)
3. Add tất cả kênh vào folder đó

**Hiệu quả:** acc có 50 kênh rải rác → sau khi chạy, mở Telegram thấy 1 folder "My Channels" chứa cả 50 kênh.

---

### 👥 6. Auto-promote vào kênh quản lý

Kết hợp 2 thao tác:
1. Tự quét tất cả kênh acc đang admin (giống Auto Folder)
2. Cấp admin các username vào TẤT CẢ kênh đó

Khác "Cấp admin" thường: không phải nhập tay danh sách kênh, tool tự quét.

| Field | Giải thích |
|---|---|
| Username cần cấp admin | List username |
| Full / Safe | Mức quyền |
| ☐ Bỏ qua nếu username trùng acc | Nếu username = chính acc đó thì skip (tránh lỗi "self-promote") |

**Ví dụ ứng dụng:** B có 30 acc, mỗi acc admin 10 kênh, muốn cấp admin cho 1 acc tổng vào toàn bộ 300 kênh → chọn 30 acc + nhập `@actong` → chạy.

---

### 🎯 7. Dồn về acc tổng

Dùng cơ chế **chatlist invite link** của Telegram để gom kênh nhanh hơn. Acc tổng JOIN qua link → tự thấy toàn bộ folder, không cần ai mời từng kênh.

**Quy trình:**
1. **Phase 1:** Acc tổng connect, lấy @username
2. **Phase 2:** Mỗi acc phụ:
   - Quét kênh đang admin
   - (Tùy chọn) Cấp admin @acctổng vào từng kênh
   - Tạo folder filter chứa các kênh
   - Export chatlist link
3. **Phase 3:** Lưu link vào `chatlist_links.txt`
4. **Phase 4:** Acc tổng JOIN từng link → tự có toàn bộ kênh + tạo folder tổng

| Field | Giải thích |
|---|---|
| Acc tổng | Chọn từ dropdown (bấm 🔄 Load từ acc đã chọn) — phải có @username |
| Folder tổng | Tên folder cuối ở acc tổng. VD: "All Managed" |
| Folder phụ | Tên folder tạm ở mỗi acc phụ (không quan trọng) |
| ☐ Cấp admin acc tổng trước | Khuyến nghị tick — acc tổng có quyền admin mới quản lý được |
| ☐ Lưu chatlist_links.txt | Lưu link để dùng sau |
| ☐ Acc tổng tự JOIN | Tick = acc tổng tự join hết link cuối cùng |

**Khi chạy sẽ hỏi cách xử lý kênh private không có invite:**
- **SKIP** — bỏ qua (an toàn nhất)
- **EXPORT** — tự tạo invite link (cần quyền `invite_users`)
- **ALL** — đưa hết vào, để Telegram tự reject

---

### 🗑️ 8. Xóa account

Xóa **vĩnh viễn** acc Telegram đang chọn. **KHÔNG THỂ UNDO.**

**Hậu quả:**
- Toàn bộ message/contact/channel acc đó admin solo → orphan
- SĐT được free, có thể đăng ký lại (acc mới hoàn toàn, không có lịch sử)
- `tdata` folder của acc bị xóa sẽ vô dụng

**3 lớp confirm bắt buộc:**
1. Gõ chính xác chữ `DELETE` (in hoa)
2. Tick ô "Tôi hiểu hậu quả"
3. Click Yes ở dialog cuối cùng

**Luôn chạy chế độ tuần tự** dù chọn song song (an toàn hơn).

---

## 🔄 TAB 3: ĐỒNG BỘ TAB

Track các tab Telegram do tool tự mở (qua nút "🪟 Mở tất cả + chia màn hình" ở Tab 1). Tab khác trên máy KHÔNG bị đụng vào.

### Track tab

| Mục | Giải thích |
|---|---|
| **Tab đang track** | Số tab Telegram tool đang quản lý |
| **🔄 Cập nhật** | Refresh số tab (loại tab đã đóng) |
| **📋 Xem danh sách** | Hiện list tab kèm hwnd/pid/folder name |

### Gửi text đồng bộ

Paste/gõ text → bấm **📤 GỬI ĐỒNG BỘ TỚI TẤT CẢ TAB**.

Cơ chế:
1. Copy text vào clipboard (Windows API)
2. Focus từng tab Telegram theo thứ tự
3. Bấm Ctrl+V để paste
4. (Tùy chọn) Bấm Enter để gửi luôn

| Mục | Giải thích |
|---|---|
| ☐ Nhấn Enter (gửi luôn) | Bỏ tick = chỉ paste vào ô chat, chưa gửi |
| Delay giữa tab (s) | Nghỉ giữa các tab (mặc định 0.3s) |

**Lưu ý:** đảm bảo các tab đang ở ô chat (đã click vào cuộc hội thoại nào đó).

### Điều khiển cửa sổ

| Nút | Giải thích |
|---|---|
| 🪟 Re-tile | Sắp xếp lại lưới tất cả tab đang track |
| 📍 Đưa lên trên | Đưa tất cả tab Telegram lên top z-order |
| ❌ ĐÓNG TẤT CẢ TAB | Gửi WM_CLOSE tới mọi tab tracked |

---

## 📜 Cửa sổ Log

Mở bằng nút **📜 Mở log** ở header.

| Mục | Giải thích |
|---|---|
| **Filter** | Lọc loại log:<br>• `all` — hiện hết<br>• `ok+error` — chỉ kết quả thành công + lỗi<br>• `error only` — chỉ lỗi<br>• `info+ok` — chỉ thông tin + ok |
| **📌 Pin** | Always-on-top — log không bị cửa sổ khác che |
| **🗑 Xóa** | Clear log hiện tại |
| **💾 Save** | Lưu log ra file `.log` / `.txt` |

**Màu log:**
- 🟢 Xanh lá = ok
- 🔴 Đỏ = error / no_perm
- 🟡 Vàng = fresh (acc mới chưa cho cấp admin)
- 🟠 Cam = privacy / invalid / not_member
- ⚫ Xám = skip (đã làm rồi)
- 🔵 Xanh dương = info

---

## ⚠️ Lưu ý chung

### Hạn chế Telegram
- Acc mới (< 1-2 ngày) thường bị `FreshChangeAdminsForbiddenError` khi cấp admin → đợi vài ngày
- Mỗi acc giới hạn ~10-50 kênh public
- Spam quá nhanh → `FloodWaitError` (tool tự sleep chờ)

### Khuyến nghị
- Lần đầu chạy: dùng chế độ **Tuần tự** + delay 1-2s để xem log dễ
- Khi đã ổn: chuyển **Song song** + max parallel = 5-10 để nhanh hơn
- Trước khi xóa acc: chắc chắn đã backup channel quan trọng

### File config
- `tg_tool_config.json` lưu tất cả setting (folder, prefix, text các ô…)
- Xóa file này = reset về mặc định
- **Không lưu password** — phải nhập 2FA mỗi session (an toàn)

### Cancel task
- Bấm ⏹ DỪNG (admin tab) hoặc ⏹ Hủy hết (header) khi cần hủy giữa chừng
- Thao tác **đã gửi tới Telegram thì không undo được**, chỉ hủy phần chưa gửi

---

## 🐛 Troubleshooting

| Triệu chứng | Nguyên nhân + cách xử lý |
|---|---|
| Tool đơ khi log nhiều | Đã fix bằng LogBus batched. Nếu vẫn lag → giảm max parallel |
| Cấp admin lỗi `FreshChangeAdminsForbiddenError` | Acc quá mới, đợi 1-3 ngày |
| Tạo username public bị `UsernamePurchaseAvailableError` | Username "đẹp" Telegram giữ làm fragment → đổi prefix khác |
| Login lỗi `database is locked` | Đã có Telegram khác mở session đó → đóng hết trước |
| Tab không tile được | Cài `pip install pygetwindow pywin32` |
| Filedialog freeze | Đã fix bằng cách dùng tkinter chuẩn — không cần thêm gì |
