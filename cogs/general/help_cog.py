"""
help_cog.py — Hệ Thống Trợ Giúp Chung 3 Tầng (y!help)
=======================================================
Tầng 1 - Home     : Danh sách danh mục (Dropdown → Tầng 2)
Tầng 2 - Category : Danh sách lệnh (Dropdown → Tầng 3 | Button 🏠 → Tầng 1)
Tầng 3 - Detail   : Chi tiết lệnh (Button ◀ → Tầng 2 | Button 🏠 → Tầng 1)
"""

from __future__ import annotations

import discord
from discord.ext import commands
from typing import Optional

COLOR_THEME = 0x2B2D31

# =============================================================================
# DỮ LIỆU TRUNG TÂM — Thêm/sửa lệnh chỉ cần chỉnh ở đây
# =============================================================================

CMD_DATA: dict[str, dict] = {
    # ── MODERATION ────────────────────────────────────────────────────────────
    "menu": {
        "name": "Hồ Sơ Nhân Sự",
        "emoji": "📋",
        "short": "Mở Menu tương tác để quản lý hồ sơ nhân sự (BQT).",
        "aliases": ["staff", "bqt"],
        "cooldown": None,
        "usage": "y!menu",
        "examples": ["y!menu"],
        "note": "Bạn cần chọn đúng category tương ứng trong Menu.",
    },
    "phattu": {
        "name": "Phạt Tù",
        "emoji": "⛓️",
        "short": "Tống một thành viên vào Chuồng Chó (Jail). Chỉ Admin/Owner.",
        "aliases": ["jail", "giam"],
        "cooldown": None,
        "usage": "y!phattu <@user> <số_lần_dọn> [lý do]",
        "examples": ["y!phattu @User 10 Spam"],
        "note": "Tù nhân phải lau dọn đủ số lần mới được thả.",
    },
    "thatu": {
        "name": "Thả Tù",
        "emoji": "🔓",
        "short": "Thả sớm một thành viên khỏi Chuồng Chó. Chỉ Admin/Owner.",
        "aliases": ["unjail", "free"],
        "cooldown": None,
        "usage": "y!thatu <@user>",
        "examples": ["y!thatu @User"],
        "note": None,
    },
    "laudon": {
        "name": "Lau Dọn",
        "emoji": "🧹",
        "short": "Tù nhân lau dọn để giảm số lần án phạt còn lại.",
        "aliases": ["clean", "cosua"],
        "cooldown": "5s",
        "usage": "y!laudon",
        "examples": ["y!laudon"],
        "note": "Mỗi lần giảm 1 án. Chỉ dùng được trong Chuồng Chó.",
    },
    "baolanh": {
        "name": "Bảo Lãnh",
        "emoji": "💸",
        "short": "Trả tiền bảo lãnh để chuộc một tù nhân về.",
        "aliases": ["bail", "bl"],
        "cooldown": None,
        "usage": "y!baolanh <@user>",
        "examples": ["y!baolanh @BanBe"],
        "note": "Chi phí tùy thuộc vào số lần phạt còn lại.",
    },
    "sua": {
        "name": "Giải Toán",
        "emoji": "🧮",
        "short": "Tù nhân giải toán nhanh để giảm 2 án. CD 15s.",
        "aliases": ["giaibai", "toan"],
        "cooldown": "15s",
        "usage": "y!sua",
        "examples": ["y!sua"],
        "note": "Phép toán có cộng/trừ/nhân/chia và ngoặc.",
    },
    "nhatxuong": {
        "name": "Nhặt Xương",
        "emoji": "🦴",
        "short": "70% giảm 5 án, 30% bị cắn ngược tăng 1 án. CD 30s.",
        "aliases": ["nxt", "xuong"],
        "cooldown": "30s",
        "usage": "y!nhatxuong",
        "examples": ["y!nhatxuong"],
        "note": None,
    },
    "lcuoc": {
        "name": "Lật Cược",
        "emoji": "🎲",
        "short": "Tung đồng xu: 50% giảm 5 án / 50% tăng 10 án. CD 20s.",
        "aliases": ["lc", "jailflip"],
        "cooldown": "20s",
        "usage": "y!lcuoc",
        "examples": ["y!lcuoc"],
        "note": "Liều cao, thưởng lớn, phạt cũng lớn!",
    },
    "lvuotnguc": {
        "name": "Lệnh Vượt Ngục",
        "emoji": "🏃",
        "short": "5% thoát hoàn toàn, 95% bị bắt lại và nhân 3 án. CD 5 phút.",
        "aliases": ["lvn", "break"],
        "cooldown": "5 phút",
        "usage": "y!lvuotnguc",
        "examples": ["y!lvuotnguc"],
        "note": "Nếu thất bại sẽ bị công khai bêu rếu ở kênh chung. Liều thì liều!",
    },
    # ── TIỆN ÍCH ──────────────────────────────────────────────────────────────
    "ehelp": {
        "name": "Cẩm Nang Sự Kiện",
        "emoji": "🌸",
        "short": "Xem hướng dẫn toàn bộ các lệnh sự kiện với UI tương tác.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!ehelp [tên_lệnh]",
        "examples": ["y!ehelp", "`y!ehelp crash`"],
        "note": None,
    },
    "help": {
        "name": "Trợ Giúp",
        "emoji": "🛡️",
        "short": "Xem danh sách lệnh quản trị và hệ thống (đang xem đây nè).",
        "aliases": ["trogiup"],
        "cooldown": None,
        "usage": "y!help [tên_lệnh]",
        "examples": ["y!help", "y!help phattu"],
        "note": None,
    },
    # ── GIVEAWAY ──────────────────────────────────────────────────────────────
    "ga": {
        "name": "Tạo Giveaway",
        "emoji": "🎉",
        "short": "Tạo Giveaway thường bằng menu tương tác.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!ga",
        "examples": ["y!ga"],
        "note": "Hệ thống sẽ gửi menu cấu hình thời gian, giải thưởng, v.v.",
    },
    "fga": {
        "name": "Tạo Flash Giveaway",
        "emoji": "⚡",
        "short": "Tạo Flash Giveaway chia thành nhiều đợt nhỏ liên tục.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!fga",
        "examples": ["y!fga"],
        "note": "Giống y!ga nhưng có thêm chức năng batch.",
    },
    "gaban": {
        "name": "Cấm Giveaway",
        "emoji": "🚫",
        "short": "Cấm một người chơi tham gia mọi Giveaway của bot.",
        "aliases": ["gablacklist"],
        "cooldown": None,
        "usage": "y!gaban <@user> [lý do]",
        "examples": ["y!gaban @User Gian lận"],
        "note": "Chỉ Admin mới có thể dùng lệnh này.",
    },
    "gaunban": {
        "name": "Mở Cấm Giveaway",
        "emoji": "✅",
        "short": "Gỡ cấm tham gia Giveaway cho người chơi.",
        "aliases": ["gaunblacklist"],
        "cooldown": None,
        "usage": "y!gaunban <@user>",
        "examples": ["y!gaunban @User"],
        "note": "Chỉ Admin mới có thể dùng lệnh này.",
    },
    "gabanlist": {
        "name": "Danh Sách Cấm",
        "emoji": "📜",
        "short": "Xem danh sách những người đang bị cấm tham gia Giveaway.",
        "aliases": ["gabannedlist"],
        "cooldown": None,
        "usage": "y!gabanlist",
        "examples": ["y!gabanlist"],
        "note": None,
    },
    "gareroll": {
        "name": "Quay Lại Giveaway",
        "emoji": "🔄",
        "short": "Quay lại ngẫu nhiên để chọn người thắng mới.",
        "aliases": ["garr"],
        "cooldown": None,
        "usage": "y!gareroll <link_tin_nhắn_ga> [số_người]",
        "examples": ["y!gareroll https://discord.com/channels/... 1"],
        "note": "Lệnh này dành cho Admin/Host quay bù người thắng.",
    },
    "feedback": {
        "name": "Xem Đánh Giá",
        "emoji": "📝",
        "short": "Xem danh sách toàn bộ bài đánh giá của một nhân sự.",
        "aliases": ["fb"],
        "cooldown": None,
        "usage": "y!fb <@user | id>",
        "examples": ["y!fb @User"],
        "note": "Dành cho việc theo dõi hiệu suất của nhân sự.",
    },
    "add": {
        "name": "Thêm Hồ Sơ",
        "emoji": "📝",
        "short": "Tạo hồ sơ cá nhân mới cho Staff.",
        "aliases": ["register", "dangky", "themhoso"],
        "cooldown": None,
        "usage": "y!add",
        "examples": ["y!add"],
        "note": "Bạn cần có ID Staff hợp lệ.",
    },
    "set": {
        "name": "Sửa Hồ Sơ",
        "emoji": "✏️",
        "short": "Chỉnh sửa hồ sơ cá nhân của Staff.",
        "aliases": ["editprofile", "suahoso"],
        "cooldown": None,
        "usage": "y!set",
        "examples": ["y!set"],
        "note": "Chỉ được sửa hồ sơ của chính mình.",
    },
    "rule": {
        "name": "Điều Lệ",
        "emoji": "📜",
        "short": "Xem bảng điều lệ server Angelic.",
        "aliases": ["rules", "luat", "dieule"],
        "cooldown": None,
        "usage": "y!rule",
        "examples": ["y!rule"],
        "note": None,
    },
    "checkdb": {
        "name": "Kiểm Tra Database",
        "emoji": "🔍",
        "short": "Kiểm tra toàn bộ danh sách đang có trong Database.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!checkdb",
        "examples": ["y!checkdb"],
        "note": "Chỉ dành cho Quản lý.",
    },
    "renewdb": {
        "name": "Đồng Bộ DB",
        "emoji": "🔄",
        "short": "Đồng bộ và làm sạch Database với Server Discord thực tế.",
        "aliases": ["syncdb", "refreshdb"],
        "cooldown": None,
        "usage": "y!renewdb",
        "examples": ["y!renewdb"],
        "note": "Chỉ dành cho Admin/Owner.",
    },
    "myreviews": {
        "name": "Lịch Sử Đánh Giá",
        "emoji": "📊",
        "short": "Xem lịch sử đánh giá staff của bạn.",
        "aliases": ["myfeedbacks", "myfb", "myrv"],
        "cooldown": None,
        "usage": "y!myreviews",
        "examples": ["y!myreviews"],
        "note": None,
    },
    "top": {
        "name": "Bảng Xếp Hạng",
        "emoji": "🏆",
        "short": "Xem bảng xếp hạng nhân sự.",
        "aliases": ["lb", "bxh", "leaderboard"],
        "cooldown": None,
        "usage": "y!top",
        "examples": ["y!top"],
        "note": "Top điểm, lượt đánh giá và số dư.",
    },
    "backup": {
        "name": "Sao Lưu DB",
        "emoji": "💾",
        "short": "Kích hoạt backup database thủ công ngay lập tức.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!backup",
        "examples": ["y!backup"],
        "note": "Chỉ dành cho Admin/Owner.",
    },
    "synclv": {
        "name": "Đồng Bộ Level",
        "emoji": "📈",
        "short": "Quét lịch sử và đồng bộ Level từ Arcane.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!synclv",
        "examples": ["y!synclv"],
        "note": "Dành cho Admin.",
    },
    "test_welcome": {
        "name": "Test Welcome",
        "emoji": "👋",
        "short": "Kiểm tra giao diện chào mừng thành viên mới.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!test_welcome [@user]",
        "examples": ["y!test_welcome", "y!test_welcome @User"],
        "note": "Dành cho Admin.",
    },
}

