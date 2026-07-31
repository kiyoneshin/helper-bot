import discord
from discord.ext import commands
from typing import Dict, Any, List

COLOR_THEME = 0x2b2d31

# Định nghĩa map các danh mục và Cog tương ứng cho y!help
HELP_CATEGORY_MAP = {
    "Quản Trị & Staff": {
        "emoji": "⚙️",
        "desc": "Các lệnh quản lý bot và máy chủ dành cho Staff/Admin.",
        "cogs": ["StaffUICog", "StaffTestCog", "StaffMsgTrackerCog", "StaffListenerCog", "StaffLeaderboardCog", "StaffEditCog", "StaffBackupCog", "StaffAddCog", "JailSystem"]
    },
    "Khác": {
        "emoji": "🛡️",
        "desc": "Các lệnh thông dụng và hệ thống khác.",
        "cogs": ["WelcomeCog", "TrapChannelCog"]
    }
}

def build_help_home(bot: commands.Bot, author: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🛡️ Trung Tâm Hỗ Trợ Của {author.display_name}",
        description=(
            "Chào mừng bạn đến với hệ thống lệnh hỗ trợ chung!\n\n"
            "Tại đây chứa các lệnh quản trị, điều hành, và tiện ích hệ thống.\n\n"
            "**Dưới đây là các danh mục lệnh hiện có:**"
        ),
        color=COLOR_THEME
    )
    
    total_cmds = 0
    for cat_name, cat_info in HELP_CATEGORY_MAP.items():
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
    embed.set_footer(text=f"Sử dụng Menu thả xuống bên dưới để khám phá • Tổng {total_cmds} lệnh")
    return embed

def build_help_category(bot: commands.Bot, category_name: str) -> discord.Embed:
    cat_info = HELP_CATEGORY_MAP.get(category_name)
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
                desc = cmd.help or cmd.description or "Không có mô tả chi tiết."
                embed.add_field(
                    name=f"y!{cmd.name}{aliases_str}",
                    value=desc,
                    inline=False
                )

    return embed

class HelpSelect(discord.ui.Select):
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
        
        for cat_name, cat_info in HELP_CATEGORY_MAP.items():
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
            placeholder="🔍 Chọn danh mục lệnh chung...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        if selected == "home":
            embed = build_help_home(self.bot, self.author)
        else:
            embed = build_help_category(self.bot, selected)

        for opt in self.options:
            opt.default = (opt.value == selected)

        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.author = author
        self.select_menu = HelpSelect(bot, author)
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


class HelpCog(commands.Cog):
    """Cog Hỗ trợ hướng dẫn lệnh chung."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if self.bot.get_command("help"):
            self.bot.remove_command("help")

    @commands.hybrid_command(
        name="help",
        aliases=["menu", "trogiup"],
        description="Xem danh sách toàn bộ các lệnh (UI Dropdown)"
    )
    async def help_cmd(self, ctx: commands.Context):
        """Lệnh hỗ trợ xem nhanh các lệnh chung và hệ thống."""
        embed = build_help_home(self.bot, ctx.author)
        view = HelpView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
