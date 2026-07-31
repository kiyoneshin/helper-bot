import discord
from discord.ext import commands

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

async def get_user_farm_items(user_id: int) -> dict:
    """
    Giả lập lấy dữ liệu nông trại của người dùng từ Database.
    TODO: Thay thế logic bằng câu lệnh SQL SELECT tương ứng của bạn.
    """
    # Trả về dict giả lập (Tên vật phẩm -> Số lượng)
    return {
        "Hạt giống Cà Chua": 10,
        "Lúa Mì": 50,
        "Cuốc Chim (Lv.1)": 1
    }

# ==============================================================================
# 2. UI COMPONENTS (Select Menu & View)
# ==============================================================================
class InventorySelect(discord.ui.Select):
    """
    Dropdown Menu cho túi đồ.
    """
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        self.bot = bot
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
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # Lấy giá trị user đã chọn
        selected_value = self.values[0]
        user_id = interaction.user.id
        
        # Cập nhật trạng thái "default" của option trong UI
        for opt in self.options:
            opt.default = (opt.value == selected_value)

        # Xây dựng Embed mới dựa trên lựa chọn
        embed = discord.Embed(
            color=0x2b2d31
        )
        embed.set_author(
            name=f"🎒 Túi Đồ Của {interaction.user.display_name}", 
            icon_url=interaction.user.display_avatar.url
        )

        if selected_value == "regular_items":
            items = await get_user_regular_items(user_id)
            embed.title = "🎒 Vật phẩm thông thường"
            
            # Format list item
            if items:
                desc = "\n".join([f"• **{name}**: {qty}" for name, qty in items.items()])
            else:
                desc = "*Túi đồ trống không!*"
            embed.description = desc
            
            embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!use <tên_item> để sử dụng")
            
        elif selected_value == "farm_items":
            items = await get_user_farm_items(user_id)
            embed.title = "🌾 Đồ nông trại"
            
            # Format list item
            if items:
                desc = "\n".join([f"• **{name}**: {qty}" for name, qty in items.items()])
            else:
                desc = "*Kho đồ trống không!*"
            embed.description = desc
            
            embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh nông trại tương ứng để sử dụng")

        # Edit lại tin nhắn chứa embed và cập nhật view (Select đã được set default mới)
        await interaction.response.edit_message(embed=embed, view=self.view)


class InventoryView(discord.ui.View):
    """
    View chứa Select Menu, xử lý timeout và phân quyền người bấm.
    """
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=60.0) # Menu tự vô hiệu hóa sau 60 giây
        self.bot = bot
        self.author = author
        self.select_menu = InventorySelect(bot, author)
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

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
        self.select_menu.disabled = True
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
        aliases=["bag"],
        description="Xem túi đồ cá nhân của bạn"
    )
    async def inventory_cmd(self, ctx: commands.Context):
        """Lệnh xem túi đồ bằng Dropdown UI."""
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
