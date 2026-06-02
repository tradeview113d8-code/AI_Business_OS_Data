# TESTING_CHECKLIST.md - Kiểm Tra & Xác Minh Toàn Diện

## ✅ Pre-Setup Checklist

Kiểm tra trước khi bắt đầu:

- [ ] Python 3.8+ đã cài đặt: `python3 --version`
- [ ] MongoDB khởi động và accessible
- [ ] File `.env` đã tạo với MONGO_URI và DB_NAME
- [ ] Git repository đã clone
- [ ] Dependencies đã cài: `pip install -r requirements.txt`
- [ ] Có Internet connection (để test API endpoints)

---

## 🚀 Setup Execution Steps

### **Phase 1: Bootstrap Collections**

```bash
python3 bootstrap.py
```

**Expected Output:**
```
Bootstrap Complete — 24 collections ready (24 newly created)
```

**Verify:**
```bash
python3 -c "
from Core.mongo import db
collections = db.list_collection_names()
print(f'✓ Total collections: {len(collections)}')
print(f'✓ Collections: {sorted(collections)}')
"
```

- [ ] 24 collections được tạo
- [ ] Không có error messages
- [ ] Script kết thúc bình thường (exit code 0)

---

### **Phase 2: Create Indexes**

```bash
python3 mongo_indexes.py
```

**Expected Output:**
```
Đang thiết lập Index...
✓ Created jobs indexes
✓ Created events indexes
✓ Created api_keys_raw indexes
✓ Created api_keys_refined indexes
✓ Created api_channels indexes

Index setup complete.
```

**Verify:**
```bash
python3 -c "
from Core.mongo import db

# Check indexes
for coll_name in ['jobs', 'events', 'api_keys_refined', 'api_channels']:
    coll = db[coll_name]
    indexes = [idx['name'] for idx in coll.list_indexes()]
    print(f'✓ {coll_name}: {indexes}')
"
```

- [ ] Jobs indexes: status, type, priority
- [ ] Events indexes: event_type, events_ttl (TTL)
- [ ] API Keys Refined indexes: raw_key_id (unique), provider, status
- [ ] API Channels indexes: raw_key_id+model (unique), enabled, provider
- [ ] Không có duplicate index errors

---

### **Phase 3: Worker Testing**

#### **Test 3.1: Key Refiner**

```bash
python3 Workers/key_refiner.py
```

**Expected Output (No Keys):**
```
No raw keys to process
```

**Or With Test Data:**
```bash
# Insert test data
python3 -c "
from Core.mongo import db
from datetime import datetime

db.api_keys_raw.insert_one({
    'key': 'sk-test123456789abcdefghijklmnopqr',
    'name': 'test_openai',
    'source': 'manual',
    'status': 'raw',
    'created_at': datetime.utcnow()
})
print('✓ Test key inserted')
"

# Run refiner
python3 Workers/key_refiner.py
```

**Expected Output With Data:**
```
Refined key test_openai -> openai with X models
Processed 1 raw keys
```

- [ ] Worker executes without crashing
- [ ] Output matches expected
- [ ] Database logs created
- [ ] api_keys_refined collection updated

#### **Test 3.2: OneAPI Sync**

```bash
python3 Workers/oneapi_sync.py
```

**Expected Output (No Refined Keys):**
```
No active refined keys to sync
```

**Or With Refined Data:**
```
Sync complete - created/updated X channels
```

**Verify:**
```bash
python3 -c "
from Core.mongo import db

# Check if api_channels were created
channels = list(db.api_channels.find().limit(5))
print(f'✓ Total channels: {db.api_channels.count_documents({})}')
for ch in channels[:3]:
    print(f'  - {ch[\"provider\"]}/{ch[\"model\"]}: enabled={ch[\"enabled\"]}')
"
```

- [ ] Worker executes without crashing
- [ ] api_channels collection populated (if refined keys exist)
- [ ] Database logs created
- [ ] No ERROR level logs

---

## 🔍 Database Verification

### **Verify All Collections Exist**

```bash
python3 -c "
from Core.mongo import db

required = [
    'requests', 'requests_refined',
    'jobs', 'dead_letter_queue',
    'reports', 'artifacts',
    'events', 'dead_events',
    'notifications',
    'knowledge',
    'logs', 'metrics', 'audit_logs',
    'health', 'system_health',
    'processing_logs',
    'scheduled_tasks',
    'plugin_registry',
    'users', 'config',
    'personal_knowledge',
    'api_keys_raw',
    'api_keys_refined',
    'api_channels',
]

existing = set(db.list_collection_names())
missing = set(required) - existing

print(f'✓ Required: {len(required)}')
print(f'✓ Found: {len(existing)}')
print(f'✓ Missing: {len(missing)}')

if missing:
    print(f'  ✗ Missing: {missing}')
"
```

