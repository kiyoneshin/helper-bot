import random
import time
from typing import Optional

import discord
from discord.ext import commands
import json

from cogs.common.db import get_or_create_event_profile, add_event_points, deduct_event_points, execute_db, update_task_progress, get_marriage

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
        
        
        # Check Co-op Marriage
        mar = await get_marriage(self.bot, str(uid))
        partner_id = None
        is_coop = False
        if mar:
            p_id_str = mar["user2_id"] if mar["user1_id"] == str(uid) else mar["user1_id"]
            partner_id = int(p_id_str)
            p_passed = now - self.cooldowns.get(partner_id, 0)
            if p_passed >= COOLDOWN_MINUTES * 60:
                is_coop = True
                self.cooldowns[partner_id] = now
                
        if event["type"] == "gain":
            if is_coop:
                amount = int(amount * 1.2)
                story = event["text"].format(amount=f"**{amount:,}**") + f"\n\n💕 **CO-OP BONUS!** Vợ/chồng của bạn <@{partner_id}> đã xắn tay vào làm chung! Cả hai nhận được x1.2 phần thưởng!"
                await add_event_points(self.bot, str(partner_id), float(amount), is_earned=True)
                
                # Check Task
                task_str = mar.get("couple_task")
                if task_str:
                    task_data = json.loads(task_str) if isinstance(task_str, str) else task_str
                    today_str = discord.utils.utcnow().strftime("%Y-%m-%d")
                    if task_data.get("date") == today_str and task_data.get("type") == "work" and not task_data.get("completed"):
                        task_data["progress"] = task_data.get("progress", 0) + 1
                        if task_data["progress"] >= task_data["target"]:
                            task_data["completed"] = True
                            from cogs.common.db import update_intimacy
                            await update_intimacy(self.bot, str(uid), 100)
                            story += f"\n\n🎉 **Nhiệm Vụ Cặp Đôi Hoàn Thành!** (+100 DTM)"
                        await execute_db(self.bot, "UPDATE marriages SET couple_task = $1::jsonb WHERE id = $2", json.dumps(task_data), mar["id"])
            
            # Cộng tiền (is_earned=True để tính vào cả đua top)
            await add_event_points(self.bot, str(uid), float(amount), is_earned=True)
            
            # Thưởng EXP Thú Cưng
            if mar and mar.get("pet_type"):
                exp_gained = 40 if is_coop else 20
                await execute_db(self.bot, "UPDATE marriages SET pet_exp = pet_exp + $1 WHERE id = $2", float(exp_gained), mar["id"])
                story += f"\n✨ *Thú cưng nhận {exp_gained} EXP vì bạn chăm chỉ làm việc!*"
            
            emb = discord.Embed(
                title="🎉 Làm việc chăm chỉ (hoặc ăn may)!",
                description=story,
                color=discord.Color.green()
            )
        else:
            # Trừ tiền
            if is_coop:
                reduced_amount = int(amount * 0.8)
                
                # Trừ người gọi lệnh
                ok1 = await deduct_event_points(self.bot, str(uid), float(reduced_amount))
                if not ok1:
                    await execute_db(self.bot, "UPDATE event_profiles SET points = 0 WHERE discord_id = $1", str(uid))
                    
                # Trừ người partner
                ok2 = await deduct_event_points(self.bot, str(partner_id), float(reduced_amount))
                if not ok2:
                    await execute_db(self.bot, "UPDATE event_profiles SET points = 0 WHERE discord_id = $1", str(partner_id))
                    
                story = event["text"].format(amount=f"**{reduced_amount:,}**") + f"\n\n💔 **ĐỒNG CAM CỘNG KHỔ!** Bạn và vợ/chồng <@{partner_id}> cùng gánh họa! Mỗi người bị trừ **{reduced_amount:,}** (đã giảm 20% thiệt hại do có người gánh cùng)."
            else:
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
        
        # Nhiệm vụ
        await update_task_progress(self.bot, uid, "work", 1)

async def setup(bot: commands.Bot):
    await bot.add_cog(WorkCog(bot))
