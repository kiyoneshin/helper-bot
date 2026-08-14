import discord
from discord.ext import commands
import logging
import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from cogs.common.db import query_db

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

RANK_MEDALS = ["<:symbol_medal_gold:1537550996664885328>", "<:symbol_medal_silver:1537552840514347048>", "<:symbol_medal_bronze:1537552838412992712>"]
ROLE_LABELS = {
    "all": "Tất Cả Chức Vụ",
    "owner": "Owner <:lb_06_godly:1535552639834783764>",
    "admin": "Admin 🛡️",
    "recep": "Recep 🌸",
    "supporter": "Supporter 💜",
}
SORT_LABELS = {
    "rating": "Điểm Đánh Giá",
    "messages": "Tin Nhắn Đã Gửi",
    "replies": "Tin Nhắn Được Phản Hồi",
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
        title="<:symbol_trophy:1537550568665649232> Bảng Xếp Hạng Staff Angelic",
        description=(
            f"<:symbol_boards:1536007665153474681> **Khoảng thời gian:** {date_range_str}\n"
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
                f"• <a:symbol_star_yellow:1537739289834553385> **Điểm TB:** `{rating:.1f}/5.0` • **Tin nhắn:** `{msg_count}` • **Reply:** `{replies}`"
            ),
            inline=False,
        )

    embed.set_footer(text=f"Angelic Bot • Hiển thị Top {len(top_records)}/{len(records)} nhân sự 🌸")
    return embed


# =============================================================================
# MODAL NHẬP NGÀY
# =============================================================================

class StartDayModal(discord.ui.Modal, title="Nhập Ngày Bắt Đầu"):
    """Modal pop-up để người dùng nhập ngày bắt đầu bằng bàn phím."""

    day_input = discord.ui.TextInput(
        label="Ngày bắt đầu (nhập số nguyên, VD: 15)",
        placeholder="Nhập một số từ 1 đến 31...",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, date_view: "DateSelectionView"):
        super().__init__()
        self.date_view = date_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.day_input.value.strip()

        # Kiểm tra định dạng số nguyên dương
        try:
            day = int(raw)
            if day <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"**Giá trị không hợp lệ:** `{raw}` không phải số nguyên dương. "
                "Vui lòng bấm lại nút nhập ngày để điền lại.",
                ephemeral=True,
            )
            return

        # Kiểm tra ngày tối đa của tháng
        month_val = self.date_view.start_month
        if not month_val:
            await interaction.response.send_message("Vui lòng chọn Tháng Bắt Đầu trước!", ephemeral=True)
            return
            
        mm, yyyy = int(month_val.split("-")[0]), int(month_val.split("-")[1])
        max_day = calendar.monthrange(yyyy, mm)[1]

        if day > max_day:
            await interaction.response.send_message(
                f"**Lỗi ngày:** Tháng {mm:02d}/{yyyy} chỉ có tối đa **{max_day}** ngày! "
                "Vui lòng bấm lại nút nhập ngày để điền lại.",
                ephemeral=True,
            )
            return

        # Hợp lệ → lưu và cập nhật embed panel
        self.date_view.start_day = day
        await interaction.response.edit_message(
            embed=self.date_view._build_status_embed(),
            view=self.date_view,
        )


class EndDayModal(discord.ui.Modal, title="Nhập Ngày Kết Thúc"):
    """Modal pop-up để người dùng nhập ngày kết thúc bằng bàn phím."""

    day_input = discord.ui.TextInput(
        label="Ngày kết thúc (nhập số nguyên, VD: 28)",
        placeholder="Nhập một số từ 1 đến 31...",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, date_view: "DateSelectionView"):
        super().__init__()
        self.date_view = date_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.day_input.value.strip()

        # Kiểm tra định dạng số nguyên dương
        try:
            day = int(raw)
            if day <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"**Giá trị không hợp lệ:** `{raw}` không phải số nguyên dương. "
                "Vui lòng bấm lại nút nhập ngày để điền lại.",
                ephemeral=True,
            )
            return

        # Kiểm tra ngày tối đa của tháng
        month_val = self.date_view.end_month
        if not month_val:
            await interaction.response.send_message("Vui lòng chọn Tháng Kết Thúc trước!", ephemeral=True)
            return

        mm, yyyy = int(month_val.split("-")[0]), int(month_val.split("-")[1])
        max_day = calendar.monthrange(yyyy, mm)[1]

        if day > max_day:
            await interaction.response.send_message(
                f"**Lỗi ngày:** Tháng {mm:02d}/{yyyy} chỉ có tối đa **{max_day}** ngày! "
                "Vui lòng bấm lại nút nhập ngày để điền lại.",
                ephemeral=True,
            )
            return

        # Hợp lệ → lưu và cập nhật embed panel
        self.date_view.end_day = day
        await interaction.response.edit_message(
            embed=self.date_view._build_status_embed(),
            view=self.date_view,
        )


