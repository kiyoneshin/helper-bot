"""
fishing_cmd.py — Lệnh kfish cho Minigame Câu Cá
==================================================
"""
import discord
from discord.ext import commands

from cogs.events.idle_farm.farm_db import get_and_update_stamina, get_farm_data
from .fishing_ui import FishingView, build_fishing_embed
from cogs.common.db import check_not_locked


class FishingCog(commands.Cog, name="Fishing"):
    """Cog Câu Cá — Minigame phản xạ để kiếm cá và tài nguyên."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="fish", aliases=["cauca", "fishing", "caca"])
    @check_not_locked()
    async def fish_cmd(self, ctx: commands.Context) -> None:
        """Đến Hồ Câu Cá để thử vận may!"""
        user_id = str(ctx.author.id)

        # 1. Cập nhật & tính thể lực, đồng thời lấy farm_data (có rod_level)
        stamina = await get_and_update_stamina(self.bot, user_id, ctx.channel.id)
        farm_data = await get_farm_data(self.bot, user_id)
        
        from cogs.events.idle_farm.farm_db import get_true_stamina_regen
        regen_interval = await get_true_stamina_regen(self.bot, user_id)

        # 2. Tạo giao diện và gửi
        embed = build_fishing_embed(ctx.author, stamina, farm_data, regen_interval)
        view  = FishingView(self.bot, user_id, ctx.author, stamina, farm_data, regen_interval)

        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FishingCog(bot))
