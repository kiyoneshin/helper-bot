import discord
from discord.ext import commands

from cogs.common.db import check_not_locked
from cogs.events.mining.mining_config import PICKAXE_UPGRADE_COST, MINING_LOOT, MAX_PICKAXE_LEVEL, PICKAXE_NAMES
from cogs.events.fishing.fishing_config import ROD_UPGRADE_COST, FISH_LOOT, MAX_ROD_LEVEL, ROD_NAMES
from cogs.events.woodcutting.woodcutting_config import AXE_UPGRADE_COST, WOODCUTTING_LOOT, MAX_AXE_LEVEL, AXE_NAMES
from cogs.events.idle_farm.machine_config import RECIPES, MACHINES, ARTISAN_GOODS
from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS
from cogs.common.item_config import ITEM_REGISTRY
from cogs.events.generals.cooking import RECIPES as COOKING_RECIPES

ALL_ITEMS = {**MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT}

def _get_item_name(item_id: str) -> str:
    if item_id in ALL_ITEMS:
        return f"{ALL_ITEMS[item_id]['icon']} {ALL_ITEMS[item_id]['name']}"
    if item_id in ARTISAN_GOODS:
        return f"{ARTISAN_GOODS[item_id]['icon']} {ARTISAN_GOODS[item_id]['name']}"
    if item_id in SEEDS:
        return f"{SEEDS[item_id]['icon']} {SEEDS[item_id]['name']}"
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

def _format_cost(cost_pts: int, cost_items: dict) -> str:
    items_str = ", ".join(
        f"**{v}** {_get_item_name(k)}"
        for k, v in cost_items.items()
    )
    return f"**{cost_pts:,.0f} Điểm** + {items_str}"

