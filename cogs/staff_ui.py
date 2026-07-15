import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any

from cogs._staff_db import query_db, extract_id
from cogs._staff_embeds import get_main_embed
from cogs._staff_views import MainView, _normalize_votes

log = logging.getLogger("StaffBot")

# =============================================================================
# LEADERBOARD VIEW
# =============================================================================

RANK_MEDALS = ['🥇', '🥈', '🥉']


def _build_leaderboard_embed(
    records: list,
    sort_by: str,
    role_filter: str
) -> discord.Embed:
    """
    Tạo Embed bảng xế hạng từ danh sách records đã lọc/sắp xếp.
    sort_by: 'rating' | 'replies'
    role_filter: 'all' | 'owner' | 'admin' | 'recep'
    """
    # --- Lọc theo role ---
    if role_filter != 'all':
        records = [r for r in records if str(r.get('role', '')).lower().strip() == role_filter]

    # --- Sắp xếp ---
    if sort_by == 'replies':
        records = sorted(
            records,
            key=lambda r: (-(r.get('weekly_replies') or 0), -(float(r.get('rating') or 0)))
        )
    else:  # mặc định: sort by rating, tie-breaker: weekly_replies
        records = sorted(
            records,
            key=lambda r: (-(float(r.get('rating') or 0)), -(r.get('weekly_replies') or 0))
        )

    top_records = records[:10]

    # --- Tên tiêu đề ---
    role_label = {
        'all': 'Tất Cả Chức Vụ',
        'owner': 'Owner 👑',
        'admin': 'Admin 🛡️',
        'recep': 'Recep 🌸'
    }.get(role_filter, role_filter.upper())

    sort_label = 'Điểm Đánh Giá ⬇️' if sort_by == 'rating' else 'Tin Nhắn Phản Hồi ⬇️'

    embed = discord.Embed(
        title=f"🏆 Bảng Xế Hạng Staff Angelic",
        description=(
            f"🗂️ **Bộ lọc:** {role_label} • 📈 **Sắp xếp theo:** {sort_label}\n"
            f"――――――――――――――――――――"
        ),
        color=0xffb6c1
    )

    if not top_records:
        embed.add_field(
            name="👀 Không có dữ liệu",
            value="Không tìm thấy nhân sự nào phù hợp với bộ lọc này.",
            inline=False
        )
        embed.set_footer(text="Angelic Bot • Dùng menu bên dưới để thay đổi bộ lọc! 🌸")
        return embed

    for idx, row in enumerate(top_records):
        rank_num = idx + 1
        medal = RANK_MEDALS[idx] if idx < len(RANK_MEDALS) else f"`#{rank_num}`"

        name       = row.get('display_name', 'Unnamed')
        discord_id = row.get('discord_id', '?')
        role       = str(row.get('role', '')).upper()
        rating     = float(row.get('rating') or 0)
        replies    = int(row.get('weekly_replies') or 0)

        field_name  = f"{medal} #{rank_num} — {name}"
        field_value = (
            f"• **Chức vụ:** `{role}` • <@{discord_id}>\n"
            f"• ⭐ **Điểm TB:** `{rating:.1f}/5.0` • 💬 **Reply tuần:** `{replies}`"
        )
        embed.add_field(name=field_name, value=field_value, inline=False)

    embed.set_footer(text=f"Angelic Bot • Hiển thị Top {len(top_records)}/{len(records)} nhân sự 🌸")
    return embed


