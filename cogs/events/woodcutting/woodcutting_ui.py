import discord
from discord.ext import commands
from typing import Any, Dict

from .woodcutting_config import (
    STAMINA_PER_CHOP, WOODCUTTING_LOOT, AXE_NAMES,
    get_woodcutting_loot, get_woodcutting_display_weights
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA
from cogs.events.mining.mining_ui import _mins_to_full
from cogs.common.db import update_event_stat

def _stamina_bar(stamina: int, bar_len: int = 10) -> str:
    filled = round(stamina / MAX_STAMINA * bar_len)
    return "🟩" * filled + "⬛" * (bar_len - filled)

def build_woodcutting_embed(author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any]) -> discord.Embed:
    axe_level = int(farm_data.get("axe_level", 1))
    axe_name = AXE_NAMES.get(axe_level, f"Lv{axe_level}")

    embed = discord.Embed(
        title="🌲 Rừng Sâu (Woodcutting)",
        description=(
            f"Chào mừng **{author.display_name}** đến với khu rừng bí ẩn!\n"
            f"Hãy đốn củi để tìm vật liệu. Mỗi lần chặt tốn **{STAMINA_PER_CHOP}** thể lực.\n"
        ),
        color=0x27ae60,
    )

    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina)})" if stamina < MAX_STAMINA else "✅ Đã đầy"
    
    embed.add_field(
        name="💪 Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )
    
    embed.add_field(
        name="🪓 Rìu Hiện Tại",
        value=f"**{axe_name}** (Lv{axe_level})",
        inline=True,
    )

    display_weights = get_woodcutting_display_weights(axe_level)
    loot_lines = [
        f"{item['icon']} **{item['name']}** — {display_weights[item_id]}%"
        for item_id, item in WOODCUTTING_LOOT.items()
    ]
    embed.add_field(name="📊 Tỉ Lệ Rớt (Base)", value="\n".join(loot_lines), inline=True)

    inventory = farm_data.get("inventory", {})
    inv_lines = [
        f"{item['icon']} {item['name']}: **{inventory.get(item_id, 0)}**"
        for item_id, item in WOODCUTTING_LOOT.items()
        if inventory.get(item_id, 0) > 0
    ]
    if inv_lines:
        embed.add_field(name="🎒 Kho Gỗ Của Bạn", value="\n".join(inv_lines), inline=False)

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng kbag để bán vật phẩm. Thể lực hồi 1 điểm mỗi 18 giây.")
    return embed

class WoodcuttingView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, stamina: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.chop_btn.disabled = (stamina < STAMINA_PER_CHOP)

    @discord.ui.button(label="Chặt Cây", emoji="🪓", style=discord.ButtonStyle.success)
    async def chop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Khu rừng của người khác, cấm chặt trộm!", ephemeral=True)
            return

        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < STAMINA_PER_CHOP:
            button.disabled = True
            farm_data = await get_farm_data(self.bot, self.user_id)
            await interaction.response.edit_message(embed=build_woodcutting_embed(self.author, current_stamina, farm_data), view=self)
            await interaction.followup.send(f"😓 Bạn đã **kiệt sức**! Hãy đợi thể lực hồi phục.\n*(Hồi đầy sau: {_mins_to_full(current_stamina)})*", ephemeral=True)
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        new_stamina = current_stamina - STAMINA_PER_CHOP
        farm_data["stamina"] = new_stamina
        axe_level = int(farm_data.get("axe_level", 1))

        loot_id, quantity = get_woodcutting_loot(axe_level)
        loot_info = WOODCUTTING_LOOT[loot_id]

        inventory = farm_data.setdefault("inventory", {})
        inventory[loot_id] = inventory.get(loot_id, 0) + quantity

        await save_farm_data(self.bot, self.user_id, farm_data)

        if new_stamina < STAMINA_PER_CHOP:
            button.disabled = True

        double_str = " **(x2 Rìu Sắt!)**" if quantity == 2 else ""
        new_embed = build_woodcutting_embed(self.author, new_stamina, farm_data)
        await interaction.response.edit_message(embed=new_embed, view=self)
        
        await update_event_stat(self.bot, self.user_id, "works", 1)
        
        await interaction.followup.send(f"🪓 Bạn vung rìu và nhận được: {loot_info['icon']} **{quantity}x {loot_info['name']}**{double_str}!", ephemeral=True)
