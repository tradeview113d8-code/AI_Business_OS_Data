import re
from datetime import datetime, timezone

class BaseWorker:
    """
    Lớp trừu tượng (Abstract Core Class) cho mọi Worker trong hệ thống.
    Bắt buộc kiểm tra an toàn định dạng ID để triệt tiêu lỗ hổng bảo mật tấn công thư mục đường dẫn (Path Traversal).
    """
    def __init__(self, name: str):
        self.name = name
        # Rào bảo mật: ID phải là cấu trúc ObjectId 24 chữ số hex HOẶC định dạng chuỗi UUID 36 ký tự
        self.id_pattern = re.compile(r'^[0-9a-fA-F]{24}$|^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

    def validate_project_id(self, project_id: str) -> bool:
        """Trả về True nếu project_id vượt qua bài kiểm tra định dạng an toàn"""
        if not project_id or not isinstance(project_id, str):
            return False
        return bool(self.id_pattern.match(project_id))

    def get_utc_now(self) -> datetime:
        """Chuẩn hóa thời gian Naive Datetime hệ thống theo chuẩn UTC chống lệch múi giờ"""
        return datetime.now(timezone.utc).replace(tzinfo=None)
