import discord
from discord.ext import commands
import logging

log = logging.getLogger("StaffBot")

class TrapChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Bỏ qua nếu tin nhắn phát ra từ chính bot
        if message.author.bot:
            return

        # Kiểm tra nếu ID trùng khớp với Kênh cấm chat cấu hình trong .env
        if message.channel.id == self.bot.trap_channel_id:
            if isinstance(message.author, discord.Member):
                try:
                    # 1. Xóa ngay tin nhắn vi phạm để giữ sạch kênh bẫy
                    await message.delete()
                    
                    # 2. Ban vĩnh viễn ngay lập tức (Xóa sạch tin nhắn của tài khoản đó trong 7 ngày qua)
                    await message.author.ban(
                        delete_message_seconds=604800, 
                        reason="Honeypot: Vi phạm nghiêm trọng quy tắc gõ chữ tại Trap Channel."
                    )
                    log.info(f"Đã BAN vĩnh viễn tài khoản {message.author} thành công!")
                except discord.Forbidden:
                    log.error(f"Bot thiếu quyền quản trị (Ban Members / Manage Messages) để xử lý {message.author}!")
                except Exception as e:
                    log.error(f"Lỗi hệ thống khi thực thi trap channel: {e}")

async def setup(bot):
    await bot.add_cog(TrapChannelCog(bot))