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
                    "Cái gì cũng phải từ từ, sức người có hạn chứ đâu phải máy càk",
                    "Vừa mới làm xong mà chưa gì đã đòi làm tiếp? Đòi vắt kiệt sức lao động hả?",
                    "Cơ thể đang cạn kiệt năng lượng, đi nghỉ mát xíu rồi quay lại nhé!",
                    "Chủ thầu đang uống trà đá, chưa giao việc đâu.",
                    "Làm việc nãy giờ đau lưng chưa? Thả lỏng đi, ráng quá còng lưng á!",
                    "Giang hồ đồn bạn bị deadline rượt, nhưng mà khoan đã, nghỉ chút coi."
                ]
                msg = random.choice(funny_waits)
                
                emb = discord.Embed(
                    title="<:symbol_hour_glass:1537570149215899658> Cứ từ từ...",
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
        ring_work_bonus = 1.0
        pet_task_bonus = 0.0
        if mar:
            p_id_str = mar["user2_id"] if mar["user1_id"] == str(uid) else mar["user1_id"]
            partner_id = int(p_id_str)
            p_passed = now - self.cooldowns.get(partner_id, 0)
            if p_passed >= COOLDOWN_MINUTES * 60:
                is_coop = True
                self.cooldowns[partner_id] = now
            
            # Fetch Ring Buff
            ring_id = mar.get("ring_id", 31)
            from cogs.events.social.marriage import RING_BUFFS
            buffs = RING_BUFFS.get(ring_id, RING_BUFFS[31])
            ring_work_bonus = buffs.get("work_bonus", 1.0)
            
            # Fetch Pet Buff
            pet_exp = float(mar.get('pet_exp', 0.0))
            pet_type = mar.get("pet_type")
            pet_level = int(pet_exp / 200) + 1 if pet_type else 0
            if pet_type == "Sói": pet_task_bonus = min(pet_level * 0.025, 1.25)
            elif pet_type == "Rồng": pet_task_bonus = pet_level * 0.01
                
        if event["type"] == "gain":
            if is_coop:
                amount = int(amount * 1.2 * ring_work_bonus)
                bonus_str = f" (Nhẫn x{ring_work_bonus})" if ring_work_bonus > 1.0 else ""
                story = event["text"].format(amount=f"**{amount:,}**") + f"\n\n<a:symbol_star_pink:1537739287947382864> **CO-OP BONUS!** Vợ/chồng của bạn <@{partner_id}> đã xắn tay vào làm chung! Cả hai nhận được x1.2 phần thưởng{bonus_str}!"
                await add_event_points(self.bot, str(partner_id), float(amount), is_earned=True)
                
                # Check Task
                task_data = None
                if mar:
                    try:
                        from cogs.events.social.marriage import get_or_create_couple_task
                        task_data = await get_or_create_couple_task(self.bot, mar)
                    except Exception:
                        pass

                if task_data and task_data.get("type") == "work" and not task_data.get("completed"):
                    task_data["progress"] = task_data.get("progress", 0) + 1
                        if task_data["progress"] >= task_data["target"]:
                            task_data["completed"] = True
                            task_reward = 100 * (1.0 + pet_task_bonus)
                            from cogs.common.db import update_intimacy
                            await update_intimacy(self.bot, str(uid), int(task_reward))
                            story += f"\n\n<:symbol_confetti:1537570146313306183> **Nhiệm Vụ Cặp Đôi Hoàn Thành!** (+{task_reward:.1f} DTM)"
                        await execute_db(self.bot, "UPDATE marriages SET couple_task = $1::jsonb WHERE id = $2", json.dumps(task_data), mar["id"] if mar else 0)
            
            # Cộng tiền (is_earned=True để tính vào cả đua top)
            await add_event_points(self.bot, str(uid), float(amount), is_earned=True)
            
            # Thưởng <:xp:1535664865308577884> Thú Cưng
            if mar and mar.get("pet_type"):
                exp_gained = 40 if is_coop else 20
                await execute_db(self.bot, "UPDATE marriages SET pet_exp = pet_exp + $1 WHERE id = $2", float(exp_gained), mar["id"] if mar else 0)
                story += f"\n<a:symbol_star_yellow:1537739289834553385> *Thú cưng nhận {exp_gained} <:xp:1535664865308577884> vì bạn chăm chỉ làm việc!*"
            
            emb = discord.Embed(
                title="<:symbol_confetti:1537570146313306183> Làm việc chăm chỉ (hoặc ăn may)!",
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
                    
                # Reset cooldown cho cả hai
                if ctx.command and hasattr(ctx.command, '_buckets') and ctx.command._buckets.valid:
                    ctx.command.reset_cooldown(ctx)
                    try:
                        cache = ctx.command._buckets._cache
                        for key in list(cache.keys()):
                            if str(partner_id) in str(key):
                                del cache[key]
                    except Exception:
                        pass
                    
                story = event["text"].format(amount=f"**{reduced_amount:,}**") + f"\n\n<:symbol_heart_breaking:1536296911655673936> **ĐỒNG CAM CỘNG KHỔ!** Bạn và vợ/chồng <@{partner_id}> cùng gánh họa! Mỗi người bị trừ **{reduced_amount:,}** (đã giảm 20% thiệt hại) và **Làm Mới Thời Gian Hồi Lệnh Làm Việc** cho cả hai!"
            else:
                ok = await deduct_event_points(self.bot, str(uid), float(amount))
                if not ok:
                    # Nếu deduct trả về False tức là ví không đủ, siết sạch ví
                    await execute_db(self.bot, "UPDATE event_profiles SET points = 0 WHERE discord_id = $1", str(uid))
                    story += "\n\n*(Ví bạn cháy sạch không còn một cắc, phá sản rồi cưng!)*"
            
            emb = discord.Embed(
                title="<:symbol_demolish:1537466095412314192> Tai nạn nghề nghiệp!",
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
