# Multi-Telegram Tool v8 — Web Interface

Gộp toàn bộ 6 file Python của v7 thành **1 file backend** + **1 file HTML** đẹp.  
Chỉ cần **double-click `start.bat`** là chạy, trình duyệt tự mở.

---

## 🚀 Cài đặt & Khởi động

### Lần đầu (cài dependencies):
```bash
pip install fastapi uvicorn[standard] telethon opentele pygetwindow pywin32
```

### Chạy (chọn 1 trong 2):
```
# Windows — double-click:
start.bat

# Hoặc:
python app.py
```

Trình duyệt sẽ tự mở tại `http://localhost:8899`

---

## 📁 Cấu trúc file (gộn gọn)

```
workspace/
├── app.py              ← Backend duy nhất (thay thế 6 file Python cũ)
├── static/
│   └── index.html      ← Giao diện HTML đẹp, 1 file
├── start.bat           ← Double-click để chạy (Windows)
├── requirements.txt    ← Dependencies
└── tg_tool_config.json ← Auto-save settings (tự tạo)
```

## 🔥 So sánh v7 vs v8

| | v7 | v8 |
|---|---|---|
| Files Python | 6 files | **1 file** (`app.py`) |
| Giao diện | CustomTkinter (desktop) | **HTML/CSS/JS** (web) |
| Khởi động | `python main.py` | **Double-click** `start.bat` |
| Log realtime | Cửa sổ riêng | **Panel bên phải** (WebSocket) |
| Trình duyệt | ❌ | ✅ Tự mở |
| Cross-platform UI | ❌ | ✅ |

---

## 🎯 Tính năng

### 🔐 Tab Đăng nhập
- Tạo bảng acc linh hoạt (1–200 acc)
- Nhập SĐT hàng loạt (kèm 2FA mỗi dòng)
- Nhập code hàng loạt (theo thứ tự hoặc khớp SĐT)
- Áp 2FA chung cho tất cả acc trống
- Gửi mã / Đăng nhập từng acc hoặc tất cả
- Export tdata (opentele)
- Đặt tên folder: @username / Tên hiển thị / Prefix / Giữ nguyên
- Copy Telegram Portable tự động
- Mở tất cả Telegram.exe + chia màn hình lưới

### 🛠️ Tab Admin & Channel
- **Tạo channel/group riêng tư** (prefix tùy chọn, export link)
- **Tạo kênh public** (username ngẫu nhiên, ảnh, welcome msg)
- **Cấp admin** cho danh sách user vào danh sách kênh
- **Cấp admin theo Folder TG** (lấy kênh từ folder filter)
- **Auto Folder** (gom tất cả kênh đang admin vào 1 folder)
- **Auto-promote** (cấp user vào tất cả kênh đang admin)
- **Dồn về acc tổng** via chatlist link
- **Xóa account** (serial, xác nhận 2 bước)

### 🔄 Tab Đồng bộ Tab
- Theo dõi tab Telegram đã mở
- Broadcast text đồng bộ qua clipboard + keybd
- Re-tile cửa sổ (xếp lưới tự động)
- Đưa cửa sổ lên trên, đóng tất cả

---

## ⚙️ Cấu hình tự động lưu
Settings được lưu vào `tg_tool_config.json` và tự restore khi mở lại.

---

## 📋 Requirements
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
telethon>=1.29.0
opentele>=1.15.1
pygetwindow>=0.0.9
pywin32>=306
```

> **Lưu ý:** `pygetwindow` và `pywin32` chỉ cần trên Windows (cho tính năng Sync Tab).  
> Các tính năng Login và Admin hoạt động trên mọi OS.
