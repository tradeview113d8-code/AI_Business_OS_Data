import time
import os
import json
from datetime import datetime, timezone, timedelta
from Core.base_worker import BaseWorker
from Core.event_worker import EventWorker
from Core.mongo import db
from Core.redis_client import redis_client, safe_redis_execute
from Core.litellm_client import safe_llm_call

class StrategyGeneratorWorker(EventWorker):
    """
    Worker Tầng 2: Chiến lược gia (Strategy Generator).
    Chỉ chịu trách nhiệm sản xuất Báo cáo Chiến lược từ nhiên liệu sạch của Tầng 1.
    Tuân thủ nghiêm ngặt Kỷ luật v10.1: Tuyệt đối không động chạm tới hunter hay sales.
    """
    def __init__(self):
        super().__init__("strategy_generator")
        # Chỉ lắng nghe sự kiện hoàn thành Phase 1 hoặc lệnh kích hoạt cưỡng bức từ Giám đốc
        self.interested_events = ["PHASE_1_COMPLETED", "FORCE_PHASE2_EARLY"]
        # Đảm bảo model mặc định dùng OpenRouter
        self.default_model = "openrouter/openai/gpt-4o-mini"

    def check_and_reserve_budget(self, project_id: str, cost_limit: float = 0.05) -> bool:
        """
        Kỷ luật tài chính nghiêm ngặt: Kiểm tra và giữ chỗ ngân sách (Budget Reservation).
        Đảm bảo an toàn dòng tiền, chống hiện tượng cạn kiệt tài khoản API bất ngờ.
        """
        budget_key = f"project_budget:{project_id}"
        
        # 1. Kiểm tra trên bộ nhớ tạm Redis trước để tối ưu tốc độ
        current_budget = redis_client.get(budget_key)
        if current_budget and float(current_budget) < cost_limit:
            return False
            
        # 2. Tạo bản ghi đóng băng ngân sách tạm thời với cơ chế TTL 120 giây phòng vệ
        now = datetime.now(timezone.utc)
        try:
            with db.client.start_session() as session:
                with session.start_transaction():
                    # Tạo reservation cách ly dòng tiền vật lý
                    db.budget_reservations.insert_one({
                        "project_id": project_id,
                        "worker_name": self.name,
                        "reserved_amount": cost_limit,
                        "created_at": now
                    }, session=session)
            return True
        except Exception:
            return False

    def process_event(self, event: dict):
        """Logic xử lý nhào nặn bản vẽ chiến lược"""
        payload = event["payload"]
        project_id = payload.get("project_id")
        
        print(f"🚀 [STRATEGY] Tiếp nhận sản xuất bản vẽ chiến lược cho Dự án ID: {project_id}")
        
        # 1. Phòng vệ Path Traversal bằng Regex hỗn hợp
        if not self.validate_project_id(project_id):
            print(f"❌ [STRATEGY] Vi phạm định dạng Project ID: {project_id}")
            return

        # 2. Khóa độc quyền dự án (Per-project Lock) tránh race-condition chạy trùng lặp
        lock_key = f"project_lock:{project_id}:{self.name}"
        if not redis_client.set(lock_key, self.instance_id, ex=300, nx=True):
            print(f"⏳ [STRATEGY] Dự án {project_id} đang được xử lý bởi một instance khác. Bỏ qua.")
            return

        # 3. Kiểm định hạn mức tài chính trước khi bung tải
        if not self.check_and_reserve_budget(project_id):
            print(f"🚨 [STRATEGY] Từ chối xử lý! Dự án {project_id} không đủ định biên ngân sách an toàn.")
            db.sos_queue.insert_one({
                "project_id": project_id,
                "worker_name": self.name,
                "error_message": "Budget reservation failed / Exhausted",
                "status": "pending",
                "created_at": datetime.now(timezone.utc)
            })
            redis_client.delete(lock_key)
            return

        try:
            # 4. Thu thập nhiên liệu sạch từ Tầng 1
            p1_data = db.product_phase_1.find_one({"project_id": project_id})
            raw_prod = db.raw_products.find_one({"project_id": project_id})
            
            if not p1_data or not raw_prod:
                print(f"⚠️ [STRATEGY] Thiếu điều kiện tiên quyết dữ liệu đầu vào cho ID: {project_id}")
                redis_client.delete(lock_key)
                return

            # Khôi phục thông tin cấu hình AI - Đảm bảo dùng OpenRouter
            insights = p1_data.get("refined_insights", {})
            model = raw_prod.get("model_assignment", self.default_model)
            # Nếu model không phải openrouter, ép về openrouter để tránh lỗi key
            if not model.startswith("openrouter/"):
                print(f"⚠️ [STRATEGY] Model {model} không phải OpenRouter, chuyển về {self.default_model}")
                model = self.default_model

            # Thiết lập Prompt tạo khung xương chiến lược kinh doanh thực chiến
            system_prompt = (
                "Bạn là Giám đốc Chiến lược Tăng trưởng tối cao. Dựa trên insight đầu vào, hãy lập kế hoạch thâm nhập "
                "thị trường hoàn chỉnh. Bạn bắt buộc phải trả về định dạng cấu trúc JSON chính xác tuyệt đối gồm: "
                "insights (mảng các chuỗi phân tích sâu), pain_keywords (mảng từ khóa nỗi đau của khách hàng), "
                "value_props (mảng các thông điệp giá trị cốt lõi đánh gục khách hàng)."
            )
            user_prompt = f"Insight nền tảng: {json.dumps(insights)}. Hãy thiết kế bản vẽ chiến lược kinh doanh."

            # Gọi LLM Router an toàn tích hợp json_repair tự vá lỗi cấu trúc
            print(f"🧠 [STRATEGY] Gọi LLM với model: {model}")
            strategy_output = safe_llm_call(model, [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], response_format={"type": "json_object"})

            now = datetime.now(timezone.utc)

            # 5. Thực thi commit dữ liệu nguyên tử vào Bộ tư lệnh Chờ duyệt của Giám đốc
            with db.client.start_session() as session:
                with session.start_transaction():
                    # Ghi nhận báo cáo ở trạng thái pending_approval chờ Sếp bấm nút duyệt trên Telegram
                    db.strategy_reports.update_one(
                        {"project_id": project_id},
                        {"$set": {
                            "project_name": raw_prod.get("project_name"),
                            "status": "pending_approval",
                            "strategy_data": strategy_output,
                            "created_at": now,
                            "updated_at": now
                        }},
                        upsert=True,
                        session=session
                    )
                    
                    # Xóa bỏ lệnh đóng băng ngân sách tạm thời sau khi kết thúc chu kỳ thành công
                    db.budget_reservations.delete_many({"project_id": project_id, "worker_name": self.name}, session=session)
                    
            print(f"✅ [STRATEGY] Đã xuất bản đồ chiến lược thành công cho Dự án {project_id}. Đang chờ duyệt tại T0.")

        except Exception as e:
            print(f"🚨 [STRATEGY] Trục trặc hệ thống xử lý mô hình chiến lược: {e}")
            db.sos_queue.insert_one({
                "project_id": project_id,
                "worker_name": self.name,
                "error_message": f"Execution crash: {str(e)}",
                "status": "pending",
                "created_at": datetime.now(timezone.utc)
            })
        finally:
            # Giải phóng khóa độc quyền để mở đường cho các lượt quét tối ưu kế tiếp
            redis_client.delete(lock_key)

    def run_daemon_loop(self):
        """Vòng lặp tuần tra Outbox hệ thống tầng 2"""
        print(f"🤖 Worker {self.name} (Chiến lược gia) đã trực chiến, chờ lệnh kích nổ...")
        self.start_heartbeat()
        
        wait = 1
        while not self.shutdown_requested:
            now = datetime.now(timezone.utc)
            
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
                    "claim_timeout": now + timedelta(minutes=5)
                }},
                sort=[("created_at", 1)]
            )
            
            if not event:
                time.sleep(wait)
                wait = min(10, wait * 2)
                continue
                
            wait = 1
            try:
                self.process_event(event)
                db.outbox_events.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}}
                )
            except Exception as e:
                retry_count = event.get("retry_count", 0) + 1
                if retry_count >= event.get("max_retry", 3):
                    db.dead_events.insert_one({"original_event": event, "error": str(e), "failed_at": datetime.now(timezone.utc)})
                    db.outbox_events.update_one({"_id": event["_id"]}, {"$set": {"status": "dead"}})
                else:
                    db.outbox_events.update_one(
                        {"_id": event["_id"]},
                        {"$inc": {"retry_count": 1}, "$set": {"status": "pending", "claimed_by": None}}
                    )
        
        self.stop()

if __name__ == "__main__":
    worker = StrategyGeneratorWorker()
    worker.run_daemon_loop()
