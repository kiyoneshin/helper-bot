import discord
from discord.ext import commands
import logging
import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from cogs._staff_db import query_db

log = logging.getLogger("StaffLeaderboard")

# Múi giờ UTC+7 (Asia/Ho_Chi_Minh)
UTC7 = timezone(timedelta(hours=7))


# =============================================================================
# TIỆN ÍCH THỜI GIAN UTC+7
# =============================================================================

def _get_current_week_range() -> tuple[datetime, datetime]:
    """
    Tính mốc đầu tuần (Thứ Hai 00:00:00) và cuối tuần (Chủ Nhật 23:59:59)
    của tuần hiện tại theo múi giờ UTC+7.
    Trả về 2 datetime aware (có tzinfo=UTC+7).
    """
    now = datetime.now(UTC7)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start_of_week, end_of_week


def _parse_date_range(date_start_str: str, date_end_str: str) -> tuple[datetime, datetime]:
    """
    Parse 2 chuỗi ngày DD/MM/YYYY thành datetime aware UTC+7.
    Trả về (start 00:00:00, end 23:59:59).
    Raise ValueError nếu sai định dạng hoặc start > end.
    """
    start = datetime.strptime(date_start_str.strip(), "%d/%m/%Y")
    end = datetime.strptime(date_end_str.strip(), "%d/%m/%Y")
    start = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC7)
    end = end.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=UTC7)
    if start > end:
        raise ValueError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
    return start, end


def _format_date(dt: datetime) -> str:
    """Format datetime thành DD/MM/YYYY"""
    return dt.strftime("%d/%m/%Y")


def _generate_month_options() -> list[discord.SelectOption]:
    """
    Tự động sinh danh sách 18 tháng gần nhất (tháng hiện tại + 17 tháng trước)
    theo múi giờ UTC+7. Trả về list[SelectOption] với:
    - label: "Tháng MM/YYYY"
    - value: "MM-YYYY"
    Tháng hiện tại nằm ở đầu danh sách.
    """
    now = datetime.now(UTC7)
    options = []
    for i in range(18):
        # Lùi i tháng từ tháng hiện tại
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        label = f"Tháng {month:02d}/{year}"
        value = f"{month:02d}-{year}"
        options.append(discord.SelectOption(label=label, value=value))
    return options


def _month_value_to_range(start_val: str, end_val: str) -> tuple[datetime, datetime]:
    """
    Chuyển đổi 2 giá trị dạng "MM-YYYY" thành khoảng thời gian:
    - start: ngày 01 của tháng bắt đầu, 00:00:00 UTC+7
    - end: ngày cuối cùng của tháng kết thúc, 23:59:59 UTC+7
    Raise ValueError nếu start > end.
    """
    s_month, s_year = int(start_val.split("-")[0]), int(start_val.split("-")[1])
    e_month, e_year = int(end_val.split("-")[0]), int(end_val.split("-")[1])

    # Ngày đầu tháng bắt đầu
    dt_start = datetime(s_year, s_month, 1, 0, 0, 0, tzinfo=UTC7)

    # Ngày cuối tháng kết thúc (dùng calendar.monthrange)
    last_day = calendar.monthrange(e_year, e_month)[1]
    dt_end = datetime(e_year, e_month, last_day, 23, 59, 59, tzinfo=UTC7)

    if dt_start > dt_end:
        raise ValueError("Tháng kết thúc phải diễn ra sau hoặc trùng với tháng bắt đầu.")

    return dt_start, dt_end


# =============================================================================
# TRUY VẤN DỮ LIỆU LEADERBOARD
# =============================================================================

async def _fetch_leaderboard_data(
    bot: Any,
    dt_start: datetime,
    dt_end: datetime,
    sort_by: str = "rating",
    role_filter: str = "all"
) -> list[dict]:
    """
    Truy vấn DB lấy dữ liệu xếp hạng đầy đủ:
    - profiles: discord_id, display_name, role, rating, weekly_replies
    - staff_message_logs: COUNT tin nhắn trong khoảng [dt_start, dt_end]
    Trả về list[dict] đã lọc role và sắp xếp.
    """
    sql = """
        SELECT
            p.discord_id,
            p.display_name,
            p.role,
            p.rating,
            p.weekly_replies,
            COALESCE(m.msg_count, 0) AS msg_count
        FROM profiles p
        LEFT JOIN (
            SELECT discord_id, COUNT(*) AS msg_count
            FROM staff_message_logs
            WHERE sent_at >= $1 AND sent_at <= $2
            GROUP BY discord_id
        ) m ON p.discord_id = m.discord_id
    """

    try:
        records = await query_db(bot, sql, dt_start, dt_end)
        data = [dict(r) for r in records] if records else []
    except Exception as e:
        log.error(f"Leaderboard DB error: {e}")
        data = []

    # Lọc theo role
    if role_filter != "all":
        data = [r for r in data if str(r.get("role", "")).lower().strip() == role_filter]

    # Sắp xếp
    if sort_by == "messages":
        data.sort(key=lambda r: (-(r.get("msg_count") or 0), -(float(r.get("rating") or 0))))
    elif sort_by == "replies":
        data.sort(key=lambda r: (-(r.get("weekly_replies") or 0), -(float(r.get("rating") or 0))))
    else:
        data.sort(key=lambda r: (-(float(r.get("rating") or 0)), -(r.get("weekly_replies") or 0)))

    return data


