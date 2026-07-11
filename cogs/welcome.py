import discord
from discord.ext import commands
import logging
import asyncio
import random

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
                
                welcome_messages = [
                    f"hé luuu, chào mừng {member.mention} tình iu đến với sivi ăng giê líc cuti cuti",
                    f"queo căm bbi {member.mention} đến với sivi của tụi mình, mong tình iu cứ thoải mái nói chuyện ạ",
                    f"lốp ăng giê líc xin chào tình iu {member.mention} đã đến với sv của chúng mình",
                    f"chào mừng {member.mention} đến với sv của tụi mình, mong tình iu sẽ có những trải nghiệm vui vẻ ạ"
                ]
                
                selected_message = random.choice(welcome_messages)
                
                await channel.send(selected_message)
                log.info(f"Đã gửi text chào mừng tới {member.display_name}")
                
            except Exception as e:
                log.error(f"Lỗi gửi tin nhắn welcome: {e}")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))