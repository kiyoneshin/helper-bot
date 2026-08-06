"""
machine_ui.py — Giao diện hệ thống Máy Chế Biến (y!machine)
=============================================================
Hiển thị 10 slot đặt máy cố định.
- Lệnh y!craft dùng để chế tạo máy ( Keg, Jar, Furnace ) và đặt vào slot trống.
- Giao diện y!machine hiển thị 10 slot.
- Nút bấm Keg/Jar/Furnace tìm máy trống trong slot để thao tác chế biến.
- Nút Thu Hoạch gom hết thành phẩm đã xong.
"""
import time
import uuid
import discord
from discord.ext import commands
from typing import Any, Dict

from .machine_config import MACHINES, RECIPES, ARTISAN_GOODS
from .farm_db import get_farm_data, save_farm_data

MAX_QUEUE_SLOTS = 10

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        return f"{m} phút"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}p" if m else f"{h}h"

def _get_item_display_name(item_id: str) -> str:
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.woodcutting.woodcutting_config import WOODCUTTING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS

    if item_id in MINING_LOOT: return f"{MINING_LOOT[item_id]['icon']} {MINING_LOOT[item_id]['name']}"
    if item_id in WOODCUTTING_LOOT: return f"{WOODCUTTING_LOOT[item_id]['icon']} {WOODCUTTING_LOOT[item_id]['name']}"
    if item_id in FISH_LOOT: return f"{FISH_LOOT[item_id]['icon']} {FISH_LOOT[item_id]['name']}"
    if item_id in ARTISAN_GOODS: return f"{ARTISAN_GOODS[item_id]['icon']} {ARTISAN_GOODS[item_id]['name']}"
    
    if "_" in item_id:
        parts = item_id.rsplit("_", 1)
        if len(parts) == 2:
            seed_id, quality = parts[0], parts[1]
            seed = SEEDS.get(seed_id)
            if seed:
                qual_icon = QUALITY_EMOJIS.get(quality, "")
                return f"{seed['icon']} {seed['name']}{(' ' + qual_icon) if qual_icon else ''}"
    return item_id

def _build_ingredient_summary(ingredients: Dict[str, int]) -> str:
    parts = []
    for item_id, qty in ingredients.items():
        parts.append(f"{_get_item_display_name(item_id)} x{qty}")
    return " + ".join(parts)

def _get_queue_list(farm_data: Dict[str, Any]) -> list:
    """
    Trả về danh sách các slot (slot_id, item_data).
    Tự động migrate dữ liệu cũ nếu dùng machine_id làm key.
    Tự động update status nếu finish_time đã qua.
    """
    machine_queue = farm_data.setdefault("machine_queue", {})
    keys_to_delete = []
    now = time.time()
    
    for k, v in list(machine_queue.items()):
        # Migrate old format where key was "keg", "jar", "furnace"
        if k in MACHINES:
            new_id = str(uuid.uuid4())
            new_v = {
                "machine_id": k,
                "status": "processing" if "finish_time" in v else "idle",
            }
            if "finish_time" in v:
                new_v["recipe_id"] = v.get("recipe_id")
                new_v["output_id"] = v.get("output_id")
                new_v["output_qty"] = v.get("output_qty", 1)
                new_v["start_time"] = v.get("start_time")
                new_v["finish_time"] = v.get("finish_time")
            machine_queue[new_id] = new_v
            keys_to_delete.append(k)
            
    for k in keys_to_delete:
        del machine_queue[k]

    # Cập nhật trạng thái "done"
    for k, v in machine_queue.items():
        if v.get("status") == "processing" and "finish_time" in v:
            if now >= v["finish_time"]:
                v["status"] = "done"

    # Trả về list và sort theo thời gian tạo (start_time hoặc arbitrary)
    items = list(machine_queue.items())
    items.sort(key=lambda x: x[1].get("start_time", 0) if "start_time" in x[1] else float("inf"))
    return items

# ---------------------------------------------------------------------------
# EMBED BUILDER
# ---------------------------------------------------------------------------

