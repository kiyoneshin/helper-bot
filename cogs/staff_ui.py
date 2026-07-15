import discord
from discord.ext import commands
import logging
from typing import Optional

from cogs._staff_db import query_db, extract_id
from cogs._staff_embeds import get_main_embed
from cogs._staff_views import MainView, _normalize_votes

log = logging.getLogger("StaffBot")


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
                "➡️ `y!top` *(hoặc `y!lb`, `y!bxh`, `y!leaderboard`)*: Xem Bảng Xếp Hạng Staff, mặc định tuần hiện tại. Nhấn nút 📅 để lọc theo khoảng ngày tùy chỉnh.\n"
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