CATEGORY_DATA: dict[str, dict] = {
    "Quản Trị Nhân Sự": {
        "emoji": "📋",
        "desc": "Quản lý nhân sự và hồ sơ thành viên BQT.",
        "commands": ["menu", "add", "set", "rule", "top", "feedback", "myreviews"],
        "cogs": ["StaffUI", "Leaderboard", "EditProfile", "AddProfile"],
    },
    "Quản Trị Hệ Thống": {
        "emoji": "⚙️",
        "desc": "Công cụ đồng bộ, backup và kiểm tra hệ thống.",
        "commands": ["checkdb", "renewdb", "backup", "synclv", "test_welcome"],
        "cogs": ["StaffUI", "BackupCog", "ArcaneLevel", "WelcomeCog"],
    },
    "Chuồng Chó (Jail)": {
        "emoji": "🐕",
        "desc": "Hệ thống tù tội và cải tạo dành cho các thành viên lỡ dại.",
        "commands": ["phattu", "thatu", "laudon", "baolanh", "sua", "nhatxuong", "lcuoc", "lvuotnguc"],
        "cogs": ["JailCore", "JailTasks", "JailGames", "JailInteraction"],
    },
    "Tiện Ích": {
        "emoji": "🛡️",
        "desc": "Các lệnh thông dụng, hỗ trợ và hướng dẫn.",
        "commands": ["ehelp", "help"],
        "cogs": ["EventHelpCog", "HelpCog"],
    },
    "Giveaway": {
        "emoji": "🎉",
        "desc": "Quản lý và tạo hệ thống phát quà Giveaway.",
        "commands": ["ga", "fga", "gaban", "gaunban", "gabanlist", "gareroll"],
        "cogs": ["GiveawayCog"],
    },
}


