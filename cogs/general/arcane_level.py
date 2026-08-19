import logging
import re
import asyncio

import discord
from discord.ext import commands

from cogs.common.db import fetchval_db, execute_db, update_task_progress

log = logging.getLogger("ArcaneLevelSync")

CHANNEL_ID = 1512145025960509540
ARCANE_ID = 437808476106784770

ROLE_LEVELS = {
    5: 1533400375443324959,
    15: 1533405894933610497,
    30: 1533406979014398043,
    50: 1533408225439912020,
    75: 1533409372779319326,
    100: 1533412010795073636
}

class ArcaneLevelSync(commands.Cog):
    """Cog đồng bộ và cấp phát Role cấp độ từ bot Arcane."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Tạo bảng DB nếu chưa có
        sql = """
        CREATE TABLE IF NOT EXISTS member_levels (
            discord_id BIGINT PRIMARY KEY,
            max_level INT
        )
        """
        await execute_db(self.bot, sql)
        log.info("Đã khởi tạo/kiểm tra bảng member_levels.")

    async def get_user_level(self, discord_id: int) -> int:
        """Lấy max_level của user trong DB."""
        sql = "SELECT max_level FROM member_levels WHERE discord_id = $1"
        res = await fetchval_db(self.bot, sql, discord_id)
        return res if res is not None else 0

    async def upsert_user_level(self, discord_id: int, level: int):
        """Cập nhật level cho user trong DB (UPSERT)."""
        sql = """
        INSERT INTO member_levels (discord_id, max_level) 
        VALUES ($1, $2) 
        ON CONFLICT (discord_id) 
        DO UPDATE SET max_level = EXCLUDED.max_level
        """
        await execute_db(self.bot, sql, discord_id, level)

    async def _assign_level_roles(self, member: discord.Member, level: int):
        """
        Tính toán và gán TẤT CẢ các role cấp độ mà user đủ điều kiện, nếu user chưa có.
        Gỡ bỏ các role cấp độ không đủ điều kiện (ví dụ: bị reset level).
        """
        if member.guild.me and member.top_role >= member.guild.me.top_role:
            log.info(f"Bỏ qua gán/gỡ role level cho {member.display_name} vì role của họ >= role của bot.")
            return

        guild = member.guild
        roles_to_add = []
        roles_to_remove = []
        
        for req_level, role_id in ROLE_LEVELS.items():
            role = guild.get_role(role_id)
            if not role:
                continue
                
            if level >= req_level:
                # Đủ level -> Thêm vào nếu chưa có
                if role not in member.roles:
                    roles_to_add.append(role)
            else:
                # Không đủ level -> Xóa nếu đang có
                if role in member.roles:
                    roles_to_remove.append(role)
        
        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"Đạt Arcane level {level}")
                await asyncio.sleep(1) # Tránh rate limit của API Discord
                log.info(f"Đã gán {len(roles_to_add)} role level cho {member.display_name}")
                
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"Level hiện tại ({level}) không đủ điều kiện")
                await asyncio.sleep(1) # Tránh rate limit của API Discord
                log.info(f"Đã gỡ {len(roles_to_remove)} role level cũ cho {member.display_name}")
                
        except discord.Forbidden:
            log.error(f"Thiếu quyền gán/gỡ role cho {member.display_name}. Vui lòng kiểm tra vị trí Role của Bot!")
        except discord.HTTPException as e:
            log.error(f"Lỗi API khi quản lý role cho {member.display_name}: {e}")

    @commands.hybrid_command(name="synclv", description="Quét lịch sử và đồng bộ Level từ Arcane (Dành cho Admin)")
    @commands.has_permissions(administrator=True)
    async def synclv_cmd(self, ctx: commands.Context):
        """Lệnh quét toàn bộ kênh báo level để cấp lại role cho toàn server."""
        await ctx.defer()
        
        if ctx.guild is None:
            await ctx.send("<:symbol_wrong:1536629915598848072> Lệnh này chỉ dùng được trong Server!")
            return

        channel = self.bot.get_channel(CHANNEL_ID)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await ctx.send("<:symbol_wrong:1536629915598848072> Kênh cấu hình CHANNEL_ID không hợp lệ hoặc bot không truy cập được.")
            return

        processed_users: set[int] = set()
        count = 0
        skipped_old = 0
        skipped_processed = 0

        # Regex bóc tách số từ chuỗi cũ 'đã lên level *<số>*' và mới 'thu thập được <số> viên kẹo'
        level_regex = re.compile(r'(?:đã lên level|thu thập được)[^\d]+(\d+)', re.IGNORECASE)

        await ctx.send("<:symbol_reload:1536007679640600648> Đang bắt đầu quét lịch sử từ kênh Arcane... Quá trình này có thể mất vài phút.")

        # channel.history(limit=None) quét từ MỚI nhất về CŨ nhất theo mặc định
        async for message in channel.history(limit=None):
            if message.author.id != ARCANE_ID:
                continue
            
            if not message.mentions:
                continue

            user = message.mentions[0]
            member = ctx.guild.get_member(user.id)
            if not member:
                continue

            if member.id in processed_users:
                skipped_processed += 1
                continue

            # Kiểm tra thời gian tin nhắn so với thời điểm member join server hiện tại
            # Nếu tin nhắn được gửi TRƯỚC KHI member join lần này, đó là lịch sử cũ ("kiếp trước").
            if member.joined_at and message.created_at < member.joined_at:
                skipped_old += 1
                continue

            match = level_regex.search(message.content)
            if match:
                level = int(match.group(1))
                
                # Cập nhật database
                await self.upsert_user_level(member.id, level)
                
                # Gán các Role cần thiết
                await self._assign_level_roles(member, level)

                # Vì quét từ MỚI về CŨ, level đầu tiên gặp chắc chắn là level cao nhất hiện tại của user đó
                processed_users.add(member.id)
                count += 1

        await ctx.send(
            f"<:symbol_right:1536629912515903578> **Hoàn tất đồng bộ!**\n"
            f"🔹 Đã cập nhật thành công cho **{count}** người dùng.\n"
            f"🔹 Bỏ qua **{skipped_processed}** tin nhắn level thấp hơn.\n"
            f"🔹 Bỏ qua **{skipped_old}** tin nhắn từ 'kiếp trước'."
        )

    @synclv_cmd.error
    async def synclv_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<:symbol_ban:1537546960003801319> Bạn phải là Administrator mới có thể sử dụng lệnh này!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Lắng nghe real-time tin nhắn báo level của Arcane."""
        if message.channel.id != CHANNEL_ID or message.author.id != ARCANE_ID:
            return
        
        if not message.mentions:
            return

        level_regex = re.compile(r'(?:đã lên level|thu thập được)[^\d]+(\d+)', re.IGNORECASE)
        match = level_regex.search(message.content)
        if not match:
            return

        level = int(match.group(1))
        user = message.mentions[0]
        
        # Nếu user là member (nằm trong guild)
        if isinstance(user, discord.Member):
            max_level = await self.get_user_level(user.id)
            if level > max_level:
                await self.upsert_user_level(user.id, level)
                await self._assign_level_roles(user, level)
                
                # Nhiệm vụ
                await update_task_progress(self.bot, user.id, "arcane_lvup", 1)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Reset level về 0 khi member tham gia server."""
        await self.upsert_user_level(member.id, 0)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Reset level về 0 khi member rời khỏi server."""
        await self.upsert_user_level(member.id, 0)


async def setup(bot: commands.Bot):
    await bot.add_cog(ArcaneLevelSync(bot))
