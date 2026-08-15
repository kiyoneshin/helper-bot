
"""
inventory_cog.py — Cog Túi Đồ Hợp Nhất (kinv / kbag / kuse)
================================================================
Hiển thị toàn bộ túi đồ theo Dropdown, bán nông sản bằng Modal,
dùng vật phẩm bằng ID số.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import discord
from discord.ext import commands

from cogs.common.db import execute_db, fetchrow_db, fetchval_db
from cogs.common.item_config import (
    ITEM_REGISTRY,
    get_item_by_id,
    get_items_by_category,
)
from cogs.events.idle_farm.farm_db import (
    get_farm_data,
    sell_inventory,
    sell_items_partial,
)

log = logging.getLogger("InventoryCog")


# ============================================================
# EMBED BUILDERS
# ============================================================

def _build_regular_embed(
    author: discord.Member | discord.User,
    inv: dict[str, int],
    category: str,
    prefix: str = 'k',
) -> discord.Embed:
    """
    Xây dựng Embed cho vật phẩm thông thường (Event/BlackMarket)
    Định dạng: [ID] Icon Tên vật phẩm (xQTY) — Mô tả
    """
    CATEGORY_META = {
        "event":       ("<:icon_08_shop:1536025530728587384> Vật phẩm Sự kiện",       0x9b59b6, f"💡 Sử dụng: `{{prefix}}use <id>`"),
        "blackmarket": ("<:icon_05_bm:1536017187243032736> Vật phẩm Chợ đen",        0x2b2d31, f"💡 Sử dụng: `{{prefix}}use <id>`"),
        "ring":        ("<:icon_02_ring:1536017180951318528> Nhẫn Cưới & Trang sức",  0xff69b4, f"💡 Dùng `{prefix}marry` hoặc `{prefix}upgrade_ring`"),
        "gift":        ("<:gift_00_symbol:1536003307011842099> Quà Tặng",                0xf1c40f, f"💡 Dùng `{prefix}gift` để tặng"),
        "lootbox":     ("<:lootbox:1535664857276489749> Hộp Quà Lootbox",         0x3498db, f"💡 Dùng `{prefix}lb open <tier>` để mở"),
        "farm":        ("<:icon_04_seed:1536017185057546242> Hạt giống",               0x2ecc71, f"💡 Mua thêm hạt giống tại `{prefix}shop`"),
    }
    title, color, footer = CATEGORY_META.get(category, ("<:icon_07_inventory:1535664855300710422> Túi đồ", 0x7289da, ""))

    embed = discord.Embed(title=title, color=color)
    embed.set_author(
        name=f"Túi Đồ của {author.display_name}",
        icon_url=author.display_avatar.url,
    )
    embed.set_thumbnail(url=author.display_avatar.url)

    if not inv:
        embed.description = f"*Mục này đang trống không. Hãy ghé `{prefix}shop` để sắm đồ!*"
    else:
        lines: list[str] = []
        # Tra cứu theo db_key để lấy ID và mô tả từ ITEM_REGISTRY
        db_key_to_item = {
            item["db_key"]: item
            for item in ITEM_REGISTRY.values()
            if item["category"] == category
        }
        
        items_to_display = []
        unrecognized = []
        for db_key, qty in inv.items():
            if qty <= 0:
                continue
            
            meta = db_key_to_item.get(db_key)
            if meta:
                items_to_display.append((meta, qty))
            else:
                # Kiểm tra xem item này có thuộc category KHÁC không
                is_known = any(item["db_key"] == db_key for item in ITEM_REGISTRY.values())
                # Chỉ hiển thị item KHÔNG NẰM TRONG REGISTRY vào tab event để tránh rác tab khác
                if not is_known and category == "event":
                    unrecognized.append((db_key, qty))
                    
        # Sắp xếp theo ID tăng dần
        items_to_display.sort(key=lambda x: x[0]["id"])
        
        for meta, qty in items_to_display:
            lines.append(
                f"`[{meta['id']}]` {meta['icon']} **{meta['name']}** (x{qty}) — {meta['description']}"
            )
            
        for db_key, qty in unrecognized:
            lines.append(f"• `{db_key}` × {qty}")
            
        embed.description = "\n".join(lines) if lines else "*Không có vật phẩm nào thuộc mục này.*"

    embed.set_footer(text=footer)
    return embed


def _build_farm_embed(
    author: discord.Member | discord.User,
    farm_data: dict[str, Any],
    tab_type: str = "eco"
) -> discord.Embed:
    """
    Xây dựng Embed cho túi đồ nông trại.
    Định dạng tương tự nhưng dùng key string từ farm_data.inventory.
    """
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS, QUALITY_MULTIPLIERS
    from cogs.events.idle_farm.machine_config import ARTISAN_GOODS
    from cogs.events.woodcutting.woodcutting_config import WOODCUTTING_LOOT

    if tab_type == "crop":
        embed = discord.Embed(
            title="<:icon_06_artisan:1536017189386059797> Nông Sản — Túi Đồ Nông Trại",
            color=0x2ecc71,
        )
    else:
        embed = discord.Embed(
            title="<:icon_03_farm_field:1536017183216369815> Hệ Sinh Thái — Túi Đồ Nông Trại",
            color=0xe67e22,
        )
        
    embed.set_author(
        name=f"Túi Đồ của {author.display_name}",
        icon_url=author.display_avatar.url,
    )
    embed.set_thumbnail(url=author.display_avatar.url)

    inventory = farm_data.get("inventory", {})
    if not inventory:
        embed.description = "*Kho đồ trống. Hãy đi trồng trọt, câu cá hoặc đào mỏ nhé!*"
        embed.set_footer(text="💡 Dùng các nút bên dưới để bán vật phẩm.")
        return embed

    seed_lines, crop_lines, ore_lines, wood_lines, fish_lines, artisan_lines = [], [], [], [], [], []
    total_crops_worth = total_ores_worth = total_wood_worth = total_fish_worth = total_artisan_worth = 0

    for item_id, count in inventory.items():
        if count <= 0:
            continue

        if item_id.startswith("seed_"):
            seed_id = item_id[5:]
            seed_info = SEEDS.get(seed_id)
            if seed_info:
                seed_lines.append(
                    f"• {seed_info['icon']} **Hạt {seed_info['name']}** (x{count})"
                    f" — {seed_info['description']}"
                )
        elif item_id in MINING_LOOT:
            ore = MINING_LOOT[item_id]
            price = ore.get("price", 0)
            total_ores_worth += price * count
            ore_lines.append(
                f"• `[{item_id}]` {ore['icon']} **{ore['name']}** (x{count})"
                f" — {price:,} điểm/cái"
            )
        elif item_id in FISH_LOOT:
            fish = FISH_LOOT[item_id]
            price = fish.get("price", 0)
            total_fish_worth += price * count
            rare = "<a:symbol_star_yellow:1537739289834553385>" if fish.get("rare_rank", 0) >= 3 else ""
            fish_lines.append(
                f"• `[{item_id}]` {fish['icon']} {rare}**{fish['name']}** (x{count})"
                f" — {price:,} điểm/cái"
            )
        else:
            parts = item_id.split("_")
            quality = parts[-1] if len(parts) > 1 else "normal"
            seed_id = "_".join(parts[:-1]) if len(parts) > 1 else item_id

            # Artisan Goods (Beer, Wine, Jam, Metal Bars)
            if item_id in ARTISAN_GOODS:
                artisan = ARTISAN_GOODS[item_id]
                price = artisan.get("price", 0)
                total_artisan_worth += price * count
                artisan_lines.append(
                    f"• `[{item_id}]` {artisan['icon']} **{artisan['name']}** (x{count})"
                    f" — {price:,} điểm/cái"
                )
            # Wood items
            elif item_id in WOODCUTTING_LOOT:
                wood = WOODCUTTING_LOOT[item_id]
                price = wood.get("price", 0)
                total_wood_worth += price * count
                wood_lines.append(
                    f"• `[{item_id}]` {wood['icon']} **{wood['name']}** (x{count})"
                    f" — {price:,} điểm/cái"
                )
            elif seed_id in SEEDS:
                seed_info = SEEDS.get(seed_id)
                if seed_info:
                    emoji = QUALITY_EMOJIS.get(quality, "")
                    multiplier = QUALITY_MULTIPLIERS.get(quality, 1.0)
                    reward_min = seed_info.get("reward_min", 0)
                    reward_max = seed_info.get("reward_max", reward_min)
                    
                    min_worth = int(reward_min * multiplier)
                    max_worth = int(reward_max * multiplier)
                    
                    total_crops_worth += min_worth * count  # Tính theo giá trị tối thiểu
                    
                    if min_worth != max_worth:
                        price_str = f"{min_worth:,} - {max_worth:,}"
                    else:
                        price_str = f"{min_worth:,}"
                        
                    crop_lines.append(
                        f"• `[{item_id}]` {seed_info['icon']} **{seed_info['name']}**"
                        f" {emoji} (x{count}) — {price_str} điểm/cái"
                    )

    desc_parts: list[str] = []
    if tab_type == "crop":
        if crop_lines:
            desc_parts.append("**<:symbol_plant:1536007706958237828> Nông sản:**\n" + "\n".join(crop_lines))
        if artisan_lines:
            desc_parts.append("**<:symbol_machine:1536297937498275850> Thủ Công Phẩm:**\n" + "\n".join(artisan_lines))
    else:
        if ore_lines:
            desc_parts.append("**<:symbol_00_mining:1536007694920585356> Khoáng sản:**\n" + "\n".join(ore_lines))
        if wood_lines:
            desc_parts.append("**<:symbol_00_woodcutting:1536007697491558491> Gỗ:**\n" + "\n".join(wood_lines))
        if fish_lines:
            desc_parts.append("**<:symbol_fish:1536007699190386740> Cá:**\n" + "\n".join(fish_lines))

    embed.description = "\n\n".join(desc_parts) if desc_parts else "*Kho trống.*"

    footer_parts: list[str] = []
    if tab_type == "crop":
        if total_crops_worth > 0:
            footer_parts.append(f"<:symbol_plant:1536007706958237828> {total_crops_worth:,} điểm")
        if total_artisan_worth > 0:
            footer_parts.append(f"<:symbol_machine:1536297937498275850> {total_artisan_worth:,} điểm")
    else:
        if total_ores_worth > 0:
            footer_parts.append(f"<:symbol_00_mining:1536007694920585356> {total_ores_worth:,} điểm")
        if total_wood_worth > 0:
            footer_parts.append(f"<:symbol_00_woodcutting:1536007697491558491> {total_wood_worth:,} điểm")
        if total_fish_worth > 0:
            footer_parts.append(f"<:symbol_fish:1536007699190386740> {total_fish_worth:,} điểm")
            
    if footer_parts:
        embed.add_field(
            name="<:symbol_money_2:1537567535229050970> Tổng Giá Trị Ước Tính",
            value=" | ".join(footer_parts),
            inline=False,
        )

    embed.set_footer(text="💡 Dùng các nút bên dưới để bán vật phẩm.")
    return embed


# ============================================================
# MODAL: BÁN ĐỒ THEO LOẠI & SỐ LƯỢNG
# ============================================================

class SellItemModal(discord.ui.Modal):
    """Modal nhập loại và số lượng vật phẩm muốn bán."""

    item_input = discord.ui.TextInput(
        label="Key vật phẩm (gõ đúng key trong túi đồ)",
        placeholder="VD: tomato_normal, copper_ore, salmon_fish ...",
        min_length=1,
        max_length=60,
        required=True,
    )
    amount_input = discord.ui.TextInput(
        label="Số lượng (nhập 0 hoặc 'all' để bán hết)",
        placeholder="VD: 5 hoặc all",
        default="all",
        min_length=1,
        max_length=10,
        required=True,
    )

    def __init__(self, bot: commands.Bot, user_id: str, view: "InventoryView"):
        super().__init__(title="💰 Bán Vật Phẩm Nông Trại")
        self.bot = bot
        self.user_id = user_id
        self._view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        item_key = self.item_input.value.strip().lower()
        raw_amount = self.amount_input.value.strip().lower()

        # Xử lý số lượng
        if raw_amount in ("all", "0", "hết"):
            amount = -1  # -1 = bán hết
        else:
            try:
                amount = int(raw_amount)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    "<:symbol_wrong:1536629915598848072> Số lượng không hợp lệ! Nhập số nguyên dương hoặc 'all'.",
                    ephemeral=True,
                )
                return

        ok, profit, msg = await sell_items_partial(self.bot, self.user_id, item_key, amount)
        if not ok:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {msg}", ephemeral=True)
            return

        # Cập nhật lại embed
        farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = _build_farm_embed(interaction.user, farm_data, tab_type=self._view._current_tab)
        await interaction.response.edit_message(embed=new_embed, view=self._view)
        await interaction.followup.send(f"<:symbol_right:1536629912515903578> {msg}", ephemeral=True)


class SellAllModal(discord.ui.Modal):
    """Modal xác nhận bán hết một category (crops/ores/fish)."""

    confirm_input = discord.ui.TextInput(
        label="Gõ 'xác nhận' để bán hết",
        placeholder="xác nhận",
        min_length=1,
        max_length=10,
        required=True,
    )

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User,
                 category: str, label: str, view: "InventoryView"):
        super().__init__(title=f"⚠️ Bán Toàn Bộ {label}?")
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.category = category
        self.label = label
        self._view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.confirm_input.value.strip().lower() != "xác nhận":
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Đã hủy thao tác bán.", ephemeral=True)
            return

        profit = await sell_inventory(self.bot, self.user_id, self.category)
        if profit <= 0:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> Bạn không có {self.label} nào để bán!", ephemeral=True
            )
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = _build_farm_embed(self.author, farm_data, tab_type=self._view._current_tab)
        await interaction.response.edit_message(embed=new_embed, view=self._view)
        await interaction.followup.send(
            f"<:symbol_right:1536629912515903578> Đã bán toàn bộ **{self.label}**! Thu về **{profit:,.0f}** điểm.",
            ephemeral=True,
        )


# ============================================================
# UI COMPONENTS
# ============================================================

class InventorySelect(discord.ui.Select):
    """Dropdown chuyển giữa các tab túi đồ."""

    def __init__(self, author: discord.Member | discord.User, current: str = "blackmarket"):
        self.author = author
        options = [
            discord.SelectOption(
                label="Vật phẩm Sự kiện",
                value="event",
                emoji="<:icon_08_shop:1536025530728587384>",
                description="Xem đồ nhận từ sự kiện",
                default=(current == "event"),
            ),
            discord.SelectOption(
                label="Hạt giống",
                value="farm",
                emoji="<:icon_04_seed:1536017185057546242>",
                description="Xem hạt giống để trồng trọt",
                default=(current == "farm"),
            ),
            discord.SelectOption(
                label="Nông sản",
                value="crop",
                emoji="<:icon_06_artisan:1536017189386059797>",
                description="Cây đã thu hoạch & thủ công phẩm",
                default=(current == "crop"),
            ),
            discord.SelectOption(
                label="Hệ sinh thái",
                value="eco",
                emoji="<:icon_03_farm_field:1536017183216369815>",
                description="Xem khoáng sản, gỗ, cá",
                default=(current == "eco"),
            ),
            discord.SelectOption(
                label="Vật phẩm Chợ đen",
                value="blackmarket",
                emoji="<:icon_05_bm:1536017187243032736>",
                description="Xem đồ mua từ chợ đen",
                default=(current == "blackmarket"),
            ),
            discord.SelectOption(
                label="Nhẫn Cưới & Trang sức",
                value="ring",
                emoji="<:icon_02_ring:1536017180951318528>",
                description="Nhẫn cưới để cầu hôn",
                default=(current == "ring"),
            ),
            discord.SelectOption(
                label="Quà Tặng",
                value="gift",
                emoji="<:gift_00_symbol:1536003307011842099>",
                description="Quà để tặng người thương",
                default=(current == "gift"),
            ),
            discord.SelectOption(
                label="Lootbox",
                value="lootbox",
                emoji="<:icon_01_chest:1536017178615091311>",
                description="Xem hộp quà may mắn",
                default=(current == "lootbox"),
            ),
            discord.SelectOption(
                label="Thức Ăn",
                value="food",
                emoji="<:icon_00_food:1536017176434049065>",
                description="Xem món ăn và buff",
                default=(current == "food"),
            ),
        ]
        super().__init__(
            placeholder="Chọn phân loại túi đồ...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        view: InventoryView = self.view  # type: ignore
        user_id = str(interaction.user.id)
        view._current_tab = selected

        for opt in self.options:
            opt.default = (opt.value == selected)

        # Rebuild view buttons + embed theo tab được chọn
        if selected in ("eco", "crop"):
            farm_data = await get_farm_data(view.bot, user_id)
            embed = _build_farm_embed(interaction.user, farm_data, tab_type=selected)
            view._show_buttons_for_tab(selected)
        else:
            row = await fetchrow_db(
                view.bot,
                "SELECT inventory FROM event_profiles WHERE discord_id = $1",
                user_id,
            )
            inv: dict[str, int] = {}
            if row and row["inventory"]:
                try:
                    raw = row["inventory"]
                    inv = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    pass
            inv = {k: v for k, v in inv.items() if v > 0}
            embed = _build_regular_embed(interaction.user, inv, selected)
            view._hide_farm_buttons()

        await interaction.response.edit_message(embed=embed, view=view)


class InventoryView(discord.ui.View):
    """View hợp nhất túi đồ với Select + Nút bán động."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, default_tab: str = "blackmarket"):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.user_id = str(author.id)
        self.message: discord.Message | None = None
        self._current_tab = default_tab

        # Khởi tạo select
        self.select_menu = InventorySelect(author, default_tab)
        self.add_item(self.select_menu)

        # Khai báo sẵn 4 nút bán (ẩn khi không ở tab farm)
        self.btn_sell_item = discord.ui.Button(
            label="Bán theo Loại & Số lượng", emoji="<:icon_05_bm:1536017187243032736>",
            style=discord.ButtonStyle.primary, row=1,
        )
        self.btn_sell_crops = discord.ui.Button(
            label="Bán Tất Cả Nông Sản", emoji="<:symbol_plant:1536007706958237828>",
            style=discord.ButtonStyle.success, row=2,
        )
        self.btn_sell_ores = discord.ui.Button(
            label="Bán Tất Cả Quặng", emoji="<:symbol_00_mining:1536007694920585356>",
            style=discord.ButtonStyle.primary, row=2,
        )
        self.btn_sell_wood = discord.ui.Button(
            label="Bán Tất Cả Gỗ", emoji="<:symbol_00_woodcutting:1536007697491558491>",
            style=discord.ButtonStyle.success, row=2,
        )
        self.btn_sell_fish = discord.ui.Button(
            label="Bán Tất Cả Cá", emoji="<:symbol_fish:1536007699190386740>",
            style=discord.ButtonStyle.secondary, row=2,
        )

        # Gắn callback
        self.btn_sell_item.callback = self._on_sell_item
        async def cb_sell_crops(interaction: discord.Interaction):
            await self._on_sell_all(interaction, "crops", "Nông sản")
        self.btn_sell_crops.callback = cb_sell_crops
        
        async def cb_sell_ores(interaction: discord.Interaction):
            await self._on_sell_all(interaction, "ores", "Khoáng sản")
        self.btn_sell_ores.callback = cb_sell_ores
        
        async def cb_sell_wood(interaction: discord.Interaction):
            await self._on_sell_all(interaction, "wood", "Gỗ")
        self.btn_sell_wood.callback = cb_sell_wood
        
        async def cb_sell_fish(interaction: discord.Interaction):
            await self._on_sell_all(interaction, "fish", "Cá")
        self.btn_sell_fish.callback = cb_sell_fish

        # Mặc định tab không phải farm nên ẩn nút
        if default_tab in ("eco", "crop"):
            self._show_buttons_for_tab(default_tab)

    def _show_buttons_for_tab(self, tab: str) -> None:
        self.clear_items()
        self.add_item(self.select_menu)
        if tab == "crop":
            self.add_item(self.btn_sell_item)
            self.add_item(self.btn_sell_crops)
        elif tab == "eco":
            self.add_item(self.btn_sell_item)
            self.add_item(self.btn_sell_ores)
            self.add_item(self.btn_sell_wood)
            self.add_item(self.btn_sell_fish)

    def _hide_farm_buttons(self) -> None:
        self.clear_items()
        self.add_item(self.select_menu)

    async def _on_sell_item(self, interaction: discord.Interaction) -> None:
        """Mở Modal bán theo loại & số lượng cụ thể."""
        modal = SellItemModal(self.bot, self.user_id, self)
        await interaction.response.send_modal(modal)

    async def _on_sell_all(self, interaction: discord.Interaction, category: str, label: str) -> None:
        """Mở Modal xác nhận bán hết một category."""
        modal = SellAllModal(self.bot, self.user_id, self.author, category, label, self)
        await interaction.response.send_modal(modal)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Đây không phải túi đồ của bạn!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ============================================================
