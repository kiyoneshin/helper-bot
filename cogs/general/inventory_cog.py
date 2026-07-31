"""
inventory_cog.py — Cog Túi Đồ Hợp Nhất (y!inv / y!bag / y!use)
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
from cogs.events.generals.black_market import BLACK_MARKET_ITEMS

log = logging.getLogger("InventoryCog")


# ============================================================
# EMBED BUILDERS
# ============================================================

def _build_regular_embed(
    author: discord.Member | discord.User,
    inv: dict[str, int],
    category: str,
) -> discord.Embed:
    """
    Xây dựng Embed cho vật phẩm thông thường (Event/BlackMarket)
    Định dạng: [ID] Icon Tên vật phẩm (xQTY) — Mô tả
    """
    CATEGORY_META = {
        "event":       ("🎪 Vật phẩm Sự kiện",       0x9b59b6, "💡 Sử dụng: `y!use <id>`"),
        "blackmarket": ("🌙 Vật phẩm Chợ đen",        0x2b2d31, "💡 Sử dụng: `y!use <id>`"),
    }
    title, color, footer = CATEGORY_META.get(category, ("🎒 Túi đồ", 0x7289da, ""))

    embed = discord.Embed(title=title, color=color)
    embed.set_author(
        name=f"🎒 Túi Đồ của {author.display_name}",
        icon_url=author.display_avatar.url,
    )
    embed.set_thumbnail(url=author.display_avatar.url)

    if not inv:
        embed.description = "*Mục này đang trống không. Hãy ghé `y!shop` để sắm đồ!*"
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
) -> discord.Embed:
    """
    Xây dựng Embed cho túi đồ nông trại.
    Định dạng tương tự nhưng dùng key string từ farm_data.inventory.
    """
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    from cogs.events.idle_farm.config import SEEDS, QUALITY_EMOJIS, QUALITY_MULTIPLIERS

    embed = discord.Embed(
        title="🌾 Hệ Sinh Thái — Túi Đồ Nông Trại",
        color=0xe67e22,
    )
    embed.set_author(
        name=f"🎒 Túi Đồ của {author.display_name}",
        icon_url=author.display_avatar.url,
    )
    embed.set_thumbnail(url=author.display_avatar.url)

    inventory = farm_data.get("inventory", {})
    if not inventory:
        embed.description = "*Kho đồ nông trại trống. Hãy đi trồng trọt, câu cá hoặc đào mỏ nhé!*"
        embed.set_footer(text="💡 Dùng các nút bên dưới để bán nông sản.")
        return embed

    seed_lines, crop_lines, ore_lines, fish_lines = [], [], [], []
    total_crops_worth = total_ores_worth = total_fish_worth = 0

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
                f" — {price:,} pts/cái"
            )
        elif item_id in FISH_LOOT:
            fish = FISH_LOOT[item_id]
            price = fish.get("price", 0)
            total_fish_worth += price * count
            rare = "⭐" if fish.get("rare_rank", 0) >= 3 else ""
            fish_lines.append(
                f"• `[{item_id}]` {fish['icon']} {rare}**{fish['name']}** (x{count})"
                f" — {price:,} pts/cái"
            )
        else:
            parts = item_id.split("_")
            quality = parts[-1] if len(parts) > 1 else "normal"
            seed_id = "_".join(parts[:-1]) if len(parts) > 1 else item_id
            seed_info = SEEDS.get(seed_id)
            if seed_info:
                emoji = QUALITY_EMOJIS.get(quality, "")
                multiplier = QUALITY_MULTIPLIERS.get(quality, 1.0)
                worth = int(seed_info["reward_min"] * multiplier)
                total_crops_worth += worth * count
                crop_lines.append(
                    f"• `[{item_id}]` {seed_info['icon']} **{seed_info['name']}**"
                    f" {emoji} (x{count}) — {worth:,} pts/cái"
                )

    desc_parts: list[str] = []
    if seed_lines:
        desc_parts.append("**🌱 Hạt giống (Không thể bán):**\n" + "\n".join(seed_lines))
    if crop_lines:
        desc_parts.append("**📦 Nông sản:**\n" + "\n".join(crop_lines))
    if ore_lines:
        desc_parts.append("**⛏️ Khoáng sản:**\n" + "\n".join(ore_lines))
    if fish_lines:
        desc_parts.append("**🐠 Cá:**\n" + "\n".join(fish_lines))

    embed.description = "\n\n".join(desc_parts) if desc_parts else "*Kho trống.*"

    footer_parts: list[str] = []
    if total_crops_worth > 0:
        footer_parts.append(f"📦 {total_crops_worth:,} pts")
    if total_ores_worth > 0:
        footer_parts.append(f"⛏️ {total_ores_worth:,} pts")
    if total_fish_worth > 0:
        footer_parts.append(f"🐠 {total_fish_worth:,} pts")
    if footer_parts:
        embed.add_field(
            name="💰 Tổng Giá Trị Ước Tính",
            value=" | ".join(footer_parts),
            inline=False,
        )

    embed.set_footer(text="💡 Dùng các nút bên dưới để bán nông sản.")
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
        super().__init__(title="🏷️ Bán Vật Phẩm Nông Trại")
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
                    "❌ Số lượng không hợp lệ! Nhập số nguyên dương hoặc 'all'.",
                    ephemeral=True,
                )
                return

        ok, profit, msg = await sell_items_partial(self.bot, self.user_id, item_key, amount)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        # Cập nhật lại embed
        farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = _build_farm_embed(interaction.user, farm_data)
        await interaction.response.edit_message(embed=new_embed, view=self._view)
        await interaction.followup.send(f"✅ {msg}", ephemeral=True)


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
            await interaction.response.send_message("❌ Đã hủy thao tác bán.", ephemeral=True)
            return

        profit = await sell_inventory(self.bot, self.user_id, self.category)
        if profit <= 0:
            await interaction.response.send_message(
                f"❌ Bạn không có {self.label} nào để bán!", ephemeral=True
            )
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = _build_farm_embed(self.author, farm_data)
        await interaction.response.edit_message(embed=new_embed, view=self._view)
        await interaction.followup.send(
            f"✅ Đã bán toàn bộ **{self.label}**! Thu về **{profit:,.0f}** điểm.",
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
                label="Vật phẩm Chợ đen",
                value="blackmarket",
                emoji="🌙",
                description="Xem đồ mua từ chợ đen",
                default=(current == "blackmarket"),
            ),
            discord.SelectOption(
                label="Vật phẩm Sự kiện",
                value="event",
                emoji="🎪",
                description="Xem đồ nhận từ sự kiện",
                default=(current == "event"),
            ),
            discord.SelectOption(
                label="Hệ sinh thái",
                value="farm",
                emoji="🌾",
                description="Xem kho nông sản, quặng, cá",
                default=(current == "farm"),
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

        for opt in self.options:
            opt.default = (opt.value == selected)

        # Rebuild view buttons + embed theo tab được chọn
        if selected == "farm":
            farm_data = await get_farm_data(view.bot, user_id)
            embed = _build_farm_embed(interaction.user, farm_data)
            view._show_farm_buttons()
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
            label="Bán theo Loại & Số lượng", emoji="🏷️",
            style=discord.ButtonStyle.primary, row=1,
        )
        self.btn_sell_crops = discord.ui.Button(
            label="Bán Tất Cả Nông Sản", emoji="📦",
            style=discord.ButtonStyle.success, row=2,
        )
        self.btn_sell_ores = discord.ui.Button(
            label="Bán Tất Cả Quặng", emoji="⛏️",
            style=discord.ButtonStyle.primary, row=2,
        )
        self.btn_sell_fish = discord.ui.Button(
            label="Bán Tất Cả Cá", emoji="🐠",
            style=discord.ButtonStyle.secondary, row=2,
        )

        # Gắn callback
        self.btn_sell_item.callback = self._on_sell_item
        self.btn_sell_crops.callback = lambda i: self._on_sell_all(i, "crops", "Nông sản")
        self.btn_sell_ores.callback = lambda i: self._on_sell_all(i, "ores", "Khoáng sản")
        self.btn_sell_fish.callback = lambda i: self._on_sell_all(i, "fish", "Cá")

        # Mặc định tab không phải farm nên ẩn nút
        if default_tab == "farm":
            self._show_farm_buttons()

    def _show_farm_buttons(self) -> None:
        self.clear_items()
        self.add_item(self.select_menu)
        self.add_item(self.btn_sell_item)
        self.add_item(self.btn_sell_crops)
        self.add_item(self.btn_sell_ores)
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
                "❌ Đây không phải túi đồ của bạn!", ephemeral=True
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
    """🎒 Cog Túi Đồ Hợp Nhất."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="inv",
        aliases=["bag", "tuido", "khodo", "inventory"],
        description="🎒 Xem toàn bộ túi đồ (Chợ đen, Sự kiện, Nông trại...)",
    )
    async def inventory_cmd(self, ctx: commands.Context) -> None:
        """Lệnh hợp nhất Túi đồ bằng Dropdown UI."""
        uid = str(ctx.author.id)

        # Mặc định mở tab Chợ đen (vì thường dùng nhất)
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

        embed = _build_regular_embed(ctx.author, inv, "blackmarket")
        view = InventoryView(self.bot, ctx.author, default_tab="blackmarket")
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="use",
        aliases=["dung", "xai"],
        description="✨ Dùng vật phẩm theo ID số. Cú pháp: y!use <id> [@mục tiêu]",
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
                f"❌ Không tìm thấy vật phẩm với ID `{item_id}`! Dùng `y!inv` để xem túi đồ.",
                delete_after=5.0,
            )
            return

        if not item.get("usable", False):
            await ctx.send(
                f"❌ **{item['name']}** không thể sử dụng bằng lệnh này!",
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
                f"❌ Bạn không có **{item['icon']} {item['name']}** trong túi đồ!",
                delete_after=5.0,
            )
            return

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
                f"✨ {ctx.author.mention} vừa sử dụng **{item['icon']} {item['name']}**"
                f" lên {target_display}!"
            ),
            color=0x57f287,
        )
        await ctx.send(embed=embed)

        # TODO: Thêm hiệu ứng thực tế của từng item tại đây
        # Ví dụ:
        # if db_key == "jail_card":
        #     await _apply_jail(ctx, target)
        # elif db_key == "timeout_1m":
        #     await target.timeout(timedelta(minutes=1))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UnifiedInventoryCog(bot))
