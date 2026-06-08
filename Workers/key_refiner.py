import time
import os
from datetime import datetime, timezone
from Core.base_worker import BaseWorker
from Core.event_worker import EventWorker
from Core.mongo import db
from Core.config import MASTER_KEY
import litellm

class KeyRefinerWorker(EventWorker):
    """
    Worker Tầng 1: Chịu trách nhiệm giải mã, kiểm tra và tinh luyện API Key[cite: 410, 442].
    Vận hành dưới dạng Daemon consumer dài hạn hỗ trợ Graceful Shutdown[cite: 541, 579].
    """
    def __init__(self):
        super().__init__("key_refiner")
        # Danh sách các sự kiện mà worker này quan tâm [cite: 548]
        self.interested_events = ["API_KEY_RAW_ADDED"]
        
    def decrypt_key(self, encrypted_key: str) -> str:
        """
        Mô phỏng giải mã API Key an toàn trong bộ nhớ RAM bằng MASTER_KEY[cite: 446].
        Trong thực tế production, đoạn này sẽ dùng cryptography.fernet.
        """
        if encrypted_key.startswith("enc_"):
            return encrypted_key.replace("enc_", "")
        return encrypted_key

    def validate_and_refine(self, key_doc: dict) -> str:
        """
        Gọi trực tiếp litellm để kiểm tra tính hợp lệ của Key.
        Phân loại chính xác các trạng thái: live, dead, hoặc quota_exceeded[cite: 453, 454, 455].
        """
        raw_key = self.decrypt_key(key_doc["encrypted_key"])
        provider = key_doc.get("provider", "openai")
        
        # Cấu hình tham số kỷ luật cho litellm client [cite: 449, 450]
        litellm.drop_params = True
        litellm.num_retries = 3
        
        try:
            print(f"🔍 [LITELLM] Đang kiểm tra sức khỏe của Key: {key_doc['name']}...")
            # Sử dụng model check giá rẻ nhất của từng nhà cung cấp để test nghiệm thu
            test_model = "gpt-3.5-turbo" if provider == "openai" else "gemini/gemini-pro"
            
            # Thực hiện cuộc gọi mồi để kiểm định trạng thái vật lý của Key
            litellm.completion(
                model=test_model,
                messages=[{"role": "user", "content": "ping"}],
                api_key=raw_key,
                timeout=10
            )
            return "live"
        except litellm.exceptions.BudgetExceededError:
            return "quota_exceeded"
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "limit" in error_msg or "credit" in error_msg:
                return "quota_exceeded"
            return "dead"

    def process_event(self, event: dict):
        """Logic xử lý tuần tự khi nhặt được Event từ Outbox [cite: 558]"""
        payload = event["payload"]
        key_id = payload.get("key_id")
        
        print(f"🚀 [KEY_REFINER] Đang xử lý tinh luyện cho Key ID: {key_id}")
        
        # Truy vấn dữ liệu gốc từ bảng raw_api_keys [cite: 67]
        key_doc = db.raw_api_keys.find_one({"key_id": key_id})
        if not key_doc:
            print(f"⚠️ [KEY_REFINER] Không tìm thấy bản ghi cho Key ID: {key_id}")
            return

        # Thực hiện kiểm định chất lượng nhiên liệu đầu vào
        status = self.validate_and_refine(key_doc)
        now = datetime.now(timezone.utc)
        
        # Mở một phiên kết nối cô lập (Session) để ghi nhận kết quả nguyên tử vào DB
        with db.client.start_session() as session:
            with session.start_transaction():
                if status == "live":
                    # Lưu trữ thông tin key sạch vào collection refined_api_keys [cite: 416, 453]
                    db.refined_api_keys.update_one(
                        {"encrypted_key": key_doc["encrypted_key"]},
                        {"$set": {
                            "name": key_doc["name"],
                            "provider": key_doc.get("provider", "openai"),
                            "health_status": "live",
                            "last_check": now,
                            "models": ["gpt-3.5-turbo", "gpt-4", "claude-3"]
                        }},
                        upsert=True,
                        session=session
                    )
                    # Ghi nhận sự kiện Hot-reload để thông báo cho các tầng xử lý LLM [cite: 456]
                    db.outbox_events.insert_one({
                        "event_type": "LITELLM_ROUTER_RELOAD",
                        "publisher": self.name,
                        "payload": {},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"✅ [KEY_REFINER] Key {key_doc['name']} HỢP LỆ. Đã chuyển sang trạng thái refined.")
                
                elif status == "quota_exceeded":
                    # Xử lý khi cạn hạn mức tài chính [cite: 455]
                    db.refined_api_keys.update_one(
                        {"encrypted_key": key_doc["encrypted_key"]},
                        {"$set": {"health_status": "quota_exceeded", "last_check": now}},
                        session=session
                    )
                    db.outbox_events.insert_one({
                        "event_type": "API_KEY_QUOTA_EXCEEDED",
                        "publisher": self.name,
                        "payload": {"key_id": key_id},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"⚠️ [KEY_REFINER] Key {key_doc['name']} đã hết hạn mức (Quota Exceeded).")
                
                else:  # status == "dead"
                    # Thu hồi và cách ly những key đã chết hoàn toàn vào bảng tử sĩ [cite: 417, 454]
                    db.dead_api_keys.insert_one({
                        "encrypted_key": key_doc["encrypted_key"],
                        "name": key_doc["name"],
                        "reason": "Authentication failed / Invalid token",
                        "dead_at": now
                    }, session=session)
                    
                    db.outbox_events.insert_one({
                        "event_type": "API_KEY_DEAD",
                        "publisher": self.name,
                        "payload": {"key_id": key_id, "reason": "Auth Failed"},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"❌ [KEY_REFINER] Key {key_doc['name']} ĐÃ CHẾT. Đã cách ly.")

    def run_daemon_loop(self):
        """Vòng lặp kéo dữ liệu từ Outbox chủ động (Daemon Worker) [cite: 541, 542]"""
        print(f"🤖 Worker {self.name} đã thức giấc, đang tuần tra Outbox_events...")
        self.start_heartbeat() # Kích hoạt nhịp đập tim độc lập gửi lên Redis [cite: 577]
        
        wait = 1
        while not self.shutdown_requested: # Kiểm tra cờ Graceful Shutdown liên tục [cite: 545, 579]
            now = datetime.now(timezone.utc)
            
            # Sử dụng find_one_and_update để tranh đoạt event một cách an toàn đa tiến trình [cite: 547]
            event = db.outbox_events.find_one_and_update(
                {
                    "status": "pending",
                    "event_type": {"$in": self.interested_events},
                    "next_retry_at": {"$lte": now}
                },
                {"$set": {
                    "status": "processing",
                    "claimed_by": self.instance_id,
                    "claimed_at": now,
                    "claim_timeout": now + os.timedelta(minutes=5) # 5 phút cho T1 [cite: 549, 576]
                }},
                sort=[("created_at", 1)] # Đảm bảo tính tuần tự thời gian FIFO [cite: 551]
            )
            
            if not event:
                time.sleep(wait)
                wait = min(10, wait * 2) # Exponential Backoff tránh nghẽn DB [cite: 554]
                continue
                
            wait = 1
            try:
                self.process_event(event)
                # Commit trạng thái đã xử lý xong thành công tuyệt đối [cite: 559]
                db.outbox_events.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}}
                )
            except Exception as e:
                # Cơ chế xử lý khi xảy ra tai nạn bất thường [cite: 560]
                retry_count = event.get("retry_count", 0) + 1
                if retry_count >= event.get("max_retry", 3):
                    # Đẩy thẳng vào danh sách đen cố định nếu cạn lượt thử lại [cite: 562, 563, 564, 565]
                    db.dead_events.insert_one({"original_event": event, "error": str(e), "failed_at": datetime.now(timezone.utc)})
                    db.outbox_events.update_one({"_id": event["_id"]}, {"$set": {"status": "dead"}})
                else:
                    # Trả lại quyền pend để chờ lượt bảo hộ kế tiếp [cite: 568]
                    db.outbox_events.update_one(
                        {"_id": event["_id"]},
                        {"$inc": {"retry_count": 1}, "$set": {"status": "pending", "claimed_by": None}}
                    )
        
        self.stop()

if __name__ == "__main__":
    worker = KeyRefinerWorker()
    worker.run_daemon_loop()
