import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any

log = logging.getLogger("StaffBot")

# =====================================================================
# 1. HÀM THÔNG MINH TỰ ĐỘNG DÒ TÌM & THỰC THI DATABASE
# =====================================================================

async def query_db(bot: Any, sql: str, *args) -> list:
    """Tự động lấy dữ liệu từ DB (SELECT)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    log.error("Không tìm thấy biến kết nối Database hợp lệ trên object bot!")
    return []

async def execute_db(bot: Any, sql: str, *args) -> bool:
    """Tự động thực thi lệnh thay đổi DB (INSERT, UPDATE, DELETE)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'execute'):
                await db_obj.execute(sql, *args)
                return True
    return False


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
# 3. GIAO DIỆN MODAL ĐÁNH GIÁ (VOTE BOX)
# =====================================================================

class VoteModal(discord.ui.Modal, title="🌟 Đánh Giá Nhân Sự"):
    """Hộp thoại nhập điểm số với bộ lọc 1 chữ số thập phân"""
    score_input = discord.ui.TextInput(
        label="Nhập điểm đánh giá (Từ 1.0 đến 5.0)",
        placeholder="Ví dụ: 4.5, 5.0, 3.8...",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, parent_view: Any, user_data: dict, member: Optional[discord.Member]):
        super().__init__()
        self.parent_view = parent_view
        self.user_data = user_data
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        input_str = self.score_input.value.strip().replace(',', '.')
        
        # KIỂM TRA ĐỊNH DẠNG: Chỉ nhận số từ 1.0 đến 5.0 và tối đa 1 chữ số thập phân
        try:
            score = float(input_str)
            if score < 1.0 or score > 5.0:
                raise ValueError()
            parts = str(score).split('.')
            if len(parts) > 1 and len(parts[1]) > 1:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "➡️ **Điểm đánh giá không hợp lệ!**\n➡️ Vui lòng chỉ nhập số từ **1.0 đến 5.0** và tối đa **1 chữ số thập phân** (Ví dụ hợp lệ: `4.5`, `5.0`, `3.8`).", 
                ephemeral=True
            )
            return

        # TÍNH TOÁN ĐIỂM TRUNG BÌNH MỚI
        old_votes = int(self.user_data.get('votes') or 0)
        old_rating = float(self.user_data.get('rating') or 0.0)
        
        new_votes = old_votes + 1
        new_rating = round(((old_rating * old_votes) + score) / new_votes, 1)
        
        # ĐẨY LÊN DATABASE RAILWAY
        doc_id = str(self.user_data.get('discord_id'))
        bot = interaction.client
        success = await execute_db(bot, "UPDATE profiles SET votes = $1, rating = $2 WHERE discord_id = $3", new_votes, new_rating, doc_id)
        
        if not success:
            await interaction.response.send_message("➡️ Có lỗi xảy ra khi kết nối đến Cơ sở dữ liệu! Vui lòng thử lại sau.", ephemeral=True)
            return

        # CẬP NHẬT DỮ LIỆU TẠI CHỖ & HIỂN THỊ LÊN NÚT BẤM
        self.user_data['votes'] = new_votes
        self.user_data['rating'] = new_rating
        
        self.parent_view.score_btn.label = f"⭐ {new_rating:.1f} / 5.0 ({new_votes} lượt)"
        
        embed = build_embed(self.user_data, self.member, self.parent_view.photo_index)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        await interaction.followup.send(f"➡️ **Cảm ơn bạn!** Đánh giá **{score}/5.0** cho **{self.user_data.get('display_name')}** đã được lưu lên Cơ sở dữ liệu!", ephemeral=True)


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
                "➡️ Bạn không thể thao tác trên bảng menu của người khác! Hãy tự gõ `y!menu` để xem nhé.", 
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

        # IN DANH SÁCH THẲNG VÀO EMBED
        list_text = f"➡️ **Danh sách các {selected_role.upper()} đang hoạt động:**\n\n"
        for idx, row in enumerate(records, 1):
            name = row.get('display_name', 'Unnamed')
            doc_id = row.get('discord_id')
            list_text += f"**{idx}. {name}** (<@{doc_id}>)\n"
            
        list_text += "\n➡️ *Vui lòng chọn tên nhân sự từ menu thả xuống bên dưới để xem hồ sơ chi tiết và đánh giá!*"

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
            await interaction.response.send_message("➡️ Không tìm thấy thông tin nhân sự này!", ephemeral=True)
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
    """View hiển thị Profile chi tiết, có nút Vote và nút hiển thị điểm (khóa bấm)"""
    def __init__(self, author_id: int, user_data: dict, member: Optional[discord.Member], staff_records: list, role_name: str):
        super().__init__(author_id=author_id)
        self.user_data = user_data
        self.member = member
        self.staff_records = staff_records
        self.role_name = role_name
        self.photo_index = 0
        
        # Xử lý bật/tắt nút ảnh
        photos = user_data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
            
        if len(photos) <= 1:
            self.prev_btn.disabled = True
            self.next_btn.disabled = True

        # Đặt thông số cho Nút Hiển Thị Điểm (Nút thứ 3 bên phải nút ảnh tiếp theo, KHÔNG BẤM ĐƯỢC)
        rating = float(user_data.get('rating') or 0.0)
        votes = int(user_data.get('votes') or 0)
        self.score_btn.label = f"⭐ {rating:.1f} / 5.0 ({votes} lượt)"

    @discord.ui.button(label="⏮️ Ảnh trước", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.user_data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
            
        if photos:
            self.photo_index = (self.photo_index - 1) % len(photos)
            embed = build_embed(self.user_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏭️ Ảnh tiếp", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.user_data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
            
        if photos:
            self.photo_index = (self.photo_index + 1) % len(photos)
            embed = build_embed(self.user_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    # NÚT HIỂN THỊ ĐIỂM (KHÓA BẤM - CHỈ ĐỂ HIỂN THỊ)
    @discord.ui.button(label="⭐ Điểm: 0.0 / 5.0", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def score_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass # Nút bị khóa nên hàm này sẽ không bao giờ bị gọi

    # NÚT BẤM VOTE ĐỂ MỞ MODAL ĐÁNH GIÁ
    @discord.ui.button(label="🌟 Đánh Giá", style=discord.ButtonStyle.success, row=0)
    async def vote_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoteModal(parent_view=self, user_data=self.user_data, member=self.member))

    @discord.ui.button(label="« Danh sách Staff", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        list_text = f"➡️ **Danh sách các {self.role_name.upper()} đang hoạt động:**\n\n"
        for idx, row in enumerate(self.staff_records, 1):
            name = row.get('display_name', 'Unnamed')
            doc_id = row.get('discord_id')
            list_text += f"**{idx}. {name}** (<@{doc_id}>)\n"
            
        list_text += "\n➡️ *Vui lòng chọn tên nhân sự từ menu thả xuống bên dưới để xem hồ sơ chi tiết và đánh giá!*"

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
            records = await query_db(self.bot, "SELECT discord_id, role, display_name, rating, votes FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**\n➡️ Hãy lên Railway kiểm tra lại xem dữ liệu bạn nhập đã được ấn phím **Enter** để xác nhận lưu chưa nhé!")
                return
            
            msg = "**📋 Danh sách thực tế đang lưu trong Database:**\n"
            for r in records:
                rating = float(r.get('rating') or 0.0)
                votes = int(r.get('votes') or 0)
                msg += f"➡️ ID: `{r['discord_id']}` | Role: `{r['role']}` | Tên: **{r['display_name']}** | ⭐ **{rating:.1f}/5.0** ({votes} vote)\n"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"➡️ Lỗi truy vấn Database: {e}")

    @commands.command(name="help", aliases=["huongdan", "lenh", "commands"])
    async def help_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị danh sách toàn bộ các câu lệnh của Bot"""
        embed = discord.Embed(
            title="📖 Bảng Hướng Dẫn Câu Lệnh Angelic Bot ໒꒱",
            description="Dưới đây là toàn bộ các câu lệnh khả dụng mà bạn có thể sử dụng trên server:",
            color=0xffb6c1
        )
        
        embed.add_field(
            name="✨ Lệnh Giao Diện & Ban Quản Trị",
            value=(
                "➡️ `y!menu` (hoặc `y!staff`, `y!bqt`): Mở bảng tương tác xem danh sách, ảnh, và đánh giá điểm cho BQT.\n"
                "➡️ `y!checkdb`: Kiểm tra nhanh danh sách nhân sự cùng số điểm Vote hiện tại trong Cơ Sở Dữ Liệu.\n"
                "➡️ `y!addstaff <id> <role> <tên>`: Thêm nhanh một nhân sự mới thẳng vào hệ thống Database."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📌 Lệnh Hệ Thống",
            value=(
                "➡️ `y!help` (hoặc `y!huongdan`): Hiển thị bảng hướng dẫn chi tiết các câu lệnh này."
            ),
            inline=False
        )
        
        embed.set_footer(text="Angelic Bot • Hãy sử dụng nút Đánh Giá trên menu để chấm điểm cho các Staff nhé!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffUICog(bot))