# =============================================================================
# DATE SELECTION VIEW — DROPDOWN THÁNG + MODAL NGÀY + 3 NÚT BẤM
# =============================================================================

class DateSelectionView(discord.ui.View):
    """

    Panel chọn khoảng ngày trên MỘT màn hình duy nhất, gồm:

      - Row 0: Dropdown chọn Tháng Bắt Đầu  (độc lập)

      - Row 1: Dropdown chọn Tháng Kết Thúc (độc lập)

      - Row 2: [ Chọn Ngày Bắt Đầu] [ Chọn Ngày Kết Thúc] [ Áp Dụng Bộ Lọc]



    Gửi dạng ephemeral. Sau khi áp dụng thành công sẽ tự xóa.

    """

    def __init__(self, leaderboard_view: "LeaderboardView"):
        super().__init__(timeout=300)
        self.leaderboard_view = leaderboard_view

        # 4 biến trạng thái HOÀN TOÀN ĐỘC LẬP
        self.start_month: Optional[str] = None   # "MM-YYYY"
        self.end_month: Optional[str] = None     # "MM-YYYY"
        self.start_day: Optional[int] = None
        self.end_day: Optional[int] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # XÂY DỰNG GIAO DIỆN (1 LẦN DUY NHẤT)
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Dựng toàn bộ giao diện: 2 dropdown tháng + 3 nút bấm."""
        self.clear_items()

        # ── ROW 0: Dropdown Tháng Bắt Đầu ─────────────────────────────
        start_sel = discord.ui.Select(
            placeholder="<:symbol_boards:1536007665153474681> Chọn Tháng Bắt Đầu...",
            min_values=1, max_values=1,
            options=_generate_month_options(),
            row=0,
        )
        start_sel.callback = self._on_start_month_select
        self.add_item(start_sel)

        # ── ROW 1: Dropdown Tháng Kết Thúc ────────────────────────────
        end_sel = discord.ui.Select(
            placeholder="<:symbol_boards:1536007665153474681> Chọn Tháng Kết Thúc...",
            min_values=1, max_values=1,
            options=_generate_month_options(),
            row=1,
        )
        end_sel.callback = self._on_end_month_select
        self.add_item(end_sel)

        # ── ROW 2: Nút 1 — Chọn Ngày Bắt Đầu ─────────────────────────
        btn_start_day = discord.ui.Button(
            label="<:symbol_boards:1536007665153474681> Chọn Ngày Bắt Đầu",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        btn_start_day.callback = self._on_open_start_day_modal
        self.add_item(btn_start_day)

        # ── ROW 2: Nút 2 — Chọn Ngày Kết Thúc ────────────────────────
        btn_end_day = discord.ui.Button(
            label="<:symbol_boards:1536007665153474681> Chọn Ngày Kết Thúc",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        btn_end_day.callback = self._on_open_end_day_modal
        self.add_item(btn_end_day)

        # ── ROW 2: Nút 3 — Áp Dụng Bộ Lọc ───────────────────────────
        btn_apply = discord.ui.Button(
            label="🔎 Áp Dụng Bộ Lọc",
            style=discord.ButtonStyle.success,
            row=2,
        )
        btn_apply.callback = self._on_apply
        self.add_item(btn_apply)

    # ------------------------------------------------------------------
    # EMBED TRẠNG THÁI (cập nhật realtime sau mỗi hành động)
    # ------------------------------------------------------------------

    def _build_status_embed(self) -> discord.Embed:
        """
        Tạo embed hiển thị trạng thái lựa chọn hiện tại của người dùng.
        Cập nhật sau mỗi lần chọn tháng hoặc nhập ngày thành công.
        """
        def _fmt_part(month: Optional[str], day: Optional[int]) -> str:
            if month and day:
                mm, yyyy = month.split("-")
                return f"Ngày **{day:02d}** Tháng **{mm}/{yyyy}**"
            elif month:
                mm, yyyy = month.split("-")
                return f"Tháng **{mm}/{yyyy}** *(chưa nhập ngày)*"
            else:
                return "*Chưa chọn*"

        start_str = _fmt_part(self.start_month, self.start_day)
        end_str   = _fmt_part(self.end_month, self.end_day)

        lines = [
            "🗂️ **Hướng dẫn:**",
            "1️⃣ Chọn **Tháng Bắt Đầu** và **Tháng Kết Thúc** ở menu phía trên.",
            "2️⃣ Bấm **<:symbol_boards:1536007665153474681> Chọn Ngày Bắt Đầu** / **<:symbol_boards:1536007665153474681> Chọn Ngày Kết Thúc** để nhập ngày.",
            "3️⃣ Bấm **🔎 Áp Dụng Bộ Lọc** khi đã điền đủ 4 trường.",
            "",
            "――――――――――――――――――――",
            f"▶️ **Bắt đầu:** {start_str}",
            f"⏹️ **Kết thúc:** {end_str}",
        ]

        embed = discord.Embed(
            title="<:symbol_boards:1536007665153474681> Chọn Khoảng Thời Gian Bảng Xếp Hạng",
            description="\n".join(lines),
            color=0xffb6c1,
        )
        embed.set_footer(text="Bạn có thể chỉnh sửa lại bất cứ lúc nào trước khi áp dụng.")
        return embed

    # ------------------------------------------------------------------
    # CALLBACK DROPDOWN THÁNG (ĐỘC LẬP HOÀN TOÀN)
    # ------------------------------------------------------------------

    async def _on_start_month_select(self, interaction: discord.Interaction):
        """Chỉ cập nhật self.start_month, KHÔNG động đến end_month."""
        self.start_month = interaction.data["values"][0]  # type: ignore[index]
        # Đánh dấu default trên đúng dropdown row=0
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 0:
                for opt in item.options:
                    opt.default = (opt.value == self.start_month)
        await interaction.response.edit_message(
            embed=self._build_status_embed(),
            view=self,
        )

    async def _on_end_month_select(self, interaction: discord.Interaction):
        """Chỉ cập nhật self.end_month, KHÔNG động đến start_month."""
        self.end_month = interaction.data["values"][0]  # type: ignore[index]
        # Đánh dấu default trên đúng dropdown row=1
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.row == 1:
                for opt in item.options:
                    opt.default = (opt.value == self.end_month)
        await interaction.response.edit_message(
            embed=self._build_status_embed(),
            view=self,
        )

    # ------------------------------------------------------------------
    # CALLBACK NÚT MỞ MODAL NHẬP NGÀY
    # ------------------------------------------------------------------

    async def _on_open_start_day_modal(self, interaction: discord.Interaction):
        """Bẫy lỗi thiếu tháng → mở StartDayModal nếu đã có tháng."""
        if not self.start_month:
            await interaction.response.send_message(
                "Vui lòng chọn **Tháng Bắt Đầu** ở menu phía trên trước!",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(StartDayModal(date_view=self))

    async def _on_open_end_day_modal(self, interaction: discord.Interaction):
        """Bẫy lỗi thiếu tháng → mở EndDayModal nếu đã có tháng."""
        if not self.end_month:
            await interaction.response.send_message(
                "Vui lòng chọn **Tháng Kết Thúc** ở menu phía trên trước!",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(EndDayModal(date_view=self))

    # ------------------------------------------------------------------
    # CALLBACK NÚT ÁP DỤNG BỘ LỌC
    # ------------------------------------------------------------------

    async def _on_apply(self, interaction: discord.Interaction):
        """
        Kiểm tra đầy đủ 4 trường → dựng datetime UTC+7 →
        kiểm tra start <= end → refresh leaderboard → xóa panel.
        """
        # 1. Kiểm tra thiếu dữ liệu
        missing: list[str] = []
        if not self.start_month:
            missing.append("Tháng Bắt Đầu")
        if self.start_day is None:
            missing.append("Ngày Bắt Đầu")
        if not self.end_month:
            missing.append("Tháng Kết Thúc")
        if self.end_day is None:
            missing.append("Ngày Kết Thúc")

        start_month_val = self.start_month
        end_month_val = self.end_month

        if missing or not start_month_val or not end_month_val or self.start_day is None or self.end_day is None:
            missing_str = ", ".join(f"**{m}**" for m in missing)
            await interaction.response.send_message(
                f"Bạn chưa điền đầy đủ thông tin! Còn thiếu: {missing_str}.\n"
                "Vui lòng hoàn thiện tất cả 4 trường trước khi áp dụng.",
                ephemeral=True,
            )
            return

        # 2. Dựng 2 đối tượng datetime UTC+7
        s_mm   = int(start_month_val.split("-")[0])
        s_yyyy = int(start_month_val.split("-")[1])
        e_mm   = int(end_month_val.split("-")[0])
        e_yyyy = int(end_month_val.split("-")[1])

        dt_start = datetime(s_yyyy, s_mm, self.start_day, 0, 0, 0, tzinfo=UTC7)
        dt_end   = datetime(e_yyyy, e_mm, self.end_day, 23, 59, 59, tzinfo=UTC7)

        # 3. Kiểm tra tính hợp lệ khoảng thời gian (kể cả xuyên năm)
        if dt_start > dt_end:
            await interaction.response.send_message(
                "**Lỗi cấu hình thời gian:** Khoảng thời gian bắt đầu không hợp lý!\n"
                "Ngày/Tháng kết thúc phải diễn ra **sau hoặc trùng** với Ngày/Tháng bắt đầu.\n"
                f"📌 Hiện tại: **{_format_date(dt_start)}** > **{_format_date(dt_end)}**\n"
                "Hãy dùng các dropdown/nút bên trên để điều chỉnh lại.",
                ephemeral=True,
            )
            # Giữ nguyên giao diện, KHÔNG xóa panel
            return

        # 4. Mọi kiểm tra qua → cập nhật LeaderboardView gốc và refresh
        self.leaderboard_view.dt_start = dt_start
        self.leaderboard_view.dt_end   = dt_end

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

        # Cập nhật tin nhắn Leaderboard gốc trên kênh chung
        if self.leaderboard_view.message:
            try:
                await self.leaderboard_view.message.edit(embed=embed, view=self.leaderboard_view)
            except Exception as e:
                log.error(f"Lỗi cập nhật Leaderboard gốc: {e}")

        # 5. Xóa panel chọn ngày ephemeral
        try:
            await interaction.response.edit_message(
                content="<:symbol_right:1536629912515903578> **Đã áp dụng thành công!** Panel này sẽ tự đóng.",
                embed=None,
                view=None,
            )
            if interaction.message:
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
            discord.SelectOption(label="<a:symbol_star_yellow:1537739289834553385> Xếp theo Điểm Đánh Giá", description="Rating cao nhất lên đầu", value="rating", emoji="<a:symbol_star_yellow:1537739289834553385>", default=(current_sort == "rating")),
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
            discord.SelectOption(label="Tất cả chức vụ", description="Hiển thị toàn bộ nhân sự", value="all", emoji="<:symbol_trophy:1537550568665649232>", default=(current_role == "all")),
            discord.SelectOption(label="Chỉ hiện Owner", description="Lọc chỉ Chủ sở hữu server", value="owner", emoji="<:lb_06_godly:1535552639834783764>", default=(current_role == "owner")),
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

    @discord.ui.button(label="Chọn Khoảng Ngày", style=discord.ButtonStyle.secondary, row=2)
    async def date_filter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mở panel chọn khoảng ngày (Dropdown Tháng + Modal Ngày) dạng ephemeral."""
        panel = DateSelectionView(leaderboard_view=self)
        await interaction.response.send_message(
            embed=panel._build_status_embed(),
            view=panel,
            ephemeral=True,
        )

    @discord.ui.button(label="Reset Bộ Lọc", style=discord.ButtonStyle.danger, row=2, emoji="<:symbol_reload:1536007679640600648>")
    async def reset_filter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset toàn bộ bộ lọc về mặc định (Tuần hiện tại, Xếp hạng: Rating, Chức vụ: Tất cả)."""
        self.dt_start, self.dt_end = _get_current_week_range()
        self.current_sort = "rating"
        self.current_role = "all"

        # Update default options in the selects
        for item in self.children:
            if isinstance(item, SortSelect):
                for opt in item.options:
                    opt.default = (opt.value == "rating")
            elif isinstance(item, RoleFilterSelect):
                for opt in item.options:
                    opt.default = (opt.value == "all")

        await self.refresh(interaction)

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

    @commands.hybrid_command(name="top", aliases=["bxh", "leaderboard"], description="Xem bảng xếp hạng nhân sự")
    async def leaderboard_cmd(self, ctx: commands.Context):
        """Bảng Xếp Hạng Nhân Sự. Mặc định: Tuần hiện tại. Nhấn để đổi khoảng ngày."""
        dt_start, dt_end = _get_current_week_range()
        data = await _fetch_leaderboard_data(self.bot, dt_start, dt_end, "rating", "all")

        if not data:
            await ctx.send(f"📭 **Không có dữ liệu nhân sự nào trong khoảng {_format_date(dt_start)} — {_format_date(dt_end)}!**")
            return

        embed = _build_leaderboard_embed(data, "rating", "all", dt_start, dt_end)
        view = LeaderboardView(dt_start, dt_end)
        view.message = await ctx.send(embed=embed, view=view)
        log.info(f"{ctx.author.display_name} vừa mở BXH ({_format_date(dt_start)} — {_format_date(dt_end)}).")


async def setup(bot):
    await bot.add_cog(StaffLeaderboardCog(bot))
