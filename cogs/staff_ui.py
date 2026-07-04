import discord
from discord.ext import commands
import json
from typing import Optional, Any

def parse_json_field(field_data) -> Any:
    if isinstance(field_data, str):
        return json.loads(field_data)
    return field_data if field_data is not None else []

def get_main_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏠 Chào mừng đến với Angelic ໒꒱",
        description=(
            "Tiếng chuông nhà thờ khẽ ngân vang, cánh cổng thiên đường đã mở rộng chào đón bạn! ଘ(੭ˊᵕˋ)੭\n"
            "Hãy biến nơi đây thành mái nhà bình yên để cùng trò chuyện, chơi game, chữa lành và lưu giữ những kỷ niệm đẹp nhé.\n\n"
            "📜 **TÓM TẮT LUẬT SERVER (CẦN NHỚ KỸ):**\n"
            "**1. Văn hóa giao tiếp:** Tôn trọng tất cả mọi người, đùa giỡn có chừng mực. Nghiêm cấm gây war, drama hay mạo danh người khác.\n"
            "**2. Lằn ranh đỏ (BAN thẳng):** Tuyệt đối không Phân biệt vùng miền/chủng tộc, sài tool phá hoại (spam/nuke/raid), hoặc mua bán trái phép.\n"
            "**3. Nội dung nhạy cảm:** Hạn chế tối đa nói tục. Cấm gửi nội dung NSFW, máu me ở kênh chung (chỉ được gửi trong 🔞｜𝐓𝐎𝐗𝐈𝐂).\n"
            "**4. Giữ gìn trật tự:** Không spam (tin nhắn, ping, sticker, ticket). Cấm quảng cáo link ngoài khi chưa được phép.\n"
            "**5. Không gian chung:** Trò chuyện đúng chủ đề từng kênh, không phá room voice của người khác và tuân thủ lời nhắc của Staff.\n\n"
            "*Vui lòng chọn menu phía dưới để làm quen với danh sách Ban Quản Trị!*"
        ),
        color=0xffb6c1
    )
    return embed

def build_embed(profile: dict, member: Optional[discord.Member], page: int) -> discord.Embed:
    photos = profile.get("photos", [])
    tags = profile.get("tags", [])
    rating = float(profile.get("rating", 0))
    votes = profile.get("votes", {})
    name = profile.get("display_name") or (member.display_name if member else "Thành viên cũ")

    embed = discord.Embed(color=0x5865f2)
    avatar_url = member.display_avatar.url if member else None
    
    if avatar_url:
        embed.set_author(name=f"✦ {name}", icon_url=avatar_url)
        embed.set_thumbnail(url=avatar_url)
    else:
        embed.set_author(name=f"✦ {name}")

    if tags: 
        embed.description = "\n".join(f"✦ {t}" for t in tags)
    embed.add_field(name="⭐ Đánh giá", value=f"**{round(rating, 1)}**/5.0 (`{len(votes)} vote`)", inline=True)
    if profile.get('contact'):
        embed.add_field(name="📞 Liên hệ", value=profile['contact'], inline=True)

    if photos:
        idx = max(0, min(page, len(photos) - 1))
        embed.set_image(url=photos[idx])
        embed.set_footer(text=f"Ảnh {idx+1}/{len(photos)}")
    else:
        embed.set_footer(text="Chưa có ảnh")
    return embed

class MainDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Tổng quan Server", value="overview", emoji="🏠"),
            discord.SelectOption(label="Owner", value="owner", description="Chủ server", emoji="👑"),
            discord.SelectOption(label="Admin", value="admin", description="Quản trị viên", emoji="🛡️"),
            discord.SelectOption(label="Recep", value="recep", description="Lễ tân / Helper", emoji="💬")
        ]
        super().__init__(placeholder="Xem thông tin ban quản trị...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role_val = self.values[0]
        if role_val == "overview":
            await interaction.response.edit_message(embed=get_main_embed(), view=self.view)
            return
            
        bot: Any = interaction.client
        async with bot.db_pool.acquire() as conn:
            records = await conn.fetch("SELECT discord_id, display_name, description FROM profiles WHERE role = $1", role_val)
        
        if not records:
            await interaction.response.send_message("Chưa có ai ở vị trí này cả.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Danh sách {role_val.capitalize()}", description="Chọn một nhân sự phía dưới để xem chi tiết.", color=0x5865f2)
        await interaction.response.edit_message(embed=embed, view=RoleView(role_val, records))

class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainDropdown())

class StaffDropdown(discord.ui.Select):
    def __init__(self, role_val: str, records: list):
        self.role_val = role_val
        options = []
        for r in records:
            name = r['display_name'] or "Unknown"
            desc = (r['description'] or "")[:50] + "..." if r['description'] else "Click xem chi tiết"
            options.append(discord.SelectOption(label=name, value=r['discord_id'], description=desc, emoji="👤"))
        super().__init__(placeholder="Chọn người muốn xem...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        uid = self.values[0]
        bot: Any = interaction.client
        async with bot.db_pool.acquire() as conn:
            profile = await conn.fetchrow("SELECT * FROM profiles WHERE discord_id = $1", uid)
        
        if profile:
            member = interaction.guild.get_member(int(uid)) if interaction.guild else None
            p_dict = dict(profile)
            p_dict['tags'] = parse_json_field(p_dict['tags'])
            p_dict['photos'] = parse_json_field(p_dict['photos'])
            p_dict['votes'] = parse_json_field(p_dict.get('votes', '{}'))
            if not isinstance(p_dict['votes'], dict): p_dict['votes'] = {}
            
            embed = build_embed(p_dict, member, 0)
            await interaction.response.edit_message(embed=embed, view=ProfileView(uid, member, p_dict, self.role_val))

class RoleView(discord.ui.View):
    def __init__(self, role_val: str, records: list):
        super().__init__(timeout=None)
        self.add_item(StaffDropdown(role_val, records))

    @discord.ui.button(label="Quay lại", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(), view=MainView())

class RateModal(discord.ui.Modal, title="Đánh giá thành viên"):
    score = discord.ui.TextInput(label="Số điểm (1-5)", placeholder="Ví dụ: 4.5", max_length=3, required=True)

    def __init__(self, user_id: str, member: Optional[discord.Member], view: 'ProfileView'):
        super().__init__()
        self.user_id = user_id
        self.member = member
        self.pview = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(str(self.score).replace(",", "."))
            if not (1 <= val <= 5): raise ValueError
        except ValueError:
            await interaction.response.send_message("Điểm không hợp lệ! Nhập số từ 1 đến 5.", ephemeral=True)
            return

        voter = str(interaction.user.id)
        if voter == self.user_id:
            await interaction.response.send_message("Không thể tự đánh giá bản thân!", ephemeral=True)
            return

        bot: Any = interaction.client
        async with bot.db_pool.acquire() as conn:
            profile = await conn.fetchrow("SELECT votes FROM profiles WHERE discord_id = $1", self.user_id)
            if not profile:
                await interaction.response.send_message("Lỗi dữ liệu.", ephemeral=True)
                return
            
            votes = parse_json_field(profile['votes'])
            if not isinstance(votes, dict): votes = {}
            
            votes[voter] = val
            new_rating = round(sum(votes.values()) / len(votes), 2)
            
            await conn.execute("UPDATE profiles SET votes = $1::jsonb, rating = $2 WHERE discord_id = $3", json.dumps(votes), new_rating, self.user_id)

        self.pview.profile["votes"] = votes
        self.pview.profile["rating"] = new_rating
        self.pview._update_buttons()
        await interaction.response.edit_message(embed=build_embed(self.pview.profile, self.member, self.pview.page), view=self.pview)

class ProfileView(discord.ui.View):
    def __init__(self, user_id: str, member: Optional[discord.Member], profile_data: dict, from_role: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.member = member
        self.profile = profile_data
        self.from_role = from_role
        self.page = 0
        self._update_buttons()

    def _update_buttons(self):
        total = len(self.profile.get("photos", []))
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id:
                if child.custom_id == "prev": child.disabled = self.page <= 0
                if child.custom_id == "next": child.disabled = self.page >= total - 1

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="back")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot: Any = interaction.client
        async with bot.db_pool.acquire() as conn:
            records = await conn.fetch("SELECT discord_id, display_name, description FROM profiles WHERE role = $1", self.from_role)
        embed = discord.Embed(title=f"Danh sách {self.from_role.capitalize()}", description="Chọn một nhân sự phía dưới để xem chi tiết.", color=0x5865f2)
        await interaction.response.edit_message(embed=embed, view=RoleView(self.from_role, records))

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(self.profile, self.member, self.page), view=self)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(len(self.profile.get("photos", [])) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(self.profile, self.member, self.page), view=self)

    @discord.ui.button(label="⭐ Đánh giá", style=discord.ButtonStyle.primary, custom_id="rate")
    async def rate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal(self.user_id, self.member, self))

class StaffUICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="menu")
    async def send_menu(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send(embed=get_main_embed(), view=MainView())

    @commands.command(name="help")
    async def custom_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Danh sách lệnh của Bot Angelic ໒꒱",
            description="Dưới đây là các lệnh và tính năng hiện tại bạn có thể sử dụng:",
            color=0x5865f2
        )
        
        embed.add_field(
            name="`y!menu`",
            value="Hiển thị bảng giao diện (Menu) xem danh sách Staff và đánh giá.",
            inline=False
        )
        embed.add_field(
            name="`y!addstaff`",
            value="*(Chỉ dành cho Admin có quyền Quản trị)* Thêm hoặc cập nhật dữ liệu Staff.\n**Cú pháp:** `y!addstaff @tag_người_đó tên_role giới_thiệu`\n*(Role hợp lệ: `owner`, `admin`, `recep`)*",
            inline=False
        )
        
        embed.set_footer(text="Gõ đúng cú pháp nhé!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffUICog(bot))