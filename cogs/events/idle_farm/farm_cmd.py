"""
farm_cmd.py — Lệnh người dùng để khởi động giao diện Nông Trại
==============================================================
Nơi tích hợp các thành phần DB, UI vào lệnh bot.
"""

import discord
from discord.ext import commands

from .farm_db import get_farm_data
from cogs.common.db import fetchval_db, check_not_locked
from .farm_ui import FarmView, build_farm_embed
from .upgrade_ui import UpgradeView, build_upgrade_embed


class IdleFarmCog(commands.Cog):
    """🌻 Cog Mini-game Idle Farm (Nông Trại Nhàn Rỗi)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="farm",
        aliases=["nongtrai"],
        description="Quản lý nông trại của bạn (Trồng trọt, thu hoạch, nâng cấp).",
    )
    @check_not_locked()
    async def farm_cmd(self, ctx: commands.Context) -> None:
        """🚜 Mở giao diện Nông Trại của bạn."""
        user_id = str(ctx.author.id)
        
        # 1. Fetch dữ liệu Nông Trại
        farm_data = await get_farm_data(self.bot, user_id)
        
        # 2. Xây dựng Embed trực quan
        embed = build_farm_embed(ctx.author, farm_data)
        
        # 3. Khởi tạo Giao Diện View
        view = FarmView(self.bot, user_id, ctx.author, farm_data)
        
        # 4. Gửi kết quả
        await ctx.send(embed=embed, view=view)


    @commands.hybrid_command(name="upgrade", aliases=["nangcap", "morong"])
    async def upgrade_cmd(self, ctx: commands.Context) -> None:
        """🚜 Mở rộng thêm ô đất cho Nông trại."""
        user_id = str(ctx.author.id)
        
        farm_data = await get_farm_data(self.bot, user_id)
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", user_id)
        points = float(user_points) if user_points else 0.0
        
        embed = build_upgrade_embed(ctx.author, farm_data, points)
        view = UpgradeView(self.bot, user_id, ctx.author, farm_data)
        
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="machine", aliases=["chebien", "maymoc"])
    async def machine_cmd(self, ctx: commands.Context) -> None:
        """🏭 Khu vực Chế biến Nông sản."""
        await ctx.send("Đang phát triển", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    # Nạp module cog vào bot
    await bot.add_cog(IdleFarmCog(bot))
