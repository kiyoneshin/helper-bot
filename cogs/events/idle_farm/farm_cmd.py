"""
farm_cmd.py — Lệnh người dùng để khởi động giao diện Nông Trại
==============================================================
Nơi tích hợp các thành phần DB, UI vào lệnh bot.
"""

import discord
from discord.ext import commands

from .farm_db import get_farm_data
from .farm_ui import FarmView, build_farm_embed
from .bag_ui import BagView, build_bag_embed

class IdleFarmCog(commands.Cog):
    """🌻 Cog Mini-game Idle Farm (Nông Trại Nhàn Rỗi)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="farm", aliases=["nongtrai"])
    async def farm_cmd(self, ctx: commands.Context) -> None:
        """🚜 Mở giao diện Nông Trại của bạn."""
        user_id = str(ctx.author.id)
        
        # 1. Fetch dữ liệu Nông Trại
        farm_data = await get_farm_data(self.bot, user_id)
        
        # 2. Xây dựng Embed trực quan
        embed = build_farm_embed(ctx.author, farm_data)
        
        # 3. Khởi tạo Giao Diện View
        view = FarmView(self.bot, user_id, ctx.author)
        
        # 4. Gửi kết quả
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="shop", aliases=["cuahang"])
    async def shop_cmd(self, ctx: commands.Context) -> None:
        """🛒 Mở cửa hàng Nông nghiệp."""
        # TODO: Chuyển FarmShopSelect sang đây
        await ctx.send("Đang phát triển", ephemeral=True)

    @commands.hybrid_command(name="bag", aliases=["khodo", "inventory"])
    async def bag_cmd(self, ctx: commands.Context) -> None:
        """🎒 Xem kho đồ Nông trại của bạn."""
        user_id = str(ctx.author.id)
        farm_data = await get_farm_data(self.bot, user_id)
        
        embed = build_bag_embed(ctx.author, farm_data)
        view = BagView(self.bot, user_id, ctx.author)
        
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="machine", aliases=["chebien", "maymoc"])
    async def machine_cmd(self, ctx: commands.Context) -> None:
        """🏭 Khu vực Chế biến Nông sản."""
        await ctx.send("Đang phát triển", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    # Nạp module cog vào bot
    await bot.add_cog(IdleFarmCog(bot))
