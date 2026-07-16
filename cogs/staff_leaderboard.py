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
    """Tính mốc đầu tuần (Thứ Hai) và cuối tuần (Chủ Nhật) theo UTC+7."""
    now = datetime.now(UTC7)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start_of_week, end_of_week


def _format_date(dt: datetime) -> str:
    """Format datetime thành DD/MM/YYYY"""
    return dt.strftime("%d/%m/%Y")


def _generate_month_options() -> list[discord.SelectOption]:
    """
    Sinh danh sách 18 tháng gần nhất từ tháng hiện tại lùi về quá khứ.
    label: "Tháng MM/YYYY", value: "MM-YYYY".
    """
    now = datetime.now(UTC7)
    options = []
    for i in range(18):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        label = f"Tháng {month:02d}/{year}"
        value = f"{month:02d}-{year}"
        options.append(discord.SelectOption(label=label, value=value))
    return options


def _month_val_to_first_day(month_val: str) -> datetime:
    """Chuyển "MM-YYYY" thành datetime ngày đầu tháng 00:00:00 UTC+7."""
    month, year = int(month_val.split("-")[0]), int(month_val.split("-")[1])
    return datetime(year, month, 1, 0, 0, 0, tzinfo=UTC7)


def _month_val_to_last_day(month_val: str) -> datetime:
    """Chuyển "MM-YYYY" thành datetime ngày cuối tháng 23:59:59 UTC+7."""
    month, year = int(month_val.split("-")[0]), int(month_val.split("-")[1])
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59, tzinfo=UTC7)


def _get_days_in_month(month_val: str) -> int:
    """Trả về số ngày trong tháng từ giá trị "MM-YYYY"."""
    month, year = int(month_val.split("-")[0]), int(month_val.split("-")[1])
    return calendar.monthrange(year, month)[1]


def _make_day_options(month_val: str, page: str) -> list[discord.SelectOption]:
    """
    Tạo danh sách SelectOption cho các ngày trong tháng, chia 2 trang:
    - page "1-15"  → ngày 01 đến 15
    - page "16-31" → ngày 16 đến ngày cuối tháng thực tế (dùng calendar)
    """
    days_in_month = _get_days_in_month(month_val)
    if page == "1-15":
        days = range(1, 16)
    else:
        days = range(16, days_in_month + 1)
    return [
        discord.SelectOption(label=f"Ngày {d:02d}", value=str(d))
        for d in days
    ]


def _month_label(month_val: str) -> str:
    """Chuyển "MM-YYYY" thành "Tháng MM/YYYY" để hiển thị."""
    month, year = month_val.split("-")
    return f"Tháng {month}/{year}"


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
    """Truy vấn DB (LEFT JOIN profiles + staff_message_logs) trả về list đã lọc/sắp xếp."""
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

    if role_filter != "all":
        data = [r for r in data if str(r.get("role", "")).lower().strip() == role_filter]

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
    """Tạo Embed bảng xếp hạng Top 10."""
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

        embed.add_field(
            name=f"{medal} #{rank_num} — {name}",
            value=(
                f"• **Chức vụ:** `{role}` • <@{discord_id}>\n"
                f"• ⭐ **Điểm TB:** `{rating:.1f}/5.0` • ✉️ **Tin nhắn:** `{msg_count}` • 💬 **Reply:** `{replies}`"
            ),
            inline=False,
        )

    embed.set_footer(text=f"Angelic Bot • Hiển thị Top {len(top_records)}/{len(records)} nhân sự 🌸")
    return embed


# =============================================================================
# DATE SELECTION VIEW — QUY TRÌNH 2 BƯỚC
# =============================================================================

