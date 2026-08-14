import discord
import json
import logging
from typing import Optional, Any
from cogs.common.db import query_db
from cogs.common.embeds import get_main_embed, build_embed
from cogs.common.logs import send_staff_log, build_log_vote

log = logging.getLogger("StaffViews")


def _normalize_votes(v_data: Any) -> dict:
    if isinstance(v_data, str):
        try:
            v_data = json.loads(v_data)
        except Exception:
            return {}

    if isinstance(v_data, list):
        result = {}
        for idx, old_score in enumerate(v_data):
            if isinstance(old_score, (int, float)):
                result[f"old_voter_{idx}"] = {"score": float(old_score), "review": "Không có nội dung"}
        return result

    if isinstance(v_data, dict):
        result = {}
        for voter_id, entry in v_data.items():
            # Dữ liệu cũ dạng số trần
            if isinstance(entry, (int, float)):
                result[voter_id] = {"score": float(entry), "review": "Không có nội dung"}
            # Dữ liệu mới đã đúng cấu trúc
            elif isinstance(entry, dict) and "score" in entry:
                result[voter_id] = {
                    "score": float(entry.get("score", 0.0)),
                    "review": str(entry.get("review") or "Không có nội dung")
                }
        return result

    return {}


def _get_rating_label(user_data: dict) -> str:
    """Tính và trả về label hiển thị điểm trung bình từ user_data."""
    votes = user_data.get('votes', {})
    normalized = _normalize_votes(votes)
    scores = [entry["score"] for entry in normalized.values() if isinstance(entry, dict)]
    if scores:
        avg = round(sum(scores) / len(scores), 1)
        return f"⭐ {avg}/5.0 ({len(scores)} lượt)"
    return "⭐ Chưa có điểm"


async def _fetch_fresh_user_data(bot: Any, discord_id: str) -> Optional[dict]:
    """
    Truy vấn DB để lấy bản ghi mới nhất của một nhân sự.
    Trả về dict hoặc None nếu không tìm thấy.
    """
    try:
        records = await query_db(bot, "SELECT * FROM profiles WHERE discord_id = $1", discord_id)
        if records:
            return dict(records[0])
    except Exception as e:
        log.error(f"Lỗi _fetch_fresh_user_data({discord_id}): {e}")
    return None


async def _fetch_fresh_staff_list(bot: Any, role_name: str) -> list:
    """
    Truy vấn DB để lấy danh sách nhân sự mới nhất của một role.
    Trả về list (có thể rỗng).
    """
    try:
        records = await query_db(bot, "SELECT * FROM profiles WHERE role ILIKE $1", f"%{role_name}%")
        return [dict(r) for r in records] if records else []
    except Exception as e:
        log.error(f"Lỗi _fetch_fresh_staff_list({role_name}): {e}")
    return []


def _build_staff_list_embed(role_name: str, staff_records: list) -> discord.Embed:
    """Tạo Embed danh sách nhân sự của một role."""
    list_text = f"**Danh sách các {role_name.upper()} đang hoạt động:**\n\n"
    for idx, row in enumerate(staff_records, 1):
        name = row.get('display_name', 'Unnamed')
        doc_id = row.get('discord_id')
        list_text += f"**{idx}. {name}** (<@{doc_id}>)\n"
    list_text += "\n⬇️ *Vui lòng chọn tên nhân sự từ menu thả xuống bên dưới để xem hồ sơ chi tiết và ảnh!*"
    return discord.Embed(
        title=f"Danh sách {role_name.upper()}",
        description=list_text,
        color=0xffb6c1
    )


# =====================================================================
# MODAL ĐÁNH GIÁ
# =====================================================================

