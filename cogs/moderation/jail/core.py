"""
jail/core.py — JailCore Cog
============================
Xử lý cốt lõi: Tống giam (y!phattu), thả tự do (y!thatu, y!laudon),
helper functions cho toàn bộ hệ thống jail.
"""
from __future__ import annotations

import json
import logging
import random
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import execute_db, fetchrow_db

log = logging.getLogger("JailCore")

# ─────────────────────────────────────────────────────────────────────
# CONSTANTS (Import từ đây ở tất cả các file khác)
# ─────────────────────────────────────────────────────────────────────
JAIL_ROLE_ID    = 1513141241330536468
JAIL_CHANNEL_ID = 1513140873662169098
OWNER_ROLE_ID   = 1498711782192189494
ADMIN_ROLE_ID   = 1510230255988900002

COLOR_JAIL = 0xFF4444
COLOR_FREE = 0x00CC66
COLOR_WARN = 0xFFAA00

# Danh sách nickname chó ngẫu nhiên (hài hước/bựa)
DOG_NICKNAMES: list[str] = [
    "Chố Mực Bựa Bậc Cao",
    "Thằng Gâu Đần",
    "Con Phốc Xương Ngạo Mạn",
    "Cún Troll Chuyên Nghiệp",
    "Chố Sủa Hơi Nhiều",
    "Bơ Đơ Gâu Gâu",
    "Cẩu Tặc Bất Đắc Dĩ",
    "Tiểu Khuyển Vô Công Rồi Nghề",
    "Chúa Chố Chuồng Số 1",
    "Phạm Nhân Sủa Trước Hỏi Sau",
    "Chố Lai Trí Tuệ Nhân Tạo",
    "Bé Gâu Ngẩn Thương Hoài",
    "Chố Con Mà Nghịch",
    "Ẳng Ẳng Điên Điên",
    "Cún Cưng Của Trại Giam",
    "Mọi Chố Lọ Lem",
    "Thám Tử Gâu Gâu Nổi Tiếng",
    "Chố Nhà Giàu Đi Ở Tù",
    "Boss Chó Của Chuồng",
    "Husky Bị Phế Truất",
]


# ─────────────────────────────────────────────────────────────────────
# CUSTOM CHECK — dùng decorator cho các lệnh tù nhân
# ─────────────────────────────────────────────────────────────────────
def is_jailed_check():
    """Decorator check xem người dùng có đang bị giam không."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.channel.id != JAIL_CHANNEL_ID:
            return False
        row = await fetchrow_db(
            ctx.bot,
            "SELECT discord_id FROM jail_records WHERE discord_id = $1",
            str(ctx.author.id),
        )
        if row is None:
            await ctx.send(
                f"❌ {ctx.author.mention} Mày không phải phạm nhân, đừng có dùng lệnh này!",
                delete_after=5.0,
            )
            return False
        return True
    return commands.check(predicate)


async def is_jailed(bot: commands.Bot, uid: str) -> bool:
    """Trả về True nếu uid đang bị giam."""
    row = await fetchrow_db(bot, "SELECT discord_id FROM jail_records WHERE discord_id = $1", uid)
    return row is not None


# ─────────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────────
async def _init_jail_tables(bot: commands.Bot) -> None:
    """Khởi tạo bảng jail_records nếu chưa có."""
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS jail_records (
            discord_id    TEXT PRIMARY KEY,
            roles_cache   TEXT,
            clean_count   INTEGER NOT NULL DEFAULT 0,
            reason        TEXT,
            original_nick TEXT,
            jailed_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """,
    )
    # Migration an toàn nếu cột chưa tồn tại
    await execute_db(
        bot,
        "ALTER TABLE jail_records ADD COLUMN IF NOT EXISTS original_nick TEXT;",
    )
    log.info("✅ Bảng jail_records đã sẵn sàng.")


async def add_penalty(bot: commands.Bot, uid: str, n: int = 1) -> int:
    """Tăng clean_count thêm n. Trả về clean_count mới."""
    await execute_db(
        bot,
        "UPDATE jail_records SET clean_count = clean_count + $1 WHERE discord_id = $2",
        n, uid,
    )
    row = await fetchrow_db(bot, "SELECT clean_count FROM jail_records WHERE discord_id = $1", uid)
    return int(row["clean_count"]) if row else 0


async def reduce_penalty(bot: commands.Bot, member: discord.Member, n: int = 1) -> bool:
    """
    Giảm clean_count đi n. Nếu về 0 thì thả tù.
    Trả về True nếu đã thả tù.
    """
    uid = str(member.id)
    row = await fetchrow_db(bot, "SELECT clean_count FROM jail_records WHERE discord_id = $1", uid)
    if row is None:
        return False

    current = int(row["clean_count"])
    new_val = max(0, current - n)

    await execute_db(
        bot,
        "UPDATE jail_records SET clean_count = $1 WHERE discord_id = $2",
        new_val, uid,
    )

    if new_val <= 0:
        await release_member(bot, member)
        return True
    return False


