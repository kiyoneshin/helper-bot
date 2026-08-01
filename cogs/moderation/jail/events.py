"""
jail/events.py — JailEvents Cog
=================================
Event listeners liên quan đến hệ thống chuồng chó:
  on_message   — Tù nhân chat sai format (không kết thúc gâu/ẳng) → xóa + cảnh cáo
  on_member_join — Nếu member vẫn còn trong DB jail sau khi rejoin → đổi lại nick chó
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db, execute_db
from .core import (
    JAIL_ROLE_ID,
    JAIL_CHANNEL_ID,
    COLOR_WARN,
    DOG_NICKNAMES,
)
import random

log = logging.getLogger("JailEvents")

# Từ kết thúc hợp lệ cho tù nhân (không phân biệt hoa thường)
VALID_ENDINGS = ("gâu", "ẳng", "gau", "ang")


def _ends_with_valid(text: str) -> bool:
    """Kiểm tra chuỗi có kết thúc bằng gâu/ẳng không (bỏ qua khoảng trắng/dấu chấm cuối)."""
    cleaned = text.strip().rstrip("!.,~? ").lower()
    return any(cleaned.endswith(v) for v in VALID_ENDINGS)


class JailEvents(commands.Cog):
    """👂 Hệ Thống Chuồng Chó — Event Listeners"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────
    # ON_MESSAGE — Bắt lỗi chat không kết thúc gâu/ẳng
    # ─────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Bỏ qua bot
        if message.author.bot:
            return

        # Chỉ xử lý trong kênh tù
        if message.channel.id != JAIL_CHANNEL_ID:
            return

        # Chỉ xử lý nếu tác giả có role Tù Nhân
        if not isinstance(message.author, discord.Member):
            return
        if not any(r.id == JAIL_ROLE_ID for r in message.author.roles):
            return

        # Bỏ qua lệnh (bắt đầu bằng prefix)
        if message.content.startswith(("y!", "!", "/", ".")):
            return

        # Bỏ qua tin nhắn trống (chỉ có attachment/sticker/embed)
        if not message.content.strip():
            return

        # Kiểm tra format
        if not _ends_with_valid(message.content):
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            try:
                warn = await message.channel.send(
                    f"🚫 {message.author.mention} **Tù nhân phải kết thúc câu bằng `gâu` hoặc `ẳng`!**\n"
                    f"Tin nhắn vi phạm đã bị xóa. Lần sau cẩn thận! 🐕",
                    delete_after=8.0,
                )
            except discord.HTTPException:
                pass

    # ─────────────────────────────────────────────────────────────────
    # ON_MEMBER_JOIN — Khôi phục nick chó nếu rejoin trong khi đang bị giam
    # ─────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Nếu thành viên vừa vào lại mà vẫn còn record jail → đặt lại nick chó."""
        uid = str(member.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count, original_nick FROM jail_records WHERE discord_id = $1",
            uid,
        )
        if row is None:
            return  # Không bị giam, bỏ qua

        # Còn trong DB jail → ép lại role Tù Nhân và đặt lại nick chó
        guild = member.guild
        jail_role = guild.get_role(JAIL_ROLE_ID)
        if jail_role is not None:
            try:
                await member.add_roles(jail_role, reason="Rejoin — đang bị giam")
            except (discord.Forbidden, discord.HTTPException) as e:
                log.error(f"Không thể ép lại role Tù Nhân cho {member} khi rejoin: {e}")

        # Đặt lại nickname chó ngẫu nhiên (vì rejoin sẽ reset nick)
        dog_name = random.choice(DOG_NICKNAMES)
        try:
            await member.edit(nick=dog_name, reason="Rejoin khi đang bị giam — đặt lại nick chó")
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Thông báo vào kênh tù
        jail_channel = self.bot.get_channel(JAIL_CHANNEL_ID)
        if isinstance(jail_channel, discord.TextChannel):
            try:
                clean_count = int(row["clean_count"])
                await jail_channel.send(
                    f"🔄 {member.mention} **(a.k.a {dog_name})** vừa quay lại server!\n"
                    f"Nhưng còn **{clean_count}** lần lau dọn chưa xong — trốn không thoát đâu! 🐕",
                )
            except discord.HTTPException:
                pass

        log.info(f"Thành viên {member} rejoin trong khi đang bị giam — đã ép lại role và nick chó.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailEvents(bot))

