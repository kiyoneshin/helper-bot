import discord
from discord.ext import commands
import logging
import asyncio

log = logging.getLogger("StaffBot")

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channel_id = 1498711783223853101

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(self.welcome_channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                await asyncio.sleep(1)
                
                embed = discord.Embed(
                    title="Aloha Mem Mới Nha! ✨",
                    description=(
                        f"Rất vui vì {member.mention} đã tìm đến Angelic ໒꒱.\n\n"
                        f"Hãy đọc luật tại <#1512135955983630617>.\n\n"
                        f"Chọn roles mà bạn muốn tại <#1498731263304007710>.\n\n"
                        f"Thả lỏng, làm quen với mọi người tại <#1498711783223853101> và biến nơi đây thành ngôi nhà thứ hai của mình nhé."
                    ),
                    color=0xffb6c1
                )
                
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                await channel.send(embed=embed)
                log.info(f"Đã gửi thiệp chào mừng tới {member.display_name}")
                
            except Exception as e:
                log.error(f"Lỗi gửi tin nhắn welcome: {e}")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))