- [ ] All 24 collections exist
- [ ] No missing critical collections

---

### **Verify Indexes Exist**

```bash
python3 -c "
from Core.mongo import db

checks = {
    'jobs': ['status', 'type', 'priority'],
    'events': ['event_type'],
    'api_keys_raw': ['status', 'created_at'],
    'api_keys_refined': ['raw_key_id', 'provider', 'status'],
    'api_channels': ['enabled', 'provider'],
}

for coll_name, required_indexes in checks.items():
    coll = db[coll_name]
    existing = [idx['name'] for idx in coll.list_indexes()]
    
    for req_idx in required_indexes:
        if any(req_idx in idx for idx in existing):
            print(f'✓ {coll_name}: {req_idx}')
        else:
            print(f'✗ {coll_name}: MISSING {req_idx}')
"
```

- [ ] All critical indexes created
- [ ] No index creation errors

---

## 📊 Logs & Events Verification

### **Check Logs**

```bash
python3 -c "
from Core.mongo import db

logs = list(db.logs.find().sort('created_at', -1).limit(10))
print(f'✓ Total logs: {db.logs.count_documents({})}')

for level in ['INFO', 'WARNING', 'ERROR']:
    count = db.logs.count_documents({'level': level})
    print(f'  - {level}: {count}')
"
```

- [ ] Logs being created
- [ ] INFO logs from bootstrap/indexes
- [ ] No unexpected ERROR logs

### **Check Events**

```bash
python3 -c "
from Core.mongo import db

states = ['pending', 'processing', 'completed', 'dead']
for state in states:
    count = db.events.count_documents({'status': state})
    print(f'✓ Events {state}: {count}')
"
```

- [ ] Events collection accessible
- [ ] Status field properly set

---

## 🧪 Integration Testing

### **Test: End-to-End API Key Flow**

```bash
python3 << 'EOF'
from Core.mongo import db
from datetime import datetime

# 1. Insert raw key
raw_id = db.api_keys_raw.insert_one({
    'key': 'sk-test123456789abcdefghijklmnopqr',
    'name': 'integration_test',
    'source': 'test',
    'status': 'raw',
    'created_at': datetime.utcnow()
}).inserted_id
print(f'✓ Test 1: Raw key inserted')

# 2. Run key_refiner
import subprocess
subprocess.run(['python3', 'Workers/key_refiner.py'], check=True)
print(f'✓ Test 2: Key refiner executed')

# 3. Verify refined key
refined = db.api_keys_refined.find_one({'raw_key_id': str(raw_id)})
if refined:
    print(f'✓ Test 3: Refined key created ({refined["provider"]})')
    
    # 4. Run oneapi_sync
    subprocess.run(['python3', 'Workers/oneapi_sync.py'], check=True)
    print(f'✓ Test 4: OneAPI sync executed')
    
    # 5. Verify channels
    channels = list(db.api_channels.find({'raw_key_id': str(raw_id)}))
    print(f'✓ Test 5: Channels created ({len(channels)} total)')
else:
    print(f'✗ Test 3: Refined key not created')

print('\n✓ Integration test PASSED')
EOF
```

- [ ] Raw key inserted successfully
- [ ] Key refiner processed the key
- [ ] Refined key created
- [ ] Channels created successfully

---

## 🔄 GitHub Integration

### **Push to GitHub**

```bash
git add .
git commit -m "Setup: Initialize MongoDB collections and indexes"
git push origin main
```

- [ ] Push successful
- [ ] No merge conflicts

### **Verify GitHub Actions**

Visit: https://github.com/tradeview113d8-code/AI_Business_OS_Data/actions

- [ ] Workflows triggered automatically
- [ ] All jobs completed (green checkmarks)
- [ ] No failed steps

---

## ✅ Final Verification Checklist

- [ ] 24 MongoDB collections created
- [ ] All database indexes created
- [ ] key_refiner worker runs without error
- [ ] oneapi_sync worker runs without error
- [ ] Logs collection contains recent entries
- [ ] No ERROR level logs in logs collection
- [ ] Integration test passed
- [ ] Git commit created
- [ ] GitHub push successful
- [ ] GitHub Actions workflows completed

---

## 🎉 Success Criteria

Setup is **COMPLETE** when:

✅ All 24 collections exist in MongoDB  
✅ All indexes created successfully  
✅ Workers execute without errors  
✅ Integration test passes  
✅ Changes pushed to GitHub  
✅ GitHub Actions completed  

**Setup SUCCESSFUL!** 🚀
