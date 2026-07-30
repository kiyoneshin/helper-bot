"""
upgrade_ui.py — Giao diện Nâng cấp Nông trại & Dụng cụ
========================================================
Bao gồm:
  • Mở rộng ô đất (y!upgrade)
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


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_upgrade_embed(author: discord.Member, farm_data: Dict[str, Any], points: float) -> discord.Embed:
    embed = discord.Embed(
        title="🔧 Nâng Cấp Trang Trại",
        color=0x3498db,
    )

    current_slots    = farm_data.get("slots", 3)
    pickaxe_level    = farm_data.get("pickaxe_level", 1)
    rod_level        = farm_data.get("rod_level", 1)
    inventory        = farm_data.get("inventory", {})

    embed.description = (
        f"Xin chào **{author.display_name}**!\n"
        f"💳 **Số dư:** {points:,.0f} điểm\n"
    )

    # --- Ô đất ---
    if current_slots >= MAX_SLOTS:
        slot_info = "🎉 Đã đạt kích thước tối đa!"
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
        pick_info = "✅ Đã đạt cấp tối đa!"
    else:
        cost_pts, cost_items = PICKAXE_UPGRADE_COST[pickaxe_level]
        items_str = ", ".join(
            f"{MINING_LOOT[k]['icon']} {v}x {MINING_LOOT[k]['name']}" for k, v in cost_items.items()
        )
        # Kiểm tra đủ nguyên liệu
        has_items = all(inventory.get(k, 0) >= v for k, v in cost_items.items())
        can_afford = points >= cost_pts
        status = "✅ Đủ vật liệu" if (has_items and can_afford) else "❌ Chưa đủ"
        pick_info = f"**{cost_pts:,.0f}** điểm + {items_str}\n_{status}_"

    embed.add_field(
        name=f"⛏️ Cuốc: {pickaxe_name} (Lv{pickaxe_level})",
        value=pick_info,
        inline=True,
    )

    # --- Cần câu ---
    rod_name = ROD_NAMES.get(rod_level, f"Lv{rod_level}")
    if rod_level >= MAX_ROD_LEVEL:
        rod_info = "✅ Đã đạt cấp tối đa!"
    else:
        cost_pts, cost_items = ROD_UPGRADE_COST[rod_level]
        # Lấy tên item từ cả MINING_LOOT lẫn FISH_LOOT
        all_items = {**MINING_LOOT, **FISH_LOOT}
        items_str = ", ".join(
            f"{all_items[k]['icon']} {v}x {all_items[k]['name']}"
            for k, v in cost_items.items()
            if k in all_items
        )
        has_items = all(inventory.get(k, 0) >= v for k, v in cost_items.items())
        can_afford = points >= cost_pts
        status = "✅ Đủ vật liệu" if (has_items and can_afford) else "❌ Chưa đủ"
        rod_info = f"**{cost_pts:,.0f}** điểm + {items_str}\n_{status}_"

    embed.add_field(
        name=f"🎣 Cần Câu: {rod_name} (Lv{rod_level})",
        value=rod_info,
        inline=True,
    )

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Nhấn nút bên dưới để nâng cấp.")
    return embed


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------

class UpgradeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, farm_data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.bot     = bot
        self.user_id = user_id
        self.author  = author

        current_slots = farm_data.get("slots", 3)
        pickaxe_level = farm_data.get("pickaxe_level", 1)
        rod_level     = farm_data.get("rod_level", 1)

        # Nút 1: Mở rộng ô đất
        btn_slot = discord.ui.Button(
            label="Mở Rộng Ô Đất",
            emoji="🚜",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=(current_slots >= MAX_SLOTS),
        )
        btn_slot.callback = self._slot_callback
        self.add_item(btn_slot)

        # Nút 2: Nâng cấp Cuốc
        btn_pick = discord.ui.Button(
            label="Nâng Cuốc Chim",
            emoji="⛏️",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(pickaxe_level >= MAX_PICKAXE_LEVEL),
        )
        btn_pick.callback = self._pickaxe_callback
        self.add_item(btn_pick)

        # Nút 3: Nâng cấp Cần câu
        btn_rod = discord.ui.Button(
            label="Nâng Cần Câu",
            emoji="🎣",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(rod_level >= MAX_ROD_LEVEL),
        )
        btn_rod.callback = self._rod_callback
        self.add_item(btn_rod)

    # -----------------------------------------------------------------------
    # HELPER: kiểm tra chủ sở hữu
    # -----------------------------------------------------------------------
    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ Bạn không thể tương tác với giao diện của người khác!", ephemeral=True
            )
            return False
        return True

    # -----------------------------------------------------------------------
    # HELPER: refresh embed & view
    # -----------------------------------------------------------------------
    async def _refresh(self, interaction: discord.Interaction, msg: str) -> None:
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        user_points   = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points        = float(user_points) if user_points else 0.0

        new_embed = build_upgrade_embed(self.author, new_farm_data, points)
        new_view  = UpgradeView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"✅ {msg}", ephemeral=True)

    # -----------------------------------------------------------------------
    # CALLBACK: Mở rộng ô đất
    # -----------------------------------------------------------------------
    async def _slot_callback(self, interaction: discord.Interaction) -> None:
        if not await self._check_owner(interaction):
            return
        ok, msg = await expand_farm_slot(self.bot, self.user_id)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
        await self._refresh(interaction, msg)

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
            await interaction.response.send_message("❌ Cuốc đã đạt cấp tối đa!", ephemeral=True)
            return

        cost_pts, cost_items = PICKAXE_UPGRADE_COST[pickaxe_level]

        # Kiểm tra điểm
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        if points < cost_pts:
            await interaction.response.send_message(
                f"❌ Không đủ điểm! Cần **{cost_pts:,.0f}**, bạn có **{points:,.0f}**.", ephemeral=True
            )
            return

        # Kiểm tra vật liệu
        for item_id, qty in cost_items.items():
            if inventory.get(item_id, 0) < qty:
                item_name = MINING_LOOT.get(item_id, {}).get("name", item_id)
                await interaction.response.send_message(
                    f"❌ Thiếu **{item_name}**! Cần {qty}, bạn có {inventory.get(item_id, 0)}.", ephemeral=True
                )
                return

        # Trừ điểm và vật liệu
        await deduct_event_points(self.bot, self.user_id, cost_pts)
        for item_id, qty in cost_items.items():
            inventory[item_id] -= qty

        farm_data["pickaxe_level"] = pickaxe_level + 1
        await save_farm_data(self.bot, self.user_id, farm_data)

        new_name = PICKAXE_NAMES.get(pickaxe_level + 1, f"Lv{pickaxe_level + 1}")
        await self._refresh(interaction, f"Nâng cấp thành công! Cuốc mới: **{new_name}**")

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
            await interaction.response.send_message("❌ Cần câu đã đạt cấp tối đa!", ephemeral=True)
            return

        cost_pts, cost_items = ROD_UPGRADE_COST[rod_level]

        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        if points < cost_pts:
            await interaction.response.send_message(
                f"❌ Không đủ điểm! Cần **{cost_pts:,.0f}**, bạn có **{points:,.0f}**.", ephemeral=True
            )
            return

        all_items = {**MINING_LOOT, **FISH_LOOT}
        for item_id, qty in cost_items.items():
            if inventory.get(item_id, 0) < qty:
                item_name = all_items.get(item_id, {}).get("name", item_id)
                await interaction.response.send_message(
                    f"❌ Thiếu **{item_name}**! Cần {qty}, bạn có {inventory.get(item_id, 0)}.", ephemeral=True
                )
                return

        await deduct_event_points(self.bot, self.user_id, cost_pts)
        for item_id, qty in cost_items.items():
            inventory[item_id] -= qty

        farm_data["rod_level"] = rod_level + 1
        await save_farm_data(self.bot, self.user_id, farm_data)

        new_name = ROD_NAMES.get(rod_level + 1, f"Lv{rod_level + 1}")
        await self._refresh(interaction, f"Nâng cấp thành công! Cần câu mới: **{new_name}**")