def build_machine_embed(
    author: discord.Member | discord.User,
    farm_data: Dict[str, Any],
) -> discord.Embed:
    queue_list = _get_queue_list(farm_data)
    num_active = len(queue_list)
    ready_count = sum(1 for _, item in queue_list if item.get("status") == "done")

    embed = discord.Embed(
        title="🏭 Khu Chế Biến Nông Sản",
        color=0xe67e22,
    )

    header = (
        f"👤 **{author.display_name}** | "
        f"📋 Slot đang dùng: **{num_active}/{MAX_QUEUE_SLOTS}**"
    )
    if ready_count:
        header += f"\n🧺 **{ready_count}** thành phẩm đang chờ thu hoạch! Nhấn nút **Thu Hoạch** nhé."
    else:
        header += "\n*Dùng lệnh `y!craft <id>` để xây thêm máy vào các slot trống.*"
    embed.description = header

    lines = []
    for i in range(MAX_QUEUE_SLOTS):
        num = i + 1
        if i < len(queue_list):
            slot_id, item = queue_list[i]
            machine_id = item.get("machine_id", "")
            machine = MACHINES.get(machine_id, {})
            machine_icon = machine.get("icon", "⚙️")
            machine_name = machine.get("name", machine_id)
            status = item.get("status", "idle")
            
            if status == "idle":
                lines.append(f"`{num:>2}.` {machine_icon} **{machine_name}**: (Trống) | 🟢 Chờ nguyên liệu")
            elif status == "done":
                output_id = item.get("output_id", "")
                output_info = ARTISAN_GOODS.get(output_id, {})
                output_display = f"{output_info.get('icon', '')} {output_info.get('name', output_id)}"
                lines.append(f"`{num:>2}.` {machine_icon} **{machine_name}**: {output_display} | ✅ Xong!")
            else:
                # processing
                output_id = item.get("output_id", "")
                output_info = ARTISAN_GOODS.get(output_id, {})
                output_display = f"{output_info.get('icon', '')} {output_info.get('name', output_id)}"
                
                recipe_id = item.get("recipe_id", "")
                recipe = RECIPES.get(recipe_id, {})
                ingredients_str = _build_ingredient_summary(recipe.get("ingredients", {}))
                
                now = time.time()
                finish_time = item.get("finish_time", 0)
                remaining = int(finish_time - now) if finish_time > now else 0
                lines.append(f"`{num:>2}.` {machine_icon} **{machine_name}**: {ingredients_str} → {output_display} | ⏳ còn **{_format_duration(remaining)}**")
        else:
            lines.append(f"`{num:>2}.` ▫️ *trống*")

    embed.add_field(
        name="📋 Danh Sách Máy (Slots)",
        value="\n".join(lines),
        inline=False,
    )

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(
        text="Dùng y!bag để bán thành phẩm  |  y!craft <id_máy> để xây máy mới"
    )
    return embed

# ---------------------------------------------------------------------------
# SELECT MENU — CHỌN RECIPE (ephemeral)
# ---------------------------------------------------------------------------

class RecipeSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        slot_id: str,
        machine_id: str,
        farm_data: Dict[str, Any],
        author: discord.Member | discord.User,
    ):
        self.bot = bot
        self.user_id = user_id
        self.slot_id = slot_id
        self.machine_id = machine_id
        self.author = author

        machine = MACHINES[machine_id]
        inventory = farm_data.get("inventory", {})
        options = []

        for recipe_id in machine["recipes"]:
            recipe = RECIPES[recipe_id]
            can_craft = all(
                inventory.get(k, 0) >= v
                for k, v in recipe["ingredients"].items()
            )
            output = ARTISAN_GOODS.get(recipe["output_id"], {})
            price = output.get("price", recipe["sell_price"])
            duration_str = _format_duration(recipe["duration_seconds"])
            desc = f"{duration_str} → Bán {price:,} điểm"
            if not can_craft:
                desc = "⚠️ Chưa đủ nguyên liệu"

            options.append(
                discord.SelectOption(
                    label=recipe["name"],
                    value=recipe_id,
                    description=desc[:100],
                    emoji=recipe["icon"],
                )
            )

        super().__init__(
            placeholder=f"📋 Chọn công thức cho {machine['name']}...",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "❌ Đây không phải khu chế biến của bạn!", ephemeral=True
            )

        recipe_id = self.values[0]
        recipe = RECIPES[recipe_id]
        farm_data = await get_farm_data(self.bot, self.user_id)
        inventory = farm_data.get("inventory", {})
        machine_queue = farm_data.setdefault("machine_queue", {})
        now = time.time()

        if self.slot_id not in machine_queue:
            return await interaction.response.send_message(
                "❌ Máy này không còn tồn tại hoặc đã bị lỗi!", ephemeral=True
            )
            
        slot_data = machine_queue[self.slot_id]
        if slot_data.get("status") != "idle":
            return await interaction.response.send_message(
                "❌ Máy này không còn trống nữa!", ephemeral=True
            )

        # Kiểm tra nguyên liệu
        missing = []
        for item_id, qty_needed in recipe["ingredients"].items():
            qty_have = inventory.get(item_id, 0)
            if qty_have < qty_needed:
                name = _get_item_display_name(item_id)
                missing.append(f"{name} (cần {qty_needed}, có {qty_have})")

        if missing:
            missing_str = "\n".join(f"• {m}" for m in missing)
            return await interaction.response.send_message(
                f"❌ Không đủ nguyên liệu để chế **{recipe['name']}**!\n{missing_str}",
                ephemeral=True,
            )

        # Trừ nguyên liệu
        for item_id, qty_needed in recipe["ingredients"].items():
            inventory[item_id] -= qty_needed
            if inventory[item_id] <= 0:
                del inventory[item_id]

        # Đưa vào chế biến
        finish_time = now + recipe["duration_seconds"]
        slot_data.update({
            "status": "processing",
            "recipe_id": recipe_id,
            "output_id": recipe["output_id"],
            "output_qty": recipe["output_qty"],
            "start_time": now,
            "finish_time": finish_time
        })
        
        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)

        output_info = ARTISAN_GOODS.get(recipe["output_id"], {})
        await interaction.response.send_message(
            f"⚙️ Bắt đầu chế biến: {recipe['icon']} **{recipe['name']}**\n"
            f"⌛ Hoàn thành sau **{_format_duration(recipe['duration_seconds'])}** → {output_info.get('icon','')} **{output_info.get('name','')}**",
            ephemeral=True,
        )

        embed = build_machine_embed(self.author, farm_data)
        if interaction.message:
            await interaction.message.edit(embed=embed)

class RecipeSelectView(discord.ui.View):
    def __init__(self, select_obj: discord.ui.Select):
        super().__init__(timeout=60)
        self.add_item(select_obj)

# ---------------------------------------------------------------------------
# MAIN VIEW — 4 NÚT
# ---------------------------------------------------------------------------

