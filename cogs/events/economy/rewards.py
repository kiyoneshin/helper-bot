"""
rewards.py — Cog Nhận Thưởng Điểm Danh (Daily & Weekly)
=========================================================
Xử lý tính năng nhận thưởng hàng ngày và hàng tuần.
Hỗ trợ chuỗi (streak) cho tính năng daily.
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from cogs.common.db import (
    add_event_points,
    execute_db,
    fetchrow_db,
)

log = logging.getLogger("Rewards")


async def _init_reward_tables(bot: commands.Bot) -> None:
    """Thêm các cột phục vụ cho tính năng Rewards vào bảng event_profiles."""
    try:
        await execute_db(
            bot,
            """
            ALTER TABLE event_profiles 
            ADD COLUMN IF NOT EXISTS last_daily TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS daily_streak INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS last_weekly TIMESTAMPTZ;
            """
        )
        log.info("✅ Đã cập nhật cấu trúc bảng event_profiles cho Rewards.")
    except Exception as e:
        log.error(f"Lỗi khi khởi tạo cột Rewards: {e}")


class Rewards(commands.Cog):
    """<:gift_00_symbol:1536003307011842099> Hệ Thống Nhận Thưởng Hàng Ngày & Hàng Tuần"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await _init_reward_tables(self.bot)

    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH Y!DAILY
    # ─────────────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="daily", aliases=["diemdanh"])
    async def daily_cmd(self, ctx: commands.Context) -> None:
        """<:gift_00_symbol:1536003307011842099> Nhận thưởng 500 điểm mỗi ngày (tăng dần theo chuỗi)."""
        uid = str(ctx.author.id)
        now = datetime.now(timezone.utc)
        
        # Đảm bảo user có profile
        from cogs.common.db import get_or_create_event_profile
        await get_or_create_event_profile(self.bot, uid)

        # Lấy dữ liệu daily hiện tại
        row = await fetchrow_db(
            self.bot, 
            "SELECT last_daily, daily_streak FROM event_profiles WHERE discord_id = $1", 
            uid
        )
        
        if not row:
            await ctx.send("❌ Đã có lỗi xảy ra khi truy vấn dữ liệu của bạn.")
            return

        last_daily = row["last_daily"]
        daily_streak = int(row["daily_streak"]) if row["daily_streak"] is not None else 0

        # Kiểm tra thời gian
        if last_daily:
            # Chuyển đổi thành UTC timezone-aware nếu bị DB trả về ngây thơ (naive)
            if last_daily.tzinfo is None:
                last_daily = last_daily.replace(tzinfo=timezone.utc)
                
            time_since_last = now - last_daily
            
            if time_since_last < timedelta(hours=24):
                # Chưa đủ 24h
                next_daily_time = last_daily + timedelta(hours=24)
                next_timestamp = int(next_daily_time.timestamp())
                
                embed = discord.Embed(
                    title="⏳ Khoan đã!",
                    description=f"Bạn đã nhận thưởng rồi. Hãy quay lại vào <t:{next_timestamp}:R> nhé!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            elif time_since_last > timedelta(hours=48):
                # Quá 48h, đứt chuỗi
                daily_streak = 0

        # Cập nhật chuỗi và tính thưởng
        daily_streak += 1
        # Cấp chuỗi tối đa được thưởng tiền là 7
        streak_multiplier = min(daily_streak, 7)
        
        base_reward = 500
        streak_bonus = (streak_multiplier - 1) * 100 if streak_multiplier > 0 else 0
        total_reward = base_reward + streak_bonus

        # Lootbox theo chuỗi streak (max 21 ngày)
        # streak 3-6: Common, 7-13: Uncommon, 14-20: Rare, 21+: Epic
        lb_tier = None
        lb_name = None
        lb_emoji = None
        from cogs.events.lootbox.lootbox_config import LB_COMMON, LB_UNCOMMON, LB_RARE, LB_EPIC
        if daily_streak >= 15:
            lb_tier, lb_name, lb_emoji = LB_EPIC, "Lootbox Epic", "🟣"
        elif daily_streak >= 10:
            lb_tier, lb_name, lb_emoji = LB_RARE, "Lootbox Rare", "🔵"
        elif daily_streak >= 6:
            lb_tier, lb_name, lb_emoji = LB_UNCOMMON, "Lootbox Uncommon", "🟢"
        elif daily_streak >= 3:
            lb_tier, lb_name, lb_emoji = LB_COMMON, "Lootbox Common", "📦"

        # Cập nhật DB
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET last_daily = $1, daily_streak = $2 WHERE discord_id = $3",
            now, daily_streak, uid
        )
        
        # Cộng tiền
        await add_event_points(self.bot, uid, total_reward, is_earned=True)

        lb_text = ""
        if lb_tier:
            from cogs.events.lootbox.lootbox_cmd import _add_lootbox_to_inventory
            await _add_lootbox_to_inventory(self.bot, uid, lb_tier, 1)
            lb_text = f"\n<:gift_00_symbol:1536003307011842099> **Thưởng Thêm:** 1x {lb_emoji} {lb_name}"

        # Trả về thông báo
        embed = discord.Embed(
            title="<:gift_00_symbol:1536003307011842099> Điểm Danh Hàng Ngày",
            description=(
                f"✅ Nhận thành công **{total_reward:,}** điểm!\n"
                f"*(Cơ bản: {base_reward:,} + Thưởng chuỗi: {streak_bonus:,})*{lb_text}\n\n"
                f"🔥 **Chuỗi hiện tại:** {daily_streak} ngày\n"
                f"*(Chuỗi càng dài thưởng càng lớn. Hãy quay lại vào ngày mai để không làm đứt chuỗi nhé!)*"
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)


    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH Y!WEEKLY
    # ─────────────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="weekly", aliases=["luongtuan"])
    async def weekly_cmd(self, ctx: commands.Context) -> None:
        """💎 Nhận lương 5000 điểm mỗi tuần."""
        uid = str(ctx.author.id)
        now = datetime.now(timezone.utc)
        
        # Đảm bảo user có profile
        from cogs.common.db import get_or_create_event_profile
        await get_or_create_event_profile(self.bot, uid)

        # Lấy dữ liệu weekly hiện tại
        row = await fetchrow_db(
            self.bot, 
            "SELECT last_weekly FROM event_profiles WHERE discord_id = $1", 
            uid
        )
        
        if not row:
            await ctx.send("❌ Đã có lỗi xảy ra khi truy vấn dữ liệu của bạn.")
            return

        last_weekly = row["last_weekly"]

        # Kiểm tra thời gian
        if last_weekly:
            if last_weekly.tzinfo is None:
                last_weekly = last_weekly.replace(tzinfo=timezone.utc)
                
            time_since_last = now - last_weekly
            
            if time_since_last < timedelta(days=7):
                # Chưa đủ 7 ngày
                next_weekly_time = last_weekly + timedelta(days=7)
                next_timestamp = int(next_weekly_time.timestamp())
                
                embed = discord.Embed(
                    title="⏳ Chưa đến ngày nhận lương!",
                    description=f"Lương tuần của bạn đang được duyệt. Hãy quay lại vào <t:{next_timestamp}:R> nhé!",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

        total_reward = 5000

        # Cập nhật DB
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET last_weekly = $1 WHERE discord_id = $2",
            now, uid
        )
        
        # Cộng tiền
        await add_event_points(self.bot, uid, total_reward, is_earned=True)

        # Thưởng thêm Lootbox
        from cogs.events.lootbox.lootbox_config import LB_COMMON
        from cogs.events.lootbox.lootbox_cmd import _add_lootbox_to_inventory
        await _add_lootbox_to_inventory(self.bot, uid, LB_COMMON, 2)

        # Trả về thông báo
        embed = discord.Embed(
            title="💎 Lương Tuần Đã Về!",
            description=(
                f"🎉 Chúc mừng bạn đã nhận **{total_reward:,}** điểm lương tuần!\n"
                f"<:gift_00_symbol:1536003307011842099> **Thưởng Thêm:** 2x 📦 Lootbox Common\n"
                f"Hãy dùng số điểm này thật khôn ngoan tại `{ctx.prefix}shop` hoặc các sòng bài Casino nhé!"
            ),
            color=0xFFD700  # Màu vàng
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Rewards(bot))
