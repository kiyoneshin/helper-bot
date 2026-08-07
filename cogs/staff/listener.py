import discord
from discord.ext import commands
import logging
import time
from typing import Any, Dict, List

log = logging.getLogger("StaffListener")

from cogs.common.logs import send_staff_log, build_log_nickname_sync

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động quét và tìm biến kết nối Database đang hoạt động trên bot"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []

async def execute_db(bot: Any, sql: str, *args) -> None:
    """Thực thi câu lệnh SQL không trả về kết quả (INSERT/UPDATE/DELETE)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'execute'):
                await db_obj.execute(sql, *args)
                return

class StaffListenerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bộ nhớ tạm lưu danh sách mốc thời gian của các lượt reply: { staff_id: [time1, time2, ...] }
        self.reply_tracker: Dict[int, List[float]] = {}
        
        # Mốc giới hạn số tin nhắn reply để kích hoạt thông báo
        self.threshold = 10
        
        # Khung thời gian giới hạn: 10 phút = 600 giây
        self.time_window = 600.0

    # =========================================================================
    # SỰ KIỆN: ĐẾM LƯỢT REPLY VÀ NHẮC NHỞ VOTE
    # =========================================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.reference and message.reference.message_id:
            try:
                replied_msg = message.reference.cached_message
                if not replied_msg:
                    replied_msg = await message.channel.fetch_message(message.reference.message_id)
                
                if not replied_msg or not replied_msg.author or replied_msg.author.bot:
                    return

                staff_id = replied_msg.author.id
                records = await query_db(self.bot, "SELECT role FROM profiles WHERE discord_id = $1", str(staff_id))
                
                if not records:
                    return
                
                db_role = str(records[0]['role']).lower().strip()
                
                if db_role in ['owner', 'admin', 'recep']:
                    current_time = time.time()
                    
                    # --- Cộng dồn weekly_replies vào DB (real-time, không mất dữ liệu khi bot restart) ---
                    try:
                        await execute_db(
                            self.bot,
                            "UPDATE profiles SET weekly_replies = weekly_replies + 1 WHERE discord_id = $1",
                            str(staff_id)
                        )
                    except Exception as e:
                        log.error(f"Lỗi cập nhật weekly_replies cho {staff_id}: {e}")

                    # --- Bộ đếm trong bộ nhớ tạm để kích hoạt nhắc nhở vote ---
                    # 1. Lấy danh sách các mốc thời gian reply hiện có của Staff
                    timestamps = self.reply_tracker.get(staff_id, [])

                    # 2. Lọc bỏ toàn bộ những mốc thời gian đã cũ vượt quá 10 phút (600 giây)
                    timestamps = [t for t in timestamps if current_time - t <= self.time_window]

                    # 3. Thêm mốc thời gian của lượt reply mới nhất này vào
                    timestamps.append(current_time)

                    # 4. Kiểm tra xem trong khung 10 phút hiện tại đã gom đủ 10 lượt chưa
                    if len(timestamps) >= self.threshold:
                        # Reset danh sách về rỗng để bắt đầu đếm lại chu kỳ mới
                        self.reply_tracker[staff_id] = []
                        
                        display_role = db_role
                        prefix = self.bot.custom_prefix
                        reminder_text = (
                            f"Nếu bạn thấy {display_role} <@{staff_id}> nhiệt tình, "
                            f"hãy đừng ngần ngại bỏ ra 1 phút sử dụng lệnh `{prefix}menu` chọn đến "
                            f"{display_role} để vote cho họ nhé!"
                        )
                        await message.channel.send(reminder_text)
                        log.info(f"Đã gửi nhắc nhở vote cho {display_role} ({staff_id}) sau khi đạt {self.threshold} reply trong {self.time_window}s.")
                    else:
                        # Nếu chưa đủ thì lưu lại danh sách đã lọc vào bộ nhớ
                        self.reply_tracker[staff_id] = timestamps
                        
            except discord.NotFound:
                pass
            except Exception as e:
                log.error(f"Lỗi hệ thống đếm lượt reply: {e}")

    # =========================================================================
    # SỰ KIỆN: TỰ ĐỘNG ĐỒNG BỘ BIỆT DANH (NICKNAME SYNC)
    # =========================================================================
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Chỉ xử lý khi display_name thay đổi
        if before.display_name == after.display_name:
            return

        try:
            # Kiểm tra nhanh: người này có phải Staff trong DB không?
            records = await query_db(
                self.bot,
                "SELECT discord_id FROM profiles WHERE discord_id = $1",
                str(after.id)
            )

            if not records:
                return  # Không phải Staff, bỏ qua

            # Cập nhật display_name mới vào DB
            await execute_db(
                self.bot,
                "UPDATE profiles SET display_name = $1 WHERE discord_id = $2",
                after.display_name,
                str(after.id)
            )
            log.info(
                f"[NicknameSync] Đã đồng bộ tên: {before.display_name!r} → {after.display_name!r} "
                f"cho Staff ID {after.id}"
            )

            # --- Log Audit ---
            log_embed = build_log_nickname_sync(
                discord_id=str(after.id),
                old_name=before.display_name,
                new_name=after.display_name,
            )
            await send_staff_log(self.bot, log_embed)

        except Exception as e:
            log.error(f"[NicknameSync] Lỗi khi đồng bộ tên cho {after.id}: {e}")

async def setup(bot):
    await bot.add_cog(StaffListenerCog(bot))