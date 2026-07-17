import discord
from discord.ext import commands
import logging
import asyncio
import random
from typing import Optional

log = logging.getLogger("StaffBot")

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channel_id = 1498711783223853101
        self.default_test_id = 468428368828956692

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
                troll_message = f"# 🌿 Một cộng đồng lành mạnh, văn minh và thân thiện. Nói không với toxic, chửi bới hay công kích cá nhân. Tại đây mọi người đều được tôn trọng, thoải mái trò chuyện, kết bạn và cùng nhau tạo nên một không gian tích cực. Chào mừng bạn đến với server! 💚🩷💚❤️💛🩶🤎🩵❣️💙❤️‍🔥💖💝❤️‍🔥❤️‍🩹💖🌵🍀🍀🌱🌿🌴🪵🌵☘️🍃🎄🌸🌷🥀🪷🌹🌻🌺"
                await channel.send(troll_message)
                log.info(f"Đã gửi text chào mừng tới {member.display_name}")
                
            except Exception as e:
                log.error(f"Lỗi gửi tin nhắn welcome: {e}")

# =====================================================================
    # LỆNH KIỂM THỬ GIAO DIỆN WELCOME (CHỈ DÀNH CHO TESTER / STAFF)
    # =====================================================================
    @commands.command(name="test_welcome")
    async def test_welcome_cmd(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """
        Lệnh giả lập sự kiện thành viên mới vào server để test Welcome.
        - Cú pháp 1: y!test_welcome             -> Mặc định ping ID 468428368828956692
        - Cú pháp 2: y!test_welcome @user / ID  -> Ping người được chỉ định
        """
        # 1. Chốt chặn cho Pylance: Đảm bảo lệnh đang chạy trong Server (Guild) chứ không phải DMs
        if not ctx.guild:
            await ctx.send("⚠️ Lệnh này chỉ có thể sử dụng bên trong Server!")
            return

        # 2. Nếu không truyền target, tìm ID test mặc định
        if target is None:
            target = ctx.guild.get_member(self.default_test_id)
            if not target:
                try:
                    target = await ctx.guild.fetch_member(self.default_test_id)
                except discord.NotFound:
                    await ctx.send(
                        f"⚠️ **Không tìm thấy thành viên có ID `{self.default_test_id}` trong server!**\n"
                        "➡️ Đang chuyển sang sử dụng tài khoản của bạn để chạy test tạm..."
                    )
                    # Ép kiểu an toàn cho Pylance: Chỉ nhận nếu tác giả thực sự là Member trong guild
                    if isinstance(ctx.author, discord.Member):
                        target = ctx.author
                except Exception as e:
                    await ctx.send(f"⚠️ Lỗi khi truy vấn ID test mặc định: {e}")
                    return

        # 3. Chốt chặn cuối cùng cho Pylance: Nếu sau các bước trên target vẫn không phải là Member thì dừng
        if not isinstance(target, discord.Member):
            await ctx.send("❌ Không thể xác định được đối tượng Member hợp lệ để chạy kiểm thử!")
            return

        # Từ dòng này trở đi, Pylance hiểu chắc chắn 100% target là discord.Member
        await ctx.send(f"🧪 **[TEST MODE]** Đang giả lập sự kiện Welcome cho **{target.display_name}** (<@{target.id}>)...")
        log.info(f"🧪 {ctx.author.display_name} vừa kích hoạt lệnh test_welcome cho mục tiêu {target.id}.")

        await self.on_member_join(target)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))