# COG CHÍNH
# ============================================================

class UnifiedInventoryCog(commands.Cog):
    """Cog Túi Đồ Hợp Nhất."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="inv",
        aliases=["bag", "tuido", "khodo", "inventory"],
        description="Xem toàn bộ túi đồ (Chợ đen, Sự kiện, Nông trại...)",
    )
    async def inventory_cmd(self, ctx: commands.Context, category: str = None) -> None:
        """Lệnh hợp nhất Túi đồ bằng Dropdown UI."""
        uid = str(ctx.author.id)

        # Xử lý category viết tắt
        cat_map = {
            "eco": "eco", "hesinhthai": "eco",
            "farm": "eco", "nongtrai": "eco",
            "crop": "crop", "nongsan": "crop",
            "seed": "farm", "hatgiong": "farm",
            "bm": "blackmarket", "choden": "blackmarket", "blackmarket": "blackmarket",
            "ev": "event", "event": "event", "sukien": "event",
            "ring": "ring", "nhan": "ring",
            "gift": "gift", "qua": "gift",
            "lb": "lootbox", "lootbox": "lootbox",
            "food": "food", "cook": "food", "doan": "food",
        }
        default_tab = "event"
        if category and category.lower() in cat_map:
            default_tab = cat_map[category.lower()]

        row = await fetchrow_db(
            self.bot,
            "SELECT inventory FROM event_profiles WHERE discord_id = $1",
            uid,
        )
        inv: dict[str, int] = {}
        if row and row["inventory"]:
            try:
                raw = row["inventory"]
                inv = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                pass
        inv = {k: v for k, v in inv.items() if v > 0}

        if default_tab in ("eco", "crop"):
            from cogs.events.idle_farm.farm_db import get_farm_data
            farm_data = await get_farm_data(self.bot, uid)
            embed = _build_farm_embed(ctx.author, farm_data, tab_type=default_tab)
        else:
            embed = _build_regular_embed(ctx.author, inv, default_tab)
            
        view = InventoryView(self.bot, ctx.author, default_tab=default_tab)
        if default_tab in ("eco", "crop"):
            view._show_buttons_for_tab(default_tab)
            
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="use",
        aliases=["dung", "xai"],
        description="<a:symbol_star_yellow:1537739289834553385> Dùng vật phẩm theo ID số. Cú pháp: use <id> [@mục tiêu]",
    )
    async def use_cmd(
        self,
        ctx: commands.Context,
        item_id: int,
        target: discord.Member | None = None,
    ) -> None:
        """Sử dụng vật phẩm bằng ID số từ ITEM_REGISTRY."""
        item = get_item_by_id(item_id)
        if item is None:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Không tìm thấy vật phẩm với ID `{item_id}`! Dùng `{self.view.bot.custom_prefix}inv` để xem túi đồ.",
                delete_after=5.0,
            )
            return

        if not item.get("usable", False):
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> **{item['name']}** không thể sử dụng bằng lệnh này!",
                delete_after=5.0,
            )
            return

        uid = str(ctx.author.id)
        db_key = item["db_key"]

        # Lấy & cập nhật inventory
        row = await fetchrow_db(
            self.bot,
            "SELECT inventory FROM event_profiles WHERE discord_id = $1",
            uid,
        )
        inv: dict[str, int] = {}
        if row and row["inventory"]:
            try:
                raw = row["inventory"]
                inv = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                pass

        qty = inv.get(db_key, 0)
        if qty <= 0:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Bạn không có **{item['icon']} {item['name']}** trong túi đồ!",
                delete_after=5.0,
            )
            return

        # KIỂM TRA & ÁP DỤNG ĐỒ ĂN (FOOD)
        if item.get("category") == "food":
            import time
            profile_row = await fetchrow_db(self.bot, "SELECT active_boosts FROM event_profiles WHERE discord_id = $1", uid)
            boosts = profile_row.get("active_boosts", {}) if profile_row else {}
            if isinstance(boosts, str):
                try: boosts = json.loads(boosts)
                except: boosts = {}
            
            boost_key = None
            boost_val = 0
            duration = 3600
            if db_key == "food_71": boost_key, boost_val, duration = "stamina_regen", 0.5, 7200
            elif db_key == "food_72": boost_key, boost_val, duration = "lb_drop_rate", 0.2, 3600
            elif db_key == "food_73": boost_key, boost_val, duration = "lb_rarity", 0.15, 3600
            elif db_key == "food_74": boost_key, boost_val, duration = "farm_yield", 1.0, 14400
            elif db_key == "food_75": boost_key, boost_val, duration = "rare_wood", 0.3, 3600
            elif db_key == "food_76": boost_key, boost_val, duration = "rare_ore", 0.3, 3600
            elif db_key == "food_77": boost_key, boost_val, duration = "rare_fish", 0.15, 3600
            elif db_key == "food_78": boost_key, boost_val, duration = "stamina_discount", 1.0, 3600
            elif db_key == "food_79": boost_key, boost_val, duration = "all_boost", 0.35, 7200
            
            now = time.time()
            if boost_key:
                if boost_key in boosts and boosts[boost_key].get("expires_at", 0) > now:
                    await ctx.send(f"<:symbol_wrong:1536629915598848072> Bạn đang có hiệu ứng của đồ ăn này rồi! Phải đợi hiệu ứng cũ hết hạn mới được ăn tiếp.", delete_after=5.0)
                    return
                boosts[boost_key] = {"value": boost_val, "expires_at": now + duration}
                await execute_db(self.bot, "UPDATE event_profiles SET active_boosts = $2::jsonb WHERE discord_id = $1", uid, json.dumps(boosts))
            elif db_key == "food_70":
                from cogs.events.idle_farm.farm_db import get_and_update_stamina, get_farm_data, save_farm_data
                from cogs.events.mining.mining_config import MAX_STAMINA
                current = await get_and_update_stamina(self.bot, uid)
                if current >= MAX_STAMINA:
                    await ctx.send("<:symbol_ban:1537546960003801319> Thể lực của bạn đã đầy, không cần ăn Salad Cà Chua!", delete_after=5.0)
                    return
                new_stamina = min(current + 30, MAX_STAMINA)
                farm_data = await get_farm_data(self.bot, uid)
                farm_data["stamina"] = new_stamina
                await save_farm_data(self.bot, uid, farm_data)


        # Trừ vật phẩm
        inv[db_key] -= 1
        if inv[db_key] <= 0:
            del inv[db_key]

        await execute_db(
            self.bot,
            "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1",
            uid,
            json.dumps(inv),
        )

        target_display = target.mention if target else "bản thân"
        embed = discord.Embed(
            description=(
                f"<a:symbol_star_yellow:1537739289834553385> {ctx.author.mention} vừa sử dụng **{item['icon']} {item['name']}**"
                f" lên {target_display}!"
            ),
            color=0x57f287,
        )
        await ctx.send(embed=embed)

        # -------------------------------------------------------------
        # HIỆU ỨNG THỰC TẾ
        # -------------------------------------------------------------
        if not target and db_key in ["timeout_1m", "timeout_5m", "ghost_ping_card", "jail_card", "disconnect_card", "fake_ban_card", "thief_card", "nickname_change"]:
            await ctx.send("<:symbol_wrong:1536629915598848072> Vật phẩm này yêu cầu bạn phải `@mục_tiêu`!", delete_after=5.0)
            return

        if target and not isinstance(target, discord.Member):
            await ctx.send("<:symbol_wrong:1536629915598848072> Mục tiêu phải là thành viên trong server này!")
            return
        
        if target:
            assert isinstance(target, discord.Member)

        from datetime import timedelta

        if db_key == "timeout_1m":
            assert isinstance(target, discord.Member)
            # try:
            #     await target.timeout(timedelta(minutes=1), reason=f"Bị {ctx.author} dùng Búa Gõ 1 Phút")
            # except discord.Forbidden:
            #     await ctx.send("<:symbol_ban:1537546960003801319> Bot không đủ quyền timeout người này!")
            #     return
            await ctx.send(f"<:symbol_demolish:1537466095412314192> {target.mention} đã bị dán băng keo vào miệng trong 1 phút!")

        elif db_key == "timeout_5m":
            assert isinstance(target, discord.Member)
            # try:
            #     await target.timeout(timedelta(minutes=5), reason=f"Bị {ctx.author} dùng Búa Gõ 5 Phút")
            # except discord.Forbidden:
            #     await ctx.send("<:symbol_ban:1537546960003801319> Bot không đủ quyền timeout người này!")
            #     return
            await ctx.send(f"<:symbol_demolish:1537466095412314192> {target.mention} đã bị dán băng keo vào miệng trong 5 phút!")

        elif db_key == "ghost_ping_card":
            assert isinstance(target, discord.Member)
            # for _ in range(3):
            #     msg = await ctx.channel.send(target.mention)
            #     await msg.delete()
            await ctx.send(f"👻 Đã chọc ghẹo {target.mention} thành công!")

        elif db_key == "disconnect_card":
            assert isinstance(target, discord.Member)
            # if target.voice and target.voice.channel:
            #     try:
            #         await target.move_to(None)
            #     except discord.Forbidden:
            #         await ctx.send("<:symbol_ban:1537546960003801319> Bot không đủ quyền sút người này!")
            #         return
            # else:
            #     await ctx.send(f"<:symbol_wrong:1536629915598848072> {target.mention} không ở trong kênh thoại nào cả!")
            #     return
            await ctx.send(f"🔌 {target.mention} vừa bị sút văng khỏi kênh thoại!")

        elif db_key == "fake_ban_card":
            assert isinstance(target, discord.Member)
            fake_embed = discord.Embed(
                title="<:symbol_demolish:1537466095412314192> THÔNG BÁO BAN!",
                description=f"**{target.mention}** đã bị cấm vĩnh viễn khỏi máy chủ.\n**Lý do:** Vi phạm nội quy cực kỳ nghiêm trọng.",
                color=0xFF0000
            )
            fake_embed.set_footer(text="Đùa tí thôi! Bị lừa rồi nhé 😂")
            await ctx.send(embed=fake_embed)

        elif db_key == "jail_card":
            assert isinstance(target, discord.Member)
            # jail_cog: Any = self.bot.get_cog("JailSystem")
            # if jail_cog:
            #     try:
            #         await jail_cog.phattu_cmd.callback(jail_cog, ctx, target, 50, reason=f"Bị {ctx.author} dùng Thẻ Bỏ Tù")
            #     except Exception as e:
            #         await ctx.send(f"<:symbol_wrong:1536629915598848072> Lỗi khi bỏ tù: {e}")
            #         return
            # else:
            #     await ctx.send("<:symbol_wrong:1536629915598848072> Tính năng Chuồng Chó hiện đang bảo trì!")
            #     return
            await ctx.send(f"🚔 {target.mention} đã bị tống vào chuồng chó!")

        elif db_key == "thief_card":
            assert isinstance(target, discord.Member)
            # Tác dụng trộm điểm hoặc tiền từ target
            # import random
            # stolen_amount = random.randint(50, 500)
            # ... cập nhật DB ...
            await ctx.send(f"🕵️ {ctx.author.mention} đã trộm thành công đồ của {target.mention}!")
            
        elif db_key == "nickname_change":
            assert isinstance(target, discord.Member)
            import random
            funny_names = ["Thánh Hề", "Kẻ Trộm Chó", "Đại Vương Móm", "Chúa Tể Báo Thủ", "Chú Bé Đần"]
            new_name = random.choice(funny_names)
            # try:
            #     await target.edit(nick=new_name, reason=f"Bị {ctx.author} dùng thẻ đổi tên")
            # except Exception:
            #     pass
            await ctx.send(f"🤡 Đã đổi tên {target.mention} thành **{new_name}**!")
            
        elif db_key == "shield_card":
            # Ghi nhận trạng thái có khiên vào DB hoặc memory
            # await execute_db(...)
            await ctx.send(f"🛡️ {ctx.author.mention} đã trang bị thẻ miễn nhiễm! Sẽ chặn 1 lần hiệu ứng xấu.")
            
        elif db_key == "free_card":
            if target:
                assert isinstance(target, discord.Member)
                target_mention = target.mention
            else:
                target_mention = ctx.author.mention
            # jail_cog = self.bot.get_cog("JailSystem")
            # Xử lý thả tù...
            await ctx.send(f"🕊️ {ctx.author.mention} đã dùng thẻ đặc xá để giải cứu {target_mention} khỏi nhà giam!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UnifiedInventoryCog(bot))
