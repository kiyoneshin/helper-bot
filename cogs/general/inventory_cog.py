import discord
from discord.ext import commands

from cogs.events.idle_farm.farm_db import get_farm_data, sell_inventory
from cogs.events.idle_farm.bag_ui import build_bag_embed

# ==============================================================================
# 1. CÁC HÀM MOCK DATA (Giả lập truy vấn Database)
# ==============================================================================
async def get_user_regular_items(user_id: int) -> dict:
    """
    Giả lập lấy dữ liệu vật phẩm thông thường của người dùng từ Database.
    TODO: Thay thế logic bằng câu lệnh SQL SELECT tương ứng của bạn.
    """
    # Trả về dict giả lập (Tên vật phẩm -> Số lượng)
    return {
        "Bình máu (Nhỏ)": 5,
        "Nước tăng lực": 2,
        "Vé x2 Kinh nghiệm": 1
    }

async def get_user_farm_items(bot: commands.Bot, user_id: int) -> dict:
    """
    Hàm này lấy data thật từ hệ thống nông trại (farm_db).
    """
    return await get_farm_data(bot, str(user_id))

# ==============================================================================
# 2. UI COMPONENTS (Select Menu & View)
# ==============================================================================
class InventorySelect(discord.ui.Select):
    """
    Dropdown Menu cho túi đồ.
    """
    def __init__(self, author: discord.Member | discord.User):
        self.author = author
        
        # Tạo 2 lựa chọn (Options)
        options = [
            discord.SelectOption(
                label="Vật phẩm sử dụng",
                value="regular_items",
                emoji="🎒",
                description="Xem túi đồ tiêu hao thông thường",
                default=True # Mặc định chọn cái này khi mở túi
            ),
            discord.SelectOption(
                label="Đồ nông trại",
                value="farm_items",
                emoji="🌾",
                description="Xem kho hạt giống và nông sản"
            )
        ]
        
        super().__init__(
            placeholder="Chọn phân loại túi đồ...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        # Lấy giá trị user đã chọn
        selected_value = self.values[0]
        user_id = interaction.user.id
        view: InventoryView = self.view # type: ignore
        
        # Cập nhật trạng thái "default" của option trong UI
        for opt in self.options:
            opt.default = (opt.value == selected_value)

        # Xây dựng Embed mới dựa trên lựa chọn
        if selected_value == "regular_items":
            items = await get_user_regular_items(user_id)
            embed = discord.Embed(
                title="🎒 Vật phẩm thông thường",
                color=0x2b2d31
            )
            embed.set_author(
                name=f"🎒 Túi Đồ Của {interaction.user.display_name}", 
                icon_url=interaction.user.display_avatar.url
            )
            
            if items:
                desc = "\n".join([f"• **{name}**: {qty}" for name, qty in items.items()])
            else:
                desc = "*Túi đồ trống không!*"
            embed.description = desc
            embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!use <tên_item> để sử dụng")
            
            # Cập nhật View (Chỉ hiện Dropdown, ẩn các nút Bán)
            view.clear_items()
            view.add_item(self)
            
        elif selected_value == "farm_items":
            farm_data = await get_user_farm_items(view.bot, user_id)
            # Tái sử dụng hàm build_bag_embed có sẵn để tính giá tiền & render
            embed = build_bag_embed(interaction.user, farm_data)
            
            # Đổi Footer theo yêu cầu mới
            # Lấy text footer cũ (nếu có phần tính tiền) và nối thêm hướng dẫn
            footer_text = "💡 Hướng dẫn: Dùng lệnh nông trại tương ứng để sử dụng"
            embed.set_footer(text=footer_text)
            
            # Cập nhật View (Hiện Dropdown + Hiện các nút Bán)
            view.clear_items()
            view.add_item(self)
            view.add_item(view.btn_sell_crops)
            view.add_item(view.btn_sell_ores)
            view.add_item(view.btn_sell_fish)

        await interaction.response.edit_message(embed=embed, view=view)


class InventoryView(discord.ui.View):
    """
    View chứa Select Menu và các nút bán (được toggle động).
    """
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.user_id = str(author.id)
        
        self.select_menu = InventorySelect(author)
        
        # Khai báo các nút bấm nhưng chưa add_item ngay từ đầu (vì mặc định là regular_items)
        self.btn_sell_crops = discord.ui.Button(label="Bán Nông Sản", emoji="📦", style=discord.ButtonStyle.success, row=1)
        self.btn_sell_ores = discord.ui.Button(label="Bán Khoáng Sản", emoji="⛏️", style=discord.ButtonStyle.primary, row=1)
        self.btn_sell_fish = discord.ui.Button(label="Bán Cá", emoji="🐠", style=discord.ButtonStyle.secondary, row=1)
        
        # Gắn callback cho các nút bấm
        self.btn_sell_crops.callback = lambda i: self._handle_sell(i, "crops", "Nông sản")
        self.btn_sell_ores.callback = lambda i: self._handle_sell(i, "ores", "Khoáng sản")
        self.btn_sell_fish.callback = lambda i: self._handle_sell(i, "fish", "Cá")
        
        # Mặc định túi đồ mở ra là regular_items nên chỉ có dropdown
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

    async def _handle_sell(self, interaction: discord.Interaction, category: str, label_name: str):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Đây không phải túi đồ của bạn!", ephemeral=True)
            return

        total_profit = await sell_inventory(self.bot, self.user_id, category)
        if total_profit <= 0:
            await interaction.response.send_message(f"❌ Bạn không có {label_name} nào để bán!", ephemeral=True)
            return

        # Cập nhật lại farm_data và render lại embed
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_bag_embed(self.author, new_farm_data)
        new_embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh nông trại tương ứng để sử dụng")

        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(f"✅ Đã bán toàn bộ {label_name}! Thu về **{total_profit:,.0f} điểm**.", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Bắt buộc kiểm tra quyền: Chỉ người gõ lệnh mới được phép chọn Menu.
        """
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Đây không phải túi đồ của bạn!", 
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """
        Xử lý khi view hết hạn.
        """
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ==============================================================================
# 3. COG CLASS (Khai báo lệnh)
# ==============================================================================
class InventoryCog(commands.Cog):
    """Cog xử lý túi đồ cá nhân."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="inv",
        aliases=["bag", "khodo", "inventory"],
        description="Xem túi đồ cá nhân của bạn (Vật phẩm, Nông trại...)"
    )
    async def inventory_cmd(self, ctx: commands.Context):
        """Lệnh xem túi đồ bằng Dropdown UI (Gộp cả tính năng Nông trại)."""
        user_id = ctx.author.id
        
        # Mặc định lấy dữ liệu đồ thông thường khi vừa gọi lệnh
        items = await get_user_regular_items(user_id)
        
        # Xây dựng Embed mặc định
        embed = discord.Embed(
            title="🎒 Vật phẩm thông thường",
            color=0x2b2d31
        )
        embed.set_author(
            name=f"🎒 Túi Đồ Của {ctx.author.display_name}", 
            icon_url=ctx.author.display_avatar.url
        )
        
        if items:
            desc = "\n".join([f"• **{name}**: {qty}" for name, qty in items.items()])
        else:
            desc = "*Túi đồ trống không!*"
        embed.description = desc
        embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!use <tên_item> để sử dụng")

        # Gắn View vào và gửi tin nhắn
        view = InventoryView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(InventoryCog(bot))
