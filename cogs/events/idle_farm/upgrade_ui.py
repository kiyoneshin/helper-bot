"""
upgrade_ui.py — Giao diện Nâng cấp Nông trại & Dụng cụ
========================================================
Bao gồm:
  • Mở rộng ô đất (kupgrade)
  • Nâng cấp Cuốc chim (pickaxe_level)
  • Nâng cấp Cần câu (rod_level)
  """
import discord
from discord.ext import commands
from typing import Any, Dict

from .config import MAX_SLOTS, get_slot_price
from .farm_db import expand_farm_slot, get_farm_data, save_farm_data
from cogs.common.db import fetchval_db, deduct_event_points
from cogs.events.mining.mining_config import (
    PICKAXE_UPGRADE_COST, PICKAXE_NAMES, MAX_PICKAXE_LEVEL, MINING_LOOT
)
from cogs.events.fishing.fishing_config import (
    ROD_UPGRADE_COST, ROD_NAMES, MAX_ROD_LEVEL, FISH_LOOT
)
from cogs.events.woodcutting.woodcutting_config import (
    AXE_UPGRADE_COST, AXE_NAMES, MAX_AXE_LEVEL, WOODCUTTING_LOOT
)
from cogs.events.idle_farm.machine_config import ARTISAN_GOODS

