"""
cooldowns.py — Lệnh kcd (Cooldowns)
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
        if duration_str:
            return f"✅ — **{label}** ({duration_str})"
        return f"✅ — **{label}**"
    if duration_str:
        return f"🕒 — **{label}** ({duration_str})"
    return f"🕒 — **{label}**"

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
        # 1. REWARDS (<:gift_00_symbol:1536003307011842099> Phần thưởng)
        # -------------------------------------------------------------
        row = await fetchrow_db(
            self.bot, 
            "SELECT last_daily, last_weekly, last_pray, lb_buy_cooldown FROM event_profiles WHERE discord_id = $1", 
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
            last_work = getattr(work_cog, 'cooldowns', {}).get(ctx.author.id, 0)
            passed = now_ts - last_work
            if passed < 10 * 60:
                work_ready = False
                work_str = format_timedelta(timedelta(seconds=(10 * 60) - passed))
                
        pray_ready = True
        pray_str = ""
        lb_buy_ready = True
        lb_buy_str = ""
        
        if row:
            if row.get("last_pray"):
                lp = row["last_pray"]
                if lp.tzinfo is None: lp = lp.replace(tzinfo=timezone.utc)
                from cogs.events.lootbox.lootbox_config import PRAY_COOLDOWN_MINUTES
                if now - lp < timedelta(minutes=PRAY_COOLDOWN_MINUTES):
                    pray_ready = False
                    pray_str = format_timedelta(timedelta(minutes=PRAY_COOLDOWN_MINUTES) - (now - lp))

            if row.get("lb_buy_cooldown"):
                import json
                cd_data = row["lb_buy_cooldown"]
                if isinstance(cd_data, str):
                    cd_data = json.loads(cd_data)
                cd_data = cd_data or {}
                last_buy_ts = max(cd_data.values()) if cd_data else None
                if last_buy_ts:
                    last_buy = datetime.fromtimestamp(last_buy_ts, tz=timezone.utc)
                    from cogs.events.lootbox.lootbox_config import LB_BUY_COOLDOWN_HOURS
                    if now < last_buy + timedelta(hours=LB_BUY_COOLDOWN_HOURS):
                        lb_buy_ready = False
                        lb_buy_str = format_timedelta(timedelta(hours=LB_BUY_COOLDOWN_HOURS) - (now - last_buy))

        rewards_lines = [
            _format_cd(daily_ready, "daily", daily_str),
            _format_cd(weekly_ready, "weekly", weekly_str),
            _format_cd(work_ready, "work", work_str),
            _format_cd(pray_ready, "pray", pray_str),
            _format_cd(lb_buy_ready, "buy lootbox", lb_buy_str)
        ]
        
        embed.add_field(name="<:gift_00_symbol:1536003307011842099> Rewards", value="\n".join(rewards_lines), inline=False)
        
        # -------------------------------------------------------------
        # 2. PROGRESS (✨ Tiến độ)
        # -------------------------------------------------------------
        farm_data = await get_farm_data(self.bot, user_id)
        from cogs.events.mining.mining_config import MAX_STAMINA
        from cogs.events.idle_farm.farm_db import get_true_stamina_regen
        stamina = await get_and_update_stamina(self.bot, user_id, ctx.channel.id) 
        regen_interval = await get_true_stamina_regen(self.bot, user_id)
        
        stamina_ready = (stamina >= MAX_STAMINA)
        stamina_str = f"{stamina}/{MAX_STAMINA}"
        if not stamina_ready:
            missing = MAX_STAMINA - stamina
            seconds_to_full = missing * regen_interval
            stamina_str += f" ({format_timedelta(timedelta(seconds=seconds_to_full))})"
            
        machine_queue = _get_queue_list(farm_data)
        machine_ready = False
        machine_str = ""
        
        total_machines = len(machine_queue)
        if total_machines == 0:
            machine_ready = True
            machine_str = "--/0"
        else:
            total_ready = sum(1 for _, item in machine_queue if item.get("status") == "done")
            total_processing = sum(1 for _, item in machine_queue if item.get("status") == "processing")
            
            if total_processing == 0 and total_ready == 0:
                machine_ready = True
                machine_str = f"--/{total_machines}"
            elif total_ready > 0:
                machine_ready = True
                machine_str = f"{total_ready}/{total_machines} 🧺"
            else:
                machine_ready = False
                earliest = min((item.get("finish_time", 0) for _, item in machine_queue if item.get("status") == "processing"), default=0)
                dur = earliest - now_ts
                if dur <= 0:
                    machine_ready = True
                    machine_str = f"Sẵn sàng/{total_machines}"
                else:
                    machine_str = f"0/{total_machines} ({format_timedelta(timedelta(seconds=dur))})"
                    
        # Check Farm Crops
        total_slots = farm_data.get("slots", 3)
        crops = farm_data.get("crops", {})
        total_ready = 0
        total_growing = 0
        earliest_crop = float('inf')

        from cogs.events.idle_farm.farm_db import calculate_crop_status
        from cogs.events.idle_farm.config import STATUS_READY, STATUS_GROWING, STATUS_WITHERED

        for slot_id in range(1, total_slots + 1):
            slot_id_str = str(slot_id)
            if slot_id_str in crops:
                status, remaining = calculate_crop_status(crops[slot_id_str], slot_id_str, crops)
                if status == STATUS_READY or status == STATUS_WITHERED:
                    total_ready += 1
                elif status == STATUS_GROWING:
                    total_growing += 1
                    if remaining < earliest_crop:
                        earliest_crop = remaining

        farm_ready = False
        farm_str = ""
        if total_growing == 0 and total_ready == 0:
            farm_ready = True
            farm_str = f"--/{total_slots}"
        elif total_ready > 0:
            farm_ready = True
            farm_str = f"{total_ready}/{total_slots} 🧺"
        else:
            farm_ready = False
            farm_str = f"0/{total_slots} ({format_timedelta(timedelta(seconds=earliest_crop))})"

        progress_lines = [
            _format_cd(stamina_ready, "chop | fish | mine", stamina_str),
            _format_cd(farm_ready, "farm", farm_str),
            _format_cd(machine_ready, "machine / craft", machine_str),
        ]
        
        embed.add_field(name="✨ Progress", value="\n".join(progress_lines), inline=False)
        
        # -------------------------------------------------------------
        # 3. ACTIONS (💞 Tương tác cặp đôi)
        # -------------------------------------------------------------
        marriage_cog = self.bot.get_cog("MarriageCog")
        actions_lines = []
        if marriage_cog:
            # Lấy buff giảm cooldown
            from cogs.common.db import get_marriage
            from cogs.events.social.marriage import RING_BUFFS
            mar = await get_marriage(self.bot, user_id)
            cd_reduction = 0.0
            pet_cd_reduction = 0.0
            
            if mar:
                ring_id = mar.get("ring_id")
                pet_id = mar.get("pet_id")
                pet_level = mar.get("pet_level", 0)
                
                buffs = RING_BUFFS.get(ring_id, {"cd_reduction": 0.0})
                cd_reduction = buffs.get("cd_reduction", 0.0)
                
                if pet_level > 0:
                    if pet_id == 45:
                        pet_cd_reduction = min(pet_level * 0.0075, 0.45)
                    elif pet_id == 46:
                        pet_cd_reduction = pet_level * 0.005
                    elif pet_id == 47:
                        pet_cd_reduction = pet_level * 0.0035

            user_cd_dict = getattr(marriage_cog, 'action_cooldowns', {}).get(user_id, {})
            # Group actions by tier
            for tier in [1, 2, 3, 4]:
                tier_actions = [k for k, v in ACTIONS.items() if v["tier"] == tier]
                if not tier_actions: continue
                
                tier_parts = []
                for action in tier_actions:
                    last_time = user_cd_dict.get(action, 0)
                    cd_seconds = ACTION_TIERS[tier]["cd"]
                    actual_cd = cd_seconds * (1.0 - cd_reduction) * (1.0 - pet_cd_reduction)
                    passed = now_ts - last_time
                    
                    if passed < actual_cd:
                        rem = actual_cd - passed
                        tier_parts.append(f"{action} {format_timedelta(timedelta(seconds=rem))}")
                    else:
                        tier_parts.append(f"{action} ✅")
                        
                actions_lines.append(f"**Tier {tier}:** " + " — ".join(tier_parts))
                        
        if actions_lines:
            embed.add_field(name="💞 Actions", value="\n".join(actions_lines), inline=False)

        
        embed.set_footer(text="Gợi ý: Hệ thống sẽ tự động nhắn tin (Ping) nhắc nhở bạn khi Thể Lực hồi đầy 100/100!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CooldownsCog(bot))