# =============================================================================
# XÂY EMBED LEADERBOARD
# =============================================================================

RANK_MEDALS = ["🥇", "🥈", "🥉"]

ROLE_LABELS = {
    "all": "Tất Cả Chức Vụ",
    "owner": "Owner 👑",
    "admin": "Admin 🛡️",
    "recep": "Recep 🌸",
    "supporter": "Supporter 💜",
}

SORT_LABELS = {
    "rating": "⭐ Điểm Đánh Giá",
    "messages": "✉️ Tin Nhắn Đã Gửi",
    "replies": "💬 Tin Nhắn Được Phản Hồi",
}


def _build_leaderboard_embed(
    records: list,
    sort_by: str,
    role_filter: str,
    dt_start: datetime,
    dt_end: datetime,
) -> discord.Embed:
    """Tạo Embed bảng xếp hạng Top 10 từ dữ liệu đã lọc/sắp xếp."""
    top_records = records[:10]

    role_label = ROLE_LABELS.get(role_filter, role_filter.upper())
    sort_label = SORT_LABELS.get(sort_by, sort_by)
    date_range_str = f"{_format_date(dt_start)} — {_format_date(dt_end)}"

    embed = discord.Embed(
        title="🏆 Bảng Xếp Hạng Staff Angelic",
        description=(
            f"📅 **Khoảng thời gian:** {date_range_str}\n"
            f"🗂️ **Bộ lọc:** {role_label} • 📈 **Xếp theo:** {sort_label}\n"
            f"――――――――――――――――――――"
        ),
        color=0xffb6c1,
    )

    if not top_records:
        embed.add_field(
            name="👀 Không có dữ liệu",
            value="Không tìm thấy nhân sự nào phù hợp với bộ lọc này.",
            inline=False,
        )
        embed.set_footer(text="Angelic Bot • Dùng menu bên dưới để thay đổi bộ lọc! 🌸")
        return embed

    for idx, row in enumerate(top_records):
        rank_num = idx + 1
        medal = RANK_MEDALS[idx] if idx < len(RANK_MEDALS) else f"`#{rank_num}`"

        name = row.get("display_name", "Unnamed")
        discord_id = row.get("discord_id", "?")
        role = str(row.get("role", "")).upper()
        rating = float(row.get("rating") or 0)
        replies = int(row.get("weekly_replies") or 0)
        msg_count = int(row.get("msg_count") or 0)

        field_name = f"{medal} #{rank_num} — {name}"
        field_value = (
            f"• **Chức vụ:** `{role}` • <@{discord_id}>\n"
            f"• ⭐ **Điểm TB:** `{rating:.1f}/5.0` • ✉️ **Tin nhắn:** `{msg_count}` • 💬 **Reply:** `{replies}`"
        )
        embed.add_field(name=field_name, value=field_value, inline=False)

    embed.set_footer(
        text=f"Angelic Bot • Hiển thị Top {len(top_records)}/{len(records)} nhân sự 🌸"
    )
    return embed


# =============================================================================
# GIAO DIỆN CHỌN NGÀY BẰNG DROPDOWN (DateSelectionView)
# =============================================================================