# =============================================================================
# BUILDERS
# =============================================================================

def build_home_embed(bot: commands.Bot, author: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🛡️ Trung Tâm Hỗ Trợ — {author.display_name}",
        description=(
            "Chào mừng! Đây là bảng điều khiển lệnh quản trị và hệ thống.\n\n"
            "Để xem lệnh **sự kiện**, hãy dùng `y!ehelp`.\n\n"
            "**📋 Chọn danh mục bên dưới để xem chi tiết:**"
        ),
        color=COLOR_THEME,
    )
    for cat_name, cat_info in CATEGORY_DATA.items():
        count = len(cat_info["commands"])
        embed.add_field(
            name=f"{cat_info['emoji']} {cat_name}",
            value=f"{cat_info['desc']}\n*({count} lệnh)*",
            inline=False,
        )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    total = sum(len(c["commands"]) for c in CATEGORY_DATA.values())
    embed.set_footer(text=f"Tổng {total} lệnh  •  Chọn danh mục từ menu bên dưới")
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
            aliases_list = cmd.get("aliases", [])
            if len(aliases_list) > 3:
                aliases_str = f" · `{'`, `'.join(f'{ctx.prefix}{a}' for a in aliases_list[:3])}` (+{len(aliases_list)-3})"
            elif aliases_list:
                aliases_str = f" · `{'`, `'.join(f'{ctx.prefix}{a}' for a in aliases_list)}`"
            else:
                aliases_str = ""
            embed.add_field(
                name=f"{cmd['emoji']} `{ctx.prefix}{key}`{aliases_str}",
                value=cmd["short"],
                inline=False,
            )
    embed.set_footer(text="Nhấn 🏠 Trang Chủ để quay về")
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
        embed.add_field(name="📛 Lệnh rút gọn/Lệnh thay thế", value=" · ".join(f"`{ctx.prefix}{a}`" for a in cmd["aliases"]), inline=True)
    if cmd.get("cooldown"):
        embed.add_field(name="⏱️ Cooldown", value=cmd["cooldown"], inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="📝 Cú pháp", value=f"`{cmd['usage']}`", inline=False)
    if cmd.get("examples"):
        embed.add_field(name="💡 Ví dụ", value="\n".join(f"`{e}`" for e in cmd["examples"]), inline=False)
    if cmd.get("note"):
        embed.add_field(name="ℹ️ Ghi chú", value=cmd["note"], inline=False)
    embed.set_footer(text="Nhấn ◀ Quay Lại để về danh sách lệnh")
    return embed


