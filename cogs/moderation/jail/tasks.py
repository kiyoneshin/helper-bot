"""
jail/tasks.py — JailTasks Cog
==============================
Cơ chế "Cày chay" cho tù nhân:
  {ctx.prefix}sua       — Giải toán (cộng/trừ/nhân/chia có dấu ngoặc) để giảm 2 án
  {ctx.prefix}nhatxuong — RNG 70% giảm 5 án, 30% tăng 1 án
  """
from __future__ import annotations

import asyncio
import operator
import random
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db
from .core import (
    JAIL_CHANNEL_ID,
    COLOR_JAIL,
    COLOR_FREE,
    COLOR_WARN,
    is_jailed_check,
    add_penalty,
    reduce_penalty,
    notify_cooldown,
)


def _generate_math_problem() -> tuple[str, int]:
    """
    Sinh một bài toán có cộng/trừ/nhân/chia với dấu ngoặc hợp lệ.
    Trả về (chuỗi đề bài, kết quả đúng).
    Đảm bảo: chia luôn chia hết, kết quả luôn nguyên dương.
    """
    # Sinh 2 phép tính lồng nhau: (a OP b) OP2 c
    ops = ["+", "-", "*"]
    op1 = random.choice(ops)
    op2 = random.choice(ops)

    a = random.randint(2, 15)
    b = random.randint(2, 15)
    c = random.randint(2, 10)

    op_fn = {"+": operator.add, "-": operator.sub, "*": operator.mul}
    inner = op_fn[op1](a, b)
    result = op_fn[op2](inner, c)

    expr = f"({a} {op1} {b}) {op2} {c}"
    return expr, result


