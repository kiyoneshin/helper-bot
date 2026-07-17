import discord
from discord.ext import commands
import logging
import asyncio
import json
from typing import Optional, Any

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
                "❌ **Vui lòng nhập ID hoặc ping nhân sự muốn xem đánh giá!**\n"
                "Ví dụ chuẩn: `y!fb <@468428368828956692>` hoặc `y!fb 468428368828956692`"
            )
            return

        try:
            records = await query_db(self.bot, "SELECT display_name, votes, rating FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send(
                    "❌ **Không tìm thấy nhân sự này trong Database!**\n"
                    "❓ Vui lòng kiểm tra lại chính xác ID hoặc ping lại."
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
                "💠 `y!menu` *(hoặc `y!staff`, `y!bqt`)*: Mở bảng menu tương tác để xem hồ sơ, tags và ảnh của Ban Quản Trị.\n"
                "💠 `y!top` *(hoặc `y!lb`, `y!bxh`, `y!leaderboard`)*: Xem Bảng Xếp Hạng Staff, mặc định tuần hiện tại. Nhấn nút 📅 để lọc theo khoảng ngày tùy chỉnh.\n"
                "💠 `y!feedback <@user/ID>` *(hoặc `y!fb`)*: Xem danh sách toàn bộ bài đánh giá chi tiết (số sao và nội dung nhận xét) của một Staff.\n"
                "💠 `y!help` *(hoặc `y!huongdan`)*: Hiển thị bảng hướng dẫn câu lệnh này."
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ 2. Đăng Ký & Quản Lý Hồ Sơ (Dành Riêng BQT)",
            value=(
                "💠 `y!add`: Bật Form Modal cho phép nhân sự mới tự đăng ký hồ sơ (Tên hiển thị, Giới thiệu, Tags, Liên hệ) và tự động cấp chức vụ theo cấu trúc Role ID của Server, sau đó kích hoạt luồng upload ảnh vĩnh viễn.\n"
                "💠 `y!set` *(hoặc `y!editprofile`, `y!suahoso`)*: Mở bảng điều khiển tương tác giúp Staff tự chỉnh sửa thông tin cá nhân hoặc lướt xem/xóa/thêm ảnh hồ sơ hiện có."
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ 3. Quản Trị Hệ Thống (Admin / Owner)",
            value=(
                "💠 `y!checkdb`: Kiểm tra nhanh danh sách toàn bộ nhân sự hiện đang được lưu trữ trong Cơ Sở Dữ Liệu PostgreSQL.\n"
                "💠 `y!renewdb`: Đồng bộ và làm sạch toàn bộ dữ liệu DB với Server thực tế (cập nhật tên, phát hiện thành viên rời server, sửa lỗi dữ liệu).\n"
                "💠 `y!backup`: Kích hoạt sao lưu Database thủ công ngay lập tức thành file `.sql`."
            ),
            inline=False
        )

        embed.add_field(
            name="🧪 4. Kiểm Thử & Debug (Chỉ Dành Cho Tester)",
            value=(
                "💠 `y!test_reply <@user/ID>`: Giả lập kích hoạt ngay câu nhắc nhở vote trên kênh chat (không cần đợi đủ 10 reply).\n"
                "💠 `y!test_vote <@user/ID> <điểm>`: Bơm điểm vote ảo vào hồ sơ để kiểm thử công thức tính và làm tròn điểm trung bình.\n"
                "💠 `y!test_reset <@user/ID>`: Lọc và dọn sạch toàn bộ các lượt vote ảo khỏi hồ sơ của Staff, trả lại điểm số thực tế."
            ),
            inline=False
        )

        embed.set_footer(text="Angelic Bot • Sử dụng mũi tên để điều hướng các menu dễ dàng hơn!")
        await ctx.send(embed=embed)

    # ──────────────────────────────────────────────────────────────────
    # LỆNH ĐỒNG BỘ VÀ LÀM SẠCH DATABASE: y!renewdb
    # ──────────────────────────────────────────────────────────────────

    @commands.command(name="renewdb", aliases=["syncdb", "refreshdb"])
    @commands.has_permissions(administrator=True)
    async def renewdb_cmd(self, ctx: commands.Context):
        """
        [Admin/Owner] Đồng bộ và làm sạch Database với Server Discord thực tế:
          - Cập nhật display_name theo tên thực trên server
          - Phát hiện & gắn nhãn hồ sơ thành viên đã rời server
          - Sửa lỗi giá trị NULL/NaN trong các trường số và JSON
        """
        guild = ctx.guild
        if guild is None:
            await ctx.send("Lệnh này chỉ dùng được trong Server!")
            return

        progress_msg = await ctx.send(
            "Đang đồng bộ Database... Vui lòng chờ trong giây lát."
        )

        try:
            records = await query_db(
                self.bot,
                "SELECT discord_id, display_name, role, rating, weekly_replies, votes FROM profiles"
            )
        except Exception as e:
            log.error(f"renewdb: Lỗi truy vấn profiles: {e}", exc_info=True)
            await progress_msg.edit(content=f"Lỗi truy vấn Database: `{e}`")
            return

        total = len(records)
        if total == 0:
            await progress_msg.edit(content="Database profiles đang trống, không có gì để đồng bộ!")
            return

        # ── Bộ đếm thống kê ──────────────────────────────────────────
        count_name_updated  = 0   # Hồ sơ được cập nhật biệt danh
        count_left_server   = 0   # Hồ sơ đã rời server
        count_data_fixed    = 0   # Hồ sơ có lỗi dữ liệu được sửa
        left_server_names: list[str] = []
        errors_in_task: list[str] = []

        # ── Xử lý từng hồ sơ ─────────────────────────────────────────
        for record in records:
            discord_id_str: str = str(record["discord_id"])
            old_name: str = str(record.get("display_name") or "Unnamed")
            updates: dict[str, Any] = {}  # field → giá trị mới cần cập nhật

            # ── 1. Kiểm tra tồn tại trên Server ──────────────────────
            member = guild.get_member(int(discord_id_str))
            if member is None:
                try:
                    member = await guild.fetch_member(int(discord_id_str))
                except discord.NotFound:
                    member = None
                except discord.HTTPException as e:
                    log.warning(f"renewdb: Không fetch được member {discord_id_str}: {e}")
                    member = None

            if member is None:
                # Thành viên không còn trong server
                count_left_server += 1
                left_server_names.append(old_name)
                log.info(f"renewdb: {old_name} ({discord_id_str}) đã rời server.")
                # Gắn nhãn display_name nếu chưa có
                if not old_name.startswith("[Đã rời Server]"):
                    updates["display_name"] = f"[Đã rời Server] {old_name}"
            else:
                # ── 2. Đồng bộ biệt danh (display_name) ──────────────
                current_nick = member.display_name
                if current_nick != old_name and not old_name.startswith("[Đã rời Server]"):
                    updates["display_name"] = current_nick
                    count_name_updated += 1
                    log.info(
                        f"renewdb: Cập nhật tên {discord_id_str}: "
                        f"'{old_name}' → '{current_nick}'"
                    )

            # ── 3. Kiểm tra & sửa lỗi cấu trúc dữ liệu ─────────────
            data_was_fixed = False

            # rating: phải là số hợp lệ trong [0, 5]
            raw_rating = record.get("rating")
            try:
                r = float(raw_rating)
                if r != r:  # NaN check
                    raise ValueError("NaN")
            except (TypeError, ValueError):
                updates["rating"] = 0.0
                data_was_fixed = True
                log.warning(f"renewdb: Reset rating NULL/NaN → 0.0 cho {discord_id_str}")

            # weekly_replies: phải là số nguyên không âm
            raw_replies = record.get("weekly_replies")
            try:
                rr = int(raw_replies)
                if rr < 0:
                    raise ValueError("Âm")
            except (TypeError, ValueError):
                updates["weekly_replies"] = 0
                data_was_fixed = True
                log.warning(f"renewdb: Reset weekly_replies NULL/invalid → 0 cho {discord_id_str}")

            # votes: phải là dict hợp lệ
            raw_votes = record.get("votes")
            try:
                if raw_votes is None:
                    raise ValueError("None")
                if isinstance(raw_votes, str):
                    parsed = json.loads(raw_votes)
                    if not isinstance(parsed, dict):
                        raise ValueError("Không phải dict")
                elif not isinstance(raw_votes, dict):
                    raise ValueError("Kiểu sai")
            except (ValueError, json.JSONDecodeError):
                updates["votes"] = json.dumps({})
                data_was_fixed = True
                log.warning(f"renewdb: Reset votes lỗi → {{}} cho {discord_id_str}")

            if data_was_fixed:
                count_data_fixed += 1

            # ── 4. Ghi cập nhật vào DB nếu có thay đổi ───────────────
            if not updates:
                continue

            set_clauses = []
            values: list[Any] = []
            for idx, (col, val) in enumerate(updates.items(), start=1):
                set_clauses.append(f"{col} = ${idx}")
                values.append(val)
            values.append(discord_id_str)
            sql = (
                f"UPDATE profiles SET {', '.join(set_clauses)} "
                f"WHERE discord_id = ${len(values)}"
            )
            try:
                await query_db(self.bot, sql, *values)
            except Exception as e:
                err_msg = f"{discord_id_str}: {e}"
                errors_in_task.append(err_msg)
                log.error(f"renewdb: Lỗi UPDATE {err_msg}", exc_info=True)

            # Nhường CPU sau mỗi 10 bản ghi
            await asyncio.sleep(0)

        # ── Xoá tin nhắn chờ ─────────────────────────────────────────
        try:
            await progress_msg.delete()
        except Exception:
            pass

        # ── Xây dựng Embed báo cáo ───────────────────────────────────
        embed = discord.Embed(
            title="Báo Cáo Đồng Bộ Database (renewdb)",
            color=0x57f287,  # Discord green
        )
        embed.add_field(
            name="Kết Quả Tổng Hợp",
            value=(
                f"Tổng số hồ sơ đã kiểm tra: **{total}**\n"
                f"Số hồ sơ được cập nhật biệt danh: **{count_name_updated}**\n"
                f"Số hồ sơ phát hiện đã rời server: **{count_left_server}**\n"
                f"Số lỗi dữ liệu đã được sửa tự động: **{count_data_fixed}**"
            ),
            inline=False,
        )

        if left_server_names:
            names_str = "\n".join(
                f"• {n}" for n in left_server_names[:15]
            )
            if len(left_server_names) > 15:
                names_str += f"\n... và {len(left_server_names) - 15} người khác"
            embed.add_field(
                name="Danh Sách Thành Viên Đã Rời Server",
                value=names_str,
                inline=False,
            )

        if errors_in_task:
            err_str = "\n".join(f"• `{e}`" for e in errors_in_task[:5])
            embed.add_field(
                name="Lỗi Phát Sinh Khi Cập Nhật",
                value=err_str,
                inline=False,
            )

        embed.set_footer(text=f"Angelic Bot • Đồng bộ bởi {ctx.author.display_name} 🌸")
        await ctx.send(embed=embed)

        log.info(
            f"renewdb hoàn tất: {total} hồ sơ, "
            f"{count_name_updated} tên đổi, "
            f"{count_left_server} rời server, "
            f"{count_data_fixed} lỗi dữ liệu sửa."
        )

    @renewdb_cmd.error
    async def renewdb_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Bạn không có quyền sử dụng lệnh này! Chỉ Admin/Owner mới được dùng `y!renewdb`.")


async def setup(bot):
    await bot.add_cog(StaffUICog(bot))

