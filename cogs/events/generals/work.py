import random
import time
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import get_or_create_event_profile, add_event_points, deduct_event_points, execute_db

from .work_events import WORK_EVENTS

COOLDOWN_MINUTES = 10

class WorkCog(commands.Cog):
    """Cog làm việc ngẫu nhiên kiếm điểm."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cooldown mapping: user_id -> float (timestamp)
        self.cooldowns: dict[int, float] = {}
        
    @commands.hybrid_command(name="work", aliases=["w"])
    async def work_cmd(self, ctx: commands.Context):
        """Làm việc ngẫu nhiên kiếm điểm (Cooldown: 10 phút)."""
        uid = ctx.author.id
        now = time.time()
        
        # Check cooldown
        if uid in self.cooldowns:
            passed = now - self.cooldowns[uid]
            if passed < COOLDOWN_MINUTES * 60:
                remaining = int(COOLDOWN_MINUTES * 60 - passed)
                mins = remaining // 60
                secs = remaining % 60
                
                funny_waits = [
                    "Bình tĩnh đi ba, làm gì mà hối như ma đuổi vậy?",
                    "Cái gì cũng phải từ từ, sức người có hạn chứ đâu phải máy cày!",
                    "Vừa mới làm xong mà chưa gì đã đòi làm tiếp? Đòi vắt kiệt sức lao động hả?",
                    "Cơ thể đang cạn kiệt năng lượng, đi nghỉ mát xíu rồi quay lại nhé!",
                    "Chủ thầu đang uống trà đá, chưa giao việc đâu.",
                    "Làm việc nãy giờ đau lưng chưa? Thả lỏng đi, ráng quá còng lưng á!",
                    "Giang hồ đồn bạn bị deadline rượt, nhưng mà khoan đã, nghỉ chút coi."
                ]
                msg = random.choice(funny_waits)
                
                emb = discord.Embed(
                    title="⏳ Cứ từ từ...",
                    description=f"{msg}\n\nQuay lại sau: **{mins} phút {secs} giây** nữa nhé!",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=emb)
                return
                
        # Update cooldown
        self.cooldowns[uid] = now
        
        # Đảm bảo có profile
        await get_or_create_event_profile(self.bot, str(uid))
        
        event = random.choice(WORK_EVENTS)
        amount = random.randint(event["min_amount"], event["max_amount"])
        story = event["text"].format(amount=f"**{amount:,}**")
        
        if event["type"] == "gain":
            # Cộng tiền (is_earned=True để tính vào cả đua top)
            await add_event_points(self.bot, str(uid), float(amount), is_earned=True)
            
            emb = discord.Embed(
                title="🎉 Làm việc chăm chỉ (hoặc ăn may)!",
                description=story,
                color=discord.Color.green()
            )
        else:
            # Trừ tiền
            ok = await deduct_event_points(self.bot, str(uid), float(amount))
            if not ok:
                # Nếu deduct trả về False tức là ví không đủ, siết sạch ví
                await execute_db(self.bot, "UPDATE event_profiles SET points = 0 WHERE discord_id = $1", str(uid))
                story += "\n\n*(Ví bạn cháy sạch không còn một cắc, phá sản rồi cưng!)*"
            
            emb = discord.Embed(
                title="💥 Tai nạn nghề nghiệp!",
                description=story,
                color=discord.Color.red()
            )
            
        emb.set_thumbnail(url=ctx.author.display_avatar.url)
        emb.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=emb)

async def setup(bot: commands.Bot):
    await bot.add_cog(WorkCog(bot))
