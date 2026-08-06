import discord
from discord.ext import commands

from cogs.events.idle_farm.farm_db import get_farm_data, get_and_update_stamina
from cogs.common.db import check_not_locked
from .woodcutting_ui import WoodcuttingView, build_woodcutting_embed

class WoodcuttingCog(commands.Cog, name="Woodcutting"):
    """🌲 Cog Lâm Nghiệp — Chặt gỗ."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="chop", aliases=["chatcay", "woodcut"])
    @check_not_locked()
    async def chop_cmd(self, ctx: commands.Context) -> None:
        """🪓 Vào Rừng đốn củi."""
        user_id = str(ctx.author.id)

        stamina = await get_and_update_stamina(self.bot, user_id, ctx.channel.id)
        farm_data = await get_farm_data(self.bot, user_id)

        embed = build_woodcutting_embed(ctx.author, stamina, farm_data)
        view = WoodcuttingView(self.bot, user_id, ctx.author, stamina)

        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WoodcuttingCog(bot))
