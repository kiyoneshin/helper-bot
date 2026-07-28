"""
farm_cmd.py — Lệnh người dùng để khởi động giao diện Nông Trại
==============================================================
Nơi tích hợp các thành phần DB, UI vào lệnh bot.
"""

import discord
from discord.ext import commands

from .farm_db import get_farm_data
from .farm_ui import FarmView, build_farm_embed

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
        
        # 3. Khởi tạo Giao Diện View (Select + Button)
        view = FarmView(self.bot, user_id, ctx.author)
        
        # 4. Gửi kết quả
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    # Nạp module cog vào bot
    await bot.add_cog(IdleFarmCog(bot))
