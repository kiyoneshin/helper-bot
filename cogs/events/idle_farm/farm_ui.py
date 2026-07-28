"""
farm_ui.py — Giao diện hiển thị và tương tác của Nông Trại
==========================================================
Chứa các view, dropdown và hàm tạo Embed.
"""

from typing import Any, Dict
import discord
from discord.ext import commands

from .config import SEEDS
from .farm_db import plant_seed, water_all, harvest_all, calculate_crop_status

class FarmShopSelect(discord.ui.Select):
    """Dropdown Menu cho phép chọn mua hạt giống."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = []
        for seed_id, seed_data in SEEDS.items():
            options.append(
                discord.SelectOption(
                    label=f"Mua: {seed_data['name']} ({seed_data['cost']} pts)",
                    value=seed_id,
                    description=seed_data['description'],
                    emoji=seed_data['icon']
                )
            )
            
        super().__init__(
            placeholder="🛒 Chọn mua hạt giống để trồng...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        
    async def callback(self, interaction: discord.Interaction):
        """Xử lý sự kiện khi người dùng chọn mua hạt giống."""
        selected_seed = self.values[0]
        seed_info = SEEDS[selected_seed]
        
        # TODO: Cần logic yêu cầu người chơi chọn Slot để trồng, hoặc tự động tìm Slot rỗng
        # await plant_seed(self.bot, str(interaction.user.id), selected_seed, slot_id=1)
        
        await interaction.response.send_message(
            f"Bạn đã chọn mua **{seed_info['name']}**! (Hệ thống xử lý đang được xây dựng)", 
            ephemeral=True
        )


class FarmView(discord.ui.View):
    """View chính của Nông Trại chứa các nút tương tác."""
    
    def __init__(self, bot: commands.Bot, user_id: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        
        # Gắn Dropdown Menu (Cửa hàng) vào View
        self.add_item(FarmShopSelect(bot))
        
    @discord.ui.button(label="Tưới Nước Tất Cả", emoji="💧", style=discord.ButtonStyle.primary, row=1)
    async def water_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: Gọi hàm water_all()
        # ok = await water_all(self.bot, self.user_id)
        await interaction.response.send_message("💦 Đã tưới nước cho toàn bộ khu vườn! (Giả lập)", ephemeral=True)
        
    @discord.ui.button(label="Thu Hoạch", emoji="🧺", style=discord.ButtonStyle.success, row=1)
    async def harvest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: Gọi hàm harvest_all()
        # report = await harvest_all(self.bot, self.user_id)
        await interaction.response.send_message("🧺 Thu hoạch thành công! Bạn nhận được vô số điểm (Giả lập)", ephemeral=True)


def build_farm_embed(author: discord.Member, farm_data: Dict[str, Any]) -> discord.Embed:
    """
    Render giao diện text hiển thị trực quan các ô đất.
    Ví dụ: [ Ô 1: Đất Trống ] | [ Ô 2: Lúa 🌾 (10p) ]
    """
    embed = discord.Embed(
        title=f"🌻 Nông Trại Của {author.display_name}",
        description="Chào mừng bạn đến với khu vườn nhàn rỗi! Hãy chăm chỉ trồng trọt để kiếm thêm thu nhập nhé.",
        color=0x2ecc71
    )
    
    slots = farm_data.get("slots", 3)
    crops = farm_data.get("crops", {})
    
    farm_display = []
    for i in range(1, slots + 1):
        slot_key = str(i)
        if slot_key in crops:
            crop_dict = crops[slot_key]
            # TODO: Tính toán trạng thái bằng hàm calculate_crop_status(crop_dict)
            # Tùy thuộc vào STATUS (GROWING, READY) để format giao diện hiển thị giờ còn lại
            farm_display.append(f"🌱 **[ Ô {i}: Đang trồng (Giả lập) ]**")
        else:
            farm_display.append(f"🟫 **[ Ô {i}: Đất Trống ]**")
            
    embed.add_field(name="Mảnh Đất Của Bạn", value="\n".join(farm_display), inline=False)
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng menu bên dưới để mua hạt giống hoặc tương tác với cây trồng.")
    
    return embed
