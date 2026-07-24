"""
jail.py — Cog Chuồng Chó (Jail System)
=======================================
Hệ thống tù giam với cơ chế lao động công ích.
Phạm nhân bị gỡ toàn bộ role, ép role Tù Nhân,
và phải lau dọn đủ số lần mới được thả.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import execute_db, fetchrow_db

log = logging.getLogger("JailSystem")

JAIL_ROLE_ID = 1513141241330536468
JAIL_CHANNEL_ID = 1513140873662169098

OWNER_ROLE_ID = 1498711782192189494
ADMIN_ROLE_ID = 1510230255988900002

COLOR_JAIL = 0xFF4444
COLOR_FREE = 0x00FF00


async def _init_jail_tables(bot: commands.Bot) -> None:
    """Khởi tạo bảng jail_records nếu chưa có."""
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS jail_records (
            discord_id TEXT PRIMARY KEY,
            roles_cache TEXT,
            clean_count INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            jailed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """,
    )
    log.info("✅ Bảng jail_records đã sẵn sàng.")


async def _release_member(bot: commands.Bot, member: discord.Member) -> bool:
    """
    Thả tù: Gỡ role Tù Nhân, khôi phục role cũ, xóa DB.
    Trả về True nếu thành công.
    """
    guild = member.guild
    jail_role = guild.get_role(JAIL_ROLE_ID)

    row = await fetchrow_db(
        bot,
        "SELECT roles_cache FROM jail_records WHERE discord_id = $1",
        str(member.id),
    )

    # Gỡ role Tù Nhân (nếu đang có)
    if jail_role and jail_role in member.roles:
        try:
            await member.remove_roles(jail_role, reason="Thả tù")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Không thể gỡ role Tù Nhân cho {member}: {e}")

    if row is None:
        # Không có record trong DB, chỉ gỡ role là đủ
        return True

    # Khôi phục role cũ
    roles_json = row["roles_cache"]
    if roles_json:
        try:
            role_ids: list[int] = json.loads(roles_json)
        except (json.JSONDecodeError, TypeError):
            role_ids = []

        restored_roles: list[discord.Role] = []
        for rid in role_ids:
            role = guild.get_role(rid)
            if role is not None:
                restored_roles.append(role)

        if restored_roles:
            try:
                await member.add_roles(*restored_roles, reason="Thả tù — khôi phục role")
            except (discord.Forbidden, discord.HTTPException) as e:
                log.error(f"Không thể khôi phục role cho {member}: {e}")

    # Xóa record
    await execute_db(bot, "DELETE FROM jail_records WHERE discord_id = $1", str(member.id))
    return True


