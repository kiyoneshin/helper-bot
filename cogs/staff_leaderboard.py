import discord
from discord.ext import commands
import logging
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
    # weekday(): 0=Mon ... 6=Sun
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
# MODAL POPUP LỌC NGÀY
# =============================================================================

class DateFilterModal(discord.ui.Modal, title="📅 Chọn Khoảng Ngày Lọc"):
    """Modal popup cho phép người dùng nhập khoảng ngày tùy chỉnh."""

    start_input = discord.ui.TextInput(
        label="Từ ngày (Định dạng: DD/MM/YYYY)",
        placeholder="Ví dụ: 20/06/2026",
        max_length=10,
        required=True,
    )
    end_input = discord.ui.TextInput(
        label="Đến ngày (Định dạng: DD/MM/YYYY)",
        placeholder="Ví dụ: 10/07/2026",
        max_length=10,
        required=True,
    )

    def __init__(self, leaderboard_view: "LeaderboardView"):
        super().__init__()
        self.leaderboard_view = leaderboard_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            dt_start, dt_end = _parse_date_range(
                self.start_input.value, self.end_input.value
            )
        except ValueError:
            await interaction.response.send_message(
                "⚠️ **Sai định dạng ngày!** Vui lòng nhập đúng dạng `DD/MM/YYYY`.\n"
                "📌 Ví dụ: `20/06/2026`",
                ephemeral=True,
            )
            return

        # Cập nhật khoảng thời gian trên View
        self.leaderboard_view.dt_start = dt_start
        self.leaderboard_view.dt_end = dt_end

        # Query DB real-time và render lại embed
        await self.leaderboard_view.refresh(interaction)


# =============================================================================
# MENU THẢ XUỐNG 1: TIÊU CHÍ SẮP XẾP
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

        # Cập nhật trạng thái default cho menu
        for opt in self.options:
            opt.default = (opt.value == view.current_sort)

        await view.refresh(interaction)


# =============================================================================
# MENU THẢ XUỐNG 2: LỌC CHỨC VỤ
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
# LEADERBOARD VIEW
# =============================================================================

class LeaderboardView(discord.ui.View):
    """View Leaderboard với 2 menu lọc tương tác + nút chọn khoảng ngày qua Modal"""

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
        """Mở Modal popup cho phép người dùng nhập khoảng ngày tùy chỉnh"""
        await interaction.response.send_modal(DateFilterModal(self))

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
