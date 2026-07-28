"""
bag_ui.py — Giao diện hiển thị Túi Đồ của Nông Trại
"""
import discord
from typing import Any, Dict
from discord.ext import commands

from .config import SEEDS, QUALITY_EMOJIS, QUALITY_MULTIPLIERS
from .farm_db import sell_all_inventory, get_farm_data

class BagView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author

    @discord.ui.button(label="Bán Tất Cả", emoji="💰", style=discord.ButtonStyle.success)
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với túi đồ của người khác!", ephemeral=True)
            return

        total_profit = await sell_all_inventory(self.bot, self.user_id)
        if total_profit <= 0:
            await interaction.response.send_message("❌ Túi đồ của bạn đang trống hoặc không có gì để bán!", ephemeral=True)
            return

        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_bag_embed(self.author, new_farm_data)

        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(f"✅ Đã bán toàn bộ nông sản! Thu về **{total_profit:,.0f} điểm**.", ephemeral=True)

def build_bag_embed(author: discord.Member, farm_data: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎒 Túi Đồ Nông Trại Của {author.display_name}",
        color=0xf1c40f
    )
    
    inventory = farm_data.get("inventory", {})
    if not inventory:
        embed.description = "Túi đồ của bạn hiện đang trống rỗng. Hãy thu hoạch thêm nông sản nhé!"
        embed.set_thumbnail(url=author.display_avatar.url)
        return embed

    seed_lines = []
    crop_lines = []
    total_worth = 0

    for item_id, count in inventory.items():
        if count <= 0: continue
        
        if item_id.startswith("seed_"):
            seed_id = item_id[5:]
            seed_info = SEEDS.get(seed_id)
            if seed_info:
                seed_name = seed_info["name"]
                seed_icon = seed_info["icon"]
                seed_lines.append(f"{seed_icon} Hạt giống {seed_name} x{count}")
        else:
            parts = item_id.split("_")
            quality = parts[-1] if len(parts) > 1 else "normal"
            seed_id = "_".join(parts[:-1]) if len(parts) > 1 else item_id
            
            seed_info = SEEDS.get(seed_id)
            if seed_info:
                seed_name = seed_info["name"]
                seed_icon = seed_info["icon"]
                emoji = QUALITY_EMOJIS.get(quality, "")
                
                base_cost = seed_info["reward_min"]
                multiplier = QUALITY_MULTIPLIERS.get(quality, 1.0)
                item_worth = int(base_cost * multiplier)
                total_worth += item_worth * count
                
                crop_lines.append(f"{seed_icon} **{seed_name}** {emoji} x{count} `({item_worth:,.0f} pts/cái)`")
        
    if not seed_lines and not crop_lines:
        embed.description = "Túi đồ của bạn hiện đang trống rỗng."
    else:
        desc = ""
        if seed_lines:
            desc += "**🌱 Hạt giống:**\n" + "\n".join(seed_lines) + "\n\n"
        if crop_lines:
            desc += "**📦 Nông sản:**\n" + "\n".join(crop_lines)
            
        embed.description = desc.strip()
        
    if total_worth > 0:
        embed.add_field(name="Tổng Giá Trị Nông Sản", value=f"💰 **{total_worth:,.0f} điểm**\n*(Nút Bán Tất Cả bên dưới chỉ bán Nông sản)*", inline=False)
        
    embed.set_thumbnail(url=author.display_avatar.url)
    return embed