class MachineView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        farm_data: Dict[str, Any],
        author: discord.Member | discord.User,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self._update_buttons(farm_data)

    def _update_buttons(self, farm_data: Dict[str, Any]):
        self.clear_items()
        queue_list = _get_queue_list(farm_data)
        
        # Check harvestable
        ready_count = sum(1 for _, item in queue_list if item.get("status") == "done")
        btn_harvest = discord.ui.Button(
            label="Thu Hoạch",
            style=discord.ButtonStyle.success if ready_count > 0 else discord.ButtonStyle.secondary,
            emoji="🧺",
            custom_id="btn_harvest",
            disabled=(ready_count == 0),
            row=0,
        )
        btn_harvest.callback = self._harvest_callback
        self.add_item(btn_harvest)

        # Nút cho các máy
        machine_styles = {
            "keg": ("🍺", "Keg", discord.ButtonStyle.primary),
            "jar": ("🫙", "Jar", discord.ButtonStyle.primary),
            "furnace": ("🔥", "Furnace", discord.ButtonStyle.primary),
        }

        for machine_id, (icon, label, style) in machine_styles.items():
            # Find if there is an idle slot for this machine
            idle_count = sum(1 for _, item in queue_list if item.get("machine_id") == machine_id and item.get("status") == "idle")
            
            btn = discord.ui.Button(
                label=f"{label}" + (f" ({idle_count})" if idle_count else ""),
                style=style if idle_count > 0 else discord.ButtonStyle.secondary,
                emoji=icon,
                custom_id=f"btn_machine_{machine_id}",
                row=0,
            )
            btn.callback = self._make_machine_callback(machine_id)
            self.add_item(btn)

    async def _harvest_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "❌ Bạn không thể thao tác trên nông trại người khác!", ephemeral=True
            )

        farm_data = await get_farm_data(self.bot, self.user_id)
        queue_list = _get_queue_list(farm_data)
        inventory = farm_data.get("inventory", {})
        machine_queue = farm_data.get("machine_queue", {})

        harvested_items = {}
        for slot_id, item in queue_list:
            if item.get("status") == "done":
                output_id = item["output_id"]
                output_qty = item.get("output_qty", 1)
                inventory[output_id] = inventory.get(output_id, 0) + output_qty
                
                # Update harvest msg
                harvested_items[output_id] = harvested_items.get(output_id, 0) + output_qty
                
                # Reset slot to idle
                item["status"] = "idle"
                item.pop("recipe_id", None)
                item.pop("output_id", None)
                item.pop("output_qty", None)
                item.pop("start_time", None)
                item.pop("finish_time", None)
                machine_queue[slot_id] = item

        if not harvested_items:
            return await interaction.response.send_message(
                "❌ Không có gì để thu hoạch!", ephemeral=True
            )

        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)

        # Build harvest message
        lines = []
        for out_id, qty in harvested_items.items():
            info = ARTISAN_GOODS.get(out_id, {})
            lines.append(f"**{qty}x** {info.get('icon', '')} {info.get('name', out_id)}")
        msg = "🧺 Thu hoạch thành công:\n" + "\n".join(lines)

        await interaction.response.send_message(msg, ephemeral=True)

        # Cập nhật lại UI
        embed = build_machine_embed(self.author, farm_data)
        self._update_buttons(farm_data)
        if interaction.message:
            await interaction.message.edit(embed=embed, view=self)

    def _make_machine_callback(self, machine_id: str):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                return await interaction.response.send_message(
                    "❌ Bạn không có quyền thao tác!", ephemeral=True
                )
                
            farm_data = await get_farm_data(self.bot, self.user_id)
            queue_list = _get_queue_list(farm_data)
            
            # Find the first idle slot for this machine
            idle_slot_id = None
            for slot_id, item in queue_list:
                if item.get("machine_id") == machine_id and item.get("status") == "idle":
                    idle_slot_id = slot_id
                    break
                    
            if not idle_slot_id:
                return await interaction.response.send_message(
                    f"❌ Bạn không có cái {MACHINES[machine_id]['name']} nào đang trống! Vui lòng Thu Hoạch máy cũ hoặc xây thêm máy mới bằng lệnh `{ctx.prefix}craft`.", 
                    ephemeral=True
                )

            select = RecipeSelect(
                bot=self.bot,
                user_id=self.user_id,
                slot_id=idle_slot_id,
                machine_id=machine_id,
                farm_data=farm_data,
                author=self.author,
            )
            view = RecipeSelectView(select)
            await interaction.response.send_message(
                f"**{MACHINES[machine_id]['name']}** đang trống, bạn muốn chế biến gì?",
                view=view,
                ephemeral=True,
            )

        return callback

async def send_machine_panel(ctx: commands.Context) -> None:
    user_id = str(ctx.author.id)
    farm_data = await get_farm_data(ctx.bot, user_id)
    embed = build_machine_embed(ctx.author, farm_data)
    view = MachineView(ctx.bot, user_id, farm_data, ctx.author)
    await ctx.send(embed=embed, view=view)
