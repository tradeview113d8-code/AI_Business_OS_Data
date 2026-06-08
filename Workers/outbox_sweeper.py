import time
from datetime import datetime, timezone
from Core.base_worker import BaseWorker
from Core.mongo import db

class OutboxSweeper(BaseWorker):
    """
    Hệ thống tuần tra Outbox: Phát hiện các event bị kẹt ở trạng thái 'processing'
    quá thời gian quy định (claim_timeout) hoặc các event 'pending' đến hạn retry.
    Tự động hồi sinh sự kiện để đảm bảo tính kỷ luật At-least-once Delivery.
    """
    def __init__(self):
        super().__init__("outbox_sweeper")

    def sweep_stale_events(self):
        now = datetime.now(timezone.utc)
        print("📦 [OUTBOX_SWEEPER] Đang kiểm tra các sự kiện bị kẹt...")
        
        # 1. Thu hồi các sự kiện bị giam cầm quá lâu (Processing nhưng quá hạn claim_timeout)
        stale_processing_events = db.outbox_events.find({
            "status": "processing",
            "claim_timeout": {"$lte": now}
        })
        
        for event in stale_processing_events:
            retry_count = event.get("retry_count", 0) + 1
            if retry_count >= 3:
                # Trục xuất thẳng vào bảng Dead Letter nếu cạn lượt cứu hộ
                db.dead_events.insert_one({
                    "original_event": event,
                    "error": "Claim timeout exceeded maximum retries",
                    "failed_at": now
                })
                db.outbox_events.update_one({"_id": event["_id"]}, {"$set": {"status": "dead"}})
                print(f"💀 [OUTBOX_SWEEPER] Sự kiện {event.get('event_type')} vượt giới hạn retry. Đã đưa vào Dead Letter.")
            else:
                # Trả tự do về trạng thái pending để worker khác nhặt lại
                db.outbox_events.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"status": "pending", "claimed_by": None}, "$inc": {"retry_count": 1}}
                )
                print(f"🔄 [OUTBOX_SWEEPER] Đã giải phóng sự kiện kẹt: {event.get('event_type')}")

    def run_cron_loop(self):
        print("🤖 Outbox Sweeper đã trực chiến. Chu kỳ tuần tra: 30 giây.")
        while True:
            try:
                self.sweep_stale_events()
            except Exception as e:
                print(f"❌ [OUTBOX_SWEEPER] Lỗi hệ thống: {e}")
            time.sleep(30)

if __name__ == "__main__":
    sweeper = OutboxSweeper()
    sweeper.run_cron_loop()
