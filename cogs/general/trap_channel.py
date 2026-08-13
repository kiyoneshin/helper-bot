import discord
from discord.ext import commands
import logging

log = logging.getLogger("StaffBot")

class TrapChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Khai báo ID kênh Log để nhận thông báo báo cáo
        self.log_channel_id = 1498728037565337770

    @commands.Cog.listener()
    async def on_ready(self):
        """Sự kiện tự động kiểm tra và gửi tin nhắn cảnh báo khi bot online"""
        if not self.bot.trap_channel_id:
            return

        channel = self.bot.get_channel(self.bot.trap_channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                # Kiểm tra xem trong kênh đã có tin nhắn nào chưa để tránh gửi lặp đi lặp lại
                async for _ in channel.history(limit=1):
                    return
                
                # Thiết kế Embed cảnh báo chuẩn
                embed = discord.Embed(
                    title="<:symbol_alert:1537546957885542450> CẢNH BÁO – BAN VĨNH VIỄN NGAY LẬP TỨC <:symbol_alert:1537546957885542450>",
                    description=(
                        "Bất kỳ tin nhắn nào gửi vào kênh này sẽ dẫn đến một hình phạt **cấm (ban) vĩnh viễn ngay lập tức**.\n"
                        "Không kháng cáo. Không có ngoại lệ.\n\n"
                        "Kênh này được cố ý đặt ở trên cùng sơ đồ server.\n"
                        "Các tài khoản Scam bot không thể đọc được tên kênh – chúng chỉ spam mọi thứ bất kể quy tắc.\n"
                        "Nếu bạn cố tình viết gì đó ở đây, bạn sẽ bị xử lý như một trong số chúng.\n\n"
                        "**Bạn đã được cảnh báo.**\n\n"
                        "*Lệnh cấm này được thực hiện tự động bởi hệ thống bot phòng thủ.*"
                    ),
                    color=0xff0000
                )
                
                await channel.send(embed=embed)
                log.info(f"Đã gửi tin nhắn cảnh báo Honeypot vào kênh bẫy thành công.")
            except Exception as e:
                log.error(f"Lỗi khi gửi tin nhắn cảnh báo vào Trap Channel: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Tính năng sập bẫy – Xóa chữ, BAN ngay lập tức và Báo Cáo"""
        if message.author.bot:
            return

        if message.channel.id == self.bot.trap_channel_id:
            if isinstance(message.author, discord.Member):
                try:
                    # 1. Xóa ngay tin nhắn vi phạm
                    await message.delete()
                    
                    # 2. Ban vĩnh viễn ngay lập tức
                    await message.author.ban(
                        delete_message_seconds=604800, 
                        reason="Honeypot: Vi phạm gõ chữ tại kênh cấm chat nghiêm ngặt."
                    )
                    log.info(f"Đã BAN vĩnh viễn tài khoản {message.author}!")

                    # 3. Gửi thông báo Log ra kênh Discord
                    log_channel = self.bot.get_channel(self.log_channel_id)
                    if isinstance(log_channel, discord.TextChannel):
                        log_embed = discord.Embed(
                            title="BÁO CÁO",
                            description="Vừa **BAN VĨNH VIỄN** một tài khoản.",
                            color=0xff0000
                        )
                        log_embed.add_field(name="Kẻ vi phạm", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
                        
                        # Lấy nội dung tin nhắn đã gõ để làm bằng chứng
                        content = message.content if message.content else "(Tin nhắn trống hoặc chứa file)"
                        log_embed.add_field(name="Nội dung vi phạm", value=f"```{content}```", inline=False)
                        
                        log_embed.set_thumbnail(url=message.author.display_avatar.url)
                        log_embed.set_footer(text="Hệ thống tự động cấm Scam Bot / Raid")
                        
                        await log_channel.send(embed=log_embed)

                except discord.Forbidden:
                    log.error(f"Bot thiếu quyền quản trị (Ban Members / Manage Messages) để xử lý {message.author}!")
                except Exception as e:
                    log.error(f"Lỗi hệ thống khi thực thi bẫy: {e}")

async def setup(bot):
    await bot.add_cog(TrapChannelCog(bot))