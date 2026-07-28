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
        value="Tung đồng xu (h = Ngửa / t = Sấp). Thắng x1.9, đứng xu nhận Jackpot x5.0.",
        inline=False
    )
    embed.add_field(
        name="🥤 y!cups <tiền_cược>",
        value="Đoán ly chứa bảo vật trong 3 ly (có 30s). Chọn đúng nhận x2.3.",
        inline=False
    )
    embed.add_field(
        name="🎲 y!dice <tiền_cược>",
        value="Lắc xúc xắc 7 mặt đặc biệt. Mặt 4,5,6 thắng (x1.25, x1.5, x2.0), mặt 7 nổ Hũ (x8).",
        inline=False
    )
    embed.add_field(
        name="🔫 y!shot <tiền_cược>",
        value="Cò quay tử thần (1 đạn thật, 5 lép). Sống sót nhận thưởng tăng dần (x1.1, x1.3, x1.8, x2.7, x5.0). Chết mất sạch và bị phạt 50 điểm.",
        inline=False
    )
    embed.add_field(
        name="🏮 y!tx <tai/xiu> <tiền_cược>",
        value="Lắc Tài Xỉu 3 viên xúc xắc. (Tài 11-17, Xỉu 4-10). Thắng ăn x1.95. Bão (3 viên giống nhau) nhà cái lụm tất.",
        inline=False
    )
    embed.add_field(
        name="🎡 y!wheel <tiền_cược>",
        value="Vòng quay may mắn 16 ô. Trúng ô Tím x9.0, Xanh lá x1.8. Thua ở ô Vàng được an ủi +1 Vé Xổ Số.",
        inline=False
    )
    embed.add_field(
        name="🎰 y!slots <tiền_cược>",
        value="Máy xẻng. Cơ hội trúng Nổ hũ siêu to: 5 biểu tượng giống nhau x25, 4 biểu tượng x3-x5, 3 biểu tượng x1.2-x1.8.",
        inline=False
    )
    embed.add_field(
        name="🦀 y!bc (hoặc y!baucua)",
        value="Bầu Cua Tôm Cá (Sảnh 30s). Gõ xuống chat `<tên_con_vật> <tiền>`. Thắng nhận Gốc + Lãi (Gốc × số mặt xuất hiện).",
        inline=False
    )
    embed.add_field(
        name="🎲 y!md <tiền_cược> [@user1...]",
        value="Xúc Xắc Quần Hùng (Multi Dice). Mời nhiều người cùng lắc xúc xắc PvP, tự động chia thưởng cho người cao điểm.",
        inline=False
    )
    embed.add_field(
        name="🦆 y!betvit <màu> <tiền_cược>",
        value="Đua vịt sự kiện. Các màu: `do`, `xanh`, `vang`, `hong`, `yon`. (Dùng `y!xemvit` để xem tỷ lệ, `y!huybet` rút tiền).",
        inline=False
    )
    embed.add_field(
        name="🎟️ y!xoso (hoặc y!lottery)",
        value="Xổ Số Kiến Thiết! Dùng `y!xoso mua <sl>` hoặc `y!xoso ban <sl>` để giao dịch vé.",
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
        name="🏆 y!etop (hoặc y!evtop, y!eventop)",
        value="Xem bảng xếp hạng 10 đại gia sự kiện có tổng điểm cày nhiều nhất.",
        inline=False
    )
    embed.add_field(
        name="🎁 y!daily (hoặc y!diemdanh)",
        value="Điểm danh nhận thưởng hàng ngày.",
        inline=False
    )
    embed.add_field(
        name="🎁 y!weekly (hoặc y!luongtuan)",
        value="Nhận lương thưởng mỗi tuần.",
        inline=False
    )
    return embed

