# TELEGRAM_BOT_SETUP.md - Hướng Dẫn Cấu Hình Telegram Bot

## 🚀 Cấu Hình Telegram Bot

### **Bước 1: Tạo Bot với BotFather**

1. Mở Telegram, tìm `@BotFather`
2. Gõ `/start` rồi `/newbot`
3. Nhập tên bot: `AI Business OS Bot`
4. Nhập username: `ai_business_os_bot` (phải unique)
5. **Sao chép Token** (VD: `123456789:ABCDefghijklmnopqrstuvwxyz`)

### **Bước 2: Cấu Hình `.env`**

Thêm vào file `.env`:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=123456789:ABCDefghijklmnopqrstuvwxyz
# Hoặc dùng TELEGRAM_BOT_TOKEN cũng được:
# TELEGRAM_BOT_TOKEN=123456789:ABCDefghijklmnopqrstuvwxyz

# Admin IDs (Telegram User ID)
# Lấy ID của bạn bằng cách gửi tin nhắn tới @userinfobot
# Có thể thêm nhiều ID, cách nhau bởi dấu phẩy
ADMIN_IDS=123456789,987654321

# MongoDB
MONGO_URI=mongodb://localhost:27017
DB_NAME=business_os_v5
```

### **Bước 3: Lấy Telegram User ID**

```bash
# Cách 1: Dùng @userinfobot trên Telegram
# - Mở Telegram
# - Tìm @userinfobot
# - Gửi bất kỳ tin nhắn nào
# - Bot sẽ trả lại ID của bạn

# Cách 2: Dùng bot của bạn
# Chạy bot và gửi /start, xem error log
# Hoặc inspect logs: db.logs.find({level: "INFO"})
```

### **Bước 4: Khởi Động Bot**

```bash
# Phương pháp 1: Chạy trực tiếp
python3 Telegram/bot.py

# Phương pháp 2: Chạy trong background
nohup python3 Telegram/bot.py > telegram_bot.log 2>&1 &

# Phương pháp 3: Dùng systemd (Linux)
# Tạo /etc/systemd/system/telegram-bot.service
```

---

## 🧪 Test Bot

### **Test 1: Bot Khởi Động**

```bash
python3 Telegram/bot.py
# Nên thấy:
# 🤖 Bot is starting...
# ✓ Telegram Token: Loaded
```

### **Test 2: Gửi /start**

1. Mở Telegram
2. Tìm bot của bạn (@ai_business_os_bot)
3. Gửi `/start`
4. **Kỳ vọng**: Bot trả lời "🤖 AI BUSINESS OS V5.1 - ONLINE" + menu

### **Test 3: Thêm API Key**

1. Gửi `/apikey`
2. Bot hỏi: "🔑 Nhập tên gợi nhớ..."
3. Nhập: `test_gemini`
4. Bot hỏi: "📎 Dán API Key..."
5. Nhập key: `sk-test1234567890abcdefghijklmnopqr`
6. **Kỳ vọng**: Bot trả lời "✅ Đã nhận API Key..."

### **Test 4: Kiểm Tra Database**

```bash
python3 -c "
from Core.mongo import db
keys = db.api_keys_raw.find({'source': 'telegram'})
for key in keys:
    print(f'✓ {key[\"name\"]}: {key[\"status\"]}')
"
```

---

## ⚠️ Troubleshooting

### **Vấn đề 1: "TELEGRAM_TOKEN not found"**

```bash
# Kiểm tra .env
cat .env | grep TELEGRAM

# Hoặc
grep -E "TELEGRAM_(TOKEN|BOT_TOKEN)" .env
```

**Giải pháp:**
- Thêm TELEGRAM_TOKEN hoặc TELEGRAM_BOT_TOKEN vào .env
- Khởi động lại bot

### **Vấn đề 2: "Từ chối: Bạn không có quyền Admin"**

```bash
# Kiểm tra ADMIN_IDS
cat .env | grep ADMIN_IDS

# Nếu rỗng:
echo "ADMIN_IDS=123456789" >> .env
# Thay 123456789 bằng ID thực của bạn
```

### **Vấn đề 3: Bot không phản hồi**

```bash
# Kiểm tra logs
tail -f telegram_bot.log

# Hoặc kiểm tra MongoDB
python3 -c "
from Core.mongo import db
print(db.logs.count_documents({'worker': 'bot'}))
logs = db.logs.find({'worker': 'bot'}).sort('created_at', -1).limit(5)
for log in logs:
    print(f'{log[\"level\"]}: {log[\"message\"]}')
"
```

### **Vấn đề 4: Rate Limiter quá nghiêm**

```python
# File: Telegram/rate_limiter.py
# Điều chỉnh giá trị:
REQUESTS_PER_MINUTE = 30  # Thay đổi số lượng request cho phép
```

---

## 🔐 Security Best Practices

1. **Không commit .env**: Đã có `.gitignore` ✅
2. **ADMIN_IDS**: Chỉ cho phép user tin tưởng ✅
3. **JSON Validation**: Dùng `json.loads()` thay vì `eval()` ✅
4. **Audit Logging**: Tất cả hành động được log ✅
5. **Rate Limiting**: Bảo vệ bot khỏi abuse ✅

---

## 📊 Monitoring Bot

### **Kiểm tra Bot Status**

```bash
python3 -c "
from Core.mongo import db
from datetime import datetime, timedelta

# Recent activity (last 1 hour)
one_hour_ago = datetime.utcnow() - timedelta(hours=1)
recent = db.audit_logs.find({
    'timestamp': {'\$gte': one_hour_ago}
}).sort('timestamp', -1)

print('📊 Bot Activity (Last 1 Hour):')
for log in recent:
    print(f'  - {log[\"action\"]} by {log[\"user_id\"]}')

# Error count
errors = db.logs.count_documents({
    'worker': 'bot',
    'level': 'ERROR',
    'created_at': {'\$gte': one_hour_ago}
})
print(f'\\n❌ Errors: {errors}')
"
```

### **Kiểm tra Bot Uptime**

```bash
# Dùng systemd
systemctl status telegram-bot

# Hoặc kiểm tra process
ps aux | grep "Telegram/bot.py"

# Hoặc kiểm tra logs
tail -20 telegram_bot.log
```

---

## 🎯 Commands Available

| Command | Mục Đích |
|---------|---------|
| `/start` | Hiển thị menu chính |
| `/menu` | Hiển thị menu chính |
| `/apikey` | Thêm API Key mới |
| `/schedule` | Lập lịch tác vụ |

---

## 📝 Ghi Chú

- Bot dùng webhook hoặc polling tùy cấu hình
- Mặc định: **polling** (infinity_polling)
- Webhook: Yêu cầu SSL certificate + public IP
- ADMIN_IDS trống = Chế độ development (cho tất cả)

---

## ✅ Checklist

- [ ] Token Telegram được tạo
- [ ] TELEGRAM_TOKEN thêm vào .env
- [ ] ADMIN_IDS cấu hình với ID của bạn
- [ ] MongoDB chạy và kết nối
- [ ] Bot khởi động thành công
- [ ] /start command hoạt động
- [ ] /apikey command hoạt động
- [ ] Audit logs được ghi
- [ ] Error logs được kiểm tra

**Setup Telegram Bot hoàn tất!** ✅
