import os

def is_admin(user_id):
    # Lấy ID từ cấu hình Render
    admin_id_env = os.environ.get("ADMIN_ID", "")
    
    # Ép kiểu cả 2 về chuỗi văn bản (String) để so sánh tuyệt đối
    return str(user_id).strip() == str(admin_id_env).strip()
    
