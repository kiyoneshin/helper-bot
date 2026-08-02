import discord
from discord.ext import commands
from typing import Dict, Any, List

COLOR_THEME = 0xffb6c1

# Định nghĩa map các danh mục và Cog tương ứng
EHELP_CATEGORY_MAP = {
    "Casino & Giải Trí": {
        "emoji": "🎰",
        "desc": "Các minigame cờ bạc và thử vận may.",
        "cogs": ["BasicGames", "CrashGame", "DuckRace", "Lottery", "MultiDice", "VietnamGames", "WheelSlots"]
    },
    "Kinh Tế & Cửa Hàng": {
        "emoji": "🛒",
        "desc": "Quản lý tiền tệ sự kiện, cửa hàng, giao dịch.",
        "cogs": ["EventShopCog", "Rewards", "MilestoneCog", "BlackMarketCog"]
    },
    "Khu Sinh Thái": {
        "emoji": "🏕️",
        "desc": "Tham gia trồng trọt, câu cá, đào mỏ.",
        "cogs": ["IdleFarmCog", "Mining", "Fishing"]
    }
}

CUSTOM_CMD_DESC = {
    "coinflip": "Tung đồng xu (h = Ngửa / t = Sấp). Thắng x1.9, đứng xu nhận Jackpot x5.0.\nCú pháp: `y!cf <h/t> <tiền_cược>`",
    "cups": "Đoán ly chứa bảo vật trong 3 ly. Chọn đúng nhận x2.3.\nCú pháp: `y!cups <tiền_cược>`",
    "dice": "Lắc xúc xắc đặc biệt. Mặt 4,5,6 thắng (x1.25 đến x2.0), mặt 7 nổ Hũ (x8).\nCú pháp: `y!dice <tiền_cược>`",
    "roulette": "Cò quay tử thần (1 đạn, 5 lép). Sống sót nhận thưởng tăng dần (tối đa x5.0).\nCú pháp: `y!shot <tiền_cược>`",
    "crash": "Tàu bay Crash, nhảy dù trước khi tàu nổ để ăn hệ số nhân (x1.1 đến x99).\nCú pháp: `y!crash <tiền_cược>`",
    "betvit": "Đua vịt sự kiện. Các màu: do, xanh, vang, hong, yon.\nCú pháp: `y!betvit <màu> <tiền>`",
    "huybet": "Hủy cược vịt hiện tại và nhận lại 100% tiền.\nCú pháp: `y!huybet`",
    "xemvit": "Xem tổng số tiền cược và ước tính tỷ lệ thưởng của các chú vịt.\nCú pháp: `y!xemvit`",
    "xoso": "Xổ Số Kiến Thiết! Mua vé số để chờ kết quả xổ cuối ngày.\nCú pháp: `y!xoso mua <số_lượng>`",
    "multidice": "Xúc Xắc PvP. Mời nhiều người cùng lắc xúc xắc, tự động chia thưởng cho người cao điểm.\nCú pháp: `y!md <tiền_cược> [@user1...]`",
    "taixiu": "Lắc 3 viên xúc xắc. (Tài 11-17, Xỉu 4-10). Thắng ăn x1.95. Bão (3 viên giống) nhà cái lụm.\nCú pháp: `y!tx <tai/xiu> <tiền_cược>`",
    "baucua": "Sảnh Bầu Cua Tôm Cá chung. Gõ tên linh vật xuống chat để đặt cược.\nCú pháp: Gõ `y!bc` để mở sảnh.",
    "wheel": "Vòng quay 16 ô. Trúng ô Tím x9.0, Xanh lá x1.8. Thua ở ô Vàng được +1 Vé Xổ Số.\nCú pháp: `y!wheel <tiền_cược>`",
    "slots": "Quay Máy Xẻng. Cơ hội trúng Nổ hũ siêu to nếu quay ra 5 biểu tượng giống nhau.\nCú pháp: `y!slots <tiền_cược>`"
}

def build_ehelp_home(bot: commands.Bot, author: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🌸 Cẩm Nang Sự Kiện Của {author.display_name} ໒꒱",
        description=(
            "Chào mừng bạn đến với hệ thống sự kiện và giải trí của Angelic!\n\n"
            "Tại đây, bạn có thể tham gia các minigame để kiếm điểm, thử vận may tại Casino, "
            "hoặc tích lũy điểm để đổi phần quà hấp dẫn.\n\n"
            "**Dưới đây là các danh mục lệnh hiện có:**"
        ),
        color=COLOR_THEME
    )
    
    total_cmds = 0
    for cat_name, cat_info in EHELP_CATEGORY_MAP.items():
        cmds_count = 0
        for cog_name in cat_info["cogs"]:
            cog = bot.get_cog(cog_name)
            if cog:
                cmds_count += len([c for c in cog.get_commands() if not c.hidden])
                
        total_cmds += cmds_count
        if cmds_count > 0:
            embed.add_field(
                name=f"{cat_info['emoji']} {cat_name}",
                value=f"{cat_info['desc']} *(Gồm {cmds_count} lệnh)*",
                inline=False
            )

    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
    embed.set_footer(text=f"Sử dụng Menu thả xuống bên dưới để khám phá • Tổng {total_cmds} lệnh sự kiện")
    return embed

def build_ehelp_category(bot: commands.Bot, category_name: str) -> discord.Embed:
    cat_info = EHELP_CATEGORY_MAP.get(category_name)
    if not cat_info:
        return discord.Embed(title="❌ Không tìm thấy danh mục", color=discord.Color.red())

    embed = discord.Embed(
        title=f"{cat_info['emoji']} {category_name}",
        description=cat_info['desc'],
        color=COLOR_THEME
    )

    for cog_name in cat_info["cogs"]:
        cog = bot.get_cog(cog_name)
        if cog:
            for cmd in cog.get_commands():
                if cmd.hidden:
                    continue
                
                aliases_str = f" (hoặc {', '.join(cmd.aliases)})" if cmd.aliases else ""
                desc = CUSTOM_CMD_DESC.get(cmd.name, cmd.help or cmd.description or "Không có mô tả chi tiết.")
                embed.add_field(
                    name=f"y!{cmd.name}{aliases_str}",
                    value=desc,
                    inline=False
                )

    return embed

class EHelpSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        self.bot = bot
        self.author = author
        
        options = [
            discord.SelectOption(
                label="Trang Chủ",
                value="home",
                emoji="🏠",
                description="Quay về trang chào mừng"
            )
        ]
        
        for cat_name, cat_info in EHELP_CATEGORY_MAP.items():
            has_commands = False
            for cog_name in cat_info["cogs"]:
                cog = bot.get_cog(cog_name)
                if cog and any(not c.hidden for c in cog.get_commands()):
                    has_commands = True
                    break
            
            if has_commands:
                options.append(discord.SelectOption(
                    label=cat_name,
                    value=cat_name,
                    emoji=cat_info["emoji"],
                    description=cat_info["desc"][:50]
                ))

        super().__init__(
            placeholder="🔍 Chọn danh mục bạn muốn xem...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        if selected == "home":
            embed = build_ehelp_home(self.bot, self.author)
        else:
            embed = build_ehelp_category(self.bot, selected)

        for opt in self.options:
            opt.default = (opt.value == selected)

        await interaction.response.edit_message(embed=embed, view=self.view)

class EHelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.author = author
        self.select_menu = EHelpSelect(bot, author)
        self.add_item(self.select_menu)
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Bạn không phải người gọi lệnh này!",
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
        embed = build_ehelp_home(self.bot, ctx.author)
        view = EHelpView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHelpCog(bot))
