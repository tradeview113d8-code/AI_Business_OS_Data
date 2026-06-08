from datetime import datetime, timezone
from Core.mongo import db

def publish_event(session, event_type: str, publisher: str, payload: dict):
    """
    Ghi dữ liệu sự kiện nguyên tử (Atomic Outbox Pattern) vào MongoDB.
    Bắt buộc phải truyền vào biến 'session' của MongoDB Transaction để đồng bộ dữ liệu.
    """
    event_doc = {
        "event_type": event_type,
        "publisher": publisher,
        "payload": payload,
        "status": "pending",
        "retry_count": 0,
        "created_at": datetime.now(timezone.utc),
        "next_retry_at": datetime.now(timezone.utc),
        "claim_timeout": 300 # Mặc định 5 phút cho T1
    }
    # Ghi thẳng sự kiện vào bảng outbox, chia sẻ chung một phiên khóa mạng an toàn với nghiệp vụ chính
    db.outbox_events.insert_one(event_doc, session=session)
    print(f"📦 [OUTBOX] Đã ghi nhận sự kiện {event_type} từ {publisher}")
