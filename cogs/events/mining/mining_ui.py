"""
mining_ui.py — Giao diện Khu Mỏ (Mining)
==========================================
Thanh thể lực, nút đập đá, xử lý loot theo cấp cuốc và cập nhật inventory.
"""
import discord
from discord.ext import commands
from typing import Any, Dict

from .mining_config import (
    MAX_STAMINA, STAMINA_PER_HIT,
    MINING_LOOT, PICKAXE_NAMES,
    STAMINA_REGEN_INTERVAL_SECONDS,
    get_mining_loot, get_mining_display_weights
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.common.db import update_event_stat


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _stamina_bar(stamina: int, max_stamina: int = MAX_STAMINA, bar_len: int = 10) -> str:
    filled = round(stamina / max_stamina * bar_len)
    return "🟩" * filled + "⬛" * (bar_len - filled)

def _mins_to_full(stamina: int) -> str:
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

def build_mining_embed(author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any]) -> discord.Embed:
    """Render giao diện Hang Động với thanh thể lực và thông tin cuốc hiện tại."""
    pickaxe_level = int(farm_data.get("pickaxe_level", 1))
    pickaxe_name  = PICKAXE_NAMES.get(pickaxe_level, f"Lv{pickaxe_level}")

    embed = discord.Embed(
        title="⛏️ Khu Mỏ Hang Động",
        description=(
            f"Chào mừng **{author.display_name}** đến với hang động bí ẩn!\n"
            f"Hãy đập đá để tìm quặng quý. Mỗi lần đập tốn **{STAMINA_PER_HIT}** thể lực.\n"
        ),
        color=0x7f8c8d,
    )

    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina)})" if stamina < MAX_STAMINA else "✅ Đã đầy"
    embed.add_field(
        name="💪 Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )
    embed.add_field(
        name="⛏️ Cuốc Hiện Tại",
        value=f"**{pickaxe_name}** (Lv{pickaxe_level})",
        inline=True,
    )

    display_weights = get_mining_display_weights(pickaxe_level)
    loot_lines = [
        f"{ore['icon']} **{ore['name']}** — {display_weights[ore_id]}%"
        for ore_id, ore in MINING_LOOT.items()
    ]
    embed.add_field(name="📊 Tỉ Lệ Rớt Đồ (Base)", value="\n".join(loot_lines), inline=True)

    inventory = farm_data.get("inventory", {})
    ore_lines = [
        f"{ore['icon']} {ore['name']}: **{inventory.get(ore_id, 0)}**"
        for ore_id, ore in MINING_LOOT.items()
        if inventory.get(ore_id, 0) > 0
    ]
    if ore_lines:
        embed.add_field(name="🎒 Kho Quặng Của Bạn", value="\n".join(ore_lines), inline=False)

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng kbag để bán quặng. Thể lực hồi 1 điểm mỗi 18 giây.")
    return embed


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------

class MiningView(discord.ui.View):
    """View chính của Khu Mỏ."""

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, stamina: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.mine_btn.disabled = (stamina < STAMINA_PER_HIT)

    @discord.ui.button(label="Đập Đá", emoji="⛏️", style=discord.ButtonStyle.primary)
    async def mine_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ Đây không phải khu mỏ của bạn!", ephemeral=True
            )
            return

        from cogs.common.db import get_active_boosts
        boosts = await get_active_boosts(self.bot, self.user_id)
        stamina_cost = STAMINA_PER_HIT
        if "stamina_discount" in boosts:
            stamina_cost = max(1, stamina_cost - int(boosts["stamina_discount"]["value"]))
            
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < stamina_cost:
            button.disabled = True
            farm_data = await get_farm_data(self.bot, self.user_id)
            await interaction.response.edit_message(
                embed=build_mining_embed(self.author, current_stamina, farm_data), view=self
            )
            await interaction.followup.send(
                f"😓 Bạn đã **kiệt sức**! Hãy đợi thể lực hồi phục.\n"
                f"*(Hồi đầy sau: {_mins_to_full(current_stamina)})*",
                ephemeral=True,
            )
            return

        # 2. Trừ thể lực
        farm_data = await get_farm_data(self.bot, self.user_id)
        new_stamina = current_stamina - stamina_cost
        farm_data["stamina"] = new_stamina
        pickaxe_level = int(farm_data.get("pickaxe_level", 1))

        # 3. Random quặng theo cấp cuốc
        loot_id, quantity = get_mining_loot(pickaxe_level, boosts)
        loot_info = MINING_LOOT[loot_id]

        inventory = farm_data.setdefault("inventory", {})
        inventory[loot_id] = inventory.get(loot_id, 0) + quantity

        # 4. Lưu DB (cập nhật lootbox nếu có)
        from cogs.events.lootbox.lootbox_cmd import _get_luck_and_boost, _add_lootbox_to_inventory
        from cogs.events.lootbox.lootbox_config import get_activity_lootbox_drop, TIER_EMOJIS, TIER_NAMES
        luck, boost_active = await _get_luck_and_boost(self.bot, self.user_id)
        lb_tier = get_activity_lootbox_drop("mine", luck, boost_active, boosts)
        lb_msg = ""
        if lb_tier:
            await _add_lootbox_to_inventory(self.bot, self.user_id, lb_tier, 1)
            lb_msg = f"\n🎁 **Rớt thêm:** 1x {TIER_EMOJIS[lb_tier]} {TIER_NAMES[lb_tier]}"

        await save_farm_data(self.bot, self.user_id, farm_data)
        await update_event_stat(self.bot, self.user_id, "mines", quantity)
        await update_event_stat(self.bot, self.user_id, "ore_mined", quantity)

        # 5. Cập nhật UI
        if new_stamina < stamina_cost:
            button.disabled = True

        double_str = " **(x2 Cuốc Sắt!)**" if quantity == 2 else ""
        new_embed = build_mining_embed(self.author, new_stamina, farm_data)
        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(
            f"⛏️ Bạn vừa đào được **{quantity}x {loot_info['icon']} {loot_info['name']}**!{double_str}{lb_msg}\n"
            f"*(Thể lực: {new_stamina}/{MAX_STAMINA})*",
            ephemeral=True,
        )
