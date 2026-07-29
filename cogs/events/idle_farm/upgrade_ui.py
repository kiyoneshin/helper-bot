"""
upgrade_ui.py — Giao diện Nâng cấp/Mở rộng Nông trại
"""
import discord
from discord.ext import commands
from typing import Any, Dict

from .config import MAX_SLOTS, get_slot_price
from .farm_db import expand_farm_slot, get_farm_data
from cogs.common.db import fetchval_db

class UpgradeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, farm_data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        
        current_slots = farm_data.get("slots", 3)
        
        # Nút Mở Rộng Ô Đất
        btn = discord.ui.Button(
            label="Mở Rộng Ô Đất",
            emoji="🚜",
            style=discord.ButtonStyle.primary,
            disabled=(current_slots >= MAX_SLOTS)
        )
        btn.callback = self.upgrade_btn_callback
        self.add_item(btn)

    async def upgrade_btn_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với giao diện của người khác!", ephemeral=True)
            return
            
        ok, msg = await expand_farm_slot(self.bot, self.user_id)
        
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        # Lấy lại data để render UI mới
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        
        new_embed = build_upgrade_embed(self.author, new_farm_data, points)
        new_view = UpgradeView(self.bot, self.user_id, self.author, new_farm_data)
        
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"✅ {msg}", ephemeral=True)


def build_upgrade_embed(author: discord.Member, farm_data: Dict[str, Any], points: float) -> discord.Embed:
    embed = discord.Embed(
        title="🚜 Nâng Cấp Nông Trại",
        color=0x3498db
    )
    
    current_slots = farm_data.get("slots", 3)
    
    desc = [
        f"Xin chào **{author.display_name}**, bạn có thể dùng điểm sự kiện để mua thêm ô đất trồng trọt tại đây.\n",
        f"🟫 **Số ô đất hiện tại:** {current_slots} / {MAX_SLOTS}",
        f"💳 **Số dư hiện tại:** {points:,.0f} điểm\n"
    ]
    
    if current_slots >= MAX_SLOTS:
        desc.append("🎉 **Chúc mừng!** Nông trại của bạn đã đạt kích thước tối đa.")
    else:
        price = get_slot_price(current_slots)
        desc.append(f"💰 **Giá mở rộng ô thứ {current_slots + 1}:** {price:,.0f} điểm")
        
    embed.description = "\n".join(desc)
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Nhấn nút bên dưới để tiến hành mở rộng.")
    
    return embed
