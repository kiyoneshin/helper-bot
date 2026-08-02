"""
event_help.py — Hệ Thống Trợ Giúp Sự Kiện 3 Tầng (y!ehelp)
============================================================
Kiến trúc:
  Tầng 1 - Home     : Danh sách danh mục (Dropdown → Tầng 2)
  Tầng 2 - Category : Danh sách lệnh trong danh mục (Dropdown → Tầng 3 | Button → Tầng 1)
  Tầng 3 - Detail   : Chi tiết lệnh (Button ◀ → Tầng 2 | Button 🏠 → Tầng 1)

Dữ liệu trung tâm: CMD_DATA + CATEGORY_DATA
"""

from __future__ import annotations

import discord
from discord.ext import commands
from typing import Optional

COLOR_THEME = 0xFFB6C1  # Angelic pink

# =============================================================================
# DỮ LIỆU TRUNG TÂM — Chỉ cần sửa ở đây khi thêm/xóa/cập nhật lệnh
# =============================================================================

CMD_DATA: dict[str, dict] = {
    # ── CASINO ────────────────────────────────────────────────────────────────
    "coinflip": {
        "name": "Coinflip",
        "emoji": "🪙",
        "short": "Tung đồng xu H/T. Thắng x1.9, đứng xu Jackpot x5.0.",
        "aliases": ["cf"],
        "cooldown": None,
        "usage": "y!cf <h/t> <tiền_cược | all>",
        "examples": ["y!cf h 50k", "y!cf t all"],
        "note": "Tỉ lệ: Thắng 44% / Thua 55% / Đứng xu 1%",
    },
    "cups": {
        "name": "Cups",
        "emoji": "🥤",
        "short": "Đoán ly có bảo vật trong 3 ly. Chọn đúng nhận x2.3.",
        "aliases": [],
        "cooldown": "30s timeout",
        "usage": "y!cups <tiền_cược | all>",
        "examples": ["y!cups 10k", "y!cups all"],
        "note": "Cần nhấn nút trong 30s, hết giờ sòng trả lại tiền.",
    },
    "dice": {
        "name": "Dice 7",
        "emoji": "🎲",
        "short": "Lắc xúc xắc 7 mặt. Mặt 4-6 thắng (x1.25→x2.0), mặt 7 nổ hũ x8.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!dice <tiền_cược | all>",
        "examples": ["y!dice 100k", "y!dice all"],
        "note": "Mặt 1-3: Thua 25%~100%. Mặt 7 (x7): Jackpot cực hiếm!",
    },
    "roulette": {
        "name": "Roulette",
        "emoji": "🔫",
        "short": "Cò quay tử thần. Sống sót lần 1-5 nhận x1.1→x5.0.",
        "aliases": ["shot"],
        "cooldown": "60s timeout",
        "usage": "y!shot <tiền_cược | all>",
        "examples": ["y!shot 50k", "y!shot all"],
        "note": "1/6 cơ hội trúng đạn mỗi lần. Rút lui sớm để chốt lời an toàn.",
    },
    "crash": {
        "name": "Crash (Tàu Bay)",
        "emoji": "🚀",
        "short": "Tàu bay tăng hệ số x1.1→x99. Nhảy dù trước khi nổ để thắng.",
        "aliases": [],
        "cooldown": "Lobby 30s",
        "usage": "y!crash <tiền_cược>",
        "examples": ["y!crash 100k", "y!crash 1m"],
        "note": "Game nhiều người. Đặt cược qua Button. Tiền bị trừ ngay khi đặt thành công.",
    },
    "wheel": {
        "name": "Vòng Quay",
        "emoji": "🎡",
        "short": "Vòng quay 16 ô. Ô Tím x9.0, Xanh lá x1.8. Thua ô Vàng +1 Vé Xổ Số.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!wheel <tiền_cược | all>",
        "examples": ["y!wheel 50k", "y!wheel all"],
        "note": "Ô Vàng tuy thua nhưng tặng 1 vé số miễn phí!",
    },
    "slots": {
        "name": "Máy Xẻng (Slots)",
        "emoji": "🎰",
        "short": "Quay máy 5 cuộn. 5 biểu tượng giống nhau = Nổ hũ Jackpot.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!slots <tiền_cược | all>",
        "examples": ["y!slots 100k", "y!slots all"],
        "note": "Nhiều cấp độ thắng tùy số biểu tượng trùng.",
    },
    "taixiu": {
        "name": "Tài Xỉu",
        "emoji": "🎲",
        "short": "Lắc 3 xúc xắc. Tài (11-17) / Xỉu (4-10). Thắng x1.95.",
        "aliases": ["tx"],
        "cooldown": None,
        "usage": "y!tx <tai/xiu> <tiền_cược | all>",
        "examples": ["y!tx tai 100k", "y!tx xiu all"],
        "note": "Bão (3 viên giống nhau): Nhà cái ăn hết tiền cược.",
    },
    "baucua": {
        "name": "Bầu Cua",
        "emoji": "🦀",
        "short": "Sảnh Bầu Cua Tôm Cá chung. Đặt cược qua chat trong sảnh.",
        "aliases": ["bc"],
        "cooldown": None,
        "usage": "y!bc",
        "examples": ["y!bc"],
        "note": "Nhiều người chơi cùng lúc. Gõ tên linh vật vào chat để đặt cược trong sảnh.",
    },
    "betvit": {
        "name": "Đua Vịt",
        "emoji": "🦆",
        "short": "Cược vào màu vịt. Vịt thắng, bạn thắng theo tỉ lệ pool.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!betvit <màu> <tiền>",
        "examples": ["y!betvit do 50k", "y!betvit xanh 100k"],
        "note": "Màu: do, xanh, vang, hong, yon. Xem tỉ lệ: `y!xemvit`. Hủy cược: `y!huybet`.",
    },
    "xoso": {
        "name": "Xổ Số",
        "emoji": "🎟️",
        "short": "Mua vé số, chờ xổ cuối ngày trúng thưởng.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!xoso mua <số_lượng>",
        "examples": ["y!xoso mua 5", "y!xoso mua 1"],
        "note": "Kết quả xổ lúc cuối ngày. Xem vé: `y!xoso xem`. Bán lại: `y!xoso ban <số>`.",
    },
    "multidice": {
        "name": "Multi Dice (PvP)",
        "emoji": "🎲",
        "short": "Xúc Xắc PvP nhiều người. Điểm cao nhất ăn cả nồi.",
        "aliases": ["md"],
        "cooldown": None,
        "usage": "y!md <tiền_cược> [@user1 @user2...]",
        "examples": ["y!md 100k @Bạn_A @Bạn_B"],
        "note": "Có thể mời tối đa nhiều người. Tự động chia thưởng khi kết thúc.",
    },
    # ── KINH TẾ ───────────────────────────────────────────────────────────────
    "daily": {
        "name": "Điểm Danh",
        "emoji": "🎁",
        "short": "Nhận thưởng 500 điểm mỗi ngày. Chuỗi càng dài, thưởng càng lớn.",
        "aliases": ["diemdanh"],
        "cooldown": "24h",
        "usage": "y!daily",
        "examples": ["y!daily"],
        "note": "Thưởng chuỗi (streak) cộng thêm tối đa 500 điểm/ngày.",
    },
    "weekly": {
        "name": "Lương Tuần",
        "emoji": "💎",
        "short": "Nhận lương 5,000 điểm mỗi tuần (7 ngày/lần).",
        "aliases": ["luongtuan"],
        "cooldown": "7 ngày",
        "usage": "y!weekly",
        "examples": ["y!weekly"],
        "note": None,
    },
    "point": {
        "name": "Xem Điểm",
        "emoji": "📊",
        "short": "Kiểm tra số dư điểm và thông tin sự kiện của bạn (hoặc người khác).",
        "aliases": ["diem", "balance", "ep"],
        "cooldown": None,
        "usage": "y!point [@user]",
        "examples": ["y!point", "y!point @BanBe"],
        "note": None,
    },
    "etop": {
        "name": "Bảng Xếp Hạng",
        "emoji": "🏆",
        "short": "Xem Top 10 người chơi có nhiều điểm tích lũy nhất server.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!etop",
        "examples": ["y!etop"],
        "note": None,
    },
    "milestone": {
        "name": "Cột Mốc",
        "emoji": "🎯",
        "short": "Xem các cột mốc phần thưởng và tiến độ đạt mốc hiện tại.",
        "aliases": ["moc"],
        "cooldown": None,
        "usage": "y!milestone",
        "examples": ["y!milestone"],
        "note": "Đạt mốc rồi dùng `y!claim` để nhận thưởng.",
    },
    "shop": {
        "name": "Cửa Hàng",
        "emoji": "🛒",
        "short": "Xem các vật phẩm có thể mua bằng điểm sự kiện.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!shop [danh_muc]",
        "examples": ["y!shop", "y!shop hat", "y!shop nongtrai"],
        "note": "Mua vật phẩm bằng lệnh `y!buy <ID> [số_lượng>`.",
    },
    "black_market": {
        "name": "Chợ Đen",
        "emoji": "🖤",
        "short": "Shop bí ẩn thay đổi hàng ngày. Hàng độc, hiếm và... bất thường.",
        "aliases": ["choden", "bm"],
        "cooldown": None,
        "usage": "y!choden",
        "examples": ["y!choden"],
        "note": "Hàng reset mỗi 00:00 UTC+7. Mua bằng điểm, tồn kho có hạn.",
    },
    "vayno": {
        "name": "Vay Nợ",
        "emoji": "🏦",
        "short": "Vay tiền từ ngân hàng dựa trên 50% điểm tích lũy của bạn.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!vayno <số_tiền>",
        "examples": ["y!vayno 100k"],
        "note": "Lãi suất 1%/ngày. Trả nợ bằng `y!trano`. Vỡ nợ sẽ bị khóa tài khoản!",
    },
    # ── KHU SINH THÁI ─────────────────────────────────────────────────────────
    "farm": {
        "name": "Nông Trại",
        "emoji": "🌻",
        "short": "Mở giao diện Nông Trại. Trồng, chăm sóc và thu hoạch mùa vụ.",
        "aliases": ["nongtrai"],
        "cooldown": None,
        "usage": "y!farm",
        "examples": ["y!farm"],
        "note": "Mua hạt giống bằng `y!shop nongtrai`. Upgrade ô đất: `y!upgrade`.",
    },
    "mine": {
        "name": "Đào Mỏ",
        "emoji": "⛏️",
        "short": "Tiến vào hang động đào quặng. Tốn 4 Thể Lực mỗi lần đào.",
        "aliases": [],
        "cooldown": "Thể lực hồi 1đ/18s",
        "usage": "y!mine",
        "examples": ["y!mine"],
        "note": "Thể lực tối đa 100. Hồi đầy sau ~30 phút. Bán quặng: `y!inv ban`.",
    },
    "fish": {
        "name": "Câu Cá",
        "emoji": "🎣",
        "short": "Thả cần đợi cá cắn. Cá hiếm bán được nhiều điểm hơn.",
        "aliases": ["cauCA"],
        "cooldown": "Phụ thuộc cần câu",
        "usage": "y!fish",
        "examples": ["y!fish"],
        "note": "Nâng cấp cần câu để tăng tỉ lệ cá hiếm và giảm thời gian chờ.",
    },
    "inventory": {
        "name": "Kho Đồ",
        "emoji": "🎒",
        "short": "Xem vật phẩm trong kho, bán nông sản/quặng/cá lấy điểm.",
        "aliases": ["inv", "kho"],
        "cooldown": None,
        "usage": "y!inv [ban]",
        "examples": ["y!inv", "y!inv ban"],
        "note": "Dùng `y!inv ban` để bán toàn bộ hàng hóa lấy điểm.",
    },
}