# =============================================================================
# VIEWS — 3 Tầng
# =============================================================================

class HomeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.message: Optional[discord.Message] = None
        self.add_item(_CategorySelect(bot, author))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải trang trợ giúp của bạn!", ephemeral=True)
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
        super().__init__(placeholder="🔍 Chọn danh mục lệnh...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat_name = self.values[0]
        embed = build_category_embed(cat_name)
        view = CategoryView(self.bot, self.author, cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class CategoryView(discord.ui.View):
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
            await interaction.response.send_message("❌ Đây không phải trang trợ giúp của bạn!", ephemeral=True)
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
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        self.bot = bot
        self.author = author
        self.cat_name = cat_name
        cat = CATEGORY_DATA.get(cat_name, {})
        options = []
        for key in cat.get("commands", []):
            cmd = CMD_DATA.get(key)
            if cmd:
                options.append(discord.SelectOption(
                    label=f"{cmd['emoji']} {cmd['name']}"[:25],
                    value=key,
                    description=cmd["short"][:50],
                ))
        super().__init__(placeholder="📖 Chọn lệnh để xem chi tiết...", options=options)

    async def callback(self, interaction: discord.Interaction):
        embed = build_detail_embed(self.values[0])
        view = DetailView(self.bot, self.author, self.cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class _HomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: CategoryView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class DetailView(discord.ui.View):
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
            await interaction.response.send_message("❌ Đây không phải trang trợ giúp của bạn!", ephemeral=True)
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
    def __init__(self):
        super().__init__(label="◀ Quay Lại", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_category_embed(view.cat_name)
        new_view = CategoryView(view.bot, view.author, view.cat_name)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class _HomeButton2(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


# =============================================================================
# COG
# =============================================================================

class HelpCog(commands.Cog):
    """🛡️ Trợ giúp lệnh hệ thống với UI 3 tầng."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        aliases=["trogiup"],
        description="Xem danh sách toàn bộ lệnh hệ thống (UI 3 tầng).",
    )
    async def help_cmd(self, ctx: commands.Context, *, cmd_name: Optional[str] = None):
        """🛡️ Trợ giúp lệnh hệ thống với UI tương tác 3 tầng."""
        if cmd_name:
            cmd_key = None
            for k, v in CMD_DATA.items():
                if cmd_name.lower() == k or cmd_name.lower() in v.get("aliases", []):
                    cmd_key = k
                    break
            
            if cmd_key:
                target_cat = None
                for cat, data in CATEGORY_DATA.items():
                    if cmd_key in data.get("commands", []):
                        target_cat = cat
                        break
                
                if target_cat:
                    embed = build_detail_embed(cmd_key)
                    view = DetailView(self.bot, ctx.author, target_cat)
                    view.message = await ctx.send(embed=embed, view=view)
                    return
                    
        embed = build_home_embed(self.bot, ctx.author)
        view = HomeView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    bot.remove_command("help")
    await bot.add_cog(HelpCog(bot))
