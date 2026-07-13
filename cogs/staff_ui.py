import discord
from discord.ext import commands
import logging
import json
from typing import Optional

from cogs._staff_db import query_db
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

    @commands.command(name="voters", aliases=["votelog", "xemvote"])
    async def check_voters(self, ctx: commands.Context, target: Optional[str] = None):
        """Lệnh kiểm tra xem ai đã vote cho ai và bao nhiêu điểm"""
        if not target:
            await ctx.send(
                "⚠️ **Vui lòng nhập ID hoặc ping nhân sự cần xem lịch sử vote!**\n"
                "➡️ Ví dụ chuẩn: `y!voters @Yon Yon Lon Ton` hoặc `y!voters 468428368828956692`"
            )
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()
        
        try:
            records = await query_db(self.bot, "SELECT display_name, role, votes, rating FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send("📭 **Không tìm thấy nhân sự này trong Database!**\n➡️ Vui lòng kiểm tra lại chính xác ID hoặc ping lại.")
                return
            
            row = records[0]
            name = row.get('display_name', 'Unnamed Staff')
            votes_dict = _normalize_votes(row.get('votes', {}))

            if not votes_dict:
                await ctx.send(f"⭐ Hồ sơ của **{name}** hiện tại **chưa có lượt đánh giá nào!**")
                return

            details = ""
            for idx, (voter_id, entry) in enumerate(votes_dict.items(), 1):
                score = entry.get("score", 0.0) if isinstance(entry, dict) else float(entry)
                if voter_id.startswith("old_"):
                    details += f"**{idx}.** Người dùng ẩn danh *(Dữ liệu cũ)*: **{score} ⭐**\n"
                else:
                    details += f"**{idx}.** <@{voter_id}> (`{voter_id}`): **{score} ⭐**\n"
            
            desc_text = f"➡️ Điểm trung bình hiện tại: **⭐ {row.get('rating', 0.0)}/5.0** ({len(votes_dict)} lượt)\n\n**Chi tiết từng lượt vote:**\n{details}"
            embed = discord.Embed(
                title=f"📋 Lịch Sử Đánh Giá Của {name}",
                description=desc_text,
                color=0xffb6c1
            )
            embed.set_footer(text="Angelic Bot • Sử dụng `y!feedback <@user>` để xem toàn bộ bài đánh giá chi tiết!")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="feedback", aliases=["fb"])
    async def feedback_cmd(self, ctx: commands.Context, target: Optional[str] = None):
        """Lệnh xem danh sách toàn bộ bài đánh giá của một nhân sự"""
        if not target:
            await ctx.send(
                "⚠️ **Vui lòng nhập ID hoặc ping nhân sự muốn xem đánh giá!**\n"
                "➡️ Ví dụ: `y!feedback @Yon Yon Lon Ton` hoặc `y!fb 468428368828956692`"
            )
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()

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

            # Xây dựng nội dung danh sách đánh giá
            review_lines = []
            for voter_id, entry in votes_dict.items():
                if not isinstance(entry, dict):
                    continue
                score = entry.get("score", 0.0)
                review = entry.get("review") or "Không có nội dung"
                if voter_id.startswith("old_"):
                    review_lines.append(f"*Ẩn danh* **{score} ⭐**, {review}")
                else:
                    review_lines.append(f"<@{voter_id}> **{score} ⭐**, {review}")

            avg_rating = row.get('rating', 0.0)
            if isinstance(avg_rating, (int, float)):
                avg_rating = round(float(avg_rating), 1)
            description = (
                f"➡️ Điểm trung bình: **⭐ {avg_rating}/5.0** ({len(votes_dict)} lượt đánh giá)\n\n"
                + "\n".join(review_lines)
            )

            # Kiểm tra giới hạn độ dài Embed (4096 ký tự)
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
                "➡️ `y!menu` *(thay thế: `y!staff`, `y!bqt`)*: Mở bảng giao diện xem danh sách và thông tin Ban Quản Trị.\n"
                "➡️ `y!voters <@user/ID>` *(thay thế: `y!votelog`, `y!xemvote`)*: Xem lịch sử ai đã vote cho một Staff và điểm cụ thể.\n"
                "➡️ `y!feedback <@user/ID>` *(thay thế: `y!fb`)*: Xem toàn bộ bài đánh giá chi tiết có kèm nội dung nhận xét của cộng đồng.\n"
                "➡️ `y!checkdb`: Kiểm tra nhanh toàn bộ nhân sự đang lưu trong Cơ Sở Dữ Liệu.\n"
                "➡️ `y!set` *(thay thế: `y!editprofile`, `y!suahoso`)*: Tự chỉnh sửa hồ sơ cá nhân của bạn trong hệ thống *(chỉ dành cho Staff).*"
            ),
            inline=False
        )

        embed.add_field(
            name="🔐 Lệnh Quản Trị *(Chỉ dành cho Admin)*",
            value=(
                "➡️ `y!addstaff <@user> <role> [mô tả]`: Thêm một nhân sự mới vào Database.\n"
                "   ↳ `role` hợp lệ: `owner` | `admin` | `recep`\n"
                "   ↳ Ví dụ: `y!addstaff @Yon admin Trưởng nhóm`"
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ Lệnh Kiểm Thử *(Chỉ dành cho Developer)*",
            value=(
                "➡️ `y!test_reply <@user/ID>`: Giả lập kích hoạt ngay tin nhắn nhắc nhở vote (không cần đợi đủ 10 reply).\n"
                "➡️ `y!test_vote <@user/ID> <điểm>`: Bơm điểm ảo vào hồ sơ Staff để kiểm tra tính toán điểm trung bình.\n"
                "   ↳ Ví dụ: `y!test_vote @Yon 4.5`\n"
                "➡️ `y!test_reset <@user/ID>`: Dọn sạch toàn bộ điểm vote ảo *(test_injection)* và giữ nguyên vote thực."
            ),
            inline=False
        )

        embed.add_field(
            name="📌 Lệnh Hệ Thống",
            value=(
                "➡️ `y!help` *(thay thế: `y!huongdan`, `y!lenh`, `y!commands`)*: Hiển thị bảng hướng dẫn câu lệnh này."
            ),
            inline=False
        )

        embed.set_footer(text="Angelic Bot • Sử dụng mũi tên để điều hướng các menu dễ dàng hơn!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffUICog(bot))