async def release_member(bot: commands.Bot, member: discord.Member) -> bool:
    """
    PUBLIC helper — Thả tù: gỡ role Tù Nhân, khôi phục role cũ, khôi phục nick, xóa DB.
    Trả về True nếu thành công.
    """
    guild = member.guild
    jail_role = guild.get_role(JAIL_ROLE_ID)

    row = await fetchrow_db(
        bot,
        "SELECT roles_cache, original_nick FROM jail_records WHERE discord_id = $1",
        str(member.id),
    )

    # Gỡ role Tù Nhân
    if jail_role and jail_role in member.roles:
        try:
            await member.remove_roles(jail_role, reason="Thả tù")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Không thể gỡ role Tù Nhân cho {member}: {e}")

    if row is None:
        return True

    # Khôi phục role cũ
    roles_json = row["roles_cache"]
    if roles_json:
        try:
            role_ids: list[int] = json.loads(roles_json)
        except (json.JSONDecodeError, TypeError):
            role_ids = []
        restored: list[discord.Role] = []
        for rid in role_ids:
            r = guild.get_role(rid)
            if r is not None:
                restored.append(r)
        if restored:
            try:
                await member.add_roles(*restored, reason="Thả tù — khôi phục role")
            except (discord.Forbidden, discord.HTTPException) as e:
                log.error(f"Không thể khôi phục role cho {member}: {e}")

    # Khôi phục nickname gốc
    original_nick: Optional[str] = row["original_nick"]
    try:
        await member.edit(nick=original_nick, reason="Thả tù — khôi phục nickname")
    except (discord.Forbidden, discord.HTTPException):
        pass  # Bỏ qua nếu không có quyền

    # Xóa record
    await execute_db(bot, "DELETE FROM jail_records WHERE discord_id = $1", str(member.id))
    return True


