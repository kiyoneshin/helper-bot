import logging
from typing import Any

log = logging.getLogger("StaffDB")

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động tìm biến kết nối DB trên bot (dù tên là db, pool, database hay db_pool)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
                
    log.error("Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
    return []