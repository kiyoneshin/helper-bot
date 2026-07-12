import discord
import json
import logging
from typing import Optional, Any
from cogs._staff_db import query_db
from cogs._staff_embeds import get_main_embed, build_embed

log = logging.getLogger("StaffViews")

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
        votes_dict = {}
        if records and records[0].get('votes') is not None:
            v_data = records[0]['votes']
            if isinstance(v_data, str):
                try: 
                    v_data = json.loads(v_data)
                except Exception: 
                    v_data = {}
            
            if isinstance(v_data, dict):
                votes_dict = v_data
            elif isinstance(v_data, list):
                for idx, old_score in enumerate(v_data):
                    if isinstance(old_score, (int, float)):
                        votes_dict[f"old_voter_{idx}"] = float(old_score)

        if not isinstance(votes_dict, dict):
            votes_dict = {}

        voter_id = str(interaction.user.id)
        
        if voter_id in votes_dict:
            await interaction.response.send_message(
                "⚠️ **Bạn đã đánh giá cho nhân sự này rồi!**\n➡️ Mỗi người chỉ được quyền vote 1 lần duy nhất cho mỗi Staff để đảm bảo tính công bằng.",
                ephemeral=True
            )
            return

        votes_dict[voter_id] = val
        scores = [float(v) for v in votes_dict.values()]
        new_avg = round(sum(scores) / len(scores), 1)

        await query_db(
            bot, 
            "UPDATE profiles SET votes = $1::text::jsonb, rating = $2 WHERE discord_id = $3",
            json.dumps(votes_dict), new_avg, target_id
        )

        if not isinstance(self.profile_view.user_data, dict):
            self.profile_view.user_data = dict(self.profile_view.user_data)

        self.profile_view.user_data['votes'] = votes_dict
        self.profile_view.user_data['rating'] = new_avg
        self.profile_view.rating_display_btn.label = f"⭐ {new_avg}/5.0 ({len(scores)} lượt)"

        if interaction.message:
            await interaction.message.edit(view=self.profile_view)
        
        await interaction.response.send_message(
            f"💖 **Cảm ơn bạn!** Đã ghi nhận điểm đánh giá **{val} ⭐** và cập nhật lên hệ thống!",
            ephemeral=True
        )


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
            
        user_data = dict(user_data)

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

        votes = user_data.get('votes', {})
        if isinstance(votes, str):
            try: 
                votes = json.loads(votes)
            except Exception: 
                votes = {}
        
        scores = []
        if isinstance(votes, list):
            scores = [float(v) for v in votes if isinstance(v, (int, float))]
        elif isinstance(votes, dict):
            scores = [float(v) for v in votes.values()]
            
        if scores and len(scores) > 0:
            avg = round(sum(scores) / len(scores), 1)
            self.rating_display_btn.label = f"⭐ {avg}/5.0 ({len(scores)} lượt)"
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

    @discord.ui.button(label="⏭️ Ảnh sau", style=discord.ButtonStyle.primary, row=0)
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