class DateSelectionView(discord.ui.View):
    """
    Panel chọn khoảng ngày 2 bước hoàn toàn bằng Dropdown.
    Gửi dạng ephemeral, sau khi xác nhận sẽ tự xóa.

    Bước 1: Chọn Tháng Bắt Đầu + Tháng Kết Thúc
    Bước 2: Chọn Ngày Bắt Đầu + Ngày Kết Thúc (chia trang 1-15 / 16-31)
    """

    def __init__(self, leaderboard_view: "LeaderboardView"):
        super().__init__(timeout=180)
        self.leaderboard_view = leaderboard_view
        # Trạng thái lựa chọn
        self.start_month: Optional[str] = None   # "MM-YYYY"
        self.end_month: Optional[str] = None     # "MM-YYYY"
        self.start_day: Optional[int] = None
        self.end_day: Optional[int] = None
        self.day_page: str = "1-15"              # "1-15" hoặc "16-31"
        self.current_step: int = 1               # 1 hoặc 2

        # Khởi tạo Bước 1
        self._build_step1()

    # ------------------------------------------------------------------
    # XÂY DỰNG GIAO DIỆN
    # ------------------------------------------------------------------

    def _build_step1(self):
        """Xóa toàn bộ items hiện tại và dựng lại giao diện Bước 1."""
        self.clear_items()
        self.current_step = 1
        self.start_day = None
        self.end_day = None

        month_opts = _generate_month_options()

        # Dropdown 1: Chọn Tháng Bắt Đầu (row 0)
        start_sel = discord.ui.Select(
            placeholder="📅 Chọn Tháng Bắt Đầu...",
            min_values=1, max_values=1,
            options=month_opts,
            row=0,
        )
        start_sel.callback = self._on_start_month_select
        self.add_item(start_sel)

        # Dropdown 2: Chọn Tháng Kết Thúc (row 1)
        end_sel = discord.ui.Select(
            placeholder="📅 Chọn Tháng Kết Thúc...",
            min_values=1, max_values=1,
            options=month_opts,
            row=1,
        )
        end_sel.callback = self._on_end_month_select
        self.add_item(end_sel)

        # Nút tiếp tục (row 2)
        next_btn = discord.ui.Button(
            label="Tiếp Tục Chọn Ngày ➡️",
            style=discord.ButtonStyle.primary,
            row=2,
        )
        next_btn.callback = self._on_next_to_step2
        self.add_item(next_btn)

    def _build_step2(self):
        """Xóa toàn bộ items và dựng lại giao diện Bước 2."""
        self.clear_items()
        self.current_step = 2
        self.start_day = None
        self.end_day = None

        # Dropdown chọn Ngày Bắt Đầu (row 0)
        start_day_opts = _make_day_options(self.start_month, self.day_page)  # type: ignore[arg-type]
        start_day_sel = discord.ui.Select(
            placeholder=f"📅 Chọn Ngày Bắt Đầu ({self.day_page})...",
            min_values=1, max_values=1,
            options=start_day_opts,
            row=0,
        )
        start_day_sel.callback = self._on_start_day_select
        self.add_item(start_day_sel)

        # Dropdown chọn Ngày Kết Thúc (row 1)
        end_day_opts = _make_day_options(self.end_month, self.day_page)  # type: ignore[arg-type]
        end_day_sel = discord.ui.Select(
            placeholder=f"📅 Chọn Ngày Kết Thúc ({self.day_page})...",
            min_values=1, max_values=1,
            options=end_day_opts,
            row=1,
        )
        end_day_sel.callback = self._on_end_day_select
        self.add_item(end_day_sel)

        # Nút đổi trang ngày (row 2)
        toggle_label = "📅 Đổi sang ngày 16-31" if self.day_page == "1-15" else "📅 Đổi sang ngày 01-15"
        toggle_btn = discord.ui.Button(
            label=toggle_label,
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        toggle_btn.callback = self._on_toggle_page
        self.add_item(toggle_btn)

        # Nút Quay Lại Bước 1 (row 3)
        back_btn = discord.ui.Button(
            label="⬅️ Quay Lại Chọn Tháng",
            style=discord.ButtonStyle.danger,
            row=3,
        )
        back_btn.callback = self._on_back_to_step1
        self.add_item(back_btn)

        # Nút Áp Dụng (row 3)
        apply_btn = discord.ui.Button(
            label="🔎 Áp Dụng Bộ Lọc",
            style=discord.ButtonStyle.success,
            row=3,
        )
        apply_btn.callback = self._on_apply
        self.add_item(apply_btn)

    def _step2_embed(self) -> discord.Embed:
        """Tạo embed hướng dẫn cho Bước 2."""
        return discord.Embed(
            title="📅 Bước 2: Chọn Ngày Cụ Thể",
            description=(
                f"Bạn đang chọn khoảng thời gian từ "
                f"**{_month_label(self.start_month)}** "  # type: ignore[arg-type]
                f"đến **{_month_label(self.end_month)}**.\n\n"  # type: ignore[arg-type]
                f"Hãy chọn **Ngày Bắt Đầu** và **Ngày Kết Thúc** trong tháng tương ứng.\n"
                f"*Dùng nút **Đổi trang** để chuyển giữa ngày 01–15 và 16–{_get_days_in_month(self.start_month)}.*"  # type: ignore[arg-type]
            ),
            color=0xffb6c1,
        )

    # ------------------------------------------------------------------
    # CALLBACK BƯỚC 1
    # ------------------------------------------------------------------

    async def _on_start_month_select(self, interaction: discord.Interaction):
        select: discord.ui.Select = interaction.data  # type: ignore[assignment]
        # Lấy giá trị từ component
        self.start_month = interaction.data["values"][0]  # type: ignore[index]
        # Cập nhật default trên dropdown
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 0:
                for opt in item.options:
                    opt.default = (opt.value == self.start_month)
        await interaction.response.edit_message(view=self)

    async def _on_end_month_select(self, interaction: discord.Interaction):
        self.end_month = interaction.data["values"][0]  # type: ignore[index]
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 1:
                for opt in item.options:
                    opt.default = (opt.value == self.end_month)
        await interaction.response.edit_message(view=self)

    async def _on_next_to_step2(self, interaction: discord.Interaction):
        """Xử lý nút 'Tiếp Tục Chọn Ngày': validate → chuyển Bước 2."""
        # Kiểm tra đã chọn đủ chưa
        if not self.start_month or not self.end_month:
            await interaction.response.send_message(
                "⚠️ **Vui lòng chọn đầy đủ cả Tháng Bắt Đầu và Tháng Kết Thúc!**",
                ephemeral=True,
            )
            return

        # Kiểm tra thứ tự tháng
        first_of_start = _month_val_to_first_day(self.start_month)
        first_of_end = _month_val_to_first_day(self.end_month)
        if first_of_start > first_of_end:
            await interaction.response.send_message(
                "⚠️ **Lỗi:** Tháng kết thúc phải diễn ra sau hoặc trùng với tháng bắt đầu!\n"
                f"📌 Bạn chọn: **{_month_label(self.start_month)}** → **{_month_label(self.end_month)}**",
                ephemeral=True,
            )
            return

        # Chuyển sang Bước 2
        self.day_page = "1-15"
        self._build_step2()
        await interaction.response.edit_message(
            content=None,
            embed=self._step2_embed(),
            view=self,
        )

    # ------------------------------------------------------------------
    # CALLBACK BƯỚC 2
    # ------------------------------------------------------------------

    async def _on_start_day_select(self, interaction: discord.Interaction):
        self.start_day = int(interaction.data["values"][0])  # type: ignore[index]
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 0:
                for opt in item.options:
                    opt.default = (opt.value == str(self.start_day))
        await interaction.response.edit_message(view=self)

    async def _on_end_day_select(self, interaction: discord.Interaction):
        self.end_day = int(interaction.data["values"][0])  # type: ignore[index]
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 1:
                for opt in item.options:
                    opt.default = (opt.value == str(self.end_day))
        await interaction.response.edit_message(view=self)

    async def _on_toggle_page(self, interaction: discord.Interaction):
        """Đổi trang ngày giữa 1-15 và 16-cuối tháng, reset lựa chọn ngày."""
        self.day_page = "16-31" if self.day_page == "1-15" else "1-15"
        self.start_day = None
        self.end_day = None
        self._build_step2()
        await interaction.response.edit_message(
            embed=self._step2_embed(),
            view=self,
        )

    async def _on_back_to_step1(self, interaction: discord.Interaction):
        """Quay lại Bước 1."""
        self._build_step1()
        await interaction.response.edit_message(
            content="📅 **Chọn khoảng thời gian bạn muốn xem Bảng Xếp Hạng:**",
            embed=None,
            view=self,
        )

    async def _on_apply(self, interaction: discord.Interaction):
        """Xử lý nút 'Áp Dụng Bộ Lọc': validate → refresh leaderboard → xóa panel."""
        # Kiểm tra đã chọn ngày chưa
        if self.start_day is None or self.end_day is None:
            await interaction.response.send_message(
                "⚠️ **Vui lòng chọn đầy đủ cả Ngày Bắt Đầu và Ngày Kết Thúc!**",
                ephemeral=True,
            )
            return

        # Ghép datetime đầy đủ UTC+7
        s_month = int(self.start_month.split("-")[0])   # type: ignore[union-attr]
        s_year  = int(self.start_month.split("-")[1])   # type: ignore[union-attr]
        e_month = int(self.end_month.split("-")[0])     # type: ignore[union-attr]
        e_year  = int(self.end_month.split("-")[1])     # type: ignore[union-attr]

        dt_start = datetime(s_year, s_month, self.start_day, 0, 0, 0, tzinfo=UTC7)
        dt_end   = datetime(e_year, e_month, self.end_day, 23, 59, 59, tzinfo=UTC7)

        # Kiểm tra thứ tự ngày
        if dt_start > dt_end:
            await interaction.response.send_message(
                f"⚠️ **Lỗi:** Ngày kết thúc phải diễn ra sau hoặc trùng với ngày bắt đầu!\n"
                f"📌 Hiện tại: **{_format_date(dt_start)}** > **{_format_date(dt_end)}**\n"
                f"Hãy dùng các dropdown phía trên để chọn lại.",
                ephemeral=True,
            )
            return

        # Cập nhật LeaderboardView gốc và refresh
        self.leaderboard_view.dt_start = dt_start
        self.leaderboard_view.dt_end = dt_end

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
                await self.leaderboard_view.message.edit(embed=embed, view=self.leaderboard_view)
            except Exception as e:
                log.error(f"Lỗi cập nhật Leaderboard gốc: {e}")

        # Xóa panel chọn ngày ẩn
        try:
            await interaction.response.edit_message(
                content="✅ **Đã áp dụng thành công!** Panel này sẽ tự đóng.",
                embed=None,
                view=None,
            )
            if interaction.message:
                await interaction.message.delete(delay=2)
        except Exception:
            pass

    async def on_timeout(self):
        self.stop()


# =============================================================================
# MENU THẢ XUỐNG: TIÊU CHÍ SẮP XẾP
# =============================================================================

class SortSelect(discord.ui.Select):
    def __init__(self, current_sort: str = "rating"):
        options = [
            discord.SelectOption(label="⭐ Xếp theo Điểm Đánh Giá", description="Rating cao nhất lên đầu", value="rating", emoji="⭐", default=(current_sort == "rating")),
            discord.SelectOption(label="✉️ Xếp theo Tin Nhắn Đã Gửi", description="Gửi nhiều tin nhắn nhất lên đầu", value="messages", emoji="✉️", default=(current_sort == "messages")),
            discord.SelectOption(label="💬 Xếp theo Tin Nhắn Được Phản Hồi", description="Nhận nhiều reply nhất lên đầu", value="replies", emoji="💬", default=(current_sort == "replies")),
        ]
        super().__init__(placeholder="📈 Chọn tiêu chí sắp xếp...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None and isinstance(self.view, LeaderboardView)
        view: LeaderboardView = self.view
        view.current_sort = self.values[0]
        for opt in self.options:
            opt.default = (opt.value == view.current_sort)
        await view.refresh(interaction)


# =============================================================================
# MENU THẢ XUỐNG: LỌC CHỨC VỤ
# =============================================================================

class RoleFilterSelect(discord.ui.Select):
    def __init__(self, current_role: str = "all"):
        options = [
            discord.SelectOption(label="Tất cả chức vụ", description="Hiển thị toàn bộ nhân sự", value="all", emoji="🏆", default=(current_role == "all")),
            discord.SelectOption(label="Chỉ hiện Owner", description="Lọc chỉ Chủ sở hữu server", value="owner", emoji="👑", default=(current_role == "owner")),
            discord.SelectOption(label="Chỉ hiện Admin", description="Lọc chỉ Quản trị viên", value="admin", emoji="🛡️", default=(current_role == "admin")),
            discord.SelectOption(label="Chỉ hiện Recep", description="Lọc chỉ Lễ tân chào đón", value="recep", emoji="🌸", default=(current_role == "recep")),
            discord.SelectOption(label="Chỉ hiện Supporter", description="Lọc chỉ Supporter", value="supporter", emoji="💜", default=(current_role == "supporter")),
        ]
        super().__init__(placeholder="🗂️ Lọc theo chức vụ...", min_values=1, max_values=1, options=options, row=1)

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
    """View Bảng Xếp Hạng: 2 menu lọc + nút mở panel chọn khoảng ngày 2 bước."""

    def __init__(self, dt_start: datetime, dt_end: datetime, current_sort: str = "rating", current_role: str = "all"):
        super().__init__(timeout=300)
        self.message: Optional[discord.Message] = None
        self.dt_start = dt_start
        self.dt_end = dt_end
        self.current_sort = current_sort
        self.current_role = current_role
        self.add_item(SortSelect(current_sort))
        self.add_item(RoleFilterSelect(current_role))

    async def refresh(self, interaction: discord.Interaction):
        """Query DB real-time và cập nhật embed."""
        bot: Any = interaction.client
        data = await _fetch_leaderboard_data(bot, self.dt_start, self.dt_end, self.current_sort, self.current_role)
        embed = _build_leaderboard_embed(data, self.current_sort, self.current_role, self.dt_start, self.dt_end)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📅 Chọn Khoảng Ngày", style=discord.ButtonStyle.secondary, row=2)
    async def date_filter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mở panel chọn khoảng ngày 2 bước dạng ephemeral."""
        panel = DateSelectionView(leaderboard_view=self)
        await interaction.response.send_message(
            "📅 **Chọn khoảng thời gian bạn muốn xem Bảng Xếp Hạng:**\n"
            "Chọn **Tháng Bắt Đầu** và **Tháng Kết Thúc**, sau đó nhấn **Tiếp Tục Chọn Ngày ➡️**.",
            view=panel,
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
        """Bảng Xếp Hạng Nhân Sự. Mặc định: Tuần hiện tại. Nhấn 📅 để đổi khoảng ngày."""
        dt_start, dt_end = _get_current_week_range()
        data = await _fetch_leaderboard_data(self.bot, dt_start, dt_end, "rating", "all")

        if not data:
            await ctx.send(f"📭 **Không có dữ liệu nhân sự nào trong khoảng {_format_date(dt_start)} — {_format_date(dt_end)}!**")
            return

        embed = _build_leaderboard_embed(data, "rating", "all", dt_start, dt_end)
        view = LeaderboardView(dt_start, dt_end)
        view.message = await ctx.send(embed=embed, view=view)
        log.info(f"🏆 {ctx.author.display_name} vừa mở BXH ({_format_date(dt_start)} — {_format_date(dt_end)}).")


async def setup(bot):
    await bot.add_cog(StaffLeaderboardCog(bot))