class VoteModal(discord.ui.Modal, title="🌟 Đánh Giá Nhân Sự"):
    """Form bật lên để người dùng nhập điểm số và bài đánh giá"""
    score_input = discord.ui.TextInput(
        label="Nhập điểm đánh giá (Từ 0 đến 5):",
        placeholder="Chấp nhận số nguyên (5, 4) hoặc thập phân (5.0, 4.5)",
        min_length=1,
        max_length=3,
        required=True
    )
    review_input = discord.ui.TextInput(
        label="Nội dung đánh giá:",
        placeholder="Chia sẻ cảm nhận của bạn về nhân sự này... (không bắt buộc)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200
    )

    def __init__(self, profile_view: "ProfileView", old_score: Optional[str] = None, old_review: Optional[str] = None):
        super().__init__()
        self.profile_view = profile_view
        self.old_score_value = old_score
        if old_score is not None:
            self.score_input.default = old_score
        if old_review is not None:
            self.review_input.default = old_review

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
                "**Điểm đánh giá không hợp lệ!**\nVui lòng chỉ nhập điểm từ `0` đến `5`. Chấp nhận dạng số nguyên như `5`, `4` hoặc tối đa 1 chữ số thập phân như `5.0`, `4.5`.",
                ephemeral=True
            )
            return

        val = round(val, 1)
        review_text = self.review_input.value.strip() if self.review_input.value else "Không có nội dung"
        if not review_text:
            review_text = "Không có nội dung"

        bot: Any = interaction.client
        # Luôn lấy target_id từ thuộc tính bất biến của ProfileView
        target_id = self.profile_view.target_discord_id

        if str(interaction.user.id) == target_id:
            await interaction.response.send_message(
                "**Bạn không thể tự đánh giá (vote) cho chính bản thân mình được nhé!**",
                ephemeral=True
            )
            return

        # --- Đọc votes mới nhất từ DB (real-time) ---
        records = await query_db(bot, "SELECT votes FROM profiles WHERE discord_id = $1", target_id)
        votes_dict = {}
        if records and records[0].get('votes') is not None:
            votes_dict = _normalize_votes(records[0]['votes'])

        voter_id = str(interaction.user.id)
        is_update = voter_id in votes_dict

        votes_dict[voter_id] = {"score": val, "review": review_text}
        scores = [entry["score"] for entry in votes_dict.values() if isinstance(entry, dict)]
        new_avg = round(sum(scores) / len(scores), 1) if scores else 0.0

        await query_db(
            bot,
            "UPDATE profiles SET votes = $1::text::jsonb, rating = $2 WHERE discord_id = $3",
            json.dumps(votes_dict), new_avg, target_id
        )

        # --- Refresh lại embed từ DB sau khi ghi vote thành công ---
        fresh_data = await _fetch_fresh_user_data(bot, target_id)
        target_name = fresh_data.get('display_name', 'Unnamed Staff') if fresh_data else 'Unnamed Staff'
        
        if fresh_data and interaction.message:
            member = self.profile_view.member
            embed = build_embed(user_data=fresh_data, member=member, photo_index=self.profile_view.photo_index)

            # Cập nhật lại label nút điểm trên ProfileView
            self.profile_view.rating_display_btn.label = _get_rating_label(fresh_data)
            await interaction.message.edit(embed=embed, view=self.profile_view)

        confirm_msg = (
            f"✏️ **Đã cập nhật bài đánh giá của bạn thành công!** (Điểm mới: **{val} ⭐**)"
            if is_update else
            f"💖 **Cảm ơn bạn!** Đã ghi nhận điểm đánh giá **{val} ⭐** và cập nhật lên hệ thống!"
        )
        await interaction.response.send_message(confirm_msg, ephemeral=True)

        # --- Gửi Log Audit vào kênh ẩn ---
        try:
            log_embed = build_log_vote(
                voter_id=voter_id,
                target_id=target_id,
                target_name=target_name,
                new_score=val,
                review_text=review_text,
                is_update=is_update,
                old_score=self.old_score_value,
            )
            await send_staff_log(bot, log_embed)
        except Exception as e:
            log.error(f"Lỗi gửi log đánh giá: {e}")


# =====================================================================
# BASE VIEW
# =====================================================================

class BaseStaffView(discord.ui.View):
    """View cơ sở chứa tính năng khóa người dùng và on_timeout chung"""
    def __init__(self, author_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Bạn không thể thao tác trên bảng menu của người khác! Hãy tự gõ `kmenu` để xem nhé.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# =====================================================================
# BACK-ONLY VIEW
# =====================================================================

class BackOnlyView(BaseStaffView):
    """View chỉ có 1 nút Quay lại"""
    def __init__(self, author_id: int):
        super().__init__(author_id=author_id)

    @discord.ui.button(label="« Quay về Trang Chủ", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_view = MainView(self.author_id)
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=get_main_embed(), view=new_view)


# =====================================================================
# MAIN VIEW (TRANG CHỦ)
# =====================================================================

class RoleSelectDropdown(discord.ui.Select):
    """Menu thả xuống chọn Chức vụ ở Trang chủ — luôn query DB mới nhất"""
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

        # Real-time: luôn lấy danh sách mới nhất từ DB
        records = await _fetch_fresh_staff_list(bot, selected_role)

        if not records:
            empty_embed = discord.Embed(
                title=f"Danh sách {selected_role.upper()}",
                description=f"🌸 Hiện tại chưa có nhân sự nào giữ vị trí **{selected_role.upper()}** trong server.\n\n*Admin có thể sử dụng lệnh `{bot.custom_prefix}add` hoặc kiểm tra lại bằng lệnh `{bot.custom_prefix}checkdb`.*",
                color=0xffb6c1
            )
            back_view = BackOnlyView(self.author_id)
            back_view.message = interaction.message
            await interaction.response.edit_message(embed=empty_embed, view=back_view)
            return

        list_embed = _build_staff_list_embed(selected_role, records)
        new_view = StaffListView(
            author_id=self.author_id,
            staff_records=records,
            role_name=selected_role
        )
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=list_embed, view=new_view)


