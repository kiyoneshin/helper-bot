"""
jail/interaction.py — JailInteraction Cog
==========================================
Tương tác cộng đồng với tù nhân:
  y!choccho @user — Tăng 1 án phạt (cooldown 5 phút/người)
  y!choan @user   — Giảm 1 án phạt (cooldown 60 giây/người)
  y!baolanh @user — Trả tiền chuộc để thả tù
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db, deduct_event_points, get_or_create_event_profile
from .core import (
    JAIL_CHANNEL_ID,
    COLOR_JAIL,
    COLOR_FREE,
    COLOR_WARN,
    is_jailed,
    add_penalty,
    reduce_penalty,
    release_member,
)

log = logging.getLogger("JailInteraction")

# Giá bảo lãnh tối thiểu — phải đắt hơn Thẻ Tống Giam (25,000) + Thẻ Đặc Xá (15,000)
BAIL_MIN_COST = 30_000
BAIL_PER_COUNT = 500   # mỗi lần lau dọn còn lại = 500 điểm thêm

class BailConfirmView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60.0)
        self.author_id = author_id
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Đây không phải yêu cầu của bạn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Xác Nhận Bảo Lãnh", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Hủy Bỏ", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()


class JailInteraction(commands.Cog):
    """🤝 Hệ Thống Chuồng Chó — Tương Tác Cộng Đồng"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────
    # Y!CHOCCHO @user — TĂNG 1 ÁN (Cooldown 5 phút/người)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="choccho", aliases=["kickdog", "ccho"])
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def choccho_cmd(self, ctx: commands.Context, member: discord.Member) -> None:
        """🦴 Chọc chó — thêm 1 án phạt cho tù nhân. Cooldown 5 phút."""
        if ctx.guild is None:
            return
        if member.bot:
            await ctx.send("❌ Chọc bot làm gì?", delete_after=5.0)
            return
        if member.id == ctx.author.id:
            await ctx.send("❌ Tự chọc mình à? 🤦", delete_after=5.0)
            return

        uid = str(member.id)
        if not await is_jailed(self.bot, uid):
            await ctx.send(
                f"⚠️ {ctx.author.mention} {member.mention} không bị giam đâu mà chọc!",
                delete_after=6.0,
            )
            return

        new_count = await add_penalty(self.bot, uid, 1)

        embed = discord.Embed(
            title="🦴 Đã Chọc Con Chó!",
            description=(
                f"{ctx.author.mention} tinh nghịch chọc vào chuồng!\n"
                f"{member.mention} bị thêm **1 án** — giờ còn **{new_count}** lần lau dọn. 😈"
            ),
            color=COLOR_JAIL,
        )
        await ctx.send(embed=embed)

    @choccho_cmd.error
    async def choccho_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Chọc nhiều quá rồi! "
                f"Nghỉ **{error.retry_after/60:.1f} phút** rồi tính.",
                delete_after=6.0,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Cú pháp: `y!choccho <@member>`", delete_after=5.0)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Không tìm thấy thành viên đó.", delete_after=5.0)

    # ─────────────────────────────────────────────────────────────────
    # Y!CHOAN @user — GIẢM 1 ÁN (Cooldown 60 giây/người)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="choan", aliases=["feeddog", "coan"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def choan_cmd(self, ctx: commands.Context, member: discord.Member) -> None:
        """🍖 Cho ăn — giảm 1 án phạt cho tù nhân. Cooldown 60 giây."""
        if ctx.guild is None:
            return
        if member.bot:
            await ctx.send("❌ Bot ăn gì được đâu?", delete_after=5.0)
            return

        uid = str(member.id)
        if not await is_jailed(self.bot, uid):
            await ctx.send(
                f"⚠️ {ctx.author.mention} {member.mention} không bị giam đâu!",
                delete_after=6.0,
            )
            return

        freed = await reduce_penalty(self.bot, member, 1)

        if freed:
            embed = discord.Embed(
                title="🎉 Lòng Tốt Đã Giải Phóng!",
                description=(
                    f"💖 {ctx.author.mention} vứt vào chuồng miếng xương thơm...\n"
                    f"{member.mention} vừa được hoàn thành án hạn — **TỰ DO**!"
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
                title="🍖 Cho Cún Ăn Vặt!",
                description=(
                    f"💖 {ctx.author.mention} tốt bụng cho {member.mention} ăn!\n"
                    f"Giảm **1 án** — còn lại **{remaining}** lần lau dọn nữa."
                ),
                color=COLOR_FREE,
            )
        await ctx.send(embed=embed)

    @choan_cmd.error
    async def choan_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Vừa cho ăn rồi! "
                f"Còn **{error.retry_after:.1f}s** nữa.",
                delete_after=6.0,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Cú pháp: `y!choan <@member>`", delete_after=5.0)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Không tìm thấy thành viên đó.", delete_after=5.0)

    # ─────────────────────────────────────────────────────────────────
    # Y!BAOLANH @user — BẢO LÃNH (TRẢ ĐIỂM SỰ KIỆN)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="baolanh", aliases=["bail", "bl"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def baolanh_cmd(self, ctx: commands.Context, member: discord.Member) -> None:
        """💸 Bảo lãnh — trả điểm sự kiện để thả tù nhân. Giá = max(30k, clean_count×500)."""
        if ctx.guild is None:
            return
        if member.bot:
            await ctx.send("❌ Bảo lãnh bot làm gì?", delete_after=5.0)
            return

        uid = str(member.id)
        if not await is_jailed(self.bot, uid):
            await ctx.send(
                f"⚠️ {ctx.author.mention} {member.mention} không bị giam đâu!",
                delete_after=6.0,
            )
            return

        # Lấy clean_count để tính giá
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count FROM jail_records WHERE discord_id = $1",
            uid,
        )
        if row is None:
            await ctx.send("❌ Không tìm thấy hồ sơ tù nhân.", delete_after=5.0)
            return

        clean_count = int(row["clean_count"])
        bail_cost = max(BAIL_MIN_COST, clean_count * BAIL_PER_COUNT)

        # Kiểm tra số dư người bảo lãnh
        payer_uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, payer_uid)
        payer_row = await fetchrow_db(
            self.bot,
            "SELECT points FROM event_profiles WHERE discord_id = $1",
            payer_uid,
        )
        payer_points = float(payer_row["points"]) if payer_row else 0.0

        if payer_points < bail_cost:
            embed_fail = discord.Embed(
                title="💸 Không Đủ Tiền Bảo Lãnh!",
                description=(
                    f"{ctx.author.mention} muốn bảo lãnh {member.mention}.\n\n"
                    f"💰 Chi phí bảo lãnh: **{bail_cost:,}** điểm\n"
                    f"💳 Số dư của bạn: **{payer_points:,.0f}** điểm\n\n"
                    f"Thiếu **{bail_cost - payer_points:,.0f}** điểm. Cày thêm đi! 😅"
                ),
                color=COLOR_WARN,
            )
            await ctx.send(embed=embed_fail)
            return

        view = BailConfirmView(ctx.author.id)
        embed_ask = discord.Embed(
            title="💸 Yêu Cầu Bảo Lãnh",
            description=(
                f"{ctx.author.mention} muốn bảo lãnh cho {member.mention}.\n\n"
                f"💰 Chi phí bảo lãnh: **{bail_cost:,}** điểm\n"
                f"💳 Số dư hiện tại: **{payer_points:,.0f}** điểm\n\n"
                f"Bạn có chắc chắn muốn bỏ ra số điểm này để bảo lãnh không?"
            ),
            color=discord.Color.gold(),
        )
        msg = await ctx.send(embed=embed_ask, view=view)
        await view.wait()

        if view.value is None:
            await msg.edit(content="❌ Đã hủy do quá thời gian.", embed=None, view=None)
            return
        elif not view.value:
            await msg.edit(content="❌ Bạn đã hủy bỏ yêu cầu bảo lãnh.", embed=None, view=None)
            return

        # Trừ điểm người bảo lãnh
        ok = await deduct_event_points(self.bot, payer_uid, bail_cost)
        if not ok:
            await msg.edit(
                content=f"❌ {ctx.author.mention} Lỗi khi trừ điểm! Vui lòng thử lại.",
                embed=None, view=None
            )
            return

        # Thả tù
        await release_member(self.bot, member)

        embed = discord.Embed(
            title="🕊️ Bảo Lãnh Thành Công!",
            description=(
                f"💸 {ctx.author.mention} vừa bỏ **{bail_cost:,}** điểm ra bảo lãnh!\n\n"
                f"🔓 {member.mention} được trả tự do — role và nickname đã khôi phục."
            ),
            color=COLOR_FREE,
        )
        embed.set_footer(text="Lần sau đừng để bạn bè phải bỏ tiền chuộc mình nhé!")
        await msg.edit(content=None, embed=embed, view=None)

    @baolanh_cmd.error
    async def baolanh_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Bình tĩnh nào! "
                f"Còn **{error.retry_after:.1f}s** nữa.",
                delete_after=6.0,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Cú pháp: `y!baolanh <@member>`", delete_after=5.0)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Không tìm thấy thành viên đó.", delete_after=5.0)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailInteraction(bot))

