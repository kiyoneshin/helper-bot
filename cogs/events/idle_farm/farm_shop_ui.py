"""
farm_shop_ui.py — Giao diện Cửa hàng Hạt giống Nông trại
"""
import discord
from discord.ext import commands
from typing import Any

from .config import SEEDS
from .farm_db import buy_seed
from cogs.common.db import fetchval_db

class SeedShopSelect(discord.ui.Select):
    """Dropdown Menu cho phép chọn mua hạt giống vào túi đồ."""
    
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
            placeholder="🛒 Chọn mua hạt giống...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        
    async def callback(self, interaction: discord.Interaction):
        view: "SeedShopView" = self.view  # type: ignore
        user_id = str(interaction.user.id)
        
        if user_id != view.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với cửa hàng này!", ephemeral=True)
            return

        selected_seed = self.values[0]
        seed_info = SEEDS.get(selected_seed)
        if not seed_info:
            return
            
        await interaction.response.send_modal(BuySeedModal(self.bot, user_id, view.author, selected_seed, seed_info, view, self))

class BuySeedModal(discord.ui.Modal):
    amount_input = discord.ui.TextInput(
        label="Nhập số lượng muốn mua",
        placeholder="Chỉ nhập số (VD: 1, 5, 10)...",
        default="1",
        min_length=1,
        max_length=3,
        required=True
    )
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, seed_id: str, seed_info: dict, view_obj: "SeedShopView", select_obj: SeedShopSelect):
        super().__init__(title=f"Mua: {seed_info['name']}")
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.seed_id = seed_id
        self.seed_info = seed_info
        self.view_obj = view_obj
        self.select_obj = select_obj
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value.strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Số lượng không hợp lệ! Vui lòng chỉ nhập số dương lớn hơn 0.", ephemeral=True)
            return
            
        ok, msg = await buy_seed(self.bot, self.user_id, self.seed_id, amount)
        
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        # Reset dropdown
        for opt in self.select_obj.options:
            opt.default = False
            
        # Lấy lại số dư để update Embed
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", self.user_id)
        points = float(user_points) if user_points else 0.0
        
        new_embed = build_farmshop_embed(self.author, points)
        await interaction.response.edit_message(embed=new_embed, view=self.view_obj)
        await interaction.followup.send(f"✅ {msg}\n(Hạt giống đã được cất vào `y!bag`)", ephemeral=True)

class SeedShopView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.add_item(SeedShopSelect(bot))

def build_farmshop_embed(author: discord.Member, points: float) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 Cửa Hàng Hạt Giống Nông Trại",
        description=(
            "Chào mừng bạn đến với Cửa hàng Nông nghiệp!\n"
            "Hãy chọn mua hạt giống phù hợp. Hạt giống sau khi mua sẽ được cất vào Túi đồ (`y!bag`).\n\n"
            f"💳 **Số dư hiện tại:** {points:,.0f} điểm"
        ),
        color=0xe67e22
    )
    
    for seed_id, seed_data in SEEDS.items():
        embed.add_field(
            name=f"{seed_data['icon']} {seed_data['name']} — {seed_data['cost']} điểm",
            value=f"Thời gian: {seed_data['grow_time_seconds']//60} phút | Bán: {seed_data['reward_min']}~ điểm",
            inline=False
        )
        
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Sau khi mua, dùng lệnh y!farm để gieo hạt.")
    return embed
