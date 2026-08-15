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
    log.error("Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
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


async def get_active_boosts(bot: Any, discord_id: str) -> dict:
    """Lấy danh sách các hiệu ứng đang kích hoạt, tự động lọc những cái hết hạn."""
    row = await fetchrow_db(bot, "SELECT active_boosts FROM event_profiles WHERE discord_id = $1", str(discord_id))
    if not row: return {}
    
    import json
    import time
    try:
        raw = row["active_boosts"]
        boosts = json.loads(raw) if isinstance(raw, str) else raw
    except:
        return {}
        
    now = time.time()
    valid_boosts = {k: v for k, v in boosts.items() if v.get("expires_at", 0) > now}
    return valid_boosts


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
            # ── BẢNG ANTI-SPAM MEDIA ───────────────────────────────────
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS media_mutes (
                    discord_id BIGINT PRIMARY KEY,
                    expire_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
            ''')

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
                    active_boosts JSONB DEFAULT '{}'::jsonb,
                    last_reset_date DATE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
                    
                    -- Phục vụ hệ thống Ngân Hàng (Vay nợ)
                    debt FLOAT DEFAULT 0.0,
                    last_interest_date DATE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
                    is_locked BOOLEAN DEFAULT FALSE,
                    negative_streak INT DEFAULT 0
                );
            ''')
            # Index phục vụ cho lệnh đua top ketop cực nhanh
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_event_leaderboard ON event_profiles (total_earned DESC);
            ''')
            
            # Khắc phục/chuyển đổi kiểu dữ liệu cũ (BIGINT -> FLOAT) nếu cần
            try:
                await conn.execute('''
                    ALTER TABLE event_profiles ALTER COLUMN points TYPE FLOAT USING points::double precision;
                    ALTER TABLE event_profiles ALTER COLUMN total_earned TYPE FLOAT USING total_earned::double precision;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS farm_data JSONB DEFAULT '{"slots": 3, "crops": {}, "inventory": {}}'::jsonb;
                    
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS debt FLOAT DEFAULT 0.0;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS last_interest_date DATE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS negative_streak INT DEFAULT 0;
                    
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS title VARCHAR DEFAULT ' Kẻ Lang Thang';
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS unlocked_titles JSONB DEFAULT '[]'::jsonb;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS marry_to VARCHAR;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS stats JSONB DEFAULT '{"quests": 0, "crops": 0, "jails": 0, "works": 0, "mines": 0, "fishes": 0}'::jsonb;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS achievements JSONB DEFAULT '[]'::jsonb;
                ''')
                
                # ── BẢNG MỚI: MARRIAGES (HỆ THỐNG CẶP ĐÔI) ──────────────────
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS marriages (
                        id SERIAL PRIMARY KEY,
                        user1_id VARCHAR UNIQUE NOT NULL,
                        user2_id VARCHAR UNIQUE NOT NULL,
                        marry_date TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                        intimacy_points FLOAT DEFAULT 0.0,
                        ring_id INT DEFAULT 31,
                        promise_text TEXT,
                        pet_type VARCHAR,
                        pet_name VARCHAR,
                        custom_image VARCHAR,
                        pet_level INT DEFAULT 1,
                        last_interaction TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                        couple_task JSONB DEFAULT '{}'::jsonb
                    );
                ''')
                
                await conn.execute('''
                    ALTER TABLE marriages ADD COLUMN IF NOT EXISTS custom_image VARCHAR;
                ''')
                
                # Đảm bảo index
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_marriages_users ON marriages (user1_id, user2_id);
                ''')

                # ── LOOTBOX: Thêm cột luck/pray vào event_profiles ──────────────
                await conn.execute('''
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS luck_points INT DEFAULT 0;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS last_pray TIMESTAMPTZ;
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS lb_buy_cooldown JSONB DEFAULT '{}'::jsonb;
                ''')

                # ── HỆ THỐNG SKILLS ─────────────────────────────────────────────
                await conn.execute('''
                    ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '{}'::jsonb;
                ''')

            except Exception as e:
                log.error(f"Lỗi ALTER TABLE event_profiles hoặc khởi tạo MARRIAGES: {e}", exc_info=True)

            # ── BẢNG LOOTBOX HISTORY ─────────────────────────────────────────────
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS lootbox_history (
                    id SERIAL PRIMARY KEY,
                    discord_id VARCHAR NOT NULL,
                    tier_id INT NOT NULL,
                    drops JSONB NOT NULL DEFAULT '[]'::jsonb,
                    count INT NOT NULL DEFAULT 1,
                    opened_at TIMESTAMPTZ DEFAULT NOW()
                );
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lb_history ON lootbox_history (discord_id, tier_id, opened_at DESC);
            ''')
                
            # Tạo bảng user_tasks (Nhiệm vụ Ngày/Tuần/Sự kiện)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_tasks (
                    discord_id BIGINT PRIMARY KEY,
                    daily_tasks JSONB DEFAULT '{"assigned_date": null, "tasks": {}}'::jsonb,
                    weekly_tasks JSONB DEFAULT '{"assigned_date": null, "tasks": {}}'::jsonb,
                    quests JSONB DEFAULT '{}'::jsonb
                );
            ''')
            
            # Bảng lưu trữ lịch sử gift code
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS gift_codes_history (
                    discord_id VARCHAR NOT NULL,
                    code_name VARCHAR NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                    PRIMARY KEY (discord_id, code_name)
                );
            ''')
            
            # Bảng cấu hình bot (dành cho prefix, thiết lập chung)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bot_configs (
                    config_key VARCHAR(50) PRIMARY KEY,
                    config_value TEXT
                );
            ''')
            
            # ── BẢNG VOICE MASTER ────────────────────────────────────────
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS voice_setups (
                    guild_id                  BIGINT PRIMARY KEY,
                    join_to_create_channel_id BIGINT NOT NULL,
                    category_id               BIGINT
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS voice_role_perms (
                    id               SERIAL PRIMARY KEY,
                    guild_id         BIGINT NOT NULL,
                    role_id          BIGINT NOT NULL,
                    can_lock         BOOLEAN NOT NULL DEFAULT FALSE,
                    can_hide         BOOLEAN NOT NULL DEFAULT FALSE,
                    can_change_limit BOOLEAN NOT NULL DEFAULT FALSE,
                    can_change_name  BOOLEAN NOT NULL DEFAULT FALSE,
                    can_transfer     BOOLEAN NOT NULL DEFAULT FALSE,
                    priority         INT     NOT NULL DEFAULT 0,
                    UNIQUE (guild_id, role_id)
                );
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_voice_role_perms_guild
                    ON voice_role_perms (guild_id);
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS active_voice_channels (
                    channel_id BIGINT PRIMARY KEY,
                    guild_id   BIGINT NOT NULL,
                    owner_id   BIGINT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')
                );
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_active_voice_guild
                    ON active_voice_channels (guild_id);
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS voice_user_settings (
                    discord_id   BIGINT PRIMARY KEY,
                    channel_name VARCHAR(100),
                    user_limit   INT     NOT NULL DEFAULT 0,
                    is_locked    BOOLEAN NOT NULL DEFAULT FALSE,
                    is_hidden    BOOLEAN NOT NULL DEFAULT FALSE
                );
            ''')

        log.info("Toàn bộ Database (Staff + Event + VoiceMaster) đã được khởi tạo và cấu trúc chuẩn xác!")
        return True
    except Exception as e:
        log.error(f"Lỗi nghiêm trọng khi khởi tạo bảng Database: {e}", exc_info=True)
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
    - is_earned=False: Chỉ cộng vào `points` (tiêu xài). Dùng cho lệnh Admin kgive hoặc lì xì không tính vào đua top.
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

