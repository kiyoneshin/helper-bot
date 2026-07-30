"""
bag_ui.py — Giao diện hiển thị Túi Đồ của Nông Trại
"""
import discord
from typing import Any, Dict
from discord.ext import commands

from .config import SEEDS, QUALITY_EMOJIS, QUALITY_MULTIPLIERS
from .farm_db import sell_inventory, get_farm_data

class BagView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author

    async def _handle_sell(self, interaction: discord.Interaction, category: str, label_name: str):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với túi đồ của người khác!", ephemeral=True)
            return

        total_profit = await sell_inventory(self.bot, self.user_id, category)
        if total_profit <= 0:
            await interaction.response.send_message(f"❌ Bạn không có {label_name} nào để bán!", ephemeral=True)
            return

        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_bag_embed(self.author, new_farm_data)

        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(f"✅ Đã bán toàn bộ {label_name}! Thu về **{total_profit:,.0f} điểm**.", ephemeral=True)

    @discord.ui.button(label="Bán Nông Sản", emoji="📦", style=discord.ButtonStyle.success)
    async def sell_crops_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_sell(interaction, "crops", "Nông sản")

    @discord.ui.button(label="Bán Khoáng Sản", emoji="⛏️", style=discord.ButtonStyle.primary)
    async def sell_ores_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_sell(interaction, "ores", "Khoáng sản")

    @discord.ui.button(label="Bán Cá", emoji="🐠", style=discord.ButtonStyle.secondary)
    async def sell_fish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_sell(interaction, "fish", "Cá")

def build_bag_embed(author: discord.Member, farm_data: Dict[str, Any]) -> discord.Embed:
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    
    embed = discord.Embed(
        title=f"🎒 Túi Đồ Sinh Thái Của {author.display_name}",
        color=0xf1c40f
    )
    
    inventory = farm_data.get("inventory", {})
    if not inventory:
        embed.description = "Túi đồ của bạn hiện đang trống rỗng. Hãy đi trồng trọt, câu cá hoặc đào mỏ nhé!"
        embed.set_thumbnail(url=author.display_avatar.url)
        return embed

    seed_lines = []
    crop_lines = []
    ore_lines = []
    fish_lines = []
    
    total_crops_worth = 0
    total_ores_worth = 0
    total_fish_worth = 0

    for item_id, count in inventory.items():
        if count <= 0: continue
        
        if item_id.startswith("seed_"):
            seed_id = item_id[5:]
            seed_info = SEEDS.get(seed_id)
            if seed_info:
                seed_name = seed_info["name"]
                seed_icon = seed_info["icon"]
                seed_lines.append(f"{seed_icon} Hạt giống {seed_name} x**{count}**")
        elif item_id in MINING_LOOT:
            ore_info = MINING_LOOT[item_id]
            price = ore_info.get("price", 0)
            worth = price * count
            total_ores_worth += worth
            ore_lines.append(f"{ore_info['icon']} **{ore_info['name']}** x**{count}** `({price:,.0f} pts/cái)`")
        elif item_id in FISH_LOOT:
            fish_info = FISH_LOOT[item_id]
            price = fish_info.get("price", 0)
            worth = price * count
            total_fish_worth += worth
            
            # Highlight cá hiếm
            rare = fish_info.get("rare_rank", 0)
            highlight = "⭐" if rare >= 3 else ""
            fish_lines.append(f"{fish_info['icon']} {highlight}**{fish_info['name']}** x**{count}** `({price:,.0f} pts/cái)`")
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
                total_crops_worth += item_worth * count
                
                crop_lines.append(f"{seed_icon} **{seed_name}** {emoji} x**{count}** `({item_worth:,.0f} pts/cái)`")
        
    if not seed_lines and not crop_lines and not ore_lines and not fish_lines:
        embed.description = "Túi đồ của bạn hiện đang trống rỗng."
    else:
        desc = ""
        if seed_lines:
            desc += "**🌱 Hạt giống (Không thể bán):**\n" + "\n".join(seed_lines) + "\n\n"
        if crop_lines:
            desc += "**📦 Nông sản:**\n" + "\n".join(crop_lines) + "\n\n"
        if ore_lines:
            desc += "**⛏️ Khoáng sản:**\n" + "\n".join(ore_lines) + "\n\n"
        if fish_lines:
            desc += "**🐠 Cá:**\n" + "\n".join(fish_lines)
            
        embed.description = desc.strip()
        
    # Tổng giá trị dự kiến
    footer_text = []
    if total_crops_worth > 0: footer_text.append(f"📦 Nông sản: {total_crops_worth:,.0f}đ")
    if total_ores_worth > 0: footer_text.append(f"⛏️ Khoáng sản: {total_ores_worth:,.0f}đ")
    if total_fish_worth > 0: footer_text.append(f"🐠 Cá: {total_fish_worth:,.0f}đ")
    
    if footer_text:
        embed.add_field(name="💰 Tổng Giá Trị Dự Kiến", value=" | ".join(footer_text), inline=False)
        
    embed.set_thumbnail(url=author.display_avatar.url)
    return embed
