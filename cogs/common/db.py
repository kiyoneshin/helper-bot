import logging
import re
import json
from typing import Any, Optional, Union
from datetime import datetime, timedelta, timezone

log = logging.getLogger("StaffDB")

# Múi giờ chuẩn server Angelic (UTC+7 Ho Chi Minh)
UTC7 = timezone(timedelta(hours=7))

# =====================================================================
# 1. BỘ HÀM TÌM KIẾM & THỰC THI TRUY VẤN DATABASE ĐA NĂNG
# =====================================================================
def _get_db_pool(bot: Any) -> Any:
    """Hàm nội bộ tìm kiếm biến connection pool trên object bot."""
    possible_names = ['db_pool', 'pool', 'db', 'database', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch') or hasattr(db_obj, 'execute'):
                return db_obj
    log.error("❌ Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
    return None

async def query_db(bot: Any, sql: str, *args) -> list:
    """Lấy danh sách nhiều bản ghi (Dùng cho BXH, quét lịch sử...). Trả về List[Record]."""
    pool = _get_db_pool(bot)
    if not pool: return []
    try:
        return await pool.fetch(sql, *args)
    except Exception as e:
        log.error(f"Lỗi query_db [{sql[:50]}...]: {e}", exc_info=True)
        return []

async def fetchrow_db(bot: Any, sql: str, *args) -> Optional[Any]:
    """Lấy đúng 1 bản ghi duy nhất (Dùng để check 1 Profile người dùng). Trả về Record hoặc None."""
    pool = _get_db_pool(bot)
    if not pool: return None
    try:
        return await pool.fetchrow(sql, *args)
    except Exception as e:
        log.error(f"Lỗi fetchrow_db [{sql[:50]}...]: {e}", exc_info=True)
        return None

async def fetchval_db(bot: Any, sql: str, *args) -> Any:
    """Lấy 1 giá trị đơn lẻ (Dùng để đếm COUNT, lấy số dư điểm...). Trả về Value hoặc None."""
    pool = _get_db_pool(bot)
    if not pool: return None
    try:
        return await pool.fetchval(sql, *args)
    except Exception as e:
        log.error(f"Lỗi fetchval_db [{sql[:50]}...]: {e}", exc_info=True)
        return None

async def execute_db(bot: Any, sql: str, *args) -> Optional[str]:
    """Thực thi lệnh thay đổi dữ liệu (INSERT, UPDATE, DELETE). Trả về Status string (vd: 'UPDATE 1')."""
    pool = _get_db_pool(bot)
    if not pool: return None
    try:
        return await pool.execute(sql, *args)
    except Exception as e:
        log.error(f"Lỗi execute_db [{sql[:50]}...]: {e}", exc_info=True)
        return None


# =====================================================================
# 2. HÀM BÓC TÁCH ID ĐA NĂNG
# =====================================================================
def extract_id(target: Optional[str]) -> Optional[str]:
    """Tự động tìm và trích xuất dãy số ID (17-20 chữ số) từ bất kỳ chuỗi đầu vào nào.
    Hỗ trợ tốt: Ping (<@123...>), ID trần (123...), hoặc Link profile Discord.
    """
    if not target:
        return None
    match = re.search(r"\d{17,20}", str(target))
    return match.group(0) if match else None


# =====================================================================
# 3. HÀM KHỞI TẠO TẤT CẢ BẢNG (GỌI TỪ MAIN.PY SETUP_HOOK)
# =====================================================================
async def init_all_tables(bot: Any) -> bool:
    """Tự động tạo các bảng cho cả hệ thống Staff BQT lẫn Sự Kiện Event."""
    pool = _get_db_pool(bot)
    if not pool:
        log.error("Không thể khởi tạo bảng vì thiếu kết nối DB!")
        return False

    try:
        async with pool.acquire() as conn:
            # ── BẢNG 1 & 2: HỆ THỐNG STAFF CŨ ──────────────────────────
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    discord_id VARCHAR PRIMARY KEY,
                    role VARCHAR, 
                    display_name VARCHAR,
                    description TEXT,
                    contact VARCHAR,
                    tags JSONB DEFAULT '[]'::jsonb,
                    photos JSONB DEFAULT '[]'::jsonb,
                    votes JSONB DEFAULT '{}'::jsonb,
                    rating NUMERIC DEFAULT 0.0,
                    weekly_replies INT DEFAULT 0
                );
            ''')
            await conn.execute('''
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS weekly_replies INT DEFAULT 0;
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS staff_message_logs (
                    id SERIAL PRIMARY KEY,
                    discord_id VARCHAR NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                );
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_msg_logs_discord_sent ON staff_message_logs (discord_id, sent_at);
            ''')

            # ── BẢNG 3: HỆ THỐNG SỰ KIỆN EVENT MỚI (EVENT_PROFILES) ────
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS event_profiles (
                    discord_id VARCHAR PRIMARY KEY,
                    points FLOAT DEFAULT 0.0,
                    total_earned FLOAT DEFAULT 0.0,
                    p2w_multiplier NUMERIC(3, 2) DEFAULT 1.00,
                    
                    -- Phục vụ cày Chat & Combo Cooldown
                    daily_chat_count INT DEFAULT 0,
                    last_chat_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                    current_streak INT DEFAULT 0,
                    
                    -- Phục vụ cày Voice (Tối đa 32 mốc/ngày = 8h)
                    daily_voice_intervals INT DEFAULT 0,
                    last_voice_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                    
                    -- Kho đồ (Thẻ bỏ tù, bảo hiểm...) & Ngày reset
                    inventory JSONB DEFAULT '{}'::jsonb,
                    farm_data JSONB DEFAULT '{"slots": 3, "crops": {}, "inventory": {}}'::jsonb,
                    last_reset_date DATE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                );
            ''')
            # Index phục vụ cho lệnh đua top y!etop cực nhanh
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_event_leaderboard ON event_profiles (total_earned DESC);
            ''')
            
            # Khắc phục/chuyển đổi kiểu dữ liệu cũ (BIGINT -> FLOAT) nếu cần
            try:
                await conn.execute('''
                    ALTER TABLE event_profiles ALTER COLUMN points TYPE FLOAT USING points::double precision;
                    ALTER TABLE event_profiles ALTER COLUMN total_earned TYPE FLOAT USING total_earned::double precision;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS farm_data JSONB DEFAULT '{"slots": 3, "crops": {}, "inventory": {}}'::jsonb;
                ''')
            except Exception as e:
                log.warning(f"Bỏ qua convert type points (có thể đã là FLOAT): {e}")
                
            
        log.info("🌸 Toàn bộ Database (Staff + Event) đã được khởi tạo và cấu trúc chuẩn xác!")
        return True
    except Exception as e:
        log.error(f"❌ Lỗi nghiêm trọng khi khởi tạo bảng Database: {e}", exc_info=True)
        return False


# =====================================================================
# 4. CÁC HÀM TIỆN ÍCH RIÊNG CHO SỰ KIỆN EVENT (EVENT CRUD HELPERS)
# =====================================================================

async def get_or_create_event_profile(bot: Any, discord_id: Union[str, int]) -> Optional[Any]:
    """Lấy thông tin event của 1 user. Nếu chưa có trong DB, tự động tạo mới với 0 điểm."""
    uid = str(discord_id)
    # Bước 1: Kiểm tra reset ngày trước khi lấy dữ liệu
    await check_and_reset_daily(bot, uid)
    
    # Bước 2: Truy vấn profile
    row = await fetchrow_db(bot, "SELECT * FROM event_profiles WHERE discord_id = $1", uid)
    if row:
        return row
        
    # Bước 3: Nếu chưa tồn tại, tạo mới
    sql_insert = '''
        INSERT INTO event_profiles (discord_id) VALUES ($1)
        ON CONFLICT (discord_id) DO NOTHING
        RETURNING *;
    '''
    return await fetchrow_db(bot, sql_insert, uid)

async def check_and_reset_daily(bot: Any, discord_id: Union[str, int]) -> None:
    """Kiểm tra nếu đã sang ngày mới (theo UTC+7), tự động reset bộ đếm chat/voice về 0."""
    uid = str(discord_id)
    sql_reset = '''
        UPDATE event_profiles
        SET daily_chat_count = 0,
            daily_voice_intervals = 0,
            last_reset_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
        WHERE discord_id = $1 
          AND last_reset_date < (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    '''
    await execute_db(bot, sql_reset, uid)

async def add_event_points(bot: Any, discord_id: Union[str, int], amount: float, is_earned: bool = True) -> bool:
    """
    Cộng điểm cho user.
    - is_earned=True (Mặc định): Cộng vào cả `points` (tiêu xài) lẫn `total_earned` (đua top). Dùng khi cày chat, voice, thắng game.
    - is_earned=False: Chỉ cộng vào `points` (tiêu xài). Dùng cho lệnh Admin y!give hoặc lì xì không tính vào đua top.
    """
    if amount <= 0: return False
    uid = str(discord_id)
    
    # Đảm bảo user đã có profile trong bảng
    await get_or_create_event_profile(bot, uid)
    
    if is_earned:
        sql = '''
            UPDATE event_profiles
            SET points = points + $2,
                total_earned = total_earned + $2
            WHERE discord_id = $1;
        '''
    else:
        sql = '''
            UPDATE event_profiles
            SET points = points + $2
            WHERE discord_id = $1;
        '''
    res = await execute_db(bot, sql, uid, amount)
    return res is not None

async def deduct_event_points(bot: Any, discord_id: Union[str, int], amount: float) -> bool:
    """Trừ điểm an toàn (Mua đồ shop, đặt cược thua). Trả về True nếu thành công, False nếu không đủ tiền."""
    if amount <= 0: return False
    uid = str(discord_id)
    
    # Sử dụng điều kiện WHERE points >= $2 để tuyệt đối không bao giờ bị âm tiền
    sql = '''
        UPDATE event_profiles
        SET points = points - $2
        WHERE discord_id = $1 AND points >= $2;
    '''
    res = await execute_db(bot, sql, uid, amount)
    # res sẽ có dạng "UPDATE 1" nếu trừ thành công, "UPDATE 0" nếu số dư không đủ
    return res == "UPDATE 1"