async def update_event_stat(bot: Any, discord_id: Union[str, int], stat_key: str, amount: int = 1) -> None:
    """Tăng (hoặc giảm) một chỉ số thống kê trong cột stats (JSONB)."""
    uid = str(discord_id)
    await get_or_create_event_profile(bot, uid)
    
    sql = f"""
        UPDATE event_profiles
        SET stats = jsonb_set(
            COALESCE(stats, '{{}}'::jsonb),
            '{{{stat_key}}}',
            (COALESCE((stats->>'{stat_key}')::int, 0) + $1)::text::jsonb
        )
        WHERE discord_id = $2;
    """
    await execute_db(bot, sql, amount, uid)

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

async def deduct_total_earned(bot: Any, discord_id: Union[str, int], amount: float) -> bool:
    """Trừ Điểm Tích Lũy (Dùng cho Cửa hàng Sự Kiện). Trả về True nếu thành công, False nếu không đủ."""
    if amount <= 0: return False
    uid = str(discord_id)
    
    sql = '''
        UPDATE event_profiles
        SET total_earned = total_earned - $2
        WHERE discord_id = $1 AND total_earned >= $2;
    '''
    res = await execute_db(bot, sql, uid, amount)
    return res == "UPDATE 1"

async def get_marriage(bot: Any, discord_id: str) -> Optional[Any]:
    """Lấy thông tin kết hôn của user."""
    sql = "SELECT * FROM marriages WHERE user1_id = $1 OR user2_id = $1"
    return await fetchrow_db(bot, sql, discord_id)