class MainView(BaseStaffView):
    """View Trang chủ chính của Menu"""
    def __init__(self, author_id: int):
        super().__init__(author_id=author_id)
        self.add_item(RoleSelectDropdown(author_id))


# =====================================================================
# STAFF LIST VIEW
# =====================================================================

class StaffSelectDropdown(discord.ui.Select):
    """Menu thả xuống chọn từng Staff cụ thể — query DB real-time khi chọn"""
    def __init__(self, author_id: int, staff_records: list, role_name: str):
        self.author_id = author_id
        self.role_name = role_name
        self._option_map: dict[str, str] = {
            str(row.get('discord_id')): row.get('display_name', 'Staff')
            for row in staff_records
        }

        options = []
        for doc_id, name in self._option_map.items():
            options.append(discord.SelectOption(
                label=name[:100],  # Discord giới hạn 100 ký tự
                description=f"Xem hồ sơ của {name}"[:100],
                value=doc_id,
                emoji="✨"
            ))

        super().__init__(placeholder="👤 Chọn nhân sự muốn xem hồ sơ...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        bot: Any = interaction.client

        # Real-time: truy vấn thẳng DB để lấy dữ liệu mới nhất
        fresh_data = await _fetch_fresh_user_data(bot, selected_id)

        if not fresh_data:
            await interaction.response.send_message(
                "<:symbol_alert:1537546957885542450> Không tìm thấy thông tin nhân sự này trong Database! Có thể hồ sơ đã bị xóa.",
                ephemeral=True
            )
            return

        member: Optional[discord.Member] = (
            interaction.guild.get_member(int(selected_id)) if interaction.guild else None
        )
        embed = build_embed(user_data=fresh_data, member=member, photo_index=0)

        # Lấy lại danh sách staff mới nhất để truyền vào ProfileView
        fresh_staff_list = await _fetch_fresh_staff_list(bot, self.role_name)

        new_view = ProfileView(
            author_id=self.author_id,
            target_discord_id=selected_id,
            fresh_user_data=fresh_data,
            member=member,
            role_name=self.role_name,
            fresh_staff_list=fresh_staff_list
        )
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class StaffListView(BaseStaffView):
    """View chứa danh sách nhân sự của 1 Role"""
    def __init__(self, author_id: int, staff_records: list, role_name: str):
        super().__init__(author_id=author_id)
        self.role_name = role_name
        self.add_item(StaffSelectDropdown(author_id, staff_records, role_name))

    @discord.ui.button(label="« Quay về Trang Chủ", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_view = MainView(self.author_id)
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=get_main_embed(), view=new_view)


# =====================================================================
# PROFILE VIEW
# =====================================================================

class ProfileView(BaseStaffView):
    """
    View hiển thị Profile chi tiết.
    - Nhận `target_discord_id` (str) làm định danh bất biến.
    - Mỗi lần nhấn nút, query DB để lấy dữ liệu mới nhất (real-time sync).
    """
    def __init__(
        self,
        author_id: int,
        target_discord_id: str,
        fresh_user_data: dict,
        member: Optional[discord.Member],
        role_name: str,
        fresh_staff_list: list
    ):
        super().__init__(author_id=author_id)
        # Định danh bất biến — không bao giờ thay đổi
        self.target_discord_id = target_discord_id
        self.member = member
        self.role_name = role_name
        self.photo_index = 0

        # Dùng để khởi tạo trạng thái nút ban đầu, KHÔNG dùng lại sau đó
        photos = fresh_user_data.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []

        if len(photos) <= 1:
            self.prev_btn.disabled = True
            self.next_btn.disabled = True

        self.rating_display_btn.label = _get_rating_label(fresh_user_data)

        # Giữ staff_list để xây Dropdown khi quay lại — sẽ được làm mới khi cần
        self._cached_staff_list = fresh_staff_list

    # ------------------------------------------------------------------
    # NÚT CHUYỂN ẢNH — Real-time sync từ DB
    # ------------------------------------------------------------------

    @discord.ui.button(label="⏮️ Ảnh trước", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot: Any = interaction.client
        # Query DB lấy dữ liệu mới nhất
        fresh_data = await _fetch_fresh_user_data(bot, self.target_discord_id)
        if not fresh_data:
            await interaction.response.send_message("Không tìm thấy hồ sơ này trong Database!", ephemeral=True)
            return

        photos = fresh_data.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []

        if photos:
            self.photo_index = (self.photo_index - 1) % len(photos)
            # Cập nhật trạng thái nút và label điểm từ dữ liệu mới
            self.prev_btn.disabled = len(photos) <= 1
            self.next_btn.disabled = len(photos) <= 1
            self.rating_display_btn.label = _get_rating_label(fresh_data)
            embed = build_embed(fresh_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏭️ Ảnh sau", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot: Any = interaction.client
        fresh_data = await _fetch_fresh_user_data(bot, self.target_discord_id)
        if not fresh_data:
            await interaction.response.send_message("<:symbol_alert:1537546957885542450> Không tìm thấy hồ sơ này trong Database!", ephemeral=True)
            return

        photos = fresh_data.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []

        if photos:
            self.photo_index = (self.photo_index + 1) % len(photos)
            self.prev_btn.disabled = len(photos) <= 1
            self.next_btn.disabled = len(photos) <= 1
            self.rating_display_btn.label = _get_rating_label(fresh_data)
            embed = build_embed(fresh_data, self.member, self.photo_index)
            await interaction.response.edit_message(embed=embed, view=self)

    # ------------------------------------------------------------------
    # NÚT HIỂN THỊ ĐIỂM (khóa, chỉ đọc)
    # ------------------------------------------------------------------

    @discord.ui.button(label="⭐ Chưa có điểm", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def rating_display_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # Nút khóa, không có hành động

    # ------------------------------------------------------------------
    # NÚT ĐÁNH GIÁ
    # ------------------------------------------------------------------

    @discord.ui.button(label="🌟 Đánh giá", style=discord.ButtonStyle.success, row=0)
    async def vote_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        voter_id = str(interaction.user.id)
        target_id = self.target_discord_id

        # Kiểm tra chống tự vote bằng target_discord_id bất biến
        if voter_id == target_id:
            await interaction.response.send_message(
                "**Bạn không thể tự đánh giá (vote) cho chính bản thân mình được nhé!**",
                ephemeral=True
            )
            return

        bot: Any = interaction.client
        fresh_data = await _fetch_fresh_user_data(bot, target_id)
        
        old_score = None
        old_review = None

        if fresh_data:
            votes = _normalize_votes(fresh_data.get('votes', {}))
            if voter_id in votes:
                entry = votes[voter_id]
                old_score = str(round(float(entry.get('score', 0.0)), 1))
                old_review = entry.get('review')
                if old_review == "Không có nội dung":
                    old_review = ""

        await interaction.response.send_modal(VoteModal(self, old_score=old_score, old_review=old_review))

    # ------------------------------------------------------------------
    # NÚT QUAY LẠI DANH SÁCH — Real-time sync từ DB
    # ------------------------------------------------------------------

    @discord.ui.button(label="« Danh sách Staff", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot: Any = interaction.client

        # Real-time: làm mới hoàn toàn danh sách nhân sự từ DB
        fresh_records = await _fetch_fresh_staff_list(bot, self.role_name)

        if not fresh_records:
            empty_embed = discord.Embed(
                title=f"Danh sách {self.role_name.upper()}",
                description=f"🌸 Hiện tại không còn nhân sự nào ở vị trí **{self.role_name.upper()}**.",
                color=0xffb6c1
            )
            back_view = BackOnlyView(self.author_id)
            back_view.message = interaction.message
            await interaction.response.edit_message(embed=empty_embed, view=back_view)
            return

        list_embed = _build_staff_list_embed(self.role_name, fresh_records)
        new_view = StaffListView(
            author_id=self.author_id,
            staff_records=fresh_records,
            role_name=self.role_name
        )
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=list_embed, view=new_view)

    # ------------------------------------------------------------------
    # NÚT VỀ TRANG CHỦ
    # ------------------------------------------------------------------

    @discord.ui.button(label="Trang Chủ", style=discord.ButtonStyle.danger, row=1)
    async def back_to_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_view = MainView(self.author_id)
        new_view.message = interaction.message
        await interaction.response.edit_message(embed=get_main_embed(), view=new_view)