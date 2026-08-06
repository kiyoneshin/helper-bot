"""
cooldowns.py — Lệnh y!cd (Cooldowns)
=====================================
Hiển thị thời gian hồi chiêu của các lệnh trong bot.
"""
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db
from cogs.events.idle_farm.farm_db import get_and_update_stamina, get_farm_data
from cogs.events.social.marriage import ACTIONS, ACTION_TIERS
from cogs.events.idle_farm.machine_ui import _get_queue_list

def format_timedelta(td: timedelta) -> str:
    secs = int(td.total_seconds())
    if secs <= 0:
        return "Sẵn sàng"
    
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    secs = secs % 60
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    if secs > 0 or not parts: parts.append(f"{secs}s")
    
    return " ".join(parts)

def _format_cd(is_ready: bool, label: str, duration_str: str = "") -> str:
    if is_ready:
        return f"✅ ~~ **{label}**"
    return f"🕒 ~~ **{label}** ({duration_str})"

class CooldownsCog(commands.Cog):
    """⏱️ Bảng hiển thị thời gian hồi chiêu của các lệnh."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="cooldowns", aliases=["cd", "rd"])
    async def cooldowns_cmd(self, ctx: commands.Context) -> None:
        """⏱️ Xem thời gian hồi của tất cả các lệnh."""
        user_id = str(ctx.author.id)
        now = datetime.now(timezone.utc)
        now_ts = time.time()
        
        embed = discord.Embed(
            title=f"{ctx.author.display_name} — cooldowns",
            color=0x2b2d31
        )
        
        # -------------------------------------------------------------
        # 1. REWARDS (🎁 Phần thưởng)
        # -------------------------------------------------------------
        row = await fetchrow_db(
            self.bot, 
            "SELECT last_daily, last_weekly FROM event_profiles WHERE discord_id = $1", 
            user_id
        )
        
        daily_ready = True
        weekly_ready = True
        daily_str = ""
        weekly_str = ""
        
        if row:
            if row["last_daily"]:
                ld = row["last_daily"]
                if ld.tzinfo is None: ld = ld.replace(tzinfo=timezone.utc)
                if now - ld < timedelta(hours=24):
                    daily_ready = False
                    daily_str = format_timedelta(timedelta(hours=24) - (now - ld))
            
            if row["last_weekly"]:
                lw = row["last_weekly"]
                if lw.tzinfo is None: lw = lw.replace(tzinfo=timezone.utc)
                if now - lw < timedelta(days=7):
                    weekly_ready = False
                    weekly_str = format_timedelta(timedelta(days=7) - (now - lw))

        # Check work cooldown
        work_ready = True
        work_str = ""
        work_cog = self.bot.get_cog("WorkCog")
        if work_cog:
            last_work = work_cog.cooldowns.get(ctx.author.id, 0)
            passed = now_ts - last_work
            if passed < 10 * 60:
                work_ready = False
                work_str = format_timedelta(timedelta(seconds=(10 * 60) - passed))
                
        rewards_lines = [
            _format_cd(daily_ready, "daily", daily_str),
            _format_cd(weekly_ready, "weekly", weekly_str),
            _format_cd(work_ready, "work", work_str)
        ]
        
        embed.add_field(name="🎁 Rewards", value="\\n".join(rewards_lines), inline=False)
        
        # -------------------------------------------------------------
        # 2. PROGRESS (✨ Tiến độ)
        # -------------------------------------------------------------
        farm_data = await get_farm_data(self.bot, user_id)
        from cogs.events.mining.mining_config import MAX_STAMINA, STAMINA_REGEN_INTERVAL_SECONDS
        stamina = await get_and_update_stamina(self.bot, user_id, ctx.channel.id) # Gán channel_id vào đây để Auto-Ping hoạt động khi họ check cd
        
        stamina_ready = (stamina == MAX_STAMINA)
        stamina_str = ""
        if not stamina_ready:
            missing = MAX_STAMINA - stamina
            seconds_to_full = missing * STAMINA_REGEN_INTERVAL_SECONDS
            stamina_str = format_timedelta(timedelta(seconds=seconds_to_full))
            
        machine_queue = _get_queue_list(farm_data)
        machine_ready = False
        machine_str = ""
        
        if not machine_queue:
            machine_ready = True
        else:
            # Check if any is done
            if any(item.get("status") == "done" for _, item in machine_queue):
                machine_ready = True
            else:
                # Find earliest finish time
                earliest = min((item.get("finish_time", 0) for _, item in machine_queue if item.get("status") == "processing"), default=0)
                if earliest > now_ts:
                    machine_ready = False
                    machine_str = format_timedelta(timedelta(seconds=earliest - now_ts))
                else:
                    machine_ready = True
                    
        progress_lines = [
            _format_cd(stamina_ready, "chop | fish | mine | farm", stamina_str),
            _format_cd(machine_ready, "machine / craft", machine_str),
        ]
        
        embed.add_field(name="✨ Progress", value="\\n".join(progress_lines), inline=False)
        
        # -------------------------------------------------------------
        # 3. ACTIONS (💞 Tương tác cặp đôi)
        # -------------------------------------------------------------
        marriage_cog = self.bot.get_cog("Marriage")
        actions_lines = []
        if marriage_cog:
            user_cd_dict = marriage_cog.action_cooldowns.get(user_id, {})
            # Group actions by tier
            for tier in [1, 2, 3, 4]:
                tier_actions = [k for k, v in ACTIONS.items() if v["tier"] == tier]
                if not tier_actions: continue
                
                # Check cooldowns for these actions
                for action in tier_actions:
                    last_time = user_cd_dict.get(action, 0)
                    cd_seconds = ACTION_TIERS[tier]["cd"]
                    
                    # Cần lấy buff cooldown từ partner, nhưng để nhanh ta dùng cd gốc 
                    # vì cd thực tế được check khi chạy lệnh, nếu họ dùng lệnh sẽ được giảm
                    passed = now_ts - last_time
                    if passed < cd_seconds:
                        actions_lines.append(_format_cd(False, action, format_timedelta(timedelta(seconds=cd_seconds - passed))))
                    else:
                        actions_lines.append(_format_cd(True, action))
                        
        if actions_lines:
            # Chỉ hiển thị 10 action tiêu biểu nhất hoặc gom nhóm nếu quá nhiều
            if len(actions_lines) > 8:
                embed.add_field(name="💞 Actions", value="\\n".join(actions_lines[:8]) + "\\n*... và nhiều hành động khác*", inline=False)
            else:
                embed.add_field(name="💞 Actions", value="\\n".join(actions_lines), inline=False)

        
        embed.set_footer(text="Gợi ý: Hệ thống sẽ tự động nhắn tin (Ping) nhắc nhở bạn khi Thể Lực hồi đầy 100/100!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CooldownsCog(bot))