CATEGORY_DATA: dict[str, dict] = {
    "Casino & Giải Trí": {
        "emoji": "🎰",
        "desc": "Các minigame cờ bạc và thử vận may.",
        "commands": ["coinflip", "cups", "dice", "roulette", "crash", "wheel", "slots", "taixiu", "baucua", "betvit", "xoso", "multidice"],
        "cogs": ["BasicGames", "CrashGame", "DuckRace", "Lottery", "MultiDice", "VietnamGames", "WheelSlots"],
    },
    "Kinh Tế & Cửa Hàng": {
        "emoji": "🛒",
        "desc": "Quản lý điểm, cửa hàng, cột mốc và ngân hàng.",
        "commands": ["daily", "weekly", "point", "etop", "milestone", "shop", "black_market", "vayno"],
        "cogs": ["EventShopCog", "Rewards", "MilestoneCog", "BlackMarketCog", "BankingCog"],
    },
    "Khu Sinh Thái": {
        "emoji": "🏕️",
        "desc": "Trồng trọt, đào mỏ, câu cá và quản lý kho đồ.",
        "commands": ["farm", "mine", "fish", "inventory"],
        "cogs": ["IdleFarmCog", "Mining", "Fishing"],
    },
}

# =============================================================================
# BUILDERS — Hàm thuần túy xây dựng Embed (không có side effect)
# =============================================================================