class StartMonthSelect(discord.ui.Select):
    """Dropdown chọn Tháng/Năm bắt đầu"""

    def __init__(self):
        options = _generate_month_options()
        super().__init__(
            placeholder="📅 Chọn Tháng Bắt Đầu...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        assert isinstance(self.view, DateSelectionView)
        self.view.selected_start_month = self.values[0]
        # Cập nhật default
        for opt in self.options:
            opt.default = (opt.value == self.values[0])
        await interaction.response.edit_message(view=self.view)


class EndMonthSelect(discord.ui.Select):
    """Dropdown chọn Tháng/Năm kết thúc"""

    def __init__(self):
        options = _generate_month_options()
        super().__init__(
            placeholder="📅 Chọn Tháng Kết Thúc...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        assert isinstance(self.view, DateSelectionView)
        self.view.selected_end_month = self.values[0]
        for opt in self.options:
            opt.default = (opt.value == self.values[0])
        await interaction.response.edit_message(view=self.view)


class DateSelectionView(discord.ui.View):
    """
    Panel chọn khoảng ngày bằng Dropdown, gửi dạng ephemeral.
    Chứa 2 dropdown chọn tháng + 1 nút xác nhận.
    """

    def __init__(self, leaderboard_view: "LeaderboardView"):
        super().__init__(timeout=120)
        self.leaderboard_view = leaderboard_view
        self.selected_start_month: Optional[str] = None  # dạng "MM-YYYY"
        self.selected_end_month: Optional[str] = None

        self.add_item(StartMonthSelect())
        self.add_item(EndMonthSelect())

    @discord.ui.button(
        label="🔎 Áp Dụng Bộ Lọc",
        style=discord.ButtonStyle.success,
        row=2,
    )
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- Kiểm tra đã chọn đủ chưa ---
        if not self.selected_start_month or not self.selected_end_month:
            await interaction.response.send_message(
                "⚠️ **Vui lòng chọn đầy đủ cả Tháng Bắt Đầu và Tháng Kết Thúc trước khi áp dụng!**",
                ephemeral=True,
            )
            return

        # --- Chuyển đổi và kiểm tra logic thời gian ---
        try:
            dt_start, dt_end = _month_value_to_range(
                self.selected_start_month, self.selected_end_month
            )
        except ValueError:
            await interaction.response.send_message(
                "⚠️ **Lỗi logic:** Tháng kết thúc phải diễn ra sau hoặc trùng với tháng bắt đầu!\n"
                "📌 Vui lòng chọn lại.",
                ephemeral=True,
            )
            return

        # --- Cập nhật mốc thời gian lên LeaderboardView cha ---
        self.leaderboard_view.dt_start = dt_start
        self.leaderboard_view.dt_end = dt_end

        # --- Refresh bảng xếp hạng gốc (query DB real-time) ---
        bot: Any = interaction.client
        data = await _fetch_leaderboard_data(
            bot, dt_start, dt_end,
            self.leaderboard_view.current_sort,
            self.leaderboard_view.current_role,
        )
        embed = _build_leaderboard_embed(
            data,
            self.leaderboard_view.current_sort,
            self.leaderboard_view.current_role,
            dt_start, dt_end,
        )

        # Cập nhật tin nhắn Leaderboard gốc
        if self.leaderboard_view.message:
            try:
                await self.leaderboard_view.message.edit(
                    embed=embed, view=self.leaderboard_view
                )
            except Exception as e:
                log.error(f"Lỗi cập nhật Leaderboard gốc: {e}")

        # --- Xóa panel chọn ngày ẩn ---
        try:
            await interaction.response.edit_message(
                content="✅ **Đã áp dụng bộ lọc thành công!** Panel này sẽ tự biến mất.",
                view=None,
            )
            # Xóa hẳn tin nhắn ephemeral sau 2 giây
            if interaction.message:
                await interaction.message.delete(delay=2)
        except Exception:
            pass

    async def on_timeout(self):
        # Tự hủy panel khi hết thời gian
        self.stop()


# =============================================================================
# MENU THẢ XUỐNG: TIÊU CHÍ SẮP XẾP (Leaderboard chính)
# =============================================================================

class SortSelect(discord.ui.Select):
    """Menu chọn tiêu chí sắp xếp"""

    def __init__(self, current_sort: str = "rating"):
        options = [
            discord.SelectOption(
                label="⭐ Xếp theo Điểm Đánh Giá",
                description="Mặc định — Rating cao nhất lên đầu",
                value="rating",
                emoji="⭐",
                default=(current_sort == "rating"),
            ),
            discord.SelectOption(
                label="✉️ Xếp theo Tin Nhắn Đã Gửi",
                description="Staff gửi nhiều tin nhắn nhất lên đầu",
                value="messages",
                emoji="✉️",
                default=(current_sort == "messages"),
            ),
            discord.SelectOption(
                label="💬 Xếp theo Tin Nhắn Được Phản Hồi",
                description="Staff nhận nhiều reply nhất lên đầu",
                value="replies",
                emoji="💬",
                default=(current_sort == "replies"),
            ),
        ]
        super().__init__(
            placeholder="📈 Chọn tiêu chí sắp xếp...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None and isinstance(self.view, LeaderboardView)
        view: LeaderboardView = self.view
        view.current_sort = self.values[0]

        for opt in self.options:
            opt.default = (opt.value == view.current_sort)

        await view.refresh(interaction)


# =============================================================================
# MENU THẢ XUỐNG: LỌC CHỨC VỤ (Leaderboard chính)
# =============================================================================

class RoleFilterSelect(discord.ui.Select):
    """Menu lọc theo chức vụ"""

    def __init__(self, current_role: str = "all"):
        options = [
            discord.SelectOption(
                label="Tất cả chức vụ",
                description="Hiển thị toàn bộ nhân sự",
                value="all",
                emoji="🏆",
                default=(current_role == "all"),
            ),
            discord.SelectOption(
                label="Chỉ hiện Owner",
                description="Lọc chỉ Chủ sở hữu server",
                value="owner",
                emoji="👑",
                default=(current_role == "owner"),
            ),
            discord.SelectOption(
                label="Chỉ hiện Admin",
                description="Lọc chỉ Quản trị viên",
                value="admin",
                emoji="🛡️",
                default=(current_role == "admin"),
            ),
            discord.SelectOption(
                label="Chỉ hiện Recep",
                description="Lọc chỉ Lễ tân chào đón",
                value="recep",
                emoji="🌸",
                default=(current_role == "recep"),
            ),
            discord.SelectOption(
                label="Chỉ hiện Supporter",
                description="Lọc chỉ Supporter",
                value="supporter",
                emoji="💜",
                default=(current_role == "supporter"),
            ),
        ]
        super().__init__(
            placeholder="🗂️ Lọc theo chức vụ...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None and isinstance(self.view, LeaderboardView)
        view: LeaderboardView = self.view
        view.current_role = self.values[0]

        for opt in self.options:
            opt.default = (opt.value == view.current_role)

        await view.refresh(interaction)


# =============================================================================
# LEADERBOARD VIEW CHÍNH
# =============================================================================

class LeaderboardView(discord.ui.View):
    """View Leaderboard với 2 menu lọc tương tác + nút mở panel chọn khoảng ngày"""

    def __init__(
        self,
        dt_start: datetime,
        dt_end: datetime,
        current_sort: str = "rating",
        current_role: str = "all",
    ):
        super().__init__(timeout=300)
        self.message: Optional[discord.Message] = None
        self.dt_start = dt_start
        self.dt_end = dt_end
        self.current_sort = current_sort
        self.current_role = current_role

        self.add_item(SortSelect(current_sort))
        self.add_item(RoleFilterSelect(current_role))

    async def refresh(self, interaction: discord.Interaction):
        """Query DB real-time và cập nhật embed"""
        bot: Any = interaction.client
        data = await _fetch_leaderboard_data(
            bot, self.dt_start, self.dt_end, self.current_sort, self.current_role
        )
        embed = _build_leaderboard_embed(
            data, self.current_sort, self.current_role, self.dt_start, self.dt_end
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📅 Chọn Khoảng Ngày", style=discord.ButtonStyle.secondary, row=2)
    async def date_filter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Gửi panel chọn khoảng ngày dạng ephemeral với Dropdown tháng"""
        panel_view = DateSelectionView(leaderboard_view=self)
        await interaction.response.send_message(
            "📅 **Chọn khoảng thời gian bạn muốn xem Bảng Xếp Hạng:**\n"
            "Hãy chọn **Tháng Bắt Đầu** và **Tháng Kết Thúc**, sau đó nhấn nút **🔎 Áp Dụng Bộ Lọc**.",
            view=panel_view,
            ephemeral=True,
        )

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# =============================================================================
# COG LỆNH LEADERBOARD
# =============================================================================

class StaffLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="top", aliases=["lb", "bxh", "leaderboard"])
    async def leaderboard_cmd(self, ctx: commands.Context):
        """
        Lệnh hiển thị Bảng Xếp Hạng Nhân Sự.
        Mặc định: Tuần hiện tại. Dùng nút 📅 để đổi khoảng ngày.
        """
        dt_start, dt_end = _get_current_week_range()

        data = await _fetch_leaderboard_data(self.bot, dt_start, dt_end, "rating", "all")

        if not data:
            date_str = f"{_format_date(dt_start)} — {_format_date(dt_end)}"
            await ctx.send(
                f"📭 **Không có dữ liệu nhân sự nào trong khoảng thời gian {date_str}!**"
            )
            return

        embed = _build_leaderboard_embed(data, "rating", "all", dt_start, dt_end)
        view = LeaderboardView(dt_start, dt_end)
        view.message = await ctx.send(embed=embed, view=view)
        log.info(
            f"🏆 {ctx.author.display_name} vừa mở Bảng Xếp Hạng "
            f"({_format_date(dt_start)} — {_format_date(dt_end)})."
        )


async def setup(bot):
    await bot.add_cog(StaffLeaderboardCog(bot))