class LeaderboardFilterSelect(discord.ui.Select):
    """Menu lọc và sắp xếp Leaderboard"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="🏆 Xếp theo Điểm Đánh Giá (Mặc định)",
                description="Tất cả chức vụ, sắp theo rating giảm dần",
                value="all|rating",
                emoji="⭐",
                default=True
            ),
            discord.SelectOption(
                label="💬 Xếp theo Tin Nhắn Phản Hồi",
                description="Tất cả chức vụ, sắp theo số reply tuần giảm dần",
                value="all|replies",
                emoji="💬"
            ),
            discord.SelectOption(
                label="👑 Chỉ hiện Owner — Xếp theo Điểm",
                description="Lọc chỉ Owner, sắp theo rating",
                value="owner|rating",
                emoji="👑"
            ),
            discord.SelectOption(
                label="🛡️ Chỉ hiện Admin — Xếp theo Điểm",
                description="Lọc chỉ Admin, sắp theo rating",
                value="admin|rating",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="🌸 Chỉ hiện Recep — Xếp theo Điểm",
                description="Lọc chỉ Recep, sắp theo rating",
                value="recep|rating",
                emoji="🌸"
            ),
            discord.SelectOption(
                label="👑 Chỉ hiện Owner — Xếp theo Reply",
                description="Lọc chỉ Owner, sắp theo reply tuần",
                value="owner|replies",
                emoji="👑"
            ),
            discord.SelectOption(
                label="🛡️ Chỉ hiện Admin — Xếp theo Reply",
                description="Lọc chỉ Admin, sắp theo reply tuần",
                value="admin|replies",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="🌸 Chỉ hiện Recep — Xếp theo Reply",
                description="Lọc chỉ Recep, sắp theo reply tuần",
                value="recep|replies",
                emoji="🌸"
            ),
        ]
        super().__init__(
            placeholder="🔎 Chọn bộ lọc và tiêu chí sắp xếp...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        bot: Any = interaction.client
        selected = self.values[0]  # dạng "role_filter|sort_by"
        role_filter, sort_by = selected.split('|', 1)

        # Cập nhật default để hiển thị tuỳ chọn hiện tại
        for opt in self.options:
            opt.default = (opt.value == selected)

        # Real-time: luôn query DB mới nhất
        try:
            records = await query_db(
                bot,
                "SELECT discord_id, display_name, role, rating, weekly_replies FROM profiles"
            )
            records = [dict(r) for r in records] if records else []
        except Exception as e:
            log.error(f"Leaderboard DB error: {e}")
            records = []

        embed = _build_leaderboard_embed(records, sort_by, role_filter)
        await interaction.response.edit_message(embed=embed, view=self.view)


class LeaderboardView(discord.ui.View):
    """View Leaderboard với menu lọc tương tác"""

    def __init__(self):
        super().__init__(timeout=300)
        self.message: Optional[discord.Message] = None
        self.add_item(LeaderboardFilterSelect())

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class StaffUICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.get_command("help"):
            self.bot.remove_command("help")

    @commands.command(name="menu", aliases=["staff", "bqt"])
    async def send_menu(self, ctx: commands.Context):
        """Lệnh hiển thị Menu giới thiệu Ban Quản Trị Angelic"""
        view = MainView(author_id=ctx.author.id)
        view.message = await ctx.send(embed=get_main_embed(), view=view)
        log.info(f"🌸 {ctx.author.display_name} vừa mở bảng Menu Staff.")

    @commands.command(name="top", aliases=["leaderboard", "xephang"])
    async def leaderboard_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị Bảng Xế Hạng Nhân Sự xuất sắc nhất"""
        try:
            records = await query_db(
                self.bot,
                "SELECT discord_id, display_name, role, rating, weekly_replies FROM profiles"
            )
            records = [dict(r) for r in records] if records else []
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")
            return

        if not records:
            await ctx.send("📭 **Database đang trống!** Chưa có nhân sự nào trong hệ thống.")
            return

        # Mặc định: xếp theo rating, tie-breaker weekly_replies
        embed = _build_leaderboard_embed(records, sort_by='rating', role_filter='all')
        view = LeaderboardView()
        view.message = await ctx.send(embed=embed, view=view)
        log.info(f"🏆 {ctx.author.display_name} vừa mở Bảng Xế Hạng.")

    @commands.command(name="checkdb")
    async def check_db(self, ctx: commands.Context):
        """Lệnh kiểm tra toàn bộ danh sách đang có trong Database"""
        try:
            records = await query_db(self.bot, "SELECT discord_id, role, display_name FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**\n➡️ Hãy lên Railway kiểm tra lại xem dữ liệu bạn nhập đã được ấn phím **Enter** để xác nhận lưu chưa nhé!")
                return

            # --- Sắp xếp theo phân cấp chức vụ: owner → admin → recep ---
            role_order = {'owner': 0, 'admin': 1, 'recep': 2}
            sorted_records = sorted(
                records,
                key=lambda x: role_order.get(x['role'].lower().strip(), 99)
            )

            # --- Render bảng monospace với căn lề ljust ---
            COL_ID   = 22
            COL_ROLE = 8
            COL_NAME = 25

            header    = f"{'ID'.ljust(COL_ID)}| {'Role'.ljust(COL_ROLE)}| Tên"
            separator = f"{'-' * COL_ID}|{'-' * (COL_ROLE + 1)}|{'-' * (COL_NAME + 1)}"

            rows = []
            for r in sorted_records:
                col_id   = str(r['discord_id']).ljust(COL_ID)
                col_role = str(r['role']).lower().strip().ljust(COL_ROLE)
                col_name = str(r['display_name'])
                rows.append(f"{col_id}| {col_role}| {col_name}")

            table_body = "\n".join(rows)
            table = f"```\n{header}\n{separator}\n{table_body}\n```"

            total       = len(sorted_records)
            cnt_owner   = sum(1 for r in sorted_records if r['role'].lower().strip() == 'owner')
            cnt_admin   = sum(1 for r in sorted_records if r['role'].lower().strip() == 'admin')
            cnt_recep   = sum(1 for r in sorted_records if r['role'].lower().strip() == 'recep')
            summary     = f"(owner: {cnt_owner} | admin: {cnt_admin} | recep: {cnt_recep})"

            await ctx.send(f"**📋 Database Profiles — {total} bản ghi {summary}**\n{table}")
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="feedback", aliases=["fb"])
    async def feedback_cmd(self, ctx: commands.Context, target: Optional[str] = None):
        """Lệnh xem danh sách toàn bộ bài đánh giá của một nhân sự"""
        target_id = extract_id(target)

        if not target_id:
            await ctx.send(
                "⚠️ **Vui lòng nhập ID hoặc ping nhân sự muốn xem đánh giá!**\n"
                "Ví dụ chuẩn: `y!fb <@468428368828956692>` hoặc `y!fb 468428368828956692`"
            )
            return

        try:
            records = await query_db(self.bot, "SELECT display_name, votes, rating FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send(
                    "📭 **Không tìm thấy nhân sự này trong Database!**\n"
                    "➡️ Vui lòng kiểm tra lại chính xác ID hoặc ping lại."
                )
                return

            row = records[0]
            name = row.get('display_name', 'Unnamed Staff')
            votes_dict = _normalize_votes(row.get('votes', {}))

            if not votes_dict:
                await ctx.send(
                    f"💖 Hồ sơ của **{name}** hiện tại **chưa có bài đánh giá nào** từ cộng đồng!"
                )
                return

            review_lines = []
            for voter_id, entry in votes_dict.items():
                if not isinstance(entry, dict):
                    continue
                try:
                    score = round(float(entry.get("score", 0.0)), 1)
                except (ValueError, TypeError):
                    score = 0.0
                review = entry.get("review") or "Không có nội dung"
                if voter_id.startswith("old_"):
                    review_lines.append(f"*Ẩn danh* **{score} ⭐**, {review}")
                else:
                    review_lines.append(f"<@{voter_id}> **{score} ⭐**, {review}")

            try:
                avg_rating = round(float(row.get('rating', 0.0)), 1)
            except (ValueError, TypeError):
                avg_rating = 0.0

            description = (
                f"Điểm trung bình: **⭐ {avg_rating}/5.0** ({len(votes_dict)} lượt đánh giá)\n\n"
                + "\n".join(review_lines)
            )

            if len(description) > 4096:
                description = description[:4090] + "..."

            embed = discord.Embed(
                title=f"📋 Danh Sách Đánh Giá Của {name}",
                description=description,
                color=0xffb6c1
            )
            embed.set_footer(text="Angelic Bot • Cảm ơn cộng đồng đã đóng góp đánh giá chân thành! 🌸")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="help", aliases=["huongdan"])
    async def help_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị danh sách toàn bộ các câu lệnh của Bot"""
        embed = discord.Embed(
            title="📖 Bảng Hướng Dẫn Câu Lệnh Angelic Bot ໒꒱",
            description="Dưới đây là toàn bộ các câu lệnh khả dụng mà bạn có thể sử dụng trên server:",
            color=0xffb6c1
        )

        embed.add_field(
            name="🌸 1. Tra Cứu & Đánh Giá (Mọi Thành Viên)",
            value=(
                "➡️ `y!menu` *(hoặc `y!staff`, `y!bqt`)*: Mở bảng menu tương tác để xem hồ sơ, tags và ảnh của Ban Quản Trị.\n"
                "➡️ `y!top` *(hoặc `y!leaderboard`, `y!xephang`)*: Xem Bảng Xếp Hạng Staff xuất sắc nhất theo điểm đánh giá và số tin nhắn được phản hồi, có bộ lọc tương tác.\n"
                "➡️ `y!feedback <@user/ID>` *(hoặc `y!fb`)*: Xem danh sách toàn bộ bài đánh giá chi tiết (số sao và nội dung nhận xét) của một Staff.\n"
                "➡️ `y!help` *(hoặc `y!huongdan`)*: Hiển thị bảng hướng dẫn câu lệnh này."
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ 2. Đăng Ký & Quản Lý Hồ Sơ (Dành Riêng BQT)",
            value=(
                "➡️ `y!add`: Bật Form Modal cho phép nhân sự mới tự đăng ký hồ sơ (Tên hiển thị, Giới thiệu, Tags, Liên hệ) và tự động cấp chức vụ theo cấu trúc Role ID của Server, sau đó kích hoạt luồng upload ảnh vĩnh viễn.\n"
                "➡️ `y!set` *(hoặc `y!editprofile`, `y!suahoso`)*: Mở bảng điều khiển tương tác giúp Staff tự chỉnh sửa thông tin cá nhân hoặc lướt xem/xóa/thêm ảnh hồ sơ hiện có."
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ 3. Quản Trị Hệ Thống (Admin / Owner)",
            value=(
                "➡️ `y!checkdb`: Kiểm tra nhanh danh sách toàn bộ nhân sự hiện đang được lưu trữ trong Cơ Sở Dữ Liệu PostgreSQL."
            ),
            inline=False
        )

        embed.add_field(
            name="🧪 4. Kiểm Thử & Debug (Chỉ Dành Cho Tester)",
            value=(
                "➡️ `y!test_reply <@user/ID>`: Giả lập kích hoạt ngay câu nhắc nhở vote trên kênh chat (không cần đợi đủ 10 reply).\n"
                "➡️ `y!test_vote <@user/ID> <điểm>`: Bơm điểm vote ảo vào hồ sơ để kiểm thử công thức tính và làm tròn điểm trung bình.\n"
                "➡️ `y!test_reset <@user/ID>`: Lọc và dọn sạch toàn bộ các lượt vote ảo khỏi hồ sơ của Staff, trả lại điểm số thực tế."
            ),
            inline=False
        )

        embed.set_footer(text="Angelic Bot • Sử dụng mũi tên để điều hướng các menu dễ dàng hơn!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StaffUICog(bot))
