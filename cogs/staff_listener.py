import discord
from discord.ext import commands
import logging
import time
from typing import Any, Dict, Optional, Tuple

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
# COG LẮNG NGHE SỰ KIỆN REPLY VÀ ĐẾM LƯỢT THEO KHUNG THỜI GIAN
# =====================================================================
class StaffListenerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bộ nhớ tạm lưu số lần reply và mốc thời gian: { staff_id: (count, last_timestamp) }
        self.reply_tracker: Dict[int, Tuple[int, float]] = {}
        
        # Mốc giới hạn số tin nhắn reply để kích hoạt thông báo
        self.threshold = 10
        
        # Khung thời gian giới hạn: 10 phút = 600 giây
        self.time_window = 600.0

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
                    current_time = time.time()
                    old_count, last_time = self.reply_tracker.get(staff_id, (0, 0.0))

                    # Kiểm tra khoảng cách từ lần reply trước có vượt quá 10 phút (600s) không
                    if current_time - last_time > self.time_window:
                        # Đã quá 10 phút từ lần reply trước -> Reset đếm lại từ số 1
                        current_count = 1
                    else:
                        # Vẫn trong khung 10 phút -> Tiếp tục cộng dồn
                        current_count = old_count + 1

                    # Cập nhật số đếm mới và mốc thời gian mới nhất vào bộ nhớ
                    self.reply_tracker[staff_id] = (current_count, current_time)

                    # Khi số lượt reply đạt đúng mốc quy định (10 lần trong 10 phút)
                    if current_count >= self.threshold:
                        # Reset bộ đếm về 0 để tránh gửi thông báo liên tục
                        self.reply_tracker[staff_id] = (0, current_time)
                        
                        display_role = db_role
                        reminder_text = (
                            f"Nếu bạn thấy {display_role} <@{staff_id}> nhiệt tình, "
                            f"hãy đừng ngần ngại bỏ ra 1 phút sử dụng lệnh `y!menu` chọn đến "
                            f"{display_role} để vote cho họ nhé!"
                        )
                        await message.channel.send(reminder_text)
                        log.info(f"Đã gửi nhắc nhở vote cho {display_role} ({staff_id}) sau khi đạt 10 reply/10 phút.")
                        
            except discord.NotFound:
                # Tin nhắn gốc đã bị xóa trước khi bot kịp đọc, bỏ qua
                pass
            except Exception as e:
                log.error(f"Lỗi hệ thống đếm lượt reply: {e}")

async def setup(bot):
    await bot.add_cog(StaffListenerCog(bot))