class JailTasks(commands.Cog):
    """Hệ Thống Chuồng Chó — Cày Chay (ksua, knhatxuong)"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────
    # Y!SUA — GIẢI TOÁN (−2 ÁN)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="sua", aliases=["giaibai", "toan"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @is_jailed_check()
    async def sua_cmd(self, ctx: commands.Context) -> None:
        """Giải toán để giảm 2 lần án phạt. Cooldown 15 giây."""
        if ctx.guild is None:
            return

        expr, answer = _generate_math_problem()

        embed = discord.Embed(
            title="📐 Bài Thi Cải Tạo!",
            description=(
                f"{ctx.author.mention} muốn học bài để ra tù sớm hả?\n\n"
                f"**Tính: `{expr} = ?`**\n\n"
                f"⏱️ Trả lời trong **15 giây** (gõ số vào chat)!"
            ),
            color=COLOR_WARN,
        )
        embed.set_footer(text="Trả lời đúng → −2 án | Sai/Hết giờ → cảnh báo")
        await ctx.send(embed=embed)

        def check(m: discord.Message) -> bool:
            return (
                m.author.id == ctx.author.id
                and m.channel.id == ctx.channel.id
                and m.content.strip().lstrip("-").isdigit()
            )

        try:
            msg = await self.bot.wait_for("message", timeout=15.0, check=check)
            user_answer = int(msg.content.strip())
        except asyncio.TimeoutError:
            await ctx.send(
                f"⌛ {ctx.author.mention} Hết giờ rồi! Học dốt vừa thôi! Thử lại sau.",
                delete_after=8.0,
            )
            return

        freed = False
        if user_answer == answer:
            if isinstance(ctx.author, discord.Member):
                freed = await reduce_penalty(self.bot, ctx.author, 2)
            else:
                freed = False

            if freed:
                embed_ok = discord.Embed(
                    title="🎓 Thiên Tài! Trả Tự Do!",
                    description=f"<:symbol_right:1536289313959186472> {ctx.author.mention} Đúng! Đáp án là **{answer}**.\nHoàn thành cải tạo — thả tù ngay!",
                    color=COLOR_FREE,
                )
            else:
                row = await fetchrow_db(
                    self.bot,
                    "SELECT clean_count FROM jail_records WHERE discord_id = $1",
                    str(ctx.author.id),
                )
                remaining = int(row["clean_count"]) if row else 0
                embed_ok = discord.Embed(
                    title="<:symbol_right:1536289313959186472> Chính Xác!",
                    description=(
                        f"{ctx.author.mention} Đúng rồi! Đáp án là **{answer}**.\n"
                        f"Giảm **2 án** — còn lại **{remaining}** lần nữa."
                    ),
                    color=COLOR_FREE,
                )
            await ctx.send(embed=embed_ok)
        else:
            embed_fail = discord.Embed(
                title="<:symbol_wrong:1536289315867598849> Sai Bét!",
                description=(
                    f"{ctx.author.mention} Sai rồi! Đáp án đúng là **{answer}**, "
                    f"mày điền **{user_answer}**.\n\n"
                    "Không được giảm án. Học lại đi! 📚"
                ),
                color=COLOR_JAIL,
            )
            await ctx.send(embed=embed_fail)
            
        if not freed:
            self.bot.loop.create_task(notify_cooldown(ctx, 15.0, "sua"))

    @sua_cmd.error
    async def sua_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Nghỉ ngơi cái đã, học nhiều cũng hại não! "
                f"Còn **{error.retry_after:.1f}s** nữa.",
                delete_after=6.0,
            )

    # ─────────────────────────────────────────────────────────────────
    # Y!NHATXUONG — RNG (70% −5 ÁN / 30% +1 ÁN)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="nhatxuong", aliases=["nxt", "xuong"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    @is_jailed_check()
    async def nhatxuong_cmd(self, ctx: commands.Context) -> None:
        """Nhặt xương — 70% thành công (−5 án), 30% chó cắn ngược (+1 án). Cooldown 30 giây."""
        if ctx.guild is None:
            return

        uid = str(ctx.author.id)
        roll = random.random()

        freed = False
        if roll < 0.70:
            # Thành công
            if isinstance(ctx.author, discord.Member):
                freed = await reduce_penalty(self.bot, ctx.author, 5)
            else:
                freed = False

            if freed:
                embed = discord.Embed(
                    title="🦴 Jackpot Xương! Trả Tự Do!",
                    description=(
                        f"🎉 {ctx.author.mention} Nhặt trúng xương vàng! "
                        "Chó hài lòng thả cổng — mày được tự do!"
                    ),
                    color=COLOR_FREE,
                )
            else:
                row = await fetchrow_db(
                    self.bot,
                    "SELECT clean_count FROM jail_records WHERE discord_id = $1",
                    uid,
                )
                remaining = int(row["clean_count"]) if row else 0
                embed = discord.Embed(
                    title="🦴 Nhặt Được Xương!",
                    description=(
                        f"🐶 {ctx.author.mention} Chó vẫy đuôi vì mày ngoan!\n"
                        f"Giảm **5 án** — còn lại **{remaining}** lần nữa."
                    ),
                    color=COLOR_FREE,
                )
        else:
            # Xui xẻo — chó cắn ngược
            new_count = await add_penalty(self.bot, uid, 1)
            embed = discord.Embed(
                title="🐕 CHÓ CẮN NGƯỢC!",
                description=(
                    f"😱 {ctx.author.mention} Tưởng nhặt được xương ngon — "
                    "ai ngờ con chó đói cắn vào tay!\n\n"
                    f"**+1 án** — giờ còn **{new_count}** lần lau dọn. Đau chưa? 🤕"
                ),
                color=COLOR_JAIL,
            )

        embed.set_footer(text="70% may mắn / 30% xui xẻo • Cooldown 30s")
        await ctx.send(embed=embed)
        
        if not freed:
            self.bot.loop.create_task(notify_cooldown(ctx, 30.0, "nhatxuong"))

    @nhatxuong_cmd.error
    async def nhatxuong_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Đừng có tranh xương với chó liên tục! "
                f"Còn **{error.retry_after:.1f}s** nữa.",
                delete_after=6.0,
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailTasks(bot))

