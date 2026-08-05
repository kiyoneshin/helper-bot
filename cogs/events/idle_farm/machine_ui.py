"""
machine_ui.py — Giao diện hệ thống Máy Chế Biến (y!machine)
=============================================================
Hiển thị dạng danh sách 10 slot hàng đợi.
- y!craft thêm máy vào slot trống
- Nút Thu Hoạch lấy hết slot đã xong
- Nút 3 máy để thêm recipe (ephemeral Select)
"""
import time
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
    """Chuyển giây thành chuỗi hiển thị đẹp."""
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
    """Tra tên đẹp cho bất kỳ item_id nào."""
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.woodcutting.woodcutting_config import WOODCUTTING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS

    if item_id in MINING_LOOT:
        i = MINING_LOOT[item_id]
        return f"{i['icon']} {i['name']}"
    if item_id in WOODCUTTING_LOOT:
        i = WOODCUTTING_LOOT[item_id]
        return f"{i['icon']} {i['name']}"
    if item_id in FISH_LOOT:
        i = FISH_LOOT[item_id]
        return f"{i['icon']} {i['name']}"
    if item_id in ARTISAN_GOODS:
        i = ARTISAN_GOODS[item_id]
        return f"{i['icon']} {i['name']}"
    # Crop: e.g. "tomato_normal"
    if "_" in item_id:
        parts = item_id.rsplit("_", 1)
        seed_id, quality = parts[0], parts[1]
        seed = SEEDS.get(seed_id)
        if seed:
            qual_icon = QUALITY_EMOJIS.get(quality, "")
            return f"{seed['icon']} {seed['name']}{(' ' + qual_icon) if qual_icon else ''}"
    return item_id


def _build_ingredient_summary(ingredients: Dict[str, int]) -> str:
    """Tóm tắt nguyên liệu thành chuỗi ngắn gọn."""
    parts = []
    for item_id, qty in ingredients.items():
        name = _get_item_display_name(item_id)
        parts.append(f"{name} x{qty}")
    return " + ".join(parts)


def _get_queue_list(farm_data: Dict[str, Any]) -> list:
    """
    Lấy danh sách hàng đợi theo thứ tự thêm vào (start_time).
    Trả về list[(machine_id, queue_item)].
    """
    machine_queue: Dict[str, Any] = farm_data.get("machine_queue", {})
    items = list(machine_queue.items())
    items.sort(key=lambda x: x[1].get("start_time", 0))
    return items


# ---------------------------------------------------------------------------
# EMBED BUILDER
# ---------------------------------------------------------------------------

def build_machine_embed(
    author: discord.Member | discord.User,
    farm_data: Dict[str, Any],
) -> discord.Embed:
    """
    Embed dạng danh sách 10 slot hàng đợi.

    Slot có máy:
      N. [icon] [Tên máy]: [nguyên liệu] → [icon SP] [Tên SP] | ✅ Xong! / ⏳ còn X

    Slot trống:
      N. ▫️ *trống*
    """
    now = time.time()
    queue_list = _get_queue_list(farm_data)
    num_active = len(queue_list)
    ready_count = sum(
        1 for _, item in queue_list
        if now >= item.get("finish_time", float("inf"))
    )

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
        header += "\n*Thêm nguyên liệu vào máy bằng nút bấm bên dưới hoặc lệnh `y!craft <máy> <recipe>`.*"
    embed.description = header

    lines = []
    for i in range(MAX_QUEUE_SLOTS):
        num = i + 1
        if i < len(queue_list):
            machine_id, item = queue_list[i]
            machine = MACHINES.get(machine_id, {})
            machine_icon = machine.get("icon", "⚙️")
            machine_name = machine.get("name", machine_id)

            output_id = item.get("output_id", "")
            output_info = ARTISAN_GOODS.get(output_id, {})
            output_display = f"{output_info.get('icon', '')} {output_info.get('name', output_id)}"

            recipe_id = item.get("recipe_id", "")
            recipe = RECIPES.get(recipe_id, {})
            ingredients_str = _build_ingredient_summary(recipe.get("ingredients", {}))

            finish_time = item.get("finish_time", 0)
            if now >= finish_time:
                status = "✅ **Xong!**"
            else:
                remaining = int(finish_time - now)
                status = f"⏳ còn **{_format_duration(remaining)}**"

            lines.append(
                f"`{num:>2}.` {machine_icon} **{machine_name}**: "
                f"{ingredients_str} → {output_display} | {status}"
            )
        else:
            lines.append(f"`{num:>2}.` ▫️ *trống*")

    embed.add_field(
        name="📋 Hàng Đợi Chế Biến",
        value="\n".join(lines),
        inline=False,
    )

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(
        text="Dùng y!bag để bán thành phẩm sau khi thu hoạch  |  y!craft <máy> <recipe> để thêm vào hàng đợi"
    )
    return embed