def build_home_embed(bot: commands.Bot, author: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🌸 Cẩm Nang Sự Kiện — {author.display_name} ໒꒱",
        description=(
            "Chào mừng bạn đến với hệ thống sự kiện Angelic!\n\n"
            "Tham gia Casino để thử vận may, Khu Sinh Thái để cày an toàn, "
            "hoặc mua sắm tại Cửa Hàng để đổi phần quà.\n\n"
            "**📋 Chọn danh mục bên dưới để xem chi tiết:**"
        ),
        color=COLOR_THEME,
    )

    total_cmds = 0
    for cat_name, cat_info in CATEGORY_DATA.items():
        count = len(cat_info["commands"])
        total_cmds += count
        embed.add_field(
            name=f"{cat_info['emoji']} {cat_name}",
            value=f"{cat_info['desc']}\n*({count} lệnh)*",
            inline=False,
        )

    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Tổng {total_cmds} lệnh sự kiện  •  Chọn danh mục từ menu bên dưới")
    return embed


def build_category_embed(cat_name: str) -> discord.Embed:
    cat = CATEGORY_DATA.get(cat_name)
    if not cat:
        return discord.Embed(title="❌ Không tìm thấy danh mục", color=discord.Color.red())

    embed = discord.Embed(
        title=f"{cat['emoji']} {cat_name}",
        description=f"{cat['desc']}\n\n**Chọn lệnh từ menu bên dưới để xem chi tiết:**",
        color=COLOR_THEME,
    )
    for key in cat["commands"]:
        cmd = CMD_DATA.get(key)
        if cmd:
            aliases = f" · `{'`, `'.join(f'y!{a}' for a in cmd['aliases'])}`" if cmd["aliases"] else ""
            embed.add_field(
                name=f"{cmd['emoji']} `y!{key}`{aliases}",
                value=cmd["short"],
                inline=False,
            )
    embed.set_footer(text="Nhấn ◀ Quay Lại để về trang chủ")
    return embed