# ─────────────────────────────────────────────────────────────────────
# COG CHÍNH
# ─────────────────────────────────────────────────────────────────────
class JailCore(commands.Cog):
    """🔒 Hệ Thống Chuồng Chó — Core (Tống Giam / Thả / Lau Dọn)"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await _init_jail_tables(self.bot)

    # ─────────────────────────────────────────────────────────────────
    # Y!PHATTU — TỐNG GIAM
    # ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="phattu", aliases=["jail", "giam"])
    @commands.has_any_role(OWNER_ROLE_ID, ADMIN_ROLE_ID)
    async def phattu_cmd(
        self,
        ctx: commands.Context,
        member: discord.Member,
        clean_count: int,
        *,
        reason: Optional[str] = "Không rõ lý do",
    ) -> None:
        """🔒 Tống giam một thành viên vào chuồng chó."""
        if ctx.guild is None:
            return
        if member.bot:
            await ctx.send(f"❌ {ctx.author.mention} Bot thì giam cái gì mậy!")
            return
        if member.id == ctx.author.id:
            await ctx.send(f"❌ {ctx.author.mention} Tự giam mình à? Thích làm phạm nhân ghê!")
            return
        if clean_count <= 0:
            await ctx.send(f"❌ {ctx.author.mention} Số lần dọn phải lớn hơn 0 chứ!")
            return

        existing = await fetchrow_db(
            self.bot,
            "SELECT discord_id FROM jail_records WHERE discord_id = $1",
            str(member.id),
        )
        if existing:
            await ctx.send(
                f"⚠️ {ctx.author.mention} {member.mention} đang bóc lịch rồi! "
                "Muốn thêm tội thì dùng `y!choccho`."
            )
            return

        guild = ctx.guild
        jail_role = guild.get_role(JAIL_ROLE_ID)
        if jail_role is None:
            await ctx.send("❌ Không tìm thấy role Tù Nhân! Kiểm tra lại `JAIL_ROLE_ID`.")
            return

        bot_top_role = guild.me.top_role

        # Lọc và lưu role
        saveable_roles: list[int] = []
        removable_roles: list[discord.Role] = []
        for role in member.roles:
            if role == guild.default_role:
                continue
            if role.is_integration() or role.is_premium_subscriber():
                continue
            if role >= bot_top_role:
                continue
            if role.id == JAIL_ROLE_ID:
                continue
            saveable_roles.append(role.id)
            removable_roles.append(role)

        roles_json = json.dumps(saveable_roles)
        original_nick = member.nick  # Lưu nickname gốc

        status = await execute_db(
            self.bot,
            "INSERT INTO jail_records (discord_id, roles_cache, clean_count, reason, original_nick) "
            "VALUES ($1, $2, $3, $4, $5)",
            str(member.id), roles_json, clean_count, reason, original_nick,
        )
        if status is None:
            await ctx.send("❌ Lỗi Database khi lưu hồ sơ tù nhân!")
            return

        # Gỡ role cũ
        if removable_roles:
            try:
                await member.remove_roles(*removable_roles, reason=f"Phạt tù bởi {ctx.author}")
            except (discord.Forbidden, discord.HTTPException) as e:
                log.error(f"Không thể gỡ role của {member}: {e}")

        # Ép role Tù Nhân
        try:
            await member.add_roles(jail_role, reason=f"Phạt tù bởi {ctx.author}")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Không thể thêm role Tù Nhân cho {member}: {e}")

        # Đổi nickname thành tên chó
        dog_name = random.choice(DOG_NICKNAMES)
        try:
            await member.edit(nick=dog_name, reason="Tống giam — đổi nickname")
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed = discord.Embed(
            title="🔒 TỐNG GIAM!",
            description=(
                f"Phạm nhân: {member.mention}\n"
                f"Người ra lệnh: {ctx.author.mention}\n"
                f"Lý do: **{reason}**\n"
                f"Hình phạt: Lau dọn **{clean_count}** lần tại <#{JAIL_CHANNEL_ID}>\n"
                f"Biệt danh mới: **{dog_name}** 🐕"
            ),
            color=COLOR_JAIL,
        )
        embed.set_footer(text="Dùng y!laudon để cải tạo • Angelic Moderation")
        await ctx.send(embed=embed)

        jail_channel = self.bot.get_channel(JAIL_CHANNEL_ID)
        if isinstance(jail_channel, discord.TextChannel):
            try:
                await jail_channel.send(
                    f"🚨 Cửa ngục khép lại! {member.mention} (a.k.a **{dog_name}**) vừa bị tống vào đây.\n"
                    f"Lý do: **{reason}**\n"
                    f"Hãy dùng `y!laudon` **{clean_count}** lần để chuộc lỗi! 🧹"
                )
            except discord.HTTPException:
                pass

    # ─────────────────────────────────────────────────────────────────
    # Y!THATU — ÂN XÁ (ADMIN)
    # ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="thatu", aliases=["unjail", "free"])
    @commands.has_any_role(OWNER_ROLE_ID, ADMIN_ROLE_ID)
    async def thatu_cmd(self, ctx: commands.Context, member: discord.Member) -> None:
        """🔓 Ân xá phạm nhân trước thời hạn."""
        if not await is_jailed(self.bot, str(member.id)):
            await ctx.send(f"⚠️ {member.mention} không phải phạm nhân.")
            return

        success = await release_member(self.bot, member)
        if success:
            embed = discord.Embed(
                title="🔓 ÂN XÁ!",
                description=(
                    f"Đã mở khóa còng! {member.mention} được ân xá trước thời hạn.\n"
                    f"Người ban lệnh: {ctx.author.mention}\n"
                    f"Toàn bộ role và nickname đã được khôi phục."
                ),
                color=COLOR_FREE,
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Có lỗi xảy ra khi thả {member.mention}!")

    # ─────────────────────────────────────────────────────────────────
    # Y!LAUDON — LAO ĐỘNG CÔNG ÍCH (TÙ NHÂN)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="laudon", aliases=["clean", "cosua"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @is_jailed_check()
    async def laudon_cmd(self, ctx: commands.Context) -> None:
        """🧹 Lau dọn chuồng chó để giảm 1 án."""
        uid = str(ctx.author.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count FROM jail_records WHERE discord_id = $1",
            uid,
        )
        if row is None:
            await ctx.send(f"❌ {ctx.author.mention} Mày không phải phạm nhân!")
            return

        current = int(row["clean_count"])
        if isinstance(ctx.author, discord.Member):
            freed = await reduce_penalty(self.bot, ctx.author, 1)
        else:
            freed = False

        if freed:
            await ctx.send(
                f"🎉 Hoàn thành cải tạo! {ctx.author.mention} "
                "đã chà sạch bóng cái chuồng chó này. Trả tự do và khôi phục quyền hạn!"
            )
        else:
            new_count = max(0, current - 1)
            await ctx.send(
                f"🧹 {ctx.author.mention} hì hục cọ toilet... "
                f"Còn lại **{new_count}** lần lau dọn để được tự do."
            )

    @laudon_cmd.error
    async def laudon_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            if ctx.channel.id == JAIL_CHANNEL_ID:
                await ctx.send(
                    f"⏳ {ctx.author.mention} Cứ từ từ, thở cái đã... "
                    f"Còn **{error.retry_after:.1f}s** nữa mới được lau tiếp.",
                    delete_after=5.0,
                )

    @phattu_cmd.error
    async def phattu_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Thiếu thông tin! Cú pháp: `y!phattu <@member> <số_lần_dọn> [lý do]`")
        elif isinstance(error, commands.MissingAnyRole):
            await ctx.send("❌ Mày không đủ quyền! Chỉ có **Owner** và **Admin** mới được dùng.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Sai cú pháp! Kiểm tra lại @mention và số lần dọn.")

    @thatu_cmd.error
    async def thatu_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingAnyRole):
            await ctx.send("❌ Mày không đủ quyền!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Không tìm thấy thành viên đó.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailCore(bot))