def build_blackmarket_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🕵️‍♂️ Chợ Đen & Hành Trang",
        description="Giao dịch vật phẩm ngầm và quản lý túi đồ cá nhân.",
        color=COLOR_THEME
    )
    embed.add_field(
        name="🏪 y!choden (hoặc y!bm, y!blackmarket)",
        value="Mở Chợ Đen để xem các vật phẩm người chơi khác đang rao bán.",
        inline=False
    )
    embed.add_field(
        name="🛒 y!ebuy (hoặc y!muadem, y!bmbuy)",
        value="Mua vật phẩm đang được rao bán trên chợ đen.",
        inline=False
    )
    embed.add_field(
        name="🎒 y!inv (hoặc y!tuido, y!bag, y!inventory)",
        value="Kiểm tra các vật phẩm hiện có trong hành trang của bạn.",
        inline=False
    )
    embed.add_field(
        name="🔮 y!use (hoặc y!dung, y!xai)",
        value="Sử dụng vật phẩm trong túi đồ của bạn.",
        inline=False
    )
    return embed

def build_admin_event_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚙️ Quản Trị Sự Kiện",
        description="Lệnh dành cho Admin/Owner sự kiện.",
        color=COLOR_THEME
    )
    embed.add_field(
        name="Lệnh Tiền Tệ",
        value="• `y!give` | `y!giveall` ── Bơm tiền sự kiện.\n• `y!take` | `y!takeall` ── Trừ tiền sự kiện.",
        inline=False
    )
    embed.add_field(
        name="Lệnh Trigger Minigame",
        value="• `y!fast_hand` ── Kích hoạt Nhanh Tay Lẹ Mắt.\n• `y!dice_lobby` ── Kích hoạt Lắc Xúc Xắc Sảnh.\n• `y!quick_grab` ── Kích hoạt Giật Lì Xì.\n• `y!mvp_tribute` ── Tri ân đại gia P2W.",
        inline=False
    )
    return embed

def build_farm_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🌻 Nông Trại Nhàn Rỗi",
        description="Chào mừng bạn đến với khu vườn nhàn rỗi! Hãy chăm chỉ trồng trọt, thu hoạch nông sản chất lượng để kiếm thật nhiều điểm.",
        color=COLOR_THEME
    )
    embed.add_field(
        name="🚜 y!farm (hoặc y!nongtrai)",
        value="Mở giao diện Nông Trại. Nơi tương tác chính để chăm sóc cây trồng (Tưới, Thu Hoạch, Dọn cỏ).",
        inline=False
    )
    embed.add_field(
        name="🛒 y!shop",
        value="Mở cửa hàng hạt giống Nông nghiệp (Đang phát triển).",
        inline=False
    )
    embed.add_field(
        name="🎒 y!bag (hoặc y!khodo)",
        value="Xem Túi đồ. Nông sản thu hoạch được chia làm 4 phẩm chất: Normal, Silver 🥈, Gold 🥇, Iridium 🌟. Bán nông sản để nhận điểm sự kiện.",
        inline=False
    )
    embed.add_field(
        name="🏭 y!machine",
        value="Khu vực Chế biến nông sản thành hàng nghệ nhân (Đang phát triển).",
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
                description="Lệnh về số dư, điểm danh, cửa hàng, BXH"
            ),
            discord.SelectOption(
                label="Chợ Đen & Hành Trang",
                value="blackmarket",
                emoji="🕵️‍♂️",
                description="Giao dịch chợ đen và sử dụng túi đồ"
            ),
            discord.SelectOption(
                label="Nông Trại Nhàn Rỗi",
                value="farm",
                emoji="🌻",
                description="Hệ thống trồng trọt kiếm điểm"
            ),
            discord.SelectOption(
                label="Quản Trị Sự Kiện",
                value="admin",
                emoji="⚙️",
                description="Các lệnh điều hành sự kiện (Admin)"
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
        elif selected == "farm":
            embed = build_farm_embed()
        elif selected == "blackmarket":
            embed = build_blackmarket_embed()
        elif selected == "admin":
            embed = build_admin_event_embed()
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
