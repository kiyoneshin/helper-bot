"""
event_help.py — Cog Menu Hướng Dẫn Sự Kiện
=========================================
Lệnh: y!ehelp (Sử dụng UI Dropdown)
"""

import discord
from discord.ext import commands

COLOR_THEME = 0xffb6c1

def build_home_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🌸 Cẩm Nang Sự Kiện Angelic ໒꒱",
        description=(
            "Chào mừng bạn đến với hệ thống sự kiện và giải trí của Angelic!\n\n"
            "Tại đây, bạn có thể tham gia các minigame để kiếm điểm, thử vận may tại Casino, "
            "hoặc tích lũy điểm để đổi những phần quà hấp dẫn trong Cửa Hàng Sự Kiện.\n\n"
            "👇 **Sử dụng Menu thả xuống bên dưới để khám phá các nhóm lệnh nhé!**"
        ),
        color=COLOR_THEME
    )
    return embed

def build_casino_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎰 Danh Sách Lệnh Casino",
        description="Thử vận may của bạn tại các trò chơi Casino. Chơi có trách nhiệm nhé!",
        color=COLOR_THEME
    )
    embed.add_field(
        name="🪙 y!cf <h/t> <tiền_cược>",
        value="Tung đồng xu (h = Ngửa / t = Sấp). Thắng nhận x2 tiền cược.",
        inline=False
    )
    embed.add_field(
        name="🥤 y!cups <tiền_cược>",
        value="Đoán ly chứa bảo vật.",
        inline=False
    )
    embed.add_field(
        name="🎲 y!dice <tiền_cược>",
        value="Lắc xúc xắc 7 mặt đặc biệt (Có cơ hội nổ Jackpot x7).",
        inline=False
    )
    embed.add_field(
        name="🔫 y!shot <tiền_cược>",
        value="Cò quay tử thần (Nga). Chơi nhiều vòng, sống sót càng lâu tiền thưởng càng khủng.",
        inline=False
    )
    embed.add_field(
        name="🏮 y!tx <tai/xiu> <tiền_cược>",
        value="Lắc Tài Xỉu 3 viên xúc xắc.",
        inline=False
    )
    embed.add_field(
        name="🎡 y!wheel <tiền_cược>",
        value="Vòng quay may mắn 16 ô với nhiều hệ số thưởng và hiệu ứng khác nhau.",
        inline=False
    )
    embed.add_field(
        name="🎰 y!slots <tiền_cược>",
        value="Máy xẻng. Cơ hội trúng Nổ hũ siêu to (Jackpot x25).",
        inline=False
    )
    return embed

def build_shop_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛒 Kinh Tế & Cửa Hàng",
        description="Quản lý điểm sự kiện và mua sắm các vật phẩm giá trị.",
        color=COLOR_THEME
    )
    embed.add_field(
        name="💳 y!point (hoặc y!vi, y!bal)",
        value="Kiểm tra số dư điểm sự kiện hiện tại và xem hạng P2W của bạn.",
        inline=False
    )
    embed.add_field(
        name="🛍️ y!shop (hoặc y!cuahang, y!store)",
        value="Mở cửa hàng vật phẩm. Dùng điểm sự kiện để đổi lấy các phần quà hấp dẫn.",
        inline=False
    )
    embed.add_field(
        name="🏆 y!etop (hoặc y!evtop, y!eventop, y!eventtop)",
        value="Xem bảng xếp hạng 10 đại gia sự kiện có tổng điểm cày nhiều nhất.",
        inline=False
    )
    return embed


class EventHelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Trang Chủ",
                value="home",
                emoji="🏠",
                description="Quay về trang chào mừng"
            ),
            discord.SelectOption(
                label="Casino & Minigame",
                value="casino",
                emoji="🎰",
                description="Danh sách các trò chơi giải trí"
            ),
            discord.SelectOption(
                label="Kinh Tế & Cửa Hàng",
                value="shop",
                emoji="🛒",
                description="Lệnh về số dư, cửa hàng, BXH"
            )
        ]
        super().__init__(
            placeholder="🔍 Chọn danh mục bạn muốn xem...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "home":
            embed = build_home_embed()
        elif selected == "casino":
            embed = build_casino_embed()
        elif selected == "shop":
            embed = build_shop_embed()
        else:
            embed = build_home_embed()

        # Update default selection for better UX
        for opt in self.options:
            opt.default = (opt.value == selected)

        await interaction.response.edit_message(embed=embed, view=self.view)


class EventHelpView(discord.ui.View):
    def __init__(self, author: discord.Member | discord.User):
        super().__init__(timeout=60.0)
        self.author = author
        self.select_menu = EventHelpSelect()
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Bạn không thể sử dụng menu này! Hãy tự gõ `y!ehelp` nhé.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.select_menu.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class EventHelpCog(commands.Cog):
    """Cog Hỗ trợ hướng dẫn sự kiện."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ehelp",
        description="Xem danh sách toàn bộ các lệnh sự kiện (UI Dropdown)"
    )
    async def ehelp_cmd(self, ctx: commands.Context):
        """Lệnh hỗ trợ xem nhanh các lệnh sự kiện bằng UI Dropdown."""
        embed = build_home_embed()
        view = EventHelpView(author=ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHelpCog(bot))
