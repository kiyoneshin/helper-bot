"""
staff_backup.py — Cog Tự Động Sao Lưu Database Angelic Bot
===========================================================
Tính năng:
  - Tự động xuất toàn bộ dữ liệu (profiles + staff_message_logs) thành file .sql thuần Python (không cần binary pg_dump).
  - Lịch trình: chạy lúc 04:00:00 sáng mỗi ngày theo múi giờ UTC+7.
  - Gửi file đính kèm vào kênh backup kín (LOG_CHANNEL_ID).
  - Lệnh y!backup: kích hoạt thủ công ngay lập tức (Admin/Owner).
"""

import discord
from discord.ext import commands, tasks
import logging
import io
import json
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import Any

from cogs.common.db import query_db

log = logging.getLogger("StaffBackup")

UTC7 = timezone(timedelta(hours=7))

BACKUP_CHANNEL_ID = 1527706133127500061
BACKUP_TIME_UTC = dt_time(hour=21, minute=0, second=0)


# =============================================================================
# HÀM XUẤT DỮ LIỆU THÀNH SQL THUẦN PYTHON
# =============================================================================

def _escape_sql_value(val: Any) -> str:
    """Chuyển một giá trị Python thành chuỗi SQL literal an toàn."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    if isinstance(val, (dict, list)):
        escaped = json.dumps(val, ensure_ascii=False).replace("'", "''")
        return f"'{escaped}'"
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


async def _dump_table_profiles(bot: Any) -> tuple[str, int]:
    rows = await query_db(bot, "SELECT * FROM profiles")
    if not rows:
        return "-- [profiles] Không có dữ liệu.\n", 0

    lines: list[str] = []
    lines.append(
        "-- ============================================================\n"
        "-- TABLE: profiles\n"
        "-- ============================================================\n"
        "CREATE TABLE IF NOT EXISTS profiles (\n"
        "    discord_id      TEXT PRIMARY KEY,\n"
        "    display_name    TEXT,\n"
        "    role            TEXT,\n"
        "    description     TEXT,\n"
        "    contact         TEXT,\n"
        "    tags            TEXT,\n"
        "    photos          TEXT,\n"
        "    votes           TEXT,\n"
        "    rating          DOUBLE PRECISION DEFAULT 0,\n"
        "    weekly_replies  INTEGER DEFAULT 0,\n"
        "    is_active       BOOLEAN DEFAULT TRUE\n"
        ");\n"
    )

    # Lấy tên cột từ bản ghi đầu tiên
    col_names = list(rows[0].keys())
    cols_str = ", ".join(col_names)

    for row in rows:
        values_str = ", ".join(_escape_sql_value(row[c]) for c in col_names)
        # ON CONFLICT: cập nhật tất cả trừ PK
        non_pk_cols = [c for c in col_names if c != "discord_id"]
        update_str = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in non_pk_cols
        )
        lines.append(
            f"INSERT INTO profiles ({cols_str}) VALUES ({values_str})\n"
            f"    ON CONFLICT (discord_id) DO UPDATE SET {update_str};\n"
        )

    return "\n".join(lines) + "\n", len(rows)


async def _dump_table_message_logs(bot: Any) -> tuple[str, int]:
    """
    Truy vấn bảng staff_message_logs và sinh SQL INSERT ... ON CONFLICT DO NOTHING.
    Trả về (sql_block, row_count).
    """
    rows = await query_db(bot, "SELECT * FROM staff_message_logs")
    if not rows:
        return "-- [staff_message_logs] Không có dữ liệu.\n", 0

    lines: list[str] = []
    lines.append(
        "-- ============================================================\n"
        "-- TABLE: staff_message_logs\n"
        "-- ============================================================\n"
        "CREATE TABLE IF NOT EXISTS staff_message_logs (\n"
        "    id          BIGSERIAL PRIMARY KEY,\n"
        "    discord_id  TEXT,\n"
        "    message_id  TEXT,\n"
        "    channel_id  TEXT,\n"
        "    sent_at     TIMESTAMPTZ\n"
        ");\n"
    )

    col_names = list(rows[0].keys())
    cols_str = ", ".join(col_names)

    for row in rows:
        values_str = ", ".join(_escape_sql_value(row[c]) for c in col_names)
        lines.append(
            f"INSERT INTO staff_message_logs ({cols_str}) VALUES ({values_str})\n"
            f"    ON CONFLICT DO NOTHING;\n"
        )

    return "\n".join(lines) + "\n", len(rows)


async def generate_sql_dump(bot: Any) -> tuple[bytes, int, int]:
    """
    Sinh toàn bộ nội dung file .sql cho tất cả các bảng.
    Trả về (file_bytes, profile_count, log_count).
    """
    now = datetime.now(UTC7)
    header = (
        f"-- ================================================================\n"
        f"-- Angelic Bot — Database Backup\n"
        f"-- Ngày tạo: {now.strftime('%d/%m/%Y %H:%M:%S')} (UTC+7)\n"
        f"-- ================================================================\n\n"
        f"SET client_encoding = 'UTF8';\n"
        f"SET standard_conforming_strings = on;\n\n"
    )

    profiles_sql, p_count = await _dump_table_profiles(bot)
    logs_sql, l_count = await _dump_table_message_logs(bot)

    full_sql = header + profiles_sql + "\n" + logs_sql
    return full_sql.encode("utf-8"), p_count, l_count


def _make_filename() -> str:
    now = datetime.now(UTC7)
    return f"backup_angelic_{now.strftime('%Y_%m_%d_%H_%M')}.sql"


def _make_backup_embed(now: datetime, p_count: int, l_count: int, is_auto: bool) -> discord.Embed:
    tag = "AUTO BACKUP" if is_auto else "MANUAL BACKUP"
    embed = discord.Embed(
        title=f"📦 [{tag}] Sao Lưu Database Thành Công",
        description=(
            f"Sao lưu dữ liệu {'định kỳ' if is_auto else 'thủ công'} "
            f"ngày **{now.strftime('%d/%m/%Y')}** hoàn tất!\n\n"
            f"**Thống kê:**\n"
            f"• Profiles: **{p_count}** bản ghi\n"
            f"• Message Logs: **{l_count}** bản ghi\n"
            f"• Thời điểm: `{now.strftime('%H:%M:%S')} UTC+7`"
        ),
        color=0x57f287,  # Discord green
    )
    embed.set_footer(text="Angelic Bot • Backup System 🌸")
    return embed


# =============================================================================
# COG BACKUP
# =============================================================================

class StaffBackupCog(commands.Cog):
    """Cog quản lý backup tự động và thủ công cho database Angelic."""

    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()
        log.info("StaffBackupCog loaded — daily backup task đã khởi động.")

    async def cog_unload(self):
        self.daily_backup.cancel()

    # ──────────────────────────────────────────────────────────────────
    # TASK TỰ ĐỘNG 04:00 UTC+7 MỖI NGÀY
    # ──────────────────────────────────────────────────────────────────

    @tasks.loop(time=BACKUP_TIME_UTC)
    async def daily_backup(self):
        """Chạy lúc 04:00 UTC+7 (= 21:00 UTC ngày hôm trước) mỗi ngày."""
        log.info("Bắt đầu auto backup định kỳ...")
        try:
            await self._do_backup(channel_id=BACKUP_CHANNEL_ID, is_auto=True)
        except Exception as e:
            log.error(f"Lỗi trong daily_backup task: {e}", exc_info=True)

    @daily_backup.before_loop
    async def before_daily_backup(self):
        await self.bot.wait_until_ready()

    # ──────────────────────────────────────────────────────────────────
    # HÀM BACKUP CHUNG (dùng cho cả auto và thủ công)
    # ──────────────────────────────────────────────────────────────────

    async def _do_backup(
        self,
        channel_id: int,
        is_auto: bool,
        ctx: commands.Context | None = None,
    ) -> None:
        """
        Xuất file SQL và gửi vào channel_id.
        Nếu có ctx, cũng gửi phản hồi về kênh của ctx.
        """
        now = datetime.now(UTC7)
        filename = _make_filename()

        # Sinh nội dung SQL
        sql_bytes, p_count, l_count = await generate_sql_dump(self.bot)

        file_obj = discord.File(
            fp=io.BytesIO(sql_bytes),
            filename=filename,
        )
        embed = _make_backup_embed(now, p_count, l_count, is_auto=is_auto)

        # Gửi vào kênh backup chính thức
        backup_channel = self.bot.get_channel(channel_id)
        if backup_channel is None:
            try:
                backup_channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                log.error(f"Không tìm thấy kênh backup ID={channel_id}: {e}")
                backup_channel = None

        if backup_channel:
            await backup_channel.send(embed=embed, file=file_obj)
            log.info(
                f"Backup gửi thành công → #{backup_channel.name} | "
                f"{p_count} profiles, {l_count} logs | {filename}"
            )
        else:
            log.warning(f"Kênh backup ID={channel_id} không tìm thấy, bỏ qua.")

        if ctx is not None and (backup_channel is None or ctx.channel.id != channel_id):
            file_obj2 = discord.File(
                fp=io.BytesIO(sql_bytes),
                filename=filename,
            )
            await ctx.send(
                content=f"**Backup thủ công hoàn tất!** File: `{filename}`",
                embed=embed,
                file=file_obj2,
            )

    # ──────────────────────────────────────────────────────────────────
    # LỆNH THỦ CÔNG: y!backup
    # ──────────────────────────────────────────────────────────────────

    @commands.command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup_cmd(self, ctx: commands.Context):
        """[Admin/Owner] Kích hoạt backup database thủ công ngay lập tức."""
        msg = await ctx.send("Đang xuất dữ liệu, vui lòng chờ...")
        try:
            await self._do_backup(
                channel_id=BACKUP_CHANNEL_ID,
                is_auto=False,
                ctx=ctx,
            )
        except Exception as e:
            log.error(f"Lỗi backup thủ công: {e}", exc_info=True)
            await ctx.send(f"Backup thất bại: `{e}`")
        finally:
            try:
                await msg.delete()
            except Exception:
                pass

    @backup_cmd.error
    async def backup_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Bạn không có quyền sử dụng lệnh này!")


async def setup(bot):
    await bot.add_cog(StaffBackupCog(bot))