async def update_intimacy(bot: Any, discord_id: str, points: int) -> bool:
    """Cộng hoặc trừ DTM."""
    if points == 0: return True
    sql = '''
        UPDATE marriages
        SET intimacy_points = intimacy_points + $2
        WHERE user1_id = $1 OR user2_id = $1;
    '''
    res = await execute_db(bot, sql, discord_id, points)
    return res is not None

async def update_marriage_interaction(bot: Any, discord_id: str) -> None:
    """Cập nhật thời gian tương tác cuối cùng."""
    sql = '''
        UPDATE marriages
        SET last_interaction = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')
        WHERE user1_id = $1 OR user2_id = $1;
    '''
    await execute_db(bot, sql, discord_id)

def check_not_locked():
    """
    Decorator kiểm tra xem người dùng có bị khóa tài khoản do vỡ nợ không.
    Gắn vào các lệnh quan trọng.
    """
    from discord.ext import commands
    
    async def predicate(ctx: commands.Context) -> bool:
        row = await fetchrow_db(ctx.bot, "SELECT is_locked FROM event_profiles WHERE discord_id = $1", str(ctx.author.id))
        if row and row["is_locked"]:
            await ctx.send(f"<:symbol_ban:1537546960003801319> {ctx.author.mention} **Tài khoản của bạn đã bị khóa do vỡ nợ ngân hàng!**\n"
                           f"Vui lòng sử dụng lệnh `{ctx.prefix}trano` để thanh toán nợ và mở khóa.")
            return False
        return True
    return commands.check(predicate)

# =====================================================================
# 5. HỆ THỐNG NHIỆM VỤ (TASK SYSTEM HELPERS)
# =====================================================================

async def get_user_tasks_row(bot: Any, discord_id: Union[str, int]) -> dict:
    """Lấy row của user_tasks, nếu chưa có thì tạo."""
    uid = int(discord_id)
    row = await fetchrow_db(bot, "SELECT * FROM user_tasks WHERE discord_id = $1", uid)
    if not row:
        sql = '''
            INSERT INTO user_tasks (discord_id) VALUES ($1)
            ON CONFLICT (discord_id) DO NOTHING RETURNING *;
        '''
        row = await fetchrow_db(bot, sql, uid)
        if not row:
            row = await fetchrow_db(bot, "SELECT * FROM user_tasks WHERE discord_id = $1", uid)
    
    # Convert asyncpg Record to dict for mutability, keeping string representation for JSONB
    return dict(row) if row else {
        "discord_id": uid,
        "daily_tasks": '{"assigned_date": null, "tasks": {}}',
        "weekly_tasks": '{"assigned_date": null, "tasks": {}}',
        "quests": '{}'
    }

async def update_task_progress(bot: Any, discord_id: Union[str, int], action_type: str, amount: int = 1) -> None:
    """
    Cập nhật tiến độ nhiệm vụ cho user.
    action_type: Chuỗi định danh loại hành động (vd: 'work', 'slots', 'taixiu', 'dice', 'chat', 'voice')
    """
    try:
        uid = int(discord_id)
        row = await get_user_tasks_row(bot, uid)
        
        # Helper parse JSONB
        def _parse(val):
            if isinstance(val, dict): return val
            if isinstance(val, str): return json.loads(val)
            return {}
            
        daily_json = _parse(row.get("daily_tasks"))
        weekly_json = _parse(row.get("weekly_tasks"))
        quests_json = _parse(row.get("quests"))
        
        def _update_dict(tasks_dict) -> bool:
            changed = False
            for tid, tdata in tasks_dict.items():
                if tdata.get("action") == action_type and not tdata.get("completed"):
                    tdata["progress"] += amount
                    if tdata["progress"] >= tdata["target"]:
                        tdata["progress"] = tdata["target"]
                        tdata["completed"] = True
                    changed = True
            return changed

        d_changed = _update_dict(daily_json.get("tasks", {}))
        w_changed = _update_dict(weekly_json.get("tasks", {}))
        q_changed = _update_dict(quests_json)

        if d_changed or w_changed or q_changed:
            sql_update = """
                UPDATE user_tasks 
                SET daily_tasks = $1::jsonb, weekly_tasks = $2::jsonb, quests = $3::jsonb 
                WHERE discord_id = $4
            """
            await execute_db(
                bot, sql_update, 
                json.dumps(daily_json), 
                json.dumps(weekly_json), 
                json.dumps(quests_json), 
                uid
            )
            
    except Exception as e:
        log.error(f"Lỗi update_task_progress cho user {discord_id}: {e}", exc_info=True)
