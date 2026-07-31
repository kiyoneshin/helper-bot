"""
event_stats.py — Quản lý điểm số & Bảng xếp hạng sự kiện
======================================================
Cung cấp các lệnh y!point (xem ví) và y!etop (bảng xếp hạng).
"""
import discord
from discord.ext import commands
from typing import Any

from cogs.common.db import get_or_create_event_profile, query_db


class EventStatsCog(commands.Cog):
    """📊 Cog Quản lý điểm số và Bảng xếp hạng Sự Kiện."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="point", aliases=["bal", "vi"])
    async def point_cmd(self, ctx: commands.Context) -> None:
        """Kiểm tra số dư và tổng điểm sự kiện của bạn."""
        uid = str(ctx.author.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        
        if not profile:
            await ctx.send("Không thể lấy dữ liệu hồ sơ sự kiện của bạn lúc này. Vui lòng thử lại sau!")
            return

        points = profile.get("points", 0)
        total_earned = profile.get("total_earned", 0)
        p2w = float(profile.get("p2w_multiplier", 1.0))
        
        if p2w <= 1.0:
            rank = "Dân Cày Chay 👥"
        elif p2w < 1.75:
            rank = "Đại Gia Tầm Trung 🌸"
        else:
            rank = "Chúa Tể P2W 👑"

        embed = discord.Embed(
            title=f"💳 Ví Sự Kiện Angelic — {ctx.author.display_name}",
            description=f"Hạng của bạn: **{rank}**",
            color=0xffb6c1
        )
        embed.add_field(
            name="🪙 Số dư hiện tại",
            value=f"`{points:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="🏆 Tổng điểm tích lũy",
            value=f"`{total_earned:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="⚡ Hệ số P2W",
            value=f"`x{p2w:.2f}`",
            inline=True
        )
        
        debt = profile.get("debt", 0.0)
        max_loan = total_earned * 0.5
        
        if debt > 0:
            embed.add_field(
                name="💸 Nợ ngân hàng",
                value=f"`{debt:,.0f}` điểm",
                inline=False
            )
        embed.add_field(
            name="🏦 Hạn mức vay",
            value=f"`{max_loan:,.0f}` điểm",
            inline=True if debt == 0 else False
        )
        
        embed.set_footer(text="Gõ y!shop để xem cửa hàng đổi quà nhé! 🌸")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="etop", aliases=["evtop", "eventtop", "eventop"])
    async def etop_cmd(self, ctx: commands.Context) -> None:
        """Xem Bảng Xếp Hạng Đua Top Điểm Sự Kiện."""
        sql = """
            SELECT discord_id, total_earned, points 
            FROM event_profiles 
            WHERE total_earned > 0 
            ORDER BY total_earned DESC 
            LIMIT 10;
        """
        rows = await query_db(self.bot, sql)

        if not rows:
            await ctx.send("📊 Bảng xếp hạng sự kiện hiện đang trống! Hãy là người đầu tiên chat để lấy điểm nhé.")
            return

        embed = discord.Embed(
            title="🏆 Bảng Xếp Hạng Sự Kiện Angelic ໒꒱",
            color=0xffb6c1
        )

        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = ""

        for idx, row in enumerate(rows):
            rank_icon = medals[idx] if idx < 3 else f"**#{idx + 1}.**"
            user_id = row["discord_id"]
            total_pts = row["total_earned"]
            current_pts = row["points"]

            leaderboard_text += (
                f"{rank_icon} <@{user_id}>\n"
                f"└ 🏆 Tổng cày: **`{total_pts:,}`** điểm *(Dư: `{current_pts:,}`)*\n\n"
            )

        embed.description = (
            "Vinh danh Top 10 chiến thần tích lũy nhiều điểm nhất trong sự kiện:\n\n"
            f"{leaderboard_text}"
        )
        
        # Sửa đổi: An toàn khi guild là None
        icon_url = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        if icon_url:
            embed.set_thumbnail(url=icon_url)
            
        embed.set_footer(text="Bảng xếp hạng dựa trên tổng điểm cày được (không bị trừ khi mua shop) 🌸")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventStatsCog(bot))
