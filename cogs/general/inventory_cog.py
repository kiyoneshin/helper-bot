import discord
from discord.ext import commands
import json
import logging
from typing import Dict

from cogs.common.db import fetchrow_db
from cogs.events.idle_farm.farm_db import get_farm_data, sell_inventory
from cogs.events.idle_farm.bag_ui import build_bag_embed
from cogs.events.generals.black_market import BLACK_MARKET_ITEMS

log = logging.getLogger("Inventory")

# ==============================================================================
# 1. CÁC HÀM LẤY DATA THỰC TẾ (REAL DATA) TỪ DATABASE
# ==============================================================================
async def get_user_regular_items(bot: commands.Bot, user_id: str) -> dict:
    """
    Lấy dữ liệu vật phẩm thông thường (từ Chợ đen, Sự kiện, v.v.)
    Được chuyển từ black_market.py sang đây.
    """
    row = await fetchrow_db(bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", user_id)
    inv: Dict[str, int] = {}
    if row and row["inventory"]:
        try:
            inv = json.loads(row["inventory"]) if isinstance(row["inventory"], str) else row["inventory"]
        except Exception as e:
            log.error(f"Lỗi parse inventory khi xem inv cho {user_id}: {e}")

    # Lọc bỏ các key có quantity <= 0
    inv = {k: v for k, v in inv.items() if v > 0}
    return inv


async def get_user_farm_items(bot: commands.Bot, user_id: str) -> dict:
    """
    Lấy dữ liệu túi đồ hệ sinh thái (Nông trại, Câu cá, Đào mỏ)
    """
    return await get_farm_data(bot, user_id)


# ==============================================================================
# 2. UI COMPONENTS (Select Menu & View)
# ==============================================================================
class InventorySelect(discord.ui.Select):
    """
    Dropdown Menu cho phép chuyển đổi qua lại giữa Túi đồ thường và Hệ sinh thái.
    """
    def __init__(self, author: discord.Member | discord.User):
        self.author = author
        
        options = [
            discord.SelectOption(
                label="Vật phẩm thông thường",
                value="regular_items",
                emoji="🎒",
                description="Xem túi đồ chợ đen và sự kiện",
                default=True # Mặc định mở túi đồ thường trước
            ),
            discord.SelectOption(
                label="Hệ sinh thái",
                value="farm_items",
                emoji="🌾",
                description="Xem kho nông sản, khoáng sản, cá"
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
        selected_value = self.values[0]
        user_id = str(interaction.user.id)
        view: InventoryView = self.view # type: ignore
        
        # Cập nhật trạng thái default cho options
        for opt in self.options:
            opt.default = (opt.value == selected_value)

        if selected_value == "regular_items":
            # -----------------------------------------------------
            # TRẠNG THÁI 1: VẬT PHẨM THÔNG THƯỜNG
            # -----------------------------------------------------
            inv = await get_user_regular_items(view.bot, user_id)
            
            embed = discord.Embed(
                title=f"🎒 Túi Đồ — {interaction.user.display_name}",
                color=0x2b2d31,
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            if not inv:
                embed.description = "Túi đồ trống rỗng! Ghé `y!choden` để sắm đồ nhé."
            else:
                lines = []
                for item_id, qty in inv.items():
                    item_meta = BLACK_MARKET_ITEMS.get(item_id)
                    item_name = item_meta["name"] if item_meta else f"`{item_id}`"
                    lines.append(f"• **{item_name}** × {qty} — dùng: `y!use {item_id}`")
                embed.description = "\n".join(lines)
            
            embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!use <tên_item> để sử dụng")
            
            # CHỈ HIỂN THỊ DROPDOWN, ẨN CÁC NÚT BÁN
            view.clear_items()
            view.add_item(self)
            
        elif selected_value == "farm_items":
            # -----------------------------------------------------
            # TRẠNG THÁI 2: HỆ SINH THÁI (CÓ NÚT BÁN)
            # -----------------------------------------------------
            farm_data = await get_user_farm_items(view.bot, user_id)
            
            # Tái sử dụng giao diện túi đồ nông trại cũ
            embed = build_bag_embed(interaction.user, farm_data)
            
            # Thay đổi footer
            embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh nông trại tương ứng để sử dụng")
            
            # XUẤT HIỆN LẠI CÁC NÚT BÁN DƯỚI DROPDOWN
            view.clear_items()
            view.add_item(self)
            view.add_item(view.btn_sell_crops)
            view.add_item(view.btn_sell_ores)
            view.add_item(view.btn_sell_fish)

        await interaction.response.edit_message(embed=embed, view=view)


class InventoryView(discord.ui.View):
    """
    View bao bọc toàn bộ hệ thống Túi Đồ (hợp nhất).
    """
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.user_id = str(author.id)
        
        self.select_menu = InventorySelect(author)
        
        # Khai báo sẵn 3 nút bán đồ của hệ sinh thái nhưng chưa thêm vào view ngay
        self.btn_sell_crops = discord.ui.Button(label="Bán Nông Sản", emoji="📦", style=discord.ButtonStyle.success, row=1)
        self.btn_sell_ores = discord.ui.Button(label="Bán Khoáng Sản", emoji="⛏️", style=discord.ButtonStyle.primary, row=1)
        self.btn_sell_fish = discord.ui.Button(label="Bán Cá", emoji="🐠", style=discord.ButtonStyle.secondary, row=1)
        
        # Liên kết callback cho các nút bấm (Sử dụng lại hàm _handle_sell)
        self.btn_sell_crops.callback = lambda i: self._handle_sell(i, "crops", "Nông sản")
        self.btn_sell_ores.callback = lambda i: self._handle_sell(i, "ores", "Khoáng sản")
        self.btn_sell_fish.callback = lambda i: self._handle_sell(i, "fish", "Cá")
        
        # Mặc định khi mở ra là "Vật phẩm thông thường" nên CHỈ add select_menu
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

    async def _handle_sell(self, interaction: discord.Interaction, category: str, label_name: str):
        """Xử lý logic khi người dùng bấm nút bán đồ hệ sinh thái."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Đây không phải túi đồ của bạn!", ephemeral=True)
            return

        total_profit = await sell_inventory(self.bot, self.user_id, category)
        if total_profit <= 0:
            await interaction.response.send_message(f"❌ Bạn không có {label_name} nào để bán!", ephemeral=True)
            return

        # Cập nhật lại farm_data và render lại UI
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_bag_embed(self.author, new_farm_data)
        new_embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh nông trại tương ứng để sử dụng")

        await interaction.response.edit_message(embed=new_embed, view=self)
        await interaction.followup.send(f"✅ Đã bán toàn bộ {label_name}! Thu về **{total_profit:,.0f} điểm**.", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Bảo vệ túi đồ: Chỉ chủ nhân mới được dùng dropdown."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Đây không phải túi đồ của bạn!", 
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ==============================================================================
# 3. COG CLASS
# ==============================================================================
class UnifiedInventoryCog(commands.Cog):
    """Cog kết hợp túi đồ thường và hệ sinh thái thành 1 lệnh duy nhất."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="inv",
        aliases=["bag", "tuido", "khodo", "inventory"],
        description="🎒 Xem toàn bộ túi đồ (Vật phẩm, Nông trại, v.v...)"
    )
    async def inventory_cmd(self, ctx: commands.Context):
        """Lệnh hợp nhất Túi đồ."""
        user_id = str(ctx.author.id)
        
        # Mặc định lấy dữ liệu đồ thông thường khi vừa gọi lệnh
        inv = await get_user_regular_items(self.bot, user_id)
        
        embed = discord.Embed(
            title=f"🎒 Túi Đồ — {ctx.author.display_name}",
            color=0x2b2d31,
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        if not inv:
            embed.description = "Túi đồ trống rỗng! Ghé `y!choden` để sắm đồ nhé."
        else:
            lines = []
            for item_id, qty in inv.items():
                item_meta = BLACK_MARKET_ITEMS.get(item_id)
                item_name = item_meta["name"] if item_meta else f"`{item_id}`"
                lines.append(f"• **{item_name}** × {qty} — dùng: `y!use {item_id}`")
            embed.description = "\n".join(lines)
            
        embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!use <tên_item> để sử dụng")

        view = InventoryView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(UnifiedInventoryCog(bot))
