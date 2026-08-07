"""
mining_cmd.py — Lệnh kmine cho Khu Mỏ
========================================
Khởi tạo giao diện Khu Mỏ và hiển thị cho người chơi.
"""
import discord
from discord.ext import commands

from cogs.events.idle_farm.farm_db import get_farm_data, get_and_update_stamina
from .mining_ui import MiningView, build_mining_embed
from cogs.common.db import check_not_locked


class MiningCog(commands.Cog, name="Mining"):
    """⛏️ Cog Khu Mỏ — Đào quặng để tích lũy tài nguyên."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="mine", aliases=["dao", "khoamo", "mining"])
    @check_not_locked()
    async def mine_cmd(self, ctx: commands.Context) -> None:
        """⛏️ Vào Khu Mỏ để đào quặng."""
        user_id = str(ctx.author.id)

        # 1. Tính thể lực hiện tại (bao gồm hồi phục theo thời gian)
        stamina = await get_and_update_stamina(self.bot, user_id, ctx.channel.id)

        # 2. Lấy farm_data để hiển thị kho quặng
        farm_data = await get_farm_data(self.bot, user_id)

        # 3. Render giao diện và gửi
        embed = build_mining_embed(ctx.author, stamina, farm_data)
        view = MiningView(self.bot, user_id, ctx.author, stamina)

        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MiningCog(bot))