# ---------------------------------------------------------------------------
# SELECT MENU — CHỌN RECIPE (ephemeral)
# ---------------------------------------------------------------------------

class RecipeSelect(discord.ui.Select):
    """Dropdown chọn recipe cho 1 máy, đưa vào hàng đợi."""

    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        machine_id: str,
        farm_data: Dict[str, Any],
        author: discord.Member | discord.User,
    ):
        self.bot = bot
        self.user_id = user_id
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
                desc = "⚠️ Chưa đủ nguyên liệu để chế"

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

        # Kiểm tra slot đầy
        queue_list = _get_queue_list(farm_data)
        if len(queue_list) >= MAX_QUEUE_SLOTS:
            return await interaction.response.send_message(
                f"❌ Hàng đợi chế biến đã đầy rồi! ({MAX_QUEUE_SLOTS}/{MAX_QUEUE_SLOTS} slot)\n"
                f"Nhấn **Thu Hoạch** để lấy thành phẩm xong rồi thêm tiếp nhé!",
                ephemeral=True,
            )

        # Kiểm tra máy đang bận
        if self.machine_id in machine_queue:
            q = machine_queue[self.machine_id]
            finish_time = q.get("finish_time", 0)
            if now < finish_time:
                remaining = _format_duration(int(finish_time - now))
                return await interaction.response.send_message(
                    f"⏳ **{MACHINES[self.machine_id]['name']}** đang chạy rồi!\n"
                    f"Còn **{remaining}** nữa mới xong. Đợi hoặc thu hoạch khi thấy ✅ nhé!",
                    ephemeral=True,
                )

        # Kiểm tra nguyên liệu — liệt kê đầy đủ chỗ thiếu
        missing = []
        for item_id, qty_needed in recipe["ingredients"].items():
            qty_have = inventory.get(item_id, 0)
            if qty_have < qty_needed:
                name = _get_item_display_name(item_id)
                missing.append(f"{name} (thiếu {qty_needed - qty_have}, có {qty_have}/{qty_needed})")

        if missing:
            missing_str = "\n".join(f"• {m}" for m in missing)
            return await interaction.response.send_message(
                f"❌ Không đủ nguyên liệu để chế **{recipe['name']}**!\n{missing_str}",
                ephemeral=True,
            )

        # Trừ nguyên liệu
        for item_id, qty_needed in recipe["ingredients"].items():
            inventory[item_id] = inventory.get(item_id, 0) - qty_needed
            if inventory[item_id] <= 0:
                inventory.pop(item_id, None)

        # Thêm vào queue
        finish_time = now + recipe["duration_seconds"]
        machine_queue[self.machine_id] = {
            "recipe_id": recipe_id,
            "recipe_name": recipe["name"],
            "output_id": recipe["output_id"],
            "output_qty": recipe["output_qty"],
            "start_time": now,
            "finish_time": finish_time,
        }
        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)

        output_info = ARTISAN_GOODS.get(recipe["output_id"], {})
        duration_str = _format_duration(recipe["duration_seconds"])
        await interaction.response.send_message(
            f"⚙️ Đã cho vào **{MACHINES[self.machine_id]['name']}**!\n"
            f"{recipe['icon']} **{recipe['name']}** → "
            f"{output_info.get('icon', '')} **{output_info.get('name', '')}**\n"
            f"⌛ Hoàn thành sau: **{duration_str}**",
            ephemeral=True,
        )

        new_farm = await get_farm_data(self.bot, self.user_id)
        new_view = MachineView(self.bot, self.user_id, self.author, new_farm)
        await interaction.edit_original_response(
            embed=build_machine_embed(self.author, new_farm),
            view=new_view,
        )


