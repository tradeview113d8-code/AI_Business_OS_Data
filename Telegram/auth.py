import os

def is_admin(user_id):
    admin_id_env = os.environ.get("ADMIN_ID", "")
    return str(user_id).strip() == str(admin_id_env).strip()
    