# Bảng tra cứu tên/icon toàn bộ vật phẩm hỗ trợ trong upgrade
_ALL_UPGRADE_ITEMS: Dict[str, dict] = {
    **MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT,
    # Artisan Goods (Phôi kim loại, sản phẩm chế biến)
    "copper_bar":    {"name": "Phôi Đồng",    "icon": "🔶"},
    "iron_bar":      {"name": "Phôi Sắt",     "icon": "⬜"},
    "gold_bar":      {"name": "Phôi Vàng",    "icon": "🌟"},
    "pine_resin":    {"name": "Nhựa Thông",   "icon": "🫙"},
    "stingray":      {"name": "Cá Đuối",      "icon": "🦈"},
    "legendary_fish":{"name": "Cá Huyền Thoại","icon": "🐉"},
}


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_upgrade_embed(author: discord.Member | discord.User, farm_data: Dict[str, Any], points: float) -> discord.Embed:
    embed = discord.Embed(
        title="🔧 Nâng Cấp Trang Trại",
        color=0x3498db,
    )

    current_slots    = farm_data.get("slots", 3)
    pickaxe_level    = farm_data.get("pickaxe_level", 1)
    rod_level        = farm_data.get("rod_level", 1)
    axe_level        = farm_data.get("axe_level", 1)
    inventory        = farm_data.get("inventory", {})

    embed.description = (
        f"Xin chào **{author.display_name}**!\n"
        f"<:symbol_credit_card:1536308433693712404> **Số dư:** {points:,.0f} điểm\n"
    )

    # --- Ô đất ---
    if current_slots >= MAX_SLOTS:
        slot_info = "<:symbol_right:1536629912515903578> Đã đạt kích thước tối đa!"
    else:
        slot_price = get_slot_price(current_slots)
        slot_info = f"Ô thứ {current_slots + 1} → **{slot_price:,.0f}** điểm"

    embed.add_field(
        name=f"🟫 Ô Đất: {current_slots}/{MAX_SLOTS}",
        value=slot_info,
        inline=False,
    )

    # --- Cuốc chim ---
    pickaxe_name = PICKAXE_NAMES.get(pickaxe_level, f"Lv{pickaxe_level}")
    if pickaxe_level >= MAX_PICKAXE_LEVEL:
        pick_info = "<:symbol_right:1536629912515903578> Đã đạt cấp tối đa!"
    else:
        cost_pts, cost_items = PICKAXE_UPGRADE_COST[pickaxe_level]
        items_str = ", ".join(
            f"{_ALL_UPGRADE_ITEMS[k]['icon']} {v}x {_ALL_UPGRADE_ITEMS[k]['name']}"
            for k, v in cost_items.items() if k in _ALL_UPGRADE_ITEMS
        ) or "_(không rõ nguyên liệu)_"
        # Kiểm tra đủ nguyên liệu
        has_items = all(inventory.get(k, 0) >= v for k, v in cost_items.items())
        can_afford = points >= cost_pts
        status = "<:symbol_right:1536629912515903578> Đủ vật liệu" if (has_items and can_afford) else "<:symbol_wrong:1536629915598848072> Chưa đủ"
        pick_info = f"**{cost_pts:,.0f}** điểm + {items_str}\n{status}"

    embed.add_field(
        name=f"<:symbol_00_mining:1536007694920585356> Cuốc: {pickaxe_name} (Lv{pickaxe_level})",
        value=pick_info,
        inline=True,
    )

    # --- Cần câu ---
    rod_name = ROD_NAMES.get(rod_level, f"Lv{rod_level}")
    if rod_level >= MAX_ROD_LEVEL:
        rod_info = "<:symbol_right:1536629912515903578> Đã đạt cấp tối đa!"
    else:
        cost_pts, cost_items = ROD_UPGRADE_COST[rod_level]
        items_str = ", ".join(
            f"{_ALL_UPGRADE_ITEMS[k]['icon']} {v}x {_ALL_UPGRADE_ITEMS[k]['name']}"
            for k, v in cost_items.items() if k in _ALL_UPGRADE_ITEMS
        ) or "_(không rõ nguyên liệu)_"
        has_items = all(inventory.get(k, 0) >= v for k, v in cost_items.items())
        can_afford = points >= cost_pts
        status = "<:symbol_right:1536629912515903578> Đủ vật liệu" if (has_items and can_afford) else "<:symbol_wrong:1536629915598848072> Chưa đủ"
        rod_info = f"**{cost_pts:,.0f}** điểm + {items_str}\n{status}"

    embed.add_field(
        name=f"<:symbol_00_fishing:1536007692437422171> Cần Câu: {rod_name} (Lv{rod_level})",
        value=rod_info,
        inline=True,
    )

    # --- Rìu ---
    axe_name = AXE_NAMES.get(axe_level, f"Lv{axe_level}")
    if axe_level >= MAX_AXE_LEVEL:
        axe_info = "<:symbol_right:1536629912515903578> Đã đạt cấp tối đa!"
    else:
        cost_pts, cost_items = AXE_UPGRADE_COST[axe_level]
        items_str = ", ".join(
            f"{_ALL_UPGRADE_ITEMS[k]['icon']} {v}x {_ALL_UPGRADE_ITEMS[k]['name']}"
            for k, v in cost_items.items() if k in _ALL_UPGRADE_ITEMS
        ) or "_(không rõ nguyên liệu)_"
        has_items = all(inventory.get(k, 0) >= v for k, v in cost_items.items())
        can_afford = points >= cost_pts
        status = "<:symbol_right:1536629912515903578> Đủ vật liệu" if (has_items and can_afford) else "<:symbol_wrong:1536629915598848072> Chưa đủ"
        axe_info = f"**{cost_pts:,.0f}** điểm + {items_str}\n{status}"

    embed.add_field(
        name=f"<:symbol_00_woodcutting:1536007697491558491> Rìu: {axe_name} (Lv{axe_level})",
        value=axe_info,
        inline=False,
    )

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Nhấn nút bên dưới để nâng cấp.")
    return embed


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------

class UpgradeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, farm_data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.bot     = bot
        self.user_id = user_id
        self.author  = author

        current_slots = farm_data.get("slots", 3)
        pickaxe_level = farm_data.get("pickaxe_level", 1)
        rod_level     = farm_data.get("rod_level", 1)
        axe_level     = farm_data.get("axe_level", 1)

        # Nút 1: Mở rộng ô đất
        btn_slot = discord.ui.Button(
            label="Mở Rộng Ô Đất",
            emoji="<:symbol_plant:1536007706958237828>",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=(current_slots >= MAX_SLOTS),
        )
        btn_slot.callback = self._slot_callback
        self.add_item(btn_slot)

        # Nút 2: Nâng cấp Cuốc
        btn_pick = discord.ui.Button(
            label="Nâng Cuốc Chim",
            emoji="<:symbol_00_mining:1536007694920585356>",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(pickaxe_level >= MAX_PICKAXE_LEVEL),
        )
        btn_pick.callback = self._pickaxe_callback
        self.add_item(btn_pick)

        # Nút 3: Nâng cấp Cần câu
        btn_rod = discord.ui.Button(
            label="Nâng Cần Câu",
            emoji="<:symbol_00_fishing:1536007692437422171>",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(rod_level >= MAX_ROD_LEVEL),
        )
        btn_rod.callback = self._rod_callback
        self.add_item(btn_rod)

        # Nút 4: Nâng cấp Rìu
        btn_axe = discord.ui.Button(
            label="Nâng Rìu",
            emoji="<:symbol_00_woodcutting:1536007697491558491>",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(axe_level >= MAX_AXE_LEVEL),
        )
        btn_axe.callback = self._axe_callback
        self.add_item(btn_axe)

    # -----------------------------------------------------------------------
    # HELPER: kiểm tra chủ sở hữu
    # -----------------------------------------------------------------------
    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "<:symbol_wrong:1536629915598848072> Bạn không thể tương tác với giao diện của người khác!", ephemeral=True
            )
            return False
        return True

    # -----------------------------------------------------------------------
    # HELPER: refresh embed & view
    # -----------------------------------------------------------------------
    async def update_view(self, interaction: discord.Interaction, msg: str) -> None:
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        user_points   = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points        = float(user_points) if user_points else 0.0

        new_embed = build_upgrade_embed(self.author, new_farm_data, points)
        new_view  = UpgradeView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"<:symbol_right:1536629912515903578> {msg}", ephemeral=True)

    # -----------------------------------------------------------------------
    # CALLBACK: Mở rộng ô đất
    # -----------------------------------------------------------------------
    async def _slot_callback(self, interaction: discord.Interaction) -> None:
        if not await self._check_owner(interaction):
            return
        ok, msg = await expand_farm_slot(self.bot, self.user_id)
        if not ok:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {msg}", ephemeral=True)
            return
        await self.update_view(interaction, msg)

    # -----------------------------------------------------------------------
    # CALLBACK: Nâng cấp Cuốc
    # -----------------------------------------------------------------------
    async def _pickaxe_callback(self, interaction: discord.Interaction) -> None:
        if not await self._check_owner(interaction):
            return

        farm_data     = await get_farm_data(self.bot, self.user_id)
        pickaxe_level = int(farm_data.get("pickaxe_level", 1))
        inventory     = farm_data.setdefault("inventory", {})

        if pickaxe_level >= MAX_PICKAXE_LEVEL:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Cuốc đã đạt cấp tối đa!", ephemeral=True)
            return

        cost_pts, cost_items = PICKAXE_UPGRADE_COST[pickaxe_level]

        # Kiểm tra điểm
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        if points < cost_pts:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> Không đủ điểm! Cần **{cost_pts:,.0f}**, bạn có **{points:,.0f}**.", ephemeral=True
            )
            return

        # Kiểm tra vật liệu
        for item_id, qty in cost_items.items():
            if inventory.get(item_id, 0) < qty:
                item_name = MINING_LOOT.get(item_id, {}).get("name", item_id)
                await interaction.response.send_message(
                    f"<:symbol_wrong:1536629915598848072> Thiếu **{item_name}**! Cần {qty}, bạn có {inventory.get(item_id, 0)}.", ephemeral=True
                )
                return

        # Trừ điểm và vật liệu
        await deduct_event_points(self.bot, self.user_id, cost_pts)
        for item_id, qty in cost_items.items():
            inventory[item_id] -= qty

        farm_data["pickaxe_level"] = pickaxe_level + 1
        await save_farm_data(self.bot, self.user_id, farm_data)

        new_name = PICKAXE_NAMES.get(pickaxe_level + 1, f"Lv{pickaxe_level + 1}")
        await self.update_view(interaction, f"Nâng cấp thành công! Cuốc mới: **{new_name}**")

    # -----------------------------------------------------------------------
    # CALLBACK: Nâng cấp Cần câu
    # -----------------------------------------------------------------------
    async def _rod_callback(self, interaction: discord.Interaction) -> None:
        if not await self._check_owner(interaction):
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        rod_level = int(farm_data.get("rod_level", 1))
        inventory = farm_data.setdefault("inventory", {})

        if rod_level >= MAX_ROD_LEVEL:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Cần câu đã đạt cấp tối đa!", ephemeral=True)
            return

        cost_pts, cost_items = ROD_UPGRADE_COST[rod_level]

        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        if points < cost_pts:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> Không đủ điểm! Cần **{cost_pts:,.0f}**, bạn có **{points:,.0f}**.", ephemeral=True
            )
            return

        all_items = {**MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT}
        for item_id, qty in cost_items.items():
            if inventory.get(item_id, 0) < qty:
                item_name = all_items.get(item_id, {}).get("name", item_id)
                await interaction.response.send_message(
                    f"<:symbol_wrong:1536629915598848072> Thiếu **{item_name}**! Cần {qty}, bạn có {inventory.get(item_id, 0)}.", ephemeral=True
                )
                return

        await deduct_event_points(self.bot, self.user_id, cost_pts)
        for item_id, qty in cost_items.items():
            inventory[item_id] -= qty

        farm_data["rod_level"] = rod_level + 1
        await save_farm_data(self.bot, self.user_id, farm_data)

        new_name = ROD_NAMES.get(rod_level + 1, f"Lv{rod_level + 1}")
        await self.update_view(interaction, f"Nâng cấp thành công! Cần câu mới: **{new_name}**")

    # -----------------------------------------------------------------------
    # CALLBACK: Nâng cấp Rìu
    # -----------------------------------------------------------------------
    async def _axe_callback(self, interaction: discord.Interaction) -> None:
        if not await self._check_owner(interaction):
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        axe_level = int(farm_data.get("axe_level", 1))
        inventory = farm_data.setdefault("inventory", {})

        if axe_level >= MAX_AXE_LEVEL:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Rìu đã đạt cấp tối đa!", ephemeral=True)
            return

        cost_pts, cost_items = AXE_UPGRADE_COST[axe_level]

        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        if points < cost_pts:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> Không đủ điểm! Cần **{cost_pts:,.0f}**, bạn có **{points:,.0f}**.", ephemeral=True
            )
            return

        all_items = {**MINING_LOOT, **FISH_LOOT, **WOODCUTTING_LOOT}
        for item_id, qty in cost_items.items():
            if inventory.get(item_id, 0) < qty:
                item_name = all_items.get(item_id, {}).get("name", item_id)
                await interaction.response.send_message(
                    f"<:symbol_wrong:1536629915598848072> Thiếu **{item_name}**! Cần {qty}, bạn có {inventory.get(item_id, 0)}.", ephemeral=True
                )
                return

        await deduct_event_points(self.bot, self.user_id, cost_pts)
        for item_id, qty in cost_items.items():
            inventory[item_id] -= qty

        farm_data["axe_level"] = axe_level + 1
        await save_farm_data(self.bot, self.user_id, farm_data)

        new_name = AXE_NAMES.get(axe_level + 1, f"Lv{axe_level + 1}")
        await self.update_view(interaction, f"Nâng cấp thành công! Rìu mới: **{new_name}**")
