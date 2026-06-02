# SETUP_GUIDE.md - Hướng Dẫn Thiết Lập AI Business OS

## 📋 Quy Trình Thiết Lập

### **Bước 1: Chuẩn Bị Môi Trường**

```bash
# Clone repository
git clone https://github.com/tradeview113d8-code/AI_Business_OS_Data.git
cd AI_Business_OS_Data

# Tạo virtual environment (tuỳ chọn nhưng được khuyến khích)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt
```

### **Bước 2: Cấu Hình Environment**

Tạo file `.env` trong root directory:

```env
MONGO_URI=mongodb://localhost:27017
# hoặc nếu dùng MongoDB Atlas:
# MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority

DB_NAME=business_os_v5

# Telegram Bot (tuỳ chọn)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### **Bước 3: Chạy Bootstrap**

```bash
# Tạo MongoDB collections
python3 bootstrap.py
```

**Output mong đợi:**
```
Bootstrap Complete — 24 collections ready (24 newly created)
```

**Hoặc nếu collections đã tồn tại:**
```
Bootstrap Complete — 24 collections ready (0 newly created)
```

### **Bước 4: Tạo Database Indexes**

```bash
# Tạo indexes để tối ưu hóa truy vấn
python3 mongo_indexes.py
```

**Output mong đợi:**
```
Đang thiết lập Index...
✓ Created jobs indexes
✓ Created events indexes
✓ Created api_keys_raw indexes
✓ Created api_keys_refined indexes
✓ Created api_channels indexes

Index setup complete.
```

### **Bước 5: Test Workers**

#### **Test Key Refiner Worker**
```bash
python3 Workers/key_refiner.py
```

**Output mong đợi (nếu không có API keys):**
```
No raw keys to process
```

**Hoặc (nếu có keys):**
```
Refined key my_openai_key -> openai with 5 models
Processed 1 raw keys
```

#### **Test OneAPI Sync Worker**
```bash
python3 Workers/oneapi_sync.py
```

**Output mong đợi (nếu không có refined keys):**
```
No active refined keys to sync
```

**Hoặc (nếu có keys):**
```
Sync complete - created/updated 5 channels
```

### **Bước 6: Khởi Động Telegram Bot (Tuỳ Chọn)**

```bash
# Nếu có Telegram bot module
python3 telegram_bot.py
```

Lúc này lệnh `/apikey` sẽ có hiệu lực.

### **Bước 7: Push Lên GitHub**

```bash
# Thêm tất cả thay đổi
git add .

# Commit thay đổi
git commit -m "Setup: Initialize MongoDB collections and indexes"

# Push lên GitHub
git push origin main
```

**GitHub Actions sẽ tự động chạy workflows** ✅

---

## 🧪 Kiểm Tra Kết Quả

### **1. Kiểm tra MongoDB Collections**

```bash
# Kết nối MongoDB (tuỳ chọn)
# Dùng MongoDB Compass hoặc mongosh:
# mongosh
# use business_os_v5
# db.collections.find()
```

### **2. Kiểm tra Logs**

```bash
# Xem logs trong MongoDB
db.logs.find().sort({created_at: -1}).limit(10)
```

### **3. Kiểm tra Events**

```bash
# Xem events trong MongoDB
db.events.find({status: "pending"}).limit(5)
```

### **4. Kiểm tra GitHub Actions**

Truy cập: https://github.com/tradeview113d8-code/AI_Business_OS_Data/actions

---

## ⚠️ Khắc Phục Lỗi Thường Gặp

### **Lỗi 1: "MONGO_URI not found"**
```
Giải pháp: Kiểm tra file .env đã được tạo chưa
cat .env  # Kiểm tra nội dung
```

### **Lỗi 2: "Connection refused"**
```
Giải pháp: MongoDB chưa khởi động
- Kiểm tra MongoDB service
- Hoặc kiểm tra MongoDB Atlas connection string
```

### **Lỗi 3: "No module named 'Core'"**
```
Giải pháp: Chạy script từ root directory
cd AI_Business_OS_Data
python3 bootstrap.py
```

### **Lỗi 4: Index creation failed**
```
Giải pháp: Xóa indexes cũ trước
db.events.dropIndex("events_ttl")  # Hoặc index khác
python3 mongo_indexes.py
```

---

## 📊 Database Schema

### **Collections Được Tạo:**

| Collection | Mục Đích |
|-----------|---------|
| `requests` | Lưu trữ requests từ người dùng |
| `jobs` | Queue công việc |
| `events` | Event bus (TTL 30 ngày) |
| `api_keys_raw` | API keys chưa xử lý |
| `api_keys_refined` | API keys đã xử lý |
| `api_channels` | Channels kết nối API |
| `logs` | Audit logs |
| `notifications` | Thông báo hệ thống |

---

## 🔄 Workflow Tự Động

Sau khi push lên GitHub, những tác vụ này sẽ chạy tự động:

1. ✅ Unit tests
2. ✅ Code linting
3. ✅ Security checks
4. ✅ Deployment (nếu cấu hình)

Xem trạng thái: **GitHub Actions tab**

---

## 📝 Ghi Chú

- **Idempotent**: Có thể chạy lại bootstrap nhiều lần mà không gây lỗi
- **Graceful degradation**: Workers sẽ skip nếu không có dữ liệu
- **Comprehensive logging**: Tất cả hành động đều được log
- **Error recovery**: Tự động retry failed events

---

## 🎯 Tiếp Theo

Sau khi setup thành công:

1. Thêm API keys qua Telegram bot: `/apikey sk-xxx`
2. Verify keys được refined: `db.api_keys_refined.find()`
3. Verify channels được tạo: `db.api_channels.find()`
4. Monitor logs: `db.logs.find({level: "ERROR"})`

**Setup hoàn tất!** 🎉
