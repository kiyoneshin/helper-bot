"""
machine_ui.py — Giao diện hệ thống Máy Chế Biến (kmachine)
=============================================================
Hiển thị 10 slot đặt máy cố định.
- Lệnh kcraft dùng để chế tạo máy ( Keg, Jar, Furnace ) và đặt vào slot trống.
- Giao diện kmachine hiển thị 10 slot.
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

    if item_id in ("wood", "wood_normal") and "wood" in WOODCUTTING_LOOT: return f"{WOODCUTTING_LOOT['wood']['icon']} {WOODCUTTING_LOOT['wood']['name']}"
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
    page: int = 0,
    per_page: int = 5,
) -> discord.Embed:
    queue_list = _get_queue_list(farm_data)
    num_active = len(queue_list)
    ready_count = sum(1 for _, item in queue_list if item.get("status") == "done")

    embed = discord.Embed(
        title="Khu Chế Biến Nông Sản",
        color=0xe67e22,
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660945752326154.gif")

    header_parts = [
        f"**{author.display_name}** | <:symbol_boards:1536007665153474681> Máy sở hữu: **{num_active}/{MAX_QUEUE_SLOTS}**"
    ]
    if ready_count > 0:
        header_parts.append(f"<:symbol_right:1536629912515903578> **{ready_count}** máy đã hoàn thành! Nhấn nút **Thu Hoạch** để nhận.")
    elif num_active < MAX_QUEUE_SLOTS:
        header_parts.append(f"💡 Còn trống **{MAX_QUEUE_SLOTS - num_active}** slot máy. Dùng `kcraft` để chế tạo thêm.")
    else:
        header_parts.append("💡 Đã đạt tối đa slot máy chế biến.")

    header = "\n".join(header_parts)

    display_slots = max(1, num_active)
    total_pages = max(1, (display_slots + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    end_idx = min(start_idx + per_page, num_active)

    lines = []
    if num_active == 0:
        lines.append("*Bạn chưa sở hữu máy chế biến nào!*\n*Dùng lệnh `kcraft` để chế tạo Thùng Ủ (Keg), Hũ Mứt (Jar), hoặc Lò Rèn (Furnace).*")
    else:
        now = time.time()
        for i in range(start_idx, end_idx):
            num = i + 1
            slot_id, item = queue_list[i]
            machine_id = item.get("machine_id", "")
            machine = MACHINES.get(machine_id, {})
            machine_icon = machine.get("icon", "<:symbol_machine:1536297937498275850>")
            machine_name = machine.get("name", machine_id)
            status = item.get("status", "idle")

            if status == "idle":
                lines.append(f"`{num:>2}.` {machine_icon} **{machine_name}** • 🟢 *Rảnh*")
            elif status == "done":
                output_id = item.get("output_id") or (RECIPES.get(item.get("recipe_id", {}), {}).get("output_id") if item.get("recipe_id") else "")
                output_info = ARTISAN_GOODS.get(output_id, {})
                output_icon = output_info.get("icon", "")
                output_name = output_info.get("name", output_id or "Thành phẩm")
                lines.append(f"`{num:>2}.` {machine_icon} ➔ {output_icon} **{output_name}** • ✅ **Xong!** *(Thu hoạch)*")
            else:
                # processing
                output_id = item.get("output_id") or (RECIPES.get(item.get("recipe_id", {}), {}).get("output_id") if item.get("recipe_id") else "")
                output_info = ARTISAN_GOODS.get(output_id, {})
                output_icon = output_info.get("icon", "")
                output_name = output_info.get("name", output_id or "Đang nấu")

                finish_time = item.get("finish_time") or 0
                remaining = int(finish_time - now) if finish_time > now else 0
                lines.append(f"`{num:>2}.` {machine_icon} ➔ {output_icon} **{output_name}** • ⏳ **{_format_duration(remaining)}**")

    slots_text = "\n".join(lines)

    if num_active > 0:
        desc_content = (
            f"{header}\n\n"
            f"<:symbol_boards:1536007665153474681> **Danh Sách Máy (Trang {page + 1}/{total_pages} • Máy {start_idx + 1} - {end_idx}):**\n"
            f"{slots_text}"
        )
    else:
        desc_content = f"{header}\n\n{slots_text}"

    if len(desc_content) > 4000:
        desc_content = desc_content[:3996] + "..."
    embed.description = desc_content

    embed.set_footer(
        text=f"Trang {page + 1}/{total_pages}  •  kbag artisan để xem kho  •  kcraft để xây máy"
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
        parent_view: Any = None,
    ):
        self.bot = bot
        self.user_id = user_id
        self.slot_id = slot_id
        self.machine_id = machine_id
        self.author = author
        self.parent_view = parent_view

        machine = MACHINES[machine_id]
        inventory = farm_data.get("inventory", {})
        options = []

        for recipe_id in machine["recipes"]:
            recipe = RECIPES[recipe_id]
            can_craft = True
            for k, v in recipe["ingredients"].items():
                qty = inventory.get(k, 0)
                if k.endswith("_normal"):
                    base = k.replace("_normal", "")
                    qty += inventory.get(base, 0)
                if qty < v:
                    can_craft = False
                    break

            output = ARTISAN_GOODS.get(recipe["output_id"], {})
            price = output.get("price", recipe["sell_price"])
            duration_str = _format_duration(recipe["duration_seconds"])
            if can_craft:
                desc = f"{duration_str} • Bán {price:,} điểm"
            else:
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
            placeholder=f"Chọn công thức cho {machine['name']}...",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Đây không phải khu chế biến của bạn!", ephemeral=True
            )

        recipe_id = self.values[0]
        recipe = RECIPES[recipe_id]
        farm_data = await get_farm_data(self.bot, self.user_id)
        inventory = farm_data.get("inventory", {})
        machine_queue = farm_data.setdefault("machine_queue", {})
        now = time.time()

        if self.slot_id not in machine_queue:
            return await interaction.response.send_message(
                "<:symbol_wrong:1536629915598848072> Máy này không còn tồn tại hoặc đã bị lỗi!", ephemeral=True
            )
            
        slot_data = machine_queue[self.slot_id]
        if slot_data.get("status") != "idle":
            return await interaction.response.send_message(
                "<:symbol_wrong:1536629915598848072> Máy này không còn trống nữa!", ephemeral=True
            )

        # Kiểm tra nguyên liệu (hỗ trợ cả legacy và standard key)
        missing = []
        for item_id, qty_needed in recipe["ingredients"].items():
            qty_have = inventory.get(item_id, 0)
            if item_id.endswith("_normal"):
                base = item_id.replace("_normal", "")
                qty_have += inventory.get(base, 0)
            if qty_have < qty_needed:
                name = _get_item_display_name(item_id)
                missing.append(f"{name} (cần {qty_needed}, có {qty_have})")

        if missing:
            missing_str = "\n".join(f"• {m}" for m in missing)
            return await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> Không đủ nguyên liệu để chế **{recipe['name']}**!\n{missing_str}",
                ephemeral=True,
            )

        # Trừ nguyên liệu
        for item_id, qty_needed in recipe["ingredients"].items():
            if item_id.endswith("_normal"):
                base = item_id.replace("_normal", "")
                rem = qty_needed
                for key_to_try in (item_id, base):
                    avail = inventory.get(key_to_try, 0)
                    deduct = min(avail, rem)
                    if deduct > 0:
                        inventory[key_to_try] -= deduct
                        if inventory[key_to_try] <= 0:
                            del inventory[key_to_try]
                        rem -= deduct
                    if rem <= 0:
                        break
            else:
                inventory[item_id] -= qty_needed
                if inventory[item_id] <= 0:
                    del inventory[item_id]

        # Fetch skills_data
        from cogs.events.skills.skills_db import get_skills, get_skill_bonus
        skills_data = await get_skills(self.bot, self.user_id)
        time_reduction = get_skill_bonus(skills_data, "farming", "machine_time_reduction")
        
        duration = int(recipe["duration_seconds"] * (1.0 - time_reduction))
        
        # Đưa vào chế biến
        finish_time = now + duration
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
            f"Bắt đầu chế biến: {recipe['icon']} **{recipe['name']}**\n"
            f"<:symbol_hour_glass:1537570149215899658> Hoàn thành sau **{_format_duration(duration)}** → {output_info.get('icon','')} **{output_info.get('name','')}**",
            ephemeral=True,
        )

        if self.parent_view and getattr(self.parent_view, "message", None):
            try:
                self.parent_view._update_buttons(farm_data)
                embed_main = build_machine_embed(self.author, farm_data, page=self.parent_view.page, per_page=self.parent_view.per_page)
                await self.parent_view.message.edit(embed=embed_main, view=self.parent_view)
            except Exception:
                pass
        elif interaction.message:
            try:
                embed = build_machine_embed(self.author, farm_data)
                await interaction.message.edit(embed=embed)
            except Exception:
                pass

class RecipeSelectView(discord.ui.View):
    def __init__(self, select_obj: discord.ui.Select):
        super().__init__(timeout=120.0)
        self.add_item(select_obj)


    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SELECT MENU — PHÁ DỠ MÁY (ephemeral)
# ---------------------------------------------------------------------------

class DemolishSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        farm_data: Dict[str, Any],
        author: discord.Member | discord.User,
        parent_view: Any = None,
    ):
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.parent_view = parent_view
        
        options = []
        queue_list = _get_queue_list(farm_data)
        for i, (slot_id, item) in enumerate(queue_list):
            machine_id = item.get("machine_id", "")
            machine = MACHINES.get(machine_id, {})
            status = item.get("status", "idle")
            
            label = f"Slot {i+1}: {machine.get('name', machine_id)}"
            desc = "Đang trống" if status == "idle" else ("Đang chờ thu hoạch" if status == "done" else "Đang chế biến")
            options.append(
                discord.SelectOption(
                    label=label,
                    value=slot_id,
                    description=desc,
                    emoji=machine.get("icon", "<:symbol_machine:1536297937498275850>")
                )
            )

        if not options:
            options.append(discord.SelectOption(label="Không có máy nào", value="none"))

        super().__init__(
            placeholder="<:symbol_demolish:1537466095412314192> Chọn máy để phá dỡ...",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Bạn không có quyền thao tác!", ephemeral=True
            )
            
        slot_id = self.values[0]
        if slot_id == "none":
            return await interaction.response.send_message("Không có máy nào để phá!", ephemeral=True)
            
        farm_data = await get_farm_data(self.bot, self.user_id)
        queue_list = _get_queue_list(farm_data)
        
        machine_queue = farm_data.get("machine_queue", {})
        if slot_id not in machine_queue:
            return await interaction.response.send_message("Máy không tồn tại hoặc đã bị phá!", ephemeral=True)
            
        item = machine_queue[slot_id]
        machine_id = item.get("machine_id", "")
        machine = MACHINES.get(machine_id, {})
        machine_name = machine.get("name", machine_id)
        
        index = next((i for i, (s_id, _) in enumerate(queue_list) if s_id == slot_id), 0) + 1
        
        confirm_view = DemolishConfirmView(
            self.bot, self.user_id, self.author, slot_id, machine_id, index, parent_view=self.parent_view
        )
        
        await interaction.response.send_message(
            f"<:symbol_alert:1537546957885542450> **CẢNH BÁO:** Bạn sắp phá dỡ **Slot {index}: {machine_name}**.\n"
            f"Bạn sẽ nhận lại 50% nguyên liệu chế tạo máy. Nếu máy đang hoạt động, nguyên liệu chế biến bên trong sẽ **mất hoàn toàn**.\n"
            f"Bạn có chắc chắn muốn phá dỡ không?",
            view=confirm_view,
            ephemeral=True
        )

class DemolishSelectView(discord.ui.View):
    def __init__(self, select_obj: discord.ui.Select):
        super().__init__(timeout=120.0)
        self.add_item(select_obj)


    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass


class DemolishConfirmView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: str,
        author: discord.Member | discord.User,
        slot_id: str,
        machine_id: str,
        index: int,
        parent_view: Any = None,
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.slot_id = slot_id
        self.machine_id = machine_id
        self.index = index
        self.parent_view = parent_view

    @discord.ui.button(label="Đồng Ý Phá", style=discord.ButtonStyle.danger, emoji="<:symbol_demolish:1537466095412314192>")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("Không có quyền!", ephemeral=True)
            
        farm_data = await get_farm_data(self.bot, self.user_id)
        machine_queue = farm_data.get("machine_queue", {})
        inventory = farm_data.get("inventory", {})
        
        if self.slot_id not in machine_queue:
            return await interaction.response.send_message("Máy không tồn tại hoặc đã bị phá rồi!", ephemeral=True)
            
        machine = MACHINES.get(self.machine_id, {})
        refunds = []
        for mat_id, qty in machine.get("ingredients", {}).items():
            refund_qty = max(1, qty // 2) if qty > 1 else 1 
            inventory[mat_id] = inventory.get(mat_id, 0) + refund_qty
            name = _get_item_display_name(mat_id)
            refunds.append(f"**{refund_qty}x** {name}")
            
        del machine_queue[self.slot_id]
        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)
        
        refund_str = "\n".join([f"• {r}" for r in refunds])
        msg = (
            f"<:symbol_demolish:1537466095412314192> Đã phá dỡ thành công **Slot {self.index}: {machine.get('name', self.machine_id)}**.\n"
            f"**Nguyên liệu thu hồi:**\n{refund_str}"
        )
        
        await interaction.response.edit_message(content=msg, view=None)

        if self.parent_view and getattr(self.parent_view, "message", None):
            try:
                self.parent_view._update_buttons(farm_data)
                embed_main = build_machine_embed(self.author, farm_data, page=self.parent_view.page, per_page=self.parent_view.per_page)
                await self.parent_view.message.edit(embed=embed_main, view=self.parent_view)
            except Exception:
                pass


    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass


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
        page: int = 0,
    ):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.page = page
        self.per_page = 5
        self.total_pages = 1
        self.message: discord.Message | None = None
        self._update_buttons(farm_data)

    def _update_buttons(self, farm_data: Dict[str, Any]):
        self.clear_items()
        queue_list = _get_queue_list(farm_data)
        display_slots = max(1, len(queue_list))
        self.total_pages = max(1, (display_slots + self.per_page - 1) // self.per_page)
        self.page = max(0, min(self.page, self.total_pages - 1))
        
        # Check harvestable
        ready_count = sum(1 for _, item in queue_list if item.get("status") == "done")
        btn_harvest = discord.ui.Button(
            label="Thu Hoạch",
            style=discord.ButtonStyle.success if ready_count > 0 else discord.ButtonStyle.secondary,
            emoji="<:button_gathering:1536007669301776486>",
            custom_id="btn_harvest",
            disabled=(ready_count == 0),
            row=0,
        )
        btn_harvest.callback = self._harvest_callback
        self.add_item(btn_harvest)

        # Nút cho các máy (Row 0)
        machine_styles = {
            "keg": (MACHINES["keg"]["icon"], "Keg", discord.ButtonStyle.primary),
            "jar": (MACHINES["jar"]["icon"], "Jar", discord.ButtonStyle.primary),
            "furnace": (MACHINES["furnace"]["icon"], "Furnace", discord.ButtonStyle.primary),
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
            
        # Row 1: Phân trang & Phá Dỡ
        btn_prev = discord.ui.Button(
            emoji="<:symbol_arrow_left:1538646235966349454>",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_prev_page",
            disabled=(self.page <= 0),
            row=1,
        )
        btn_prev.callback = self._prev_page_callback
        self.add_item(btn_prev)

        btn_indicator = discord.ui.Button(
            label=f"Trang {self.page + 1}/{self.total_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_page_num",
            disabled=True,
            row=1,
        )
        self.add_item(btn_indicator)

        btn_next = discord.ui.Button(
            emoji="<:symbol_arrow_right:1538646237757186078>",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_next_page",
            disabled=(self.page >= self.total_pages - 1),
            row=1,
        )
        btn_next.callback = self._next_page_callback
        self.add_item(btn_next)

        # Nút Phá Dỡ
        btn_demolish = discord.ui.Button(
            label="Phá Dỡ Máy",
            style=discord.ButtonStyle.danger,
            emoji="<:symbol_demolish:1537466095412314192>",
            custom_id="btn_demolish",
            disabled=(len(queue_list) == 0),
            row=1,
        )
        btn_demolish.callback = self._demolish_callback
        self.add_item(btn_demolish)

    async def _prev_page_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Bạn không thể thao tác trên nông trại người khác!", ephemeral=True
            )
        if self.page > 0:
            self.page -= 1
        farm_data = await get_farm_data(self.bot, self.user_id)
        embed = build_machine_embed(self.author, farm_data, page=self.page, per_page=self.per_page)
        self._update_buttons(farm_data)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _next_page_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Bạn không thể thao tác trên nông trại người khác!", ephemeral=True
            )
        if self.page < self.total_pages - 1:
            self.page += 1
        farm_data = await get_farm_data(self.bot, self.user_id)
        embed = build_machine_embed(self.author, farm_data, page=self.page, per_page=self.per_page)
        self._update_buttons(farm_data)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _harvest_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Bạn không thể thao tác trên nông trại người khác!", ephemeral=True
            )

        farm_data = await get_farm_data(self.bot, self.user_id)
        queue_list = _get_queue_list(farm_data)
        inventory = farm_data.get("inventory", {})
        machine_queue = farm_data.get("machine_queue", {})

        harvested_items = {}
        for slot_id, item in queue_list:
            if item.get("status") == "done":
                output_id = item.get("output_id")
                if not output_id and item.get("recipe_id"):
                    rec = RECIPES.get(item["recipe_id"])
                    if rec:
                        output_id = rec.get("output_id")
                        output_qty = rec.get("output_qty", 1)
                else:
                    output_qty = item.get("output_qty", 1)

                if output_id:
                    inventory[output_id] = inventory.get(output_id, 0) + output_qty
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
                "<:symbol_wrong:1536629915598848072> Không có gì để thu hoạch!", ephemeral=True
            )

        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, self.user_id, farm_data)

        # Build harvest message
        lines = []
        for out_id, qty in harvested_items.items():
            info = ARTISAN_GOODS.get(out_id, {})
            lines.append(f"• **{qty}x** {info.get('icon', '')} **{info.get('name', out_id)}**")
        prefix = getattr(self.bot, "custom_prefix", "k")
        msg = (
            "<:symbol_right:1536629912515903578> **Thu hoạch thành công:**\n"
            + "\n".join(lines)
            + f"\n\n*Thành phẩm đã được thêm vào kho nông trại! Dùng `{prefix}bag artisan` để xem.*"
        )

        await interaction.response.send_message(msg, ephemeral=True)

        # Cập nhật lại UI: update buttons trước để clamp self.page chuẩn xác
        self._update_buttons(farm_data)
        embed = build_machine_embed(self.author, farm_data, page=self.page, per_page=self.per_page)
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)
            elif self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception:
            pass

    def _make_machine_callback(self, machine_id: str):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                return await interaction.response.send_message(
                    "<:symbol_ban:1537546960003801319> Bạn không có quyền thao tác!", ephemeral=True
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
                    f"<:symbol_wrong:1536629915598848072> Bạn không có cái {MACHINES[machine_id]['name']} nào đang trống! Vui lòng Thu Hoạch máy cũ hoặc xây thêm máy mới bằng lệnh `{self.bot.custom_prefix}craft`.",   # type: ignore
                    ephemeral=True
                )

            select = RecipeSelect(
                bot=self.bot,
                user_id=self.user_id,
                slot_id=idle_slot_id,
                machine_id=machine_id,
                farm_data=farm_data,
                author=self.author,
                parent_view=self,
            )
            view = RecipeSelectView(select)
            await interaction.response.send_message(
                f"**{MACHINES[machine_id]['name']}** đang trống, bạn muốn chế biến gì?",
                view=view,
                ephemeral=True,
            )

        return callback

    async def _demolish_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Bạn không có quyền thao tác!", ephemeral=True
            )
            
        farm_data = await get_farm_data(self.bot, self.user_id)
        queue_list = _get_queue_list(farm_data)
        
        if len(queue_list) == 0:
            return await interaction.response.send_message(
                "<:symbol_wrong:1536629915598848072> Không có máy nào để phá!", ephemeral=True
            )
            
        select = DemolishSelect(
            bot=self.bot,
            user_id=self.user_id,
            farm_data=farm_data,
            author=self.author,
            parent_view=self,
        )
        view = DemolishSelectView(select)
        await interaction.response.send_message(
            "<:symbol_demolish:1537466095412314192> Vui lòng chọn máy bạn muốn phá dỡ ở menu bên dưới:",
            view=view,
            ephemeral=True
        )


    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass


async def send_machine_panel(ctx: commands.Context) -> None:
    user_id = str(ctx.author.id)
    farm_data = await get_farm_data(ctx.bot, user_id)
    view = MachineView(ctx.bot, user_id, farm_data, ctx.author)
    embed = build_machine_embed(ctx.author, farm_data, page=view.page, per_page=view.per_page)
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg
