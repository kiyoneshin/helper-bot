import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any

log = logging.getLogger("StaffBot")

# =====================================================================
# 1. HÀM THÔNG MINH TỰ ĐỘNG DÒ TÌM DATABASE TRÊN BOT
# =====================================================================

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động tìm biến kết nối DB trên bot (dù tên là db, pool, database hay db_pool)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
                
    log.error("Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
    return []


# =====================================================================
# 2. CÁC HÀM TẠO EMBED GIAO DIỆN
# =====================================================================

def get_main_embed() -> discord.Embed:
    """Tạo Embed chào mừng và luật server ở trang đầu tiên"""
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
            "➡️ *Vui lòng chọn menu phía dưới để làm quen với danh sách Ban Quản Trị!*"
        ),
        color=0xffb6c1
    )
    return embed


def build_embed(user_data: dict, member: Optional[discord.Member] = None, photo_index: int = 0) -> discord.Embed:
    """Tạo Embed hiển thị Profile của Staff"""
    display_name = user_data.get('display_name', 'Unnamed Staff')
    role_name = user_data.get('role', 'staff').upper()
    
    embed = discord.Embed(
        title=f"✨ {display_name} ✨",
        color=0xffb6c1
    )
    
    tags = user_data.get('tags', [])
    if isinstance(tags, str):
        try: 
            tags = json.loads(tags)
        except Exception: 
            tags = []
        
    if tags:
        embed.description = "\n".join(f"♱ {t}" for t in tags)
    else:
        embed.description = "*Chưa có thông tin giới thiệu.*"
        
    if member and member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)
        
    photos = user_data.get('photos', [])
    if isinstance(photos, str):
        try: 
            photos = json.loads(photos)
        except Exception: 
            photos = []
        
    if photos and len(photos) > photo_index:
        img_url = str(photos[photo_index]).strip()
        if img_url.startswith("http://") or img_url.startswith("https://"):
            embed.set_image(url=img_url)
        else:
            log.warning(f"⚠️ Phát hiện URL ảnh không hợp lệ trong DB, tự động bỏ qua: {img_url}")
            
    total_photos = max(1, len(photos))
    embed.set_footer(text=f"Vị trí: {role_name} • Ảnh {photo_index + 1}/{total_photos}")
    return embed


# =====================================================================
# 3. MODAL (FORM) NHẬP ĐIỂM ĐÁNH GIÁ VOTE (ĐÃ FIX TRIỆT ĐỂ LỖI DICT/JSON)
# =====================================================================

class VoteModal(discord.ui.Modal, title="🌟 Đánh Giá Nhân Sự"):
    """Form bật lên để người dùng nhập điểm số từ 0 đến 5"""
    score_input = discord.ui.TextInput(
        label="Nhập điểm đánh giá (Từ 0 đến 5):",
        placeholder="Chấp nhận số nguyên (5, 4) hoặc thập phân (5.0, 4.5)",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, profile_view):
        super().__init__()
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        val_str = self.score_input.value.strip().replace(',', '.')
        
        try:
            val = float(val_str)
            if not (0.0 <= val <= 5.0):
                raise ValueError()
                
            parts = val_str.split('.')
            if len(parts) == 2 and len(parts[1]) > 1:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "⚠️ **Điểm đánh giá không hợp lệ!**\n➡️ Vui lòng chỉ nhập điểm từ `0` đến `5`. Chấp nhận dạng số nguyên như `5`, `4` hoặc tối đa 1 chữ số thập phân như `5.0`, `4.5`.",
                ephemeral=True
            )
            return

        val = round(val, 1)
        bot: Any = interaction.client
        target_id = str(self.profile_view.user_data.get('discord_id'))

        if str(interaction.user.id) == target_id:
            await interaction.response.send_message(
                "⚠️ **Bạn không thể tự đánh giá (vote) cho chính bản thân mình được nhé!**",
                ephemeral=True
            )
            return

        records = await query_db(bot, "SELECT votes FROM profiles WHERE discord_id = $1", target_id)
        votes_list = []
        if records and records[0].get('votes') is not None:
            v_data = records[0]['votes']
            if isinstance(v_data, str):
                try: 
                    votes_list = json.loads(v_data)
                except Exception: 
                    votes_list = []
            elif isinstance(v_data, list):
                votes_list = v_data

        # LỚP GIÁP BẢO VỆ CHỐNG CRASH: Nếu trong DB lưu nhầm thành dict '{}' hoặc kiểu khác, tự động ép về list rỗng '[]'
        if not isinstance(votes_list, list):
            votes_list = []

        votes_list.append(val)
        new_avg = round(sum(float(v) for v in votes_list) / len(votes_list), 1)

        await query_db(
            bot, 
            "UPDATE profiles SET votes = $1::text::jsonb, rating = $2 WHERE discord_id = $3",
            json.dumps(votes_list), new_avg, target_id
        )

        self.profile_view.user_data['votes'] = votes_list
        self.profile_view.user_data['rating'] = new_avg
        self.profile_view.rating_display_btn.label = f"⭐ {new_avg}/5.0 ({len(votes_list)} lượt)"

        if interaction.message:
            await interaction.message.edit(view=self.profile_view)
        
        await interaction.response.send_message(
            f"💖 **Cảm ơn bạn!** Đã ghi nhận điểm đánh giá **{val} ⭐** và cập nhật lên hệ thống!",
            ephemeral=True
        )


# =====================================================================
# 4. CÁC CLASS GIAO DIỆN (VIEWS & DROPDOWNS)
# =====================================================================

class BaseStaffView(discord.ui.View):
    """View cơ sở chứa tính năng khóa người dùng"""
    def __init__(self, author_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Bạn không thể thao tác trên bảng menu của người khác! Hãy tự gõ `y!menu` để xem nhé.", 
                ephemeral=True
            )
            return False
        return True


class BackOnlyView(BaseStaffView):
    """View chỉ có 1 nút Quay lại"""
    def __init__(self, author_id: int):
        super().__init__(author_id=author_id)

    @discord.ui.button(label="« Quay về Trang Chủ", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(), view=MainView(self.author_id))


class RoleSelectDropdown(discord.ui.Select):
    """Menu thả xuống chọn Chức vụ ở Trang chủ"""
    def __init__(self, author_id: int):
        self.author_id = author_id
        options = [
            discord.SelectOption(label="Owner", description="Xem danh sách Chủ sở hữu server", emoji="👑", value="owner"),
            discord.SelectOption(label="Admin", description="Xem danh sách Quản trị viên", emoji="🛡️", value="admin"),
            discord.SelectOption(label="Recep", description="Xem danh sách Lễ tân chào đón", emoji="🌸", value="recep")
        ]
        super().__init__(placeholder="🗂️ Chọn bộ phận BQT bạn muốn xem...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_role = self.values[0]
        bot: Any = interaction.client
        
        try:
            records = await query_db(bot, "SELECT * FROM profiles WHERE role ILIKE $1", f"%{selected_role}%")
        except Exception as e:
            log.error(f"Lỗi lấy dữ liệu DB: {e}")
            records = []

        if not records or len(records) == 0:
            empty_embed = discord.Embed(
                title=f"📋 Danh sách {selected_role.upper()}",
                description=f"🌸 Hiện tại chưa có nhân sự nào giữ vị trí **{selected_role.upper()}** trong server.\n\n*Admin có thể sử dụng lệnh `y!addstaff` hoặc kiểm tra lại bằng lệnh `y!checkdb`.*",
                color=0xffb6c1
            )
            await interaction.response.edit_message(embed=empty_embed, view=BackOnlyView(self.author_id))
            return

        list_text = f"➡️ **Danh sách các {selected_role.upper()} đang hoạt động:**\n\n"
        for idx, row in enumerate(records, 1):
            name = row.get('display_name', 'Unnamed')
            doc_id = row.get('discord_id')
            list_text += f"**{idx}. {name}** (<@{doc_id}>)\n"
            
        list_text += "\n➡️ *Vui lòng chọn tên nhân sự từ menu thả xuống bên dưới để xem hồ sơ chi tiết và ảnh!*"

        role_embed = discord.Embed(
            title=f"📋 Danh sách {selected_role.upper()}",
            description=list_text,
            color=0xffb6c1
        )
        await interaction.response.edit_message(
            embed=role_embed, 
            view=StaffListView(author_id=self.author_id, staff_records=records, role_name=selected_role)
        )


class MainView(BaseStaffView):
    """View Trang chủ chính của Menu"""
    def __init__(self, author_id: int):
        super().__init__(author_id=author_id)
        self.add_item(RoleSelectDropdown(author_id))


class StaffSelectDropdown(discord.ui.Select):
    """Menu thả xuống chọn từng Staff cụ thể"""
    def __init__(self, author_id: int, staff_records: list, role_name: str):
        self.author_id = author_id
        self.staff_records = staff_records
        self.role_name = role_name
        
        options = []
        for row in staff_records:
            name = row.get('display_name', 'Staff')
            doc_id = str(row.get('discord_id'))
            options.append(discord.SelectOption(label=name, description=f"Xem hồ sơ của {name}", value=doc_id, emoji="✨"))
            
        super().__init__(placeholder="👤 Chọn nhân sự muốn xem hồ sơ...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        user_data = next((item for item in self.staff_records if str(item['discord_id']) == selected_id), None)
        
        if not user_data:
            await interaction.response.send_message("Không tìm thấy thông tin nhân sự này!", ephemeral=True)
            return
            
        member: Optional[discord.Member] = interaction.guild.get_member(int(selected_id)) if interaction.guild else None
        embed = build_embed(user_data=user_data, member=member, photo_index=0)
        
        await interaction.response.edit_message(
            embed=embed, 
            view=ProfileView(author_id=self.author_id, user_data=user_data, member=member, staff_records=self.staff_records, role_name=self.role_name)
        )


class StaffListView(BaseStaffView):
    """View chứa danh sách nhân sự của 1 Role"""
    def __init__(self, author_id: int, staff_records: list, role_name: str):
        super().__init__(author_id=author_id)
        self.add_item(StaffSelectDropdown(author_id, staff_records, role_name))

    @discord.ui.button(label="« Quay về Trang Chủ", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(), view=MainView(self.author_id))


class ProfileView(BaseStaffView):
    """View hiển thị Profile chi tiết, có nút chuyển ảnh, nút điểm trung bình (khóa) và nút đánh giá"""
    def __init__(self, author_id: int, user_data: dict, member: Optional[discord.Member], staff_records: list, role_name: str):
        super().__init__(author_id=author_id)
        self.user_data = user_data
        self.member = member
        self.staff_records = staff_records
        self.role_name = role_name
        self.photo_index = 0
        
        photos = user_data.get('photos', [])
        if isinstance(photos, str):
            try: 
                photos = json.loads(photos)
            except Exception: 
                photos = []
            
        if len(photos) <= 1:
            self.prev_btn.disabled = True
            self.next_btn.disabled = True

        votes = user_data.get('votes', [])
        if isinstance(votes, str):
            try: 
                votes = json.loads(votes)
            except Exception: 
                votes = []
        
        # Bảo vệ chống lỗi dict '{}' lúc khởi tạo View
        if not isinstance(votes, list):
            votes = []
            
        if votes and len(votes) > 0:
            avg = round(sum(float(v) for v in votes) / len(votes), 1)
            self.rating_display_btn.label = f"⭐ {avg}/5.0 ({len(votes)} lượt)"
        else:
            self.rating_display_btn.label = "⭐ Chưa có điểm"

    @discord.ui.button(label="⏮️ Ảnh trước", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.user_data.get('photos', [])
        if isinstance(photos, str):
            try: 
                photos = json.loads(photos)
            except Exception: 
                photos = []
            
        if photos:
            self.photo_index = (self.photo_index - 1) % len(photos)
            embed = build_embed(self.user_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏭️ Ảnh tiếp", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.user_data.get('photos', [])
        if isinstance(photos, str):
            try: 
                photos = json.loads(photos)
            except Exception: 
                photos = []
            
        if photos:
            self.photo_index = (self.photo_index + 1) % len(photos)
            embed = build_embed(self.user_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⭐ Chưa có điểm", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def rating_display_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🌟 Đánh giá", style=discord.ButtonStyle.success, row=0)
    async def vote_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_id = str(self.user_data.get('discord_id'))
        if str(interaction.user.id) == target_id:
            await interaction.response.send_message(
                "⚠️ **Bạn không thể tự đánh giá (vote) cho chính bản thân mình được nhé!**",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(VoteModal(self))

    @discord.ui.button(label="« Danh sách Staff", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        list_text = f"➡️ **Danh sách các {self.role_name.upper()} đang hoạt động:**\n\n"
        for idx, row in enumerate(self.staff_records, 1):
            name = row.get('display_name', 'Unnamed')
            doc_id = row.get('discord_id')
            list_text += f"**{idx}. {name}** (<@{doc_id}>)\n"
            
        list_text += "\n➡️ *Vui lòng chọn tên nhân sự từ menu thả xuống bên dưới để xem hồ sơ chi tiết và ảnh!*"

        role_embed = discord.Embed(
            title=f"📋 Danh sách {self.role_name.upper()}",
            description=list_text,
            color=0xffb6c1
        )
        await interaction.response.edit_message(
            embed=role_embed, 
            view=StaffListView(self.author_id, self.staff_records, self.role_name)
        )

    @discord.ui.button(label="🏠 Trang Chủ", style=discord.ButtonStyle.danger, row=1)
    async def back_to_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(), view=MainView(self.author_id))


# =====================================================================
# 5. COG CHÍNH & CÁC LỆNH Y!MENU / Y!CHECKDB / Y!HELP
# =====================================================================

class StaffUICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.get_command("help"):
            self.bot.remove_command("help")

    @commands.command(name="menu", aliases=["staff", "bqt"])
    async def send_menu(self, ctx: commands.Context):
        """Lệnh hiển thị Menu giới thiệu Ban Quản Trị Angelic"""
        await ctx.send(embed=get_main_embed(), view=MainView(author_id=ctx.author.id))
        log.info(f"🌸 {ctx.author.display_name} vừa mở bảng Menu Staff.")

    @commands.command(name="checkdb")
    async def check_db(self, ctx: commands.Context):
        """Lệnh kiểm tra toàn bộ danh sách đang có trong Database"""
        try:
            records = await query_db(self.bot, "SELECT discord_id, role, display_name FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**\n➡️ Hãy lên Railway kiểm tra lại xem dữ liệu bạn nhập đã được ấn phím **Enter** để xác nhận lưu chưa nhé!")
                return
            
            msg = "**📋 Danh sách thực tế đang lưu trong Database:**\n"
            for r in records:
                msg += f"➡️ ID: `{r['discord_id']}` | Role: `{r['role']}` | Tên: **{r['display_name']}**\n"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="help", aliases=["huongdan", "lenh", "commands"])
    async def help_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị danh sách toàn bộ các câu lệnh của Bot"""
        embed = discord.Embed(
            title="📖 Bảng Hướng Dẫn Câu Lệnh Angelic Bot ໒꒱",
            description="Dưới đây là toàn bộ các câu lệnh khả dụng mà bạn có thể sử dụng trên server:",
            color=0xffb6c1
        )
        
        embed.add_field(
            name="✨ Lệnh Giao Diện & Nhân Sự",
            value=(
                "➡️ `y!menu` (hoặc `y!staff`, `y!bqt`): Mở bảng giao diện xem danh sách và thông tin Ban Quản Trị.\n"
                "➡️ `y!checkdb`: Kiểm tra nhanh danh sách toàn bộ nhân sự đang được lưu trong Cơ Sở Dữ Liệu.\n"
                "➡️ `y!addstaff <id> <role> <tên>`: Thêm nhanh một nhân sự mới vào hệ thống Database."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📌 Lệnh Hệ Thống",
            value=(
                "➡️ `y!help` (hoặc `y!huongdan`): Hiển thị bảng hướng dẫn câu lệnh này."
            ),
            inline=False
        )
        
        embed.set_footer(text="Angelic Bot • Sử dụng mũi tên để điều hướng các menu dễ dàng hơn!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffUICog(bot))