def _build_recipe_embed(ctx, category: str) -> discord.Embed:
    embed = discord.Embed(
        title="<:symbol_recipes:1535664863362158743> Bách Khoa Toàn Thư Công Thức",
        color=0xf39c12,
    )
    
    if category == "upgrade":
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1536036455367970916.gif")
        embed.description = f"Công thức nâng cấp công cụ.\nSử dụng lệnh `{ctx.prefix}upgrade` để nâng cấp."
        
        pickaxe_desc = {
            2: "Mở khóa tỷ lệ rớt Quặng Vàng (2%)",
            3: "Mở khóa tỷ lệ rớt Kim Cương (1%)",
            4: "Tăng mạnh tỷ lệ rớt Vàng và Kim Cương (4%)"
        }
        pickaxe_lines = []
        for level in range(1, MAX_PICKAXE_LEVEL):
            cost_pts, cost_items = PICKAXE_UPGRADE_COST[level]
            cost_str = _format_cost(cost_pts, cost_items)
            desc = pickaxe_desc.get(level+1, "")
            icon = PICKAXE_NAMES.get(level+1, "").split()[-1] if PICKAXE_NAMES.get(level+1) else ""
            pickaxe_lines.append(f"**Lên Cuốc Lv{level+1} {icon}:** {cost_str}\n  └ *{desc}*")
        embed.add_field(name="<:symbol_00_mining:1536007694920585356> Nâng Cấp Cuốc Chim", value="\n".join(pickaxe_lines), inline=False)

        rod_desc = {
            2: "Mở khóa tỷ lệ rớt Bạch Tuộc (2%)",
            3: "Mở khóa rớt Cá Huyền Thoại khi Perfect Catch",
            4: "Tăng mạnh tỷ lệ rớt Cá Huyền Thoại (2% - 5%)"
        }
        rod_lines = []
        for level in range(1, MAX_ROD_LEVEL):
            cost_pts, cost_items = ROD_UPGRADE_COST[level]
            cost_str = _format_cost(cost_pts, cost_items)
            desc = rod_desc.get(level+1, "")
            icon = ROD_NAMES.get(level+1, "").split()[-1] if ROD_NAMES.get(level+1) else ""
            rod_lines.append(f"**Lên Cần Câu Lv{level+1} {icon}:** {cost_str}\n  └ *{desc}*")
        embed.add_field(name="<:symbol_00_fishing:1536007692437422171> Nâng Cấp Cần Câu", value="\n".join(rod_lines), inline=False)

        axe_desc = {
            2: "Mở khóa tỷ lệ rớt Nhựa Cây (1%)",
            3: "Tăng mạnh rớt Gỗ Cứng (18%) và Nhựa Cây (3%)",
            4: "Tăng mạnh rớt Nhựa Cây (6%) và Nhựa Thông (10%)"
        }
        axe_lines = []
        for level in range(1, MAX_AXE_LEVEL):
            cost_pts, cost_items = AXE_UPGRADE_COST[level]
            cost_str = _format_cost(cost_pts, cost_items)
            desc = axe_desc.get(level+1, "")
            icon = AXE_NAMES.get(level+1, "").split()[-1] if AXE_NAMES.get(level+1) else ""
            axe_lines.append(f"**Lên Rìu Lv{level+1} {icon}:** {cost_str}\n  └ *{desc}*")
        embed.add_field(name="<:symbol_00_woodcutting:1536007697491558491> Nâng Cấp Rìu", value="\n".join(axe_lines), inline=False)

    elif category == "machine":
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660945752326154.gif")
        embed.description = f"Công thức xây máy.\nSử dụng lệnh `{ctx.prefix}craft` để xây máy."
        
        build_machine_lines = [
            f"**[ID: 101] <:machine_08_keg:1535657702020354098> Thùng Ủ Rượu (Keg):** **30** {_get_item_name('wood')} + **1** {_get_item_name('copper_bar')} + **1** {_get_item_name('iron_bar')}",
            f"**[ID: 102] <:machine_09_jar:1535657704021037156> Máy Làm Mứt (Jar):** **30** {_get_item_name('wood')} + **20** {_get_item_name('stone')} + **2** {_get_item_name('coal')}",
            f"**[ID: 103] <:machine_10_furnace:1535657705958674452> Lò Rèn (Furnace):** **20** {_get_item_name('stone')} + **5** {_get_item_name('copper_ore')}",
            f"*(Dùng lệnh `{ctx.prefix}craft <id>` để xây máy vào 10 slot của bạn)*"
        ]
        embed.add_field(name="<:symbol_machine:1536297937498275850> Công Thức Xây Máy", value="\n".join(build_machine_lines), inline=False)

    elif category == "artisan":
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660945752326154.gif")
        embed.description = f"Công thức chế biến nông sản."
        
        machine_lines = []
        for machine_id, machine in MACHINES.items():
            machine_lines.append(f"**{machine['icon']} {machine['name']}**:")
            for recipe_id in machine['recipes']:
                r = RECIPES[recipe_id]
                ing_str = " + ".join(f"**{v}** {_get_item_name(k)}" for k, v in r["ingredients"].items())
                out_name = _get_item_name(r["output_id"])
                time_str = _format_duration(r["duration_seconds"])
                machine_lines.append(f"  └ **{r['name']}**: {ing_str} ➡️ **{r['output_qty']}** {out_name} ({time_str})")
        
        current_chunk = []
        current_len = 0
        part = 1
        for line in machine_lines:
            if current_len + len(line) + 1 > 1000:
                embed.add_field(name=f"<:symbol_machine:1536297937498275850> Công Thức Chế Biến (Phần {part})", value="\n".join(current_chunk), inline=False)
                current_chunk = []
                current_len = 0
                part += 1
            current_chunk.append(line)
            current_len += len(line) + 1
        
        if current_chunk:
            embed.add_field(name=f"<:symbol_machine:1536297937498275850> Công Thức Chế Biến (Phần {part})" if part > 1 else "Công Thức Chế Biến", value="\n".join(current_chunk), inline=False)

    elif category == "cook":
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660942875041822.gif")
        embed.description = f"Công thức nấu ăn.\nSử dụng lệnh `{ctx.prefix}kcook <id> [số lượng]` để nấu."
        
        cooking_lines = []
        for food_id, ingredients in COOKING_RECIPES.items():
            food_item = ITEM_REGISTRY.get(food_id)
            if not food_item: continue
            
            food_name = f"{food_item['icon']} {food_item['name']}"
            ing_strs = []
            for req in ingredients:
                amount = req['amount']
                req_type = req['type']
                ing_strs.append(f"**{amount}** {_get_item_name(req_type)}")
            
            ing_str = " + ".join(ing_strs)
            desc = food_item.get('description', '')
            cooking_lines.append(f"**[ID: {food_id}] {food_name}:** {ing_str}\n  └ *{desc}*")
        if cooking_lines:
            cooking_lines.append(f"*(Dùng lệnh `{ctx.prefix}cook <id> [số lượng]` để nấu ăn)*")
            # Split to avoid 1024 char limit
            current_chunk = []
            current_len = 0
            part = 1
            for line in cooking_lines:
                if current_len + len(line) + 1 > 1000:
                    embed.add_field(name=f"<:symbol_00_cooking:1536007684241756291> Công Thức Nấu Ăn (Phần {part})", value="\n".join(current_chunk), inline=False)
                    current_chunk = [line]
                    current_len = len(line)
                    part += 1
                else:
                    current_chunk.append(line)
                    current_len += len(line) + 1
            
            if current_chunk:
                embed.add_field(name=f"<:symbol_00_cooking:1536007684241756291> Công Thức Nấu Ăn (Phần {part})", value="\n".join(current_chunk), inline=False)

    embed.set_footer(text="Angelic Casino • Bách Khoa Toàn Thư 🌸")
    return embed

