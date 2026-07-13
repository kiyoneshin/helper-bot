import logging
import re
from typing import Any, Optional

log = logging.getLogger("StaffDB")

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động tìm biến kết nối DB trên bot"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
                
    log.error("Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
    return []

# =====================================================================
# HÀM BÓC TÁCH ID ĐA NĂNG (MỚI THÊM)
# =====================================================================
def extract_id(target: Optional[str]) -> Optional[str]:
    """Tự động tìm và trích xuất dãy số ID (17-20 chữ số) từ bất kỳ chuỗi đầu vào nào.
    Hỗ trợ tốt: Ping (<@123...>), ID trần (123...), hoặc Link profile Discord.
    """
    if not target:
        return None
    # Tìm chuỗi có từ 17 đến 20 chữ số liên tiếp (Tiêu chuẩn ID của Discord)
    match = re.search(r"\d{17,20}", str(target))
    return match.group(0) if match else None