def build_detail_embed(cmd_key: str) -> discord.Embed:
    cmd = CMD_DATA.get(cmd_key)
    if not cmd:
        return discord.Embed(title="❌ Không tìm thấy lệnh", color=discord.Color.red())

    embed = discord.Embed(
        title=f"{cmd['emoji']} {cmd['name']}",
        description=cmd["short"],
        color=COLOR_THEME,
    )

    if cmd.get("aliases"):
        embed.add_field(
            name="📛 Lệnh rút gọn",
            value=" · ".join(f"`y!{a}`" for a in cmd["aliases"]),
            inline=True,
        )
    if cmd.get("cooldown"):
        embed.add_field(name="⏱️ Cooldown", value=cmd["cooldown"], inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="📝 Cú pháp", value=f"`{cmd['usage']}`", inline=False)

    if cmd.get("examples"):
        embed.add_field(
            name="💡 Ví dụ",
            value="\n".join(f"`{e}`" for e in cmd["examples"]),
            inline=False,
        )
    if cmd.get("note"):
        embed.add_field(name="ℹ️ Ghi chú", value=cmd["note"], inline=False)

    embed.set_footer(text="Nhấn ◀ Quay Lại để về danh sách lệnh")
    return embed


# =============================================================================
# VIEWS — 3 Tầng UI tương tác
# =============================================================================

