import discord
from discord.ext import commands
import logging
import asyncio
import json
from typing import Optional, Any

from cogs.common.db import query_db, extract_id, execute_db
from cogs.common.embeds import get_main_embed
from cogs.common.views import MainView, _normalize_votes
from cogs.common.logs import send_staff_log, build_log_delete
from cogs.common.embeds import get_main_embed, get_rules_embed

log = logging.getLogger("StaffBot")


# ──────────────────────────────────────────────────────────────────
# CLASS UI VIEW 
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# CLASS COG CHÍNH (Chứa toàn bộ lệnh commands của Bot)
# ──────────────────────────────────────────────────────────────────
class StaffUICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="menu", aliases=["staff", "bqt"], description="Mở bảng menu Ban Quản Trị Angelic ໒꒱")
    async def send_menu(self, ctx: commands.Context):
        """Lệnh hiển thị Menu giới thiệu Ban Quản Trị Angelic"""
        view = MainView(author_id=ctx.author.id)
        view.message = await ctx.send(embed=get_main_embed(), view=view)
        log.info(f"{ctx.author.display_name} vừa mở bảng Menu Staff.")

    @commands.hybrid_command(name="rule", aliases=["rules", "luat", "dieule"], description="Xem bảng điều lệ server Angelic")
    async def rule_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị Bảng Nội Quy Server Angelic"""
        await ctx.send(embed=get_rules_embed())
        log.info(f"{ctx.author.display_name} vừa xem bảng điều lệ server.")

    @commands.hybrid_command(name="checkdb", description="Kiểm tra toàn bộ danh sách đang có trong Database")
    async def check_db(self, ctx: commands.Context):
        """Lệnh kiểm tra toàn bộ danh sách đang có trong Database"""
        try:
            records = await query_db(self.bot, "SELECT discord_id, role, display_name FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**\n➡️ Hãy lên Railway kiểm tra lại xem dữ liệu bạn nhập đã được ấn phím **Enter** để xác nhận lưu chưa nhé!")
                return

            role_order = {'owner': 0, 'admin': 1, 'recep': 2}
            sorted_records = sorted(
                records,
                key=lambda x: role_order.get(x['role'].lower().strip(), 99)
            )

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

            await ctx.send(f"**Database Profiles — {total} bản ghi {summary}**\n{table}")
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.hybrid_command(name="feedback", aliases=["fb"], description="Xem danh sách toàn bộ bài đánh giá của một nhân sự")
    async def feedback_cmd(self, ctx: commands.Context, target: Optional[str] = None):
        """Lệnh xem danh sách toàn bộ bài đánh giá của một nhân sự"""
        target_id = extract_id(target)

        if not target_id:
            await ctx.send(
                "<:symbol_wrong:1536629915598848072> **Vui lòng nhập ID hoặc ping nhân sự muốn xem đánh giá!**\n"
                f"Ví dụ chuẩn: `{ctx.prefix}fb <@468428368828956692>` hoặc `{ctx.prefix}fb 468428368828956692`"
            )
            return

        try:
            records = await query_db(self.bot, "SELECT display_name, votes, rating FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send(
                    "<:symbol_wrong:1536629915598848072> **Không tìm thấy nhân sự này trong Database!**\n"
                    "<:symbol_question_mark:1537739280640647178> Vui lòng kiểm tra lại chính xác ID hoặc ping lại."
                )
                return

            row = records[0]
            name = row.get('display_name', 'Unnamed Staff')
            votes_dict = _normalize_votes(row.get('votes', {}))

            if not votes_dict:
                await ctx.send(
                    f"<a:symbol_star_pink:1537739287947382864> Hồ sơ của **{name}** hiện tại **chưa có bài đánh giá nào** từ cộng đồng!"
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
                    review_lines.append(f"*Ẩn danh* **{score} <a:symbol_star_yellow:1537739289834553385>**, {review}")
                else:
                    review_lines.append(f"<@{voter_id}> **{score} <a:symbol_star_yellow:1537739289834553385>**, {review}")

            try:
                avg_rating = round(float(row.get('rating', 0.0)), 1)
            except (ValueError, TypeError):
                avg_rating = 0.0

            description = (
                f"Điểm trung bình: **<a:symbol_star_yellow:1537739289834553385> {avg_rating}/5.0** ({len(votes_dict)} lượt đánh giá)\n\n"
                + "\n".join(review_lines)
            )

            if len(description) > 4096:
                description = description[:4090] + "..."

            embed = discord.Embed(
                title=f"Danh Sách Đánh Giá Của {name}",
                description=description,
                color=0xffb6c1
            )
            embed.set_footer(text="Angelic Bot • Cảm ơn cộng đồng đã đóng góp đánh giá chân thành! 🌸")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.hybrid_command(name="myreviews", aliases=["myfeedbacks", "myfb", "myrv"], description="Xem lịch sử đánh giá staff của bạn")
    async def myreviews_cmd(self, ctx: commands.Context):
        """Lệnh xem lịch sử đánh giá cá nhân của bạn"""
        voter_id = str(ctx.author.id)

        try:
            records = await query_db(self.bot, "SELECT discord_id, display_name, votes FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**")
                return

            my_reviews = []
            for row in records:
                votes_dict = _normalize_votes(row.get('votes', {}))
                if voter_id in votes_dict:
                    entry = votes_dict[voter_id]
                    if isinstance(entry, dict):
                        try:
                            score = round(float(entry.get('score', 0.0)), 1)
                        except (ValueError, TypeError):
                            score = 0.0
                        review = entry.get('review') or "Không có nội dung"
                        staff_name = row.get('display_name', 'Unnamed Staff')
                        staff_id = row.get('discord_id')
                        my_reviews.append((staff_name, staff_id, score, review))

            if not my_reviews:
                await ctx.send("Bạn chưa từng để lại bài đánh giá nào cho đội ngũ Staff.")
                return

            embed = discord.Embed(
                title=f"Lịch Sử Đánh Giá Của {ctx.author.display_name}",
                description=f"Dưới đây là danh sách các bài đánh giá bạn đã viết cho Staff:\n**Tổng số bài đánh giá:** {len(my_reviews)}",
                color=0xffb6c1
            )

            for staff_name, staff_id, score, review in my_reviews:
                embed.add_field(
                    name=f"Đánh giá {staff_name}",
                    value=f"• **Staff:** <@{staff_id}>\n• **điểm số:** {score} <a:symbol_star_yellow:1537739289834553385>\n• **Nhận xét:** {review}",
                    inline=False
                )

            embed.set_footer(text="Angelic Bot • Lịch sử đánh giá cá nhân 🌸")
            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Lỗi lệnh myreviews: {e}")
            await ctx.send(f"Lỗi truy vấn Database: {e}")



    # ──────────────────────────────────────────────────────────────────
    # LỆNH ĐỒNG BỘ VÀ LÀM SẠCH DATABASE: krenewdb
    # ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="renewdb", aliases=["syncdb", "refreshdb"], description="Đồng bộ và làm sạch Database với Server Discord thực tế")
    @commands.has_permissions(administrator=True)
    async def renewdb_cmd(self, ctx: commands.Context):
        """
        [Admin/Owner] Đồng bộ và làm sạch Database với Server Discord thực tế:
          - Cập nhật display_name theo tên thực trên server
          - Phát hiện & gắn nhãn hồ sơ thành viên đã rời server
          - Sửa lỗi giá trị NULL/NaN trong các trường số và JSON
          """
        ROLE_ID_MAP = {
            "owner": 1498711782192189494,  # <-- Thay ID Role Owner vào đây
            "admin": 1510230255988900002,  # <-- Thay ID Role Admin vào đây
            "recep": 1511010582826848520,  # <-- Thay ID Role Recep vào đây
        }
        
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

        count_name_updated  = 0   
        count_removed_staff = 0   
        count_data_fixed    = 0   
        removed_staff_list: list[str] = []
        errors_in_task: list[str] = []

        for record in records:
            discord_id_str: str = str(record["discord_id"])
            old_name: str = str(record.get("display_name") or "Unnamed")
            db_role: str = str(record.get("role", "")).lower().strip()
            updates: dict[str, Any] = {}  

            member = guild.get_member(int(discord_id_str))
            if member is None:
                try:
                    member = await guild.fetch_member(int(discord_id_str))
                except discord.NotFound:
                    member = None
                except discord.HTTPException as e:
                    log.warning(f"renewdb: Không fetch được member {discord_id_str}: {e}")
                    member = None



            required_role_id = ROLE_ID_MAP.get(db_role)
            has_role = False
            if member is not None and required_role_id:
                has_role = any(role.id == required_role_id for role in member.roles)

            if member is None or (member is not None and required_role_id and not has_role):
                log.info(f"renewdb: Xóa staff {discord_id_str} vì rời server hoặc mất role BQT.")
                await execute_db(self.bot, "DELETE FROM staff_message_logs WHERE discord_id = $1", discord_id_str)
                await execute_db(self.bot, "DELETE FROM profiles WHERE discord_id = $1", discord_id_str)
                count_removed_staff += 1
                removed_staff_list.append(old_name)
                continue

            current_nick = member.display_name
            if current_nick != old_name:
                updates["display_name"] = current_nick
                count_name_updated += 1
                log.info(
                    f"renewdb: Cập nhật tên {discord_id_str}: "
                    f"'{old_name}' → '{current_nick}'"
                )

            data_was_fixed = False

            raw_rating = record.get("rating")
            try:
                r = float(raw_rating)
                if r != r:  
                    raise ValueError("NaN")
            except (TypeError, ValueError):
                updates["rating"] = 0.0
                data_was_fixed = True
                log.warning(f"renewdb: Reset rating NULL/NaN → 0.0 cho {discord_id_str}")

            raw_replies = record.get("weekly_replies")
            try:
                rr = int(raw_replies)
                if rr < 0:
                    raise ValueError("Âm")
            except (TypeError, ValueError):
                updates["weekly_replies"] = 0
                data_was_fixed = True
                log.warning(f"renewdb: Reset weekly_replies NULL/invalid → 0 cho {discord_id_str}")

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

            await asyncio.sleep(0)

        try:
            await progress_msg.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="Báo Cáo Đồng Bộ Database (renewdb)",
            color=0x57f287,  
        )
        embed.add_field(
            name="Kết Quả Tổng Hợp",
            value=(
                f"Tổng số hồ sơ đã kiểm tra: **{total}**\n"
                f"Số hồ sơ được cập nhật biệt danh: **{count_name_updated}**\n"
                f"Số hồ sơ đã bị xóa (Rời server / Mất Role): **{count_removed_staff}**\n"
                f"Số lỗi dữ liệu đã được sửa tự động: **{count_data_fixed}**"
            ),
            inline=False,
        )

        if removed_staff_list:
            names_str = "\n".join(
                f"• {n}" for n in removed_staff_list[:15]
            )
            if len(removed_staff_list) > 15:
                names_str += f"\n... và {len(removed_staff_list) - 15} người khác"
            embed.add_field(
                name="🗑️ Danh Sách Staff Đã Bị Xóa Khỏi DB",
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
            f"{count_removed_staff} bị xóa, "
            f"{count_data_fixed} lỗi dữ liệu sửa."
        )

    @renewdb_cmd.error
    async def renewdb_cmd_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"Bạn không có quyền sử dụng lệnh này! Chỉ Admin/Owner mới được dùng `{ctx.prefix}renewdb`.")


    async def renewdb_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"Bạn không có quyền sử dụng lệnh này! Chỉ Admin/Owner mới được dùng `{ctx.prefix}renewdb`.")


async def setup(bot):
    await bot.add_cog(StaffUICog(bot))