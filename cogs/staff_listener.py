import discord
from discord.ext import commands
import logging
from typing import Any, Dict, Optional

log = logging.getLogger("StaffListener")

# =====================================================================
# HÀM TỰ ĐỘNG DÒ TÌM DATABASE TRÊN BOT
# =====================================================================
async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động quét và tìm biến kết nối Database đang hoạt động trên bot"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []

# =====================================================================
# COG LẮNG NGHE SỰ KIỆN REPLY VÀ ĐẾM LƯỢT
# =====================================================================
class StaffListenerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bộ nhớ tạm lưu số lần được reply: { discord_id_của_staff: số_lần_được_reply }
        self.reply_counters: Dict[int, int] = {}
        # Mốc giới hạn tin nhắn reply để kích hoạt thông báo (Bạn có thể sửa thành 10)
        self.threshold = 10

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Bỏ qua nếu tin nhắn là của bot hoặc nhắn tin riêng (DMs)
        if message.author.bot or not message.guild:
            return

        # Kiểm tra xem tin nhắn hiện tại có phải là một hành động Reply hay không
        if message.reference and message.reference.message_id:
            try:
                # Lấy tin nhắn gốc được phản hồi (Kiểm tra trong bộ nhớ cache trước)
                replied_msg = message.reference.cached_message
                if not replied_msg:
                    # Nếu không có trong cache, tải trực tiếp từ API Discord
                    replied_msg = await message.channel.fetch_message(message.reference.message_id)
                
                # Bỏ qua nếu không tìm thấy tin nhắn gốc hoặc người được reply là bot
                if not replied_msg or not replied_msg.author or replied_msg.author.bot:
                    return

                staff_id = replied_msg.author.id

                # Truy vấn vào Database xem ID người được reply này có phải là Staff không và giữ role gì
                records = await query_db(self.bot, "SELECT role FROM profiles WHERE discord_id = $1", str(staff_id))
                
                # Nếu không có tên trong cơ sở dữ liệu profiles thì bỏ qua
                if not records:
                    return
                
                # Lấy chức vụ từ DB và chuẩn hóa viết thường, xóa khoảng trắng
                db_role = str(records[0]['role']).lower().strip()
                
                # Chỉ xử lý nếu nhân sự đó thuộc các nhóm role quy định
                if db_role in ['owner', 'admin', 'recep']:
                    # Cộng dồn 1 lượt vào bộ đếm của Staff này
                    current_count = self.reply_counters.get(staff_id, 0) + 1
                    self.reply_counters[staff_id] = current_count

                    # Khi số lượt reply đạt đúng mốc quy định (ví dụ 10 lần)
                    if current_count >= self.threshold:
                        # Reset bộ đếm về 0 để bắt đầu một chu kỳ đếm 10 lần mới
                        self.reply_counters[staff_id] = 0
                        
                        # Tự động chọn chữ hiển thị tương ứng theo nhóm
                        display_role = db_role
                        
                        # Gửi tin nhắn nhắc nhở tự động điều hướng bằng mũi tên
                        reminder_text = (
                            f"Nếu bạn thấy {display_role} <@{staff_id}> nhiệt tình, "
                            f"hãy đừng ngần ngại bỏ ra 1 phút sử dụng lệnh `y!menu` chọn đến "
                            f"{display_role} để vote cho họ nhé!"
                        )
                        await message.channel.send(reminder_text)
                        log.info(f"Đã gửi nhắc nhở vote cho {display_role} với ID {staff_id} sau khi đạt mốc reply.")
                        
            except discord.NotFound:
                # Tin nhắn gốc đã bị xóa trước khi bot kịp đọc, bỏ qua
                pass
            except Exception as e:
                log.error(f"Lỗi hệ thống đếm lượt reply: {e}")

async def setup(bot):
    await bot.add_cog(StaffListenerCog(bot))