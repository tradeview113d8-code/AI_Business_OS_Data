import litellm
import json
from json_repair import repair_json
from Core.mongo import db

# Bật tính năng bỏ qua các lỗi cấu hình nhà cung cấp không quan trọng
litellm.drop_params = True

def get_dynamic_token_buffer(model_name: str, system_prompt: str) -> int:
    """
    Tính toán biên an toàn Token động (Dynamic Buffer): Chừa lại 10% giới hạn mô hình 
    cộng với độ dài của chuỗi system_prompt nhằm chống lỗi quá tải context.
    """
    # Trả về giá trị mặc định cho Phase 0, logic tiktoken đếm thực tế sẽ tích hợp trong T1/T2
    return 4000

def safe_llm_call(model: str, messages: list, response_format=None) -> dict:
    """
    Hàm gọi LLM bọc lớp bảo vệ cao cấp: 
    Tự động bắt lỗi, tích hợp cơ chế sửa mã JSON lỗi bằng thư viện json_repair.
    """
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = litellm.completion(**kwargs)
        raw_text = response.choices[0].message.content

        if response_format and response_format.get("type") == "json_object":
            try:
                # Thử giải mã thuần túy trước
                return json.loads(raw_text)
            except json.JSONDecodeError:
                print("⚠️ [JSON_REPAIR] Phát hiện chuỗi JSON vỡ từ LLM. Đang kích hoạt cứu hộ...")
                # Cứu hộ dữ liệu: Ép vá chuỗi vỡ thành cấu hình JSON hợp lệ
                repaired_text = repair_json(raw_text)
                return json.loads(repaired_text)
        
        return {"text": raw_text}

    except Exception as e:
        print(f"❌ [LITELLM] Lỗi gọi mô hình nghiêm trọng: {e}")
        raise e
