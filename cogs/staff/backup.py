"""
staff_backup.py — Cog Tự Động Sao Lưu Database Angelic Bot
===========================================================
Tính năng:
  - Tự động xuất toàn bộ dữ liệu sử dụng pg_dump với Custom Format (-F c).
  - Lịch trình: chạy lúc 04:00:00 sáng mỗi ngày theo múi giờ UTC+7.
  - Gửi file đính kèm vào kênh backup kín (LOG_CHANNEL_ID).
  - Lệnh kbackup: kích hoạt thủ công ngay lập tức (Admin/Owner).
  """

import discord
from discord.ext import commands, tasks
import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import Optional

log = logging.getLogger("StaffBackup")

UTC7 = timezone(timedelta(hours=7))

BACKUP_CHANNEL_ID = 1527706133127500061
BACKUP_TIME_UTC = dt_time(hour=21, minute=0, second=0)


def _make_filename() -> str:
    now = datetime.now(UTC7)
    return f"backup_angelic_{now.strftime('%Y_%m_%d_%H_%M')}.backup"


def _make_backup_embed(now: datetime, file_size_mb: float, is_auto: bool) -> discord.Embed:
    tag = "AUTO" if is_auto else "MANUAL"
    embed = discord.Embed(
        title=f"📦 [{tag}] Sao Lưu Toàn Bộ Database Thành Công",
        description=(
            f"Sao lưu dữ liệu {'định kỳ' if is_auto else 'thủ công'} "
            f"ngày **{now.strftime('%d/%m/%Y')}** hoàn tất!\n\n"
            f"**Thống kê:**\n"
            f"• Dung lượng: **{file_size_mb:.2f} MB**\n"
            f"• Định dạng: `Custom Format (pg_restore)`\n"
            f"• Thời điểm: `{now.strftime('%H:%M:%S')} UTC+7`"
        ),
        color=0x57f287,  # Discord green
    )
    embed.set_footer(text="Angelic Bot • Backup System 🌸")
    return embed


class StaffBackupCog(commands.Cog):
    """Cog quản lý backup tự động và thủ công cho database Angelic bằng pg_dump."""

    def __init__(self, bot: commands.Bot):
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
        ctx: Optional[commands.Context] = None,
    ) -> None:
        """
        Sử dụng pg_dump để xuất file backup Custom Format và gửi vào channel_id.
        """
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            log.error("Thiếu biến môi trường DATABASE_URL để thực hiện backup.")
            if ctx:
                await ctx.send("<:symbol_wrong:1536289315867598849> Thiếu biến môi trường `DATABASE_URL`!")
            return

        now = datetime.now(UTC7)
        filename = _make_filename()

        log.info(f"Đang thực thi pg_dump ra file: {filename}")
        
        # Lệnh pg_dump: -F c (Custom Format), -f (Output file)
        # Bọc tham số URL trong ngoặc kép để tránh lỗi ký tự đặc biệt
        cmd = f'pg_dump "{db_url}" -F c -f "{filename}"'
        
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode('utf-8').strip() if stderr else "Lỗi không xác định."
            log.error(f"pg_dump thất bại (Exit code {proc.returncode}): {error_msg}")
            raise Exception(f"pg_dump failed with exit code {proc.returncode}: {error_msg}")

        # Sau khi dump thành công, kiểm tra dung lượng file
        try:
            file_size_bytes = os.path.getsize(filename)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            embed = _make_backup_embed(now, file_size_mb, is_auto=is_auto)
            file_obj = discord.File(filename)

            # Lấy channel backup
            backup_channel = self.bot.get_channel(channel_id)
            if backup_channel is None:
                try:
                    backup_channel = await self.bot.fetch_channel(channel_id)
                except Exception as e:
                    log.error(f"Không tìm thấy kênh backup ID={channel_id}: {e}")
                    backup_channel = None

            # Gửi tin nhắn
            if ctx is not None and (backup_channel is None or ctx.channel.id != channel_id):
                # Gửi cho ctx nếu lệnh thủ công chạy khác kênh
                await ctx.send(
                    content=f"**Backup thủ công hoàn tất!** File: `{filename}`",
                    embed=embed,
                    file=file_obj,
                )
            elif isinstance(backup_channel, discord.TextChannel):
                await backup_channel.send(embed=embed, file=file_obj)
                log.info(f"Backup gửi thành công → #{backup_channel.name} | {file_size_mb:.2f} MB | {filename}")
            else:
                log.warning(f"Kênh backup ID={channel_id} không tìm thấy hoặc không hỗ trợ gửi tin nhắn, bỏ qua gửi file.")

        except Exception as e:
            log.error(f"Lỗi khi xử lý hoặc gửi file backup: {e}", exc_info=True)
            raise e
        finally:
            # Luôn dọn dẹp file .backup bất kể thành công hay thất bại
            if os.path.exists(filename):
                os.remove(filename)
                log.info(f"Đã dọn dẹp file {filename} khỏi ổ đĩa.")


    # ──────────────────────────────────────────────────────────────────
    # LỆNH THỦ CÔNG: kbackup
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="backup", description="[Admin/Owner] Kích hoạt backup database thủ công ngay lập tức.")
    @commands.has_permissions(administrator=True)
    async def backup_cmd(self, ctx: commands.Context):
        """[Admin/Owner] Kích hoạt backup database thủ công ngay lập tức."""
        msg = await ctx.send("Đang xuất dữ liệu bằng `pg_dump`, vui lòng chờ...")
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
    async def backup_cmd_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"Bạn không có quyền sử dụng lệnh này! Chỉ Admin/Owner mới được dùng `{ctx.prefix}backup`.")


    async def backup_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Bạn không có quyền sử dụng lệnh này!")


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffBackupCog(bot))