# ---------------------------------------------------------------------------
# MACHINE VIEW
# ---------------------------------------------------------------------------

class MachineView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        author: discord.Member | discord.User,
        farm_data: Dict[str, Any],
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author

        now = time.time()
        queue_list = _get_queue_list(farm_data)
        num_active = len(queue_list)
        has_ready = any(
            now >= item.get("finish_time", float("inf"))
            for _, item in queue_list
        )
        queue_full = num_active >= MAX_QUEUE_SLOTS
        machine_queue = farm_data.get("machine_queue", {})

        # --- Row 0: Nút Thu Hoạch ---
        harvest_btn = discord.ui.Button(
            label="Thu Hoạch",
            emoji="🧺",
            style=discord.ButtonStyle.success if has_ready else discord.ButtonStyle.secondary,
            row=0,
        )
        harvest_btn.callback = self._harvest_callback
        self.add_item(harvest_btn)

        # --- Row 1: Nút 3 máy ---
        machine_defs = [
            ("keg",     "🍺", "Keg"),
            ("jar",     "🫙", "Jar"),
            ("furnace", "🔥", "Lò Rèn"),
        ]
        for machine_id, icon, label in machine_defs:
            in_queue = machine_id in machine_queue
            if in_queue:
                q_finish = machine_queue[machine_id].get("finish_time", 0)
                style = discord.ButtonStyle.success if now >= q_finish else discord.ButtonStyle.secondary
            else:
                style = discord.ButtonStyle.primary

            btn = discord.ui.Button(
                label=label,
                emoji=icon,
                style=style,
                disabled=(queue_full and not in_queue),
                row=1,
            )
            btn.callback = self._make_machine_callback(machine_id)
            self.add_item(btn)

        # --- Row 2: Làm Mới ---
        refresh_btn = discord.ui.Button(
            label="Làm Mới",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

    # -----------------------------------------------------------------------

    def _make_machine_callback(self, machine_id: str):
        async def _callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                return await interaction.response.send_message(
                    "❌ Đây không phải khu chế biến của bạn!", ephemeral=True
                )

            fresh_farm = await get_farm_data(self.bot, self.user_id)
            now = time.time()
            machine_queue = fresh_farm.get("machine_queue", {})
            queue_list = _get_queue_list(fresh_farm)

            # Nếu máy đang trong queue và đã xong → tự động thu hoạch
            if machine_id in machine_queue:
                q = machine_queue[machine_id]
                finish_time = q.get("finish_time", 0)
                if now >= finish_time:
                    output_id = q["output_id"]
                    output_qty = q["output_qty"]
                    inv = fresh_farm.setdefault("inventory", {})
                    inv[output_id] = inv.get(output_id, 0) + output_qty
                    machine_queue.pop(machine_id)
                    fresh_farm["machine_queue"] = machine_queue
                    await save_farm_data(self.bot, self.user_id, fresh_farm)
                    output_info = ARTISAN_GOODS.get(output_id, {})
                    await interaction.response.send_message(
                        f"✅ Lấy thành công **{output_qty}x {output_info.get('icon', '')} "
                        f"{output_info.get('name', output_id)}** từ **{MACHINES[machine_id]['name']}**!\n"
                        f"*(Kiểm tra `y!bag` để bán nhé!)*",
                        ephemeral=True,
                    )
                    new_farm = await get_farm_data(self.bot, self.user_id)
                    new_view = MachineView(self.bot, self.user_id, self.author, new_farm)
                    return await interaction.edit_original_response(
                        embed=build_machine_embed(self.author, new_farm),
                        view=new_view,
                    )
                else:
                    remaining = _format_duration(int(finish_time - now))
                    return await interaction.response.send_message(
                        f"⏳ **{MACHINES[machine_id]['name']}** đang bận! "
                        f"Còn **{remaining}** nữa. Đợi xong hoặc nhấn **Thu Hoạch** khi thấy ✅ nhé!",
                        ephemeral=True,
                    )

            # Slot đầy
            if len(queue_list) >= MAX_QUEUE_SLOTS:
                return await interaction.response.send_message(
                    f"❌ Hàng đợi đang đầy! ({MAX_QUEUE_SLOTS}/{MAX_QUEUE_SLOTS} slot)\n"
                    f"Thu hoạch bớt thành phẩm rồi mới thêm tiếp được.",
                    ephemeral=True,
                )

            # Mở Select Menu
            select = RecipeSelect(
                self.bot, self.user_id, machine_id, fresh_farm, self.author
            )
            temp_view = discord.ui.View(timeout=60)
            temp_view.add_item(select)
            machine = MACHINES[machine_id]
            await interaction.response.send_message(
                f"⚙️ **{machine['icon']} {machine['name']}** — Chọn công thức muốn chế biến:",
                view=temp_view,
                ephemeral=True,
            )

        return _callback

    # -----------------------------------------------------------------------

    async def _harvest_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "❌ Đây không phải khu chế biến của bạn!", ephemeral=True
            )

        farm_data = await get_farm_data(self.bot, self.user_id)
        machine_queue = farm_data.get("machine_queue", {})
        now = time.time()
        inventory = farm_data.setdefault("inventory", {})

        harvested = []
        for machine_id in list(machine_queue.keys()):
            item = machine_queue[machine_id]
            if now >= item.get("finish_time", float("inf")):
                output_id = item["output_id"]
                output_qty = item["output_qty"]
                inventory[output_id] = inventory.get(output_id, 0) + output_qty
                machine_queue.pop(machine_id)
                output_info = ARTISAN_GOODS.get(output_id, {})
                harvested.append(
                    f"{output_qty}x {output_info.get('icon', '')} {output_info.get('name', output_id)}"
                )

        if not harvested:
            return await interaction.response.send_message(
                "🧺 Chưa có thành phẩm nào sẵn sàng để thu hoạch!\n"
                "*(Hãy đợi máy chạy xong. Slot ✅ mới lấy được)*",
                ephemeral=True,
            )

        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)

        items_str = "\n".join(f"• **{h}**" for h in harvested)
        await interaction.response.send_message(
            f"✅ Thu hoạch thành công **{len(harvested)}** loại thành phẩm!\n"
            f"{items_str}\n"
            f"*(Dùng `y!bag` để xem và bán)*",
            ephemeral=True,
        )
        new_farm = await get_farm_data(self.bot, self.user_id)
        new_view = MachineView(self.bot, self.user_id, self.author, new_farm)
        await interaction.edit_original_response(
            embed=build_machine_embed(self.author, new_farm),
            view=new_view,
        )

    # -----------------------------------------------------------------------

    async def _refresh_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "❌ Đây không phải khu chế biến của bạn!", ephemeral=True
            )
        new_farm = await get_farm_data(self.bot, self.user_id)
        new_view = MachineView(self.bot, self.user_id, self.author, new_farm)
        await interaction.response.edit_message(
            embed=build_machine_embed(self.author, new_farm),
            view=new_view,
        )
