import discord
from discord.ext import commands

from cogs.common.db import check_not_locked
from cogs.events.mining.mining_config import PICKAXE_UPGRADE_COST, MINING_LOOT, MAX_PICKAXE_LEVEL
from cogs.events.fishing.fishing_config import ROD_UPGRADE_COST, FISH_LOOT, MAX_ROD_LEVEL
from cogs.events.woodcutting.woodcutting_config import AXE_UPGRADE_COST, WOODCUTTING_LOOT, MAX_AXE_LEVEL
from cogs.events.idle_farm.machine_config import RECIPES, MACHINES, ARTISAN_GOODS
from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS

ALL_ITEMS = {**MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT}

def _get_item_name(item_id: str) -> str:
    if item_id in ALL_ITEMS:
        return f"{ALL_ITEMS[item_id]['icon']} {ALL_ITEMS[item_id]['name']}"
    if item_id in ARTISAN_GOODS:
        return f"{ARTISAN_GOODS[item_id]['icon']} {ARTISAN_GOODS[item_id]['name']}"
    if "_" in item_id:
        parts = item_id.rsplit("_", 1)
        if parts[0] in SEEDS:
            seed = SEEDS[parts[0]]
            emoji = QUALITY_EMOJIS.get(parts[1], "")
            return f"{seed['icon']} {seed['name']} {emoji}".strip()
    return item_id

def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60} phút"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}p" if m else f"{h}h"

class RecipesCog(commands.Cog, name="Recipes"):
    """🛠️ Cog Bách khoa toàn thư Công Thức (Recipes)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_cost(self, cost_pts: int, cost_items: dict) -> str:
        items_str = ", ".join(
            f"**{v}** {_get_item_name(k)}"
            for k, v in cost_items.items()
        )
        return f"**{cost_pts:,.0f} Điểm** + {items_str}"

    @commands.hybrid_command(name="recipe", aliases=["recipes"])
    @check_not_locked()
    async def recipe_cmd(self, ctx: commands.Context) -> None:
        """🛠️ Xem bách khoa toàn thư công thức nâng cấp & chế tạo."""
        embed = discord.Embed(
            title="📜 Bách Khoa Toàn Thư Công Thức",
            description=f"Tổng hợp tất cả các công thức nâng cấp công cụ và chế tạo trong nông trại.\nSử dụng lệnh `{ctx.prefix}upgrade` để nâng cấp công cụ, `{ctx.prefix}craft` để dùng máy.",
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

        # 4. Chế Tạo Máy Móc (Sắp tới)
        build_machine_lines = [
            f"🔹 **[ID: 61] 🍺 Thùng Ủ Rượu (Keg):** **30** {_get_item_name('wood_normal')} + **1** {_get_item_name('copper_bar')} + **1** {_get_item_name('iron_bar')}",
            f"🔹 **[ID: 62] 🫙 Máy Làm Mứt (Jar):** **30** {_get_item_name('wood_normal')} + **20** {_get_item_name('stone')} + **2** {_get_item_name('coal')}",
            f"🔹 **[ID: 63] 🔥 Lò Rèn (Furnace):** **20** {_get_item_name('stone')} + **5** {_get_item_name('copper_ore')}",
            "*(Dùng lệnh `kcraft <id>` để xây máy vào 10 slot của bạn)*"
        ]
        embed.add_field(name="🏗️ Công Thức Xây Máy", value="\n".join(build_machine_lines), inline=False)

        # 5. Công Thức Chế Biến Nông Sản
        machine_lines = []
        for machine_id, machine in MACHINES.items():
            machine_lines.append(f"**{machine['icon']} {machine['name']}**:")
            for recipe_id in machine['recipes']:
                r = RECIPES[recipe_id]
                ing_str = " + ".join(f"**{v}** {_get_item_name(k)}" for k, v in r["ingredients"].items())
                out_name = _get_item_name(r["output_id"])
                time_str = _format_duration(r["duration_seconds"])
                machine_lines.append(f"  └ 🔹 **{r['name']}**: {ing_str} ➡️ **{r['output_qty']}** {out_name} ({time_str})")
        
        embed.add_field(name="🏭 Công Thức Chế Biến", value="\n".join(machine_lines), inline=False)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Angelic Casino • Bách Khoa Toàn Thư 🌸")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecipesCog(bot))