class RecipeSelect(discord.ui.Select):
    def __init__(self, author: discord.Member | discord.User, ctx, current: str = "upgrade"):
        self.author = author
        self.ctx = ctx
        options = [
            discord.SelectOption(
                label="Nâng Cấp Công Cụ",
                value="upgrade",
                emoji="<:symbol_00_crafting:1536007686389235733>",
                description="Cuốc chim, Cần câu, Rìu",
                default=(current == "upgrade"),
            ),
            discord.SelectOption(
                label="Xây Máy",
                value="machine",
                emoji="<:symbol_gear:1536007677468082266>",
                description="Công thức xây máy",
                default=(current == "machine"),
            ),
            discord.SelectOption(
                label="Chế Biến",
                value="artisan",
                emoji="<:symbol_machine:1536297937498275850>",
                description="Công thức mứt, ủ rượu, nung quặng",
                default=(current == "artisan"),
            ),
            discord.SelectOption(
                label="Nấu Ăn",
                value="cook",
                emoji="<:symbol_00_cooking:1536007684241756291>",
                description="Các món ăn gia tăng chỉ số",
                default=(current == "cook"),
            ),
        ]
        super().__init__(
            placeholder="Chọn danh mục công thức...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Bạn không có quyền thao tác menu này!", ephemeral=True)
            
        selected = self.values[0]
        for opt in self.options:
            opt.default = (opt.value == selected)

        embed = _build_recipe_embed(self.ctx, selected)
        await interaction.response.edit_message(embed=embed, view=self.view)

class RecipeView(discord.ui.View):
    def __init__(self, author: discord.Member | discord.User, ctx, default_tab: str = "upgrade"):
        super().__init__(timeout=120.0)
        self.author = author
        self.ctx = ctx
        self.select_menu = RecipeSelect(author, ctx, default_tab)
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        self.select_menu.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

class RecipesCog(commands.Cog, name="Recipes"):
    """Cog Bách khoa toàn thư Công Thức (Recipes)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="recipe", aliases=["recipes"])
    @check_not_locked()
    async def recipe_cmd(self, ctx: commands.Context, category: str = None) -> None:
        """Xem bách khoa toàn thư công thức nâng cấp & chế tạo."""
        
        cat_map = {
            "upgrade": "upgrade", "nangcap": "upgrade",
            "craft": "machine", "chetao": "machine", "machine": "machine", "maymoc": "machine",
            "artisan": "artisan", "chebien": "artisan",
            "cook": "cook", "nauan": "cook", "food": "cook",
        }
        
        default_tab = "upgrade"
        if category and category.lower() in cat_map:
            default_tab = cat_map[category.lower()]
            
        embed = _build_recipe_embed(ctx, default_tab)
        view = RecipeView(ctx.author, ctx, default_tab=default_tab)
        view.message = await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecipesCog(bot))
