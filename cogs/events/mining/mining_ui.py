"""
mining_ui.py — Giao diện Khu Mỏ (Mining)
==========================================
Thanh thể lực, nút đập đá, xử lý loot và cập nhật inventory.
"""
import random
import discord
from discord.ext import commands
from typing import Any, Dict

from .mining_config import (
    MAX_STAMINA, STAMINA_PER_HIT,
    MINING_LOOT, _LOOT_KEYS, _LOOT_WEIGHTS,
    STAMINA_REGEN_INTERVAL_SECONDS,
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _stamina_bar(stamina: int, max_stamina: int = MAX_STAMINA, bar_len: int = 10) -> str:
    """Render thanh thể lực bằng emoji."""
    filled = round(stamina / max_stamina * bar_len)
    return "🟩" * filled + "⬛" * (bar_len - filled)

def _mins_to_full(stamina: int) -> str:
    """Tính thời gian để hồi đủ thể lực từ stamina hiện tại."""
    missing = MAX_STAMINA - stamina
    if missing <= 0:
        return "Đầy"
    total_seconds = missing * STAMINA_REGEN_INTERVAL_SECONDS
    hours, rem = divmod(total_seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_mining_embed(author: discord.Member, stamina: int, farm_data: Dict[str, Any]) -> discord.Embed:
    """
    Render giao diện Hang Động với thanh thể lực trực quan.
    """
    embed = discord.Embed(
        title="⛏️ Khu Mỏ Hang Động",
        description=(
            f"Chào mừng **{author.display_name}** đến với hang động bí ẩn!\n"
            "Hãy đập đá để tìm quặng quý. Mỗi lần đập tốn "
            f"**{STAMINA_PER_HIT}** thể lực.\n"
        ),
        color=0x7f8c8d,
    )

    # Thanh thể lực
    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina)})" if stamina < MAX_STAMINA else "✅ Đã đầy"
    embed.add_field(
        name="💪 Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )

    # Danh sách tỉ lệ rơi
    loot_lines = []
    for ore_id, ore in MINING_LOOT.items():
        loot_lines.append(f"{ore['icon']} **{ore['name']}** — {ore['weight']}%")
    embed.add_field(name="📊 Tỉ Lệ Rớt Đồ", value="\n".join(loot_lines), inline=True)

    # Quặng trong inventory
    inventory = farm_data.get("inventory", {})
    ore_lines = []
    for ore_id, ore in MINING_LOOT.items():
        count = inventory.get(ore_id, 0)
        if count > 0:
            ore_lines.append(f"{ore['icon']} {ore['name']}: **{count}**")
    if ore_lines:
        embed.add_field(name="🎒 Kho Quặng Của Bạn", value="\n".join(ore_lines), inline=True)

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng y!bag để bán quặng. Thể lực hồi 1 điểm mỗi 3 phút.")
    return embed


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------

class MiningView(discord.ui.View):
    """View chính của Khu Mỏ."""

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, stamina: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author

        # Disable nút nếu hết thể lực
        self.mine_btn.disabled = (stamina < STAMINA_PER_HIT)

    @discord.ui.button(label="Đập Đá", emoji="⛏️", style=discord.ButtonStyle.primary)
    async def mine_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ Đây không phải khu mỏ của bạn!", ephemeral=True
            )
            return

        # --- 1. Cập nhật & kiểm tra thể lực ---
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)

        if current_stamina < STAMINA_PER_HIT:
            button.disabled = True
            farm_data = await get_farm_data(self.bot, self.user_id)
            new_embed = build_mining_embed(self.author, current_stamina, farm_data)
            await interaction.response.edit_message(embed=new_embed, view=self)
            await interaction.followup.send(
                f"😓 Bạn đã **kiệt sức**! Hãy đợi thể lực hồi phục nhé.\n"
                f"*(Hồi đầy sau: {_mins_to_full(current_stamina)})*",
                ephemeral=True,
            )
            return

        # --- 2. Trừ thể lực ---
        farm_data = await get_farm_data(self.bot, self.user_id)
        new_stamina = current_stamina - STAMINA_PER_HIT
        farm_data["stamina"] = new_stamina
        # Không cập nhật last_stamina_update ở đây để tránh reset timer hồi

        # --- 3. Quay RNG lấy quặng ---
        loot_id: str = random.choices(_LOOT_KEYS, weights=_LOOT_WEIGHTS, k=1)[0]
        loot_info = MINING_LOOT[loot_id]

        inventory = farm_data.setdefault("inventory", {})
        inventory[loot_id] = inventory.get(loot_id, 0) + 1

        # --- 4. Lưu DB ---
        await save_farm_data(self.bot, self.user_id, farm_data)

        # --- 5. Cập nhật UI ---
        if new_stamina < STAMINA_PER_HIT:
            button.disabled = True

        new_embed = build_mining_embed(self.author, new_stamina, farm_data)
        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(
            f"⛏️ Bạn vừa đào được **1x {loot_info['icon']} {loot_info['name']}**! "
            f"(Thể lực: {new_stamina}/{MAX_STAMINA})",
            ephemeral=True,
        )
