import discord
from discord.ext import commands
import logging
import time
from typing import Any, Dict, List

log = logging.getLogger("StaffListener")

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động quét và tìm biến kết nối Database đang hoạt động trên bot"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []

class StaffListenerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bộ nhớ tạm lưu danh sách mốc thời gian của các lượt reply: { staff_id: [time1, time2, ...] }
        self.reply_tracker: Dict[int, List[float]] = {}
        
        # Mốc giới hạn số tin nhắn reply để kích hoạt thông báo
        self.threshold = 10
        
        # Khung thời gian giới hạn: 10 phút = 600 giây
        self.time_window = 600.0

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
                        reminder_text = (
                            f"Nếu bạn thấy {display_role} <@{staff_id}> nhiệt tình, "
                            f"hãy đừng ngần ngại bỏ ra 1 phút sử dụng lệnh `y!menu` chọn đến "
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

async def setup(bot):
    await bot.add_cog(StaffListenerCog(bot))