class HomeView(discord.ui.View):
    """Tầng 1: Trang chủ với Dropdown chọn danh mục."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.message: Optional[discord.Message] = None
        self.add_item(_CategorySelect(bot, author))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _CategorySelect(discord.ui.Select):
    """Dropdown chọn danh mục trong tầng 1."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        self.bot = bot
        self.author = author
        options = [
            discord.SelectOption(
                label=cat_name,
                value=cat_name,
                emoji=cat_info["emoji"],
                description=cat_info["desc"][:50],
            )
            for cat_name, cat_info in CATEGORY_DATA.items()
        ]
        super().__init__(placeholder="🔍 Chọn danh mục lệnh...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        cat_name = self.values[0]
        embed = build_category_embed(cat_name)
        view = CategoryView(self.bot, self.author, cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class CategoryView(discord.ui.View):
    """Tầng 2: Danh sách lệnh trong danh mục."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.cat_name = cat_name
        self.message: Optional[discord.Message] = None

        self.add_item(_CommandSelect(bot, author, cat_name))
        self.add_item(_HomeButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _CommandSelect(discord.ui.Select):
    """Dropdown chọn lệnh cụ thể trong tầng 2."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        self.bot = bot
        self.author = author
        self.cat_name = cat_name

        cat = CATEGORY_DATA.get(cat_name, {})
        options = []
        for key in cat.get("commands", []):
            cmd = CMD_DATA.get(key)
            if cmd:
                label = f"{cmd['emoji']} {cmd['name']}"
                options.append(discord.SelectOption(
                    label=label[:25],
                    value=key,
                    description=cmd["short"][:50],
                ))

        super().__init__(
            placeholder="📖 Chọn lệnh để xem chi tiết...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cmd_key = self.values[0]
        embed = build_detail_embed(cmd_key)
        view = DetailView(self.bot, self.author, self.cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class _HomeButton(discord.ui.Button):
    """Nút quay về trang chủ."""

    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: CategoryView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class DetailView(discord.ui.View):
    """Tầng 3: Chi tiết lệnh."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.cat_name = cat_name
        self.message: Optional[discord.Message] = None

        self.add_item(_BackButton())
        self.add_item(_HomeButton2())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _BackButton(discord.ui.Button):
    """Nút quay lại danh mục."""

    def __init__(self):
        super().__init__(label="◀ Quay Lại", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_category_embed(view.cat_name)
        new_view = CategoryView(view.bot, view.author, view.cat_name)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class _HomeButton2(discord.ui.Button):
    """Nút về trang chủ từ tầng 3."""

    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


# =============================================================================
# COG — Lệnh y!ehelp
# =============================================================================

class EventHelpCog(commands.Cog):
    """🌸 Cẩm nang hướng dẫn sự kiện với UI 3 tầng."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ehelp",
        description="Xem danh sách toàn bộ các lệnh sự kiện (UI 3 tầng).",
    )
    async def ehelp_cmd(self, ctx: commands.Context):
        """🌸 Cẩm nang sự kiện với UI tương tác 3 tầng."""
        embed = build_home_embed(self.bot, ctx.author)
        view = HomeView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHelpCog(bot))
