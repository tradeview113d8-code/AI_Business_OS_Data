import time
import os
import asyncio
from datetime import datetime, timezone
from Core.base_worker import BaseWorker
from Core.event_worker import EventWorker
from Core.mongo import db
from playwright.async_api import async_playwright

class SocialValidatorWorker(EventWorker):
    """
    Worker Tầng 1: Chịu trách nhiệm kiểm định tài khoản MXH (Facebook, TikTok, v.v.).
    Sử dụng Playwright Stealth cơ bản để quét trạng thái profile mà không bị block.
    """
    def __init__(self):
        super().__init__("social_validator")
        self.interested_events = ["SOCIAL_ACCOUNT_RAW_ADDED", "TEST_SOCIAL_ACCOUNT"]

    async def validate_profile_stealth(self, account_doc: dict) -> str:
        """
        Khởi chạy trình duyệt Playwright ngầm giả lập vân tay người dùng để kiểm tra profile công khai.
        Giải quyết triệt để vấn đề chặn bot từ các nền tảng lớn.
        """
        platform = account_doc.get("platform", "facebook")
        profile_url = account_doc.get("profile_url", "")
        proxy_config = account_doc.get("proxy", None) # Đọc cấu hình proxy riêng biệt nếu có

        if not profile_url:
            return "dead"

        async with async_playwright() as p:
            browser_kwargs = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            }
            # Tích hợp Proxy động cấp phần cứng mạng nếu dự án yêu cầu định biên
            if proxy_config and "url" in proxy_config:
                browser_kwargs["proxy"] = {"server": proxy_config["url"]}
            elif os.getenv("PROXY_DEAD_TEST"): # Mối nguy khi thiếu proxy
                return "proxy_dead"

            try:
                print(f"🌐 [PLAYWRIGHT] Đang trinh sát tàng hình profile {platform}: {profile_url}")
                browser = await p.chromium.launch(**browser_kwargs)
                
                # Giả lập User-Agent chuẩn thiết bị di động cao cấp tránh bị nghi ngờ
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                # Điều hướng an toàn với timeout 30 giây chống treo luồng mạng
                response = await page.goto(profile_url, timeout=30000, wait_until="domcontentloaded")
                
                if not response or response.status == 404:
                    await browser.close()
                    return "dead"
                
                content = await page.content()
                await browser.close()

                # Phân tích dấu hiệu nhận biết trạng thái tài khoản từ phản hồi vật lý
                content_lower = content.lower()
                if "checkpoint" in content_lower or "bị khóa" in content_lower or "secure" in content_lower:
                    return "checkpoint"
                if "not found" in content_lower or "trang này không hiển thị" in content_lower:
                    return "dead"

                return "live"

            except Exception as e:
                print(f"⚠️ [PLAYWRIGHT] Tai nạn khi cào dữ liệu trình duyệt: {e}")
                return "dead"

    def process_event(self, event: dict):
        """Luồng xử lý nghiệp vụ chính đồng bộ với Outbox Pattern"""
        payload = event["payload"]
        account_id = payload.get("account_id")
        
        print(f"🚀 [SOCIAL_VALIDATOR] Tiếp nhận kiểm tra tài khoản ID: {account_id}")
        
        account_doc = db.social_accounts.find_one({"account_id": account_id})
        if not account_doc:
            print(f"⚠️ [SOCIAL_VALIDATOR] Không tìm thấy dữ liệu cho Account ID: {account_id}")
            return

        # Playwright chạy trên cơ chế Async, ta cần bọc luồng đồng bộ bằng event loop
        loop = asyncio.get_event_loop()
        status = loop.run_until_complete(self.validate_profile_stealth(account_doc))
        
        now = datetime.now(timezone.utc)
        
        # Thực hiện cập nhật DB và phát Event nguyên tử trong 1 Transaction đơn lẻ
        with db.client.start_session() as session:
            with session.start_transaction():
                if status == "live":
                    db.social_accounts.update_one(
                        {"account_id": account_id},
                        {"$set": {"status": "live", "last_validated": now, "checkpoint_details": None}},
                        session=session
                    )
                    db.outbox_events.insert_one({
                        "event_type": "SOCIAL_ACCOUNT_LIVE",
                        "publisher": self.name,
                        "payload": {"account_id": account_id, "platform": account_doc["platform"]},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"✅ [SOCIAL_VALIDATOR] Tài khoản {account_id} hoàn toàn KHỎE MẠNH.")
                    
                elif status == "checkpoint":
                    db.social_accounts.update_one(
                        {"account_id": account_id},
                        {"$set": {"status": "checkpoint", "last_validated": now, "checkpoint_details": "Stealth login detected check"}},
                        session=session
                    )
                    db.outbox_events.insert_one({
                        "event_type": "SOCIAL_CHECKPOINT",
                        "publisher": self.name,
                        "payload": {"account_id": account_id, "platform": account_doc["platform"], "checkpoint_type": "verify"},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"⚠️ [SOCIAL_VALIDATOR] Tài khoản {account_id} dính CHECKPOINT.")
                    
                elif status == "proxy_dead":
                    db.outbox_events.insert_one({
                        "event_type": "PROXY_DEAD",
                        "publisher": self.name,
                        "payload": {"account_id": account_id, "proxy_url": account_doc.get("proxy", {}).get("url")},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"🚨 [SOCIAL_VALIDATOR] Đầu rò rỉ mạng: Proxy của tài khoản {account_id} ĐÃ CHẾT.")
                    
                else: # dead
                    db.social_accounts.update_one(
                        {"account_id": account_id},
                        {"$set": {"status": "dead", "last_validated": now}},
                        session=session
                    )
                    db.outbox_events.insert_one({
                        "event_type": "SOCIAL_ACCOUNT_DEAD",
                        "publisher": self.name,
                        "payload": {"account_id": account_id, "reason": "Profile link unreachable"},
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": now,
                        "next_retry_at": now,
                        "claim_timeout": 300
                    }, session=session)
                    print(f"❌ [SOCIAL_VALIDATOR] Tài khoản {account_id} ĐÃ TỪ TRẦN.")

    def run_daemon_loop(self):
        """Vòng lặp kéo Outbox có cấu trúc bảo vệ đa tiến trình"""
        print(f"🤖 Worker {self.name} đã thức giấc, đang tuần tra Outbox mạng xã hội...")
        self.start_heartbeat() # Báo nhịp tim lên Redis ngầm
        
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
                    "claim_timeout": now + os.timedelta(minutes=5)
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
    worker = SocialValidatorWorker()
    worker.run_daemon_loop()