class JailSystem(commands.Cog):
    """🔒 Hệ Thống Chuồng Chó — Tù Giam & Lao Động Công Ích"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await _init_jail_tables(self.bot)

    # ─────────────────────────────────────────────────────────────────────
    # LỆNH Y!PHATTU — TỐNG GIAM
    # ─────────────────────────────────────────────────────────────────────
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
        if member.bot:
            await ctx.send(f"❌ {ctx.author.mention} Bot thì giam cái gì mậy!")
            return
        if member.id == ctx.author.id:
            await ctx.send(f"❌ {ctx.author.mention} Tự giam mình à? Thích làm phạm nhân ghê!")
            return
        if clean_count <= 0:
            await ctx.send(f"❌ {ctx.author.mention} Số lần dọn phải lớn hơn 0 chứ!")
            return

        # Kiểm tra đã bị giam chưa
        existing = await fetchrow_db(
            self.bot,
            "SELECT discord_id FROM jail_records WHERE discord_id = $1",
            str(member.id),
        )
        if existing:
            await ctx.send(f"⚠️ {ctx.author.mention} {member.mention} đang bóc lịch rồi! Muốn thêm tội thì gõ thêm lệnh khác.")
            return

        guild = ctx.guild
        if guild is None:
            return

        jail_role = guild.get_role(JAIL_ROLE_ID)
        if jail_role is None:
            await ctx.send("❌ Không tìm thấy role Tù Nhân! Kiểm tra lại `JAIL_ROLE_ID`.")
            return

        bot_top_role = guild.me.top_role

        # Lọc role cần lưu trữ
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

        # Lưu DB
        status = await execute_db(
            self.bot,
            "INSERT INTO jail_records (discord_id, roles_cache, clean_count, reason) VALUES ($1, $2, $3, $4)",
            str(member.id), roles_json, clean_count, reason,
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

        # Thông báo ở kênh hiện tại
        embed = discord.Embed(
            title="🔒 TỐNG GIAM!",
            description=(
                f"Phạm nhân: {member.mention}\n"
                f"Người ra lệnh: {ctx.author.mention}\n"
                f"Lý do: **{reason}**\n"
                f"Hình phạt: Lau dọn **{clean_count}** lần tại <#{JAIL_CHANNEL_ID}>"
            ),
            color=COLOR_JAIL,
        )
        embed.set_footer(text="Dùng y!laudon để cải tạo • Angelic Moderation")
        await ctx.send(embed=embed)

        # Bắn thông báo vào kênh tù
        jail_channel = self.bot.get_channel(JAIL_CHANNEL_ID)
        if isinstance(jail_channel, discord.TextChannel):
            try:
                await jail_channel.send(
                    f"🚨 Cửa ngục khép lại! {member.mention} vừa bị tống vào đây.\n"
                    f"Lý do: **{reason}**\n"
                    f"Hãy dùng `y!laudon` **{clean_count}** lần để chuộc lỗi! 🧹"
                )
            except discord.HTTPException:
                pass

    # ─────────────────────────────────────────────────────────────────────
    # LỆNH Y!THATU — THẢI TÙ (ÂN XÁ)
    # ─────────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="thatu", aliases=["unjail", "free"])
    @commands.has_any_role(OWNER_ROLE_ID, ADMIN_ROLE_ID)
    async def thatu_cmd(self, ctx: commands.Context, member: discord.Member) -> None:
        """🔓 Ân xá phạm nhân trước thời hạn."""
        success = await _release_member(self.bot, member)
        if success:
            embed = discord.Embed(
                title="🔓 ÂN XÁ!",
                description=(
                    f"Đã mở khóa còng! {member.mention} được ân xá trước thời hạn.\n"
                    f"Người ban lệnh: {ctx.author.mention}\n"
                    f"Toàn bộ role đã được khôi phục."
                ),
                color=COLOR_FREE,
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Có lỗi xảy ra khi thả {member.mention}!")

    # ─────────────────────────────────────────────────────────────────────
    # LỆNH Y!LAUDON — LAO ĐỘNG CÔNG ÍCH (DÀNH CHO PHẠM NHÂN)
    # ─────────────────────────────────────────────────────────────────────
    @commands.command(name="laudon", aliases=["clean", "cosua"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def laudon_cmd(self, ctx: commands.Context) -> None:
        """🧹 Lau dọn chuồng chó để giảm án."""
        # Chỉ hoạt động trong kênh tù
        if ctx.channel.id != JAIL_CHANNEL_ID:
            return

        uid = str(ctx.author.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count FROM jail_records WHERE discord_id = $1",
            uid,
        )

        if row is None:
            await ctx.send(f"❌ {ctx.author.mention} Mày không phải phạm nhân, lau dọn làm gì?")
            return

        current_count = int(row["clean_count"])

        if current_count <= 0:
            # Edge case: đã xong nhưng chưa thả
            if isinstance(ctx.author, discord.Member):
                await _release_member(self.bot, ctx.author)
            await ctx.send(f"🎉 {ctx.author.mention} đã hoàn thành cải tạo! Trả tự do!")
            return

        new_count = current_count - 1

        await execute_db(
            self.bot,
            "UPDATE jail_records SET clean_count = $1 WHERE discord_id = $2",
            new_count, uid,
        )

        if new_count > 0:
            await ctx.send(
                f"🧹 {ctx.author.mention} hì hục cọ toilet... "
                f"Còn lại **{new_count}** lần lau dọn để được tự do."
            )
        else:
            # Hoàn thành → Thả tù
            if isinstance(ctx.author, discord.Member):
                await _release_member(self.bot, ctx.author)
            await ctx.send(
                f"🎉 Hoàn thành cải tạo! {ctx.author.mention} "
                f"đã chà sạch bóng cái chuồng chó này. "
                f"Trả tự do và khôi phục quyền hạn!"
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
            await ctx.send(
                "❌ Thiếu thông tin! Cú pháp: `y!phattu <@member> <số_lần_dọn> [lý do]`"
            )
        elif isinstance(error, commands.MissingAnyRole):
            await ctx.send("❌ Mày không đủ quyền! Chỉ có **Owner** và **Admin** mới được dùng lệnh này.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Sai cú pháp! Kiểm tra lại @mention và số lần dọn.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailSystem(bot))
