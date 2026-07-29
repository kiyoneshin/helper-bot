"""
fishing_cmd.py — Lệnh y!fish cho Minigame Câu Cá
==================================================
"""
import discord
from discord.ext import commands

from cogs.events.idle_farm.farm_db import get_and_update_stamina
from .fishing_ui import FishingView, build_fishing_embed


class FishingCog(commands.Cog, name="Fishing"):
    """🎣 Cog Câu Cá — Minigame phản xạ để kiếm cá và tài nguyên."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="fish", aliases=["cauca", "fishing", "caca"])
    async def fish_cmd(self, ctx: commands.Context) -> None:
        """🎣 Đến Hồ Câu Cá để thử vận may!"""
        user_id = str(ctx.author.id)

        # 1. Cập nhật & tính thể lực hiện tại
        stamina = await get_and_update_stamina(self.bot, user_id)

        # 2. Tạo giao diện và gửi
        embed = build_fishing_embed(ctx.author, stamina)
        view = FishingView(self.bot, user_id, ctx.author, stamina)

        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FishingCog(bot))
