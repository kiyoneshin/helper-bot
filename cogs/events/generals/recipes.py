import discord
from discord.ext import commands

from cogs.common.db import check_not_locked
from cogs.events.mining.mining_config import PICKAXE_UPGRADE_COST, MINING_LOOT, MAX_PICKAXE_LEVEL
from cogs.events.fishing.fishing_config import ROD_UPGRADE_COST, FISH_LOOT, MAX_ROD_LEVEL
from cogs.events.woodcutting.woodcutting_config import AXE_UPGRADE_COST, WOODCUTTING_LOOT, MAX_AXE_LEVEL

ALL_ITEMS = {**MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT}

class RecipesCog(commands.Cog, name="Recipes"):
    """🛠️ Cog Bách khoa toàn thư Công Thức (Recipes)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_cost(self, cost_pts: int, cost_items: dict) -> str:
        items_str = ", ".join(
            f"**{v}** {ALL_ITEMS[k]['icon']} {ALL_ITEMS[k]['name']}"
            for k, v in cost_items.items()
            if k in ALL_ITEMS
        )
        return f"**{cost_pts:,.0f} Điểm** + {items_str}"

    @commands.hybrid_command(name="recipe", aliases=["recipes", "crafting"])
    @check_not_locked()
    async def recipe_cmd(self, ctx: commands.Context) -> None:
        """🛠️ Xem bách khoa toàn thư công thức nâng cấp & chế tạo."""
        embed = discord.Embed(
            title="📜 Bách Khoa Toàn Thư Công Thức",
            description="Tổng hợp tất cả các công thức nâng cấp công cụ và chế tạo trong nông trại.\nSử dụng lệnh `y!upgrade` để tiến hành nâng cấp công cụ.",
            color=0xf39c12,
        )

        # 1. Cuốc Chim
        pickaxe_lines = []
        for level in range(1, MAX_PICKAXE_LEVEL):
            cost_pts, cost_items = PICKAXE_UPGRADE_COST[level]
            cost_str = self._format_cost(cost_pts, cost_items)
            pickaxe_lines.append(f"🔹 **Lên Cuốc Lv{level+1}:** {cost_str}")
        embed.add_field(name="⛏️ Nâng Cấp Cuốc Chim", value="\n".join(pickaxe_lines), inline=False)

        # 2. Cần Câu
        rod_lines = []
        for level in range(1, MAX_ROD_LEVEL):
            cost_pts, cost_items = ROD_UPGRADE_COST[level]
            cost_str = self._format_cost(cost_pts, cost_items)
            rod_lines.append(f"🔹 **Lên Cần Câu Lv{level+1}:** {cost_str}")
        embed.add_field(name="🎣 Nâng Cấp Cần Câu", value="\n".join(rod_lines), inline=False)

        # 3. Rìu
        axe_lines = []
        for level in range(1, MAX_AXE_LEVEL):
            cost_pts, cost_items = AXE_UPGRADE_COST[level]
            cost_str = self._format_cost(cost_pts, cost_items)
            axe_lines.append(f"🔹 **Lên Rìu Lv{level+1}:** {cost_str}")
        embed.add_field(name="🪓 Nâng Cấp Rìu", value="\n".join(axe_lines), inline=False)

        # 4. Chế Tạo Đặc Biệt
        embed.add_field(name="🛠️ Công Thức Đặc Biệt", value="*(Đang cập nhật - Coming soon...)*", inline=False)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Angelic Casino • Bách Khoa Toàn Thư 🌸")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecipesCog(bot))
