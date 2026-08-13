"""
jail/minigames.py — JailGames Cog
==================================
Minigame sinh tử cho tù nhân:
  {ctx.prefix}lcuoc     — Tung đồng xu: Thắng −5 án | Thua +10 án
  {ctx.prefix}lvuotnguc — 5% tự do | 95% nhân 3 án + tag Admin
  """
from __future__ import annotations

import random

import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db, execute_db
from .core import (
    JAIL_CHANNEL_ID,
    ADMIN_ROLE_ID,
    COLOR_JAIL,
    COLOR_FREE,
    COLOR_WARN,
    is_jailed_check,
    add_penalty,
    reduce_penalty,
    release_member,
    notify_cooldown,
    MAIN_CHANNEL_ID,
)


class JailGames(commands.Cog):
    """Hệ Thống Chuồng Chó — Minigame (klcuoc, klvuotnguc)"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────
    # Y!LCUOC — TUNG ĐỒNG XU (50/50: −5 ÁN / +10 ÁN)
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="lcuoc", aliases=["lc", "jailflip"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    @is_jailed_check()
    async def lcuoc_cmd(self, ctx: commands.Context) -> None:
        """Tung đồng xu sinh tử: Thắng −5 án / Thua +10 án. Cooldown 20 giây."""
        if ctx.guild is None:
            return

        uid = str(ctx.author.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count FROM jail_records WHERE discord_id = $1",
            uid,
        )
        if row is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không có dữ liệu tù nhân.")
            return

        current = int(row["clean_count"])

        # Thông báo đang tung
        embed_toss = discord.Embed(
            title="🪙 Đồng Xu Sinh Tử!",
            description=(
                f"{ctx.author.mention} run run tung đồng xu...\n\n"
                f"**Thắng:** Giảm **5 án** (còn {max(0, current-5)})\n"
                f"**Thua:** Tăng **10 án** (lên {current+10})\n\n"
                "<:gambling_dice:1537539887769591828> *Quay vòng...*"
            ),
            color=COLOR_WARN,
        )
        msg = await ctx.send(embed=embed_toss)

        win = random.random() < 0.5
        coin_face = "🟡 NGỬA!" if win else "⚫ SẤP!"
        freed = False

        if win:
            if isinstance(ctx.author, discord.Member):
                freed = await reduce_penalty(self.bot, ctx.author, 5)
            else:
                freed = False

            if freed:
                embed_result = discord.Embed(
                    title=f"🪙 {coin_face} — THẮNG & TỰ DO!",
                    description=f"🎉 {ctx.author.mention} Ngửa đồng xu! Hoàn thành cải tạo — thả tù ngay!",
                    color=COLOR_FREE,
                )
            else:
                new_row = await fetchrow_db(
                    self.bot,
                    "SELECT clean_count FROM jail_records WHERE discord_id = $1",
                    uid,
                )
                remaining = int(new_row["clean_count"]) if new_row else 0
                embed_result = discord.Embed(
                    title=f"🪙 {coin_face} — THẮNG!",
                    description=(
                        f"🎉 {ctx.author.mention} Ngửa đồng xu!\n"
                        f"Giảm **5 án** — còn lại **{remaining}** lần."
                    ),
                    color=COLOR_FREE,
                )
        else:
            new_count = await add_penalty(self.bot, uid, 10)
            embed_result = discord.Embed(
                title=f"🪙 {coin_face} — THUA!",
                description=(
                    f"💀 {ctx.author.mention} Đen đủi! Sấp đồng xu!\n"
                    f"Tăng **10 án** — giờ còn **{new_count}** lần lau dọn. Chơi dao thì đứt tay! 🩸"
                ),
                color=COLOR_JAIL,
            )

        try:
            await msg.edit(embed=embed_result)
        except discord.HTTPException:
            await ctx.send(embed=embed_result)
            
        if not freed:
            self.bot.loop.create_task(notify_cooldown(ctx, 20.0, "lcuoc"))

    @lcuoc_cmd.error
    async def lcuoc_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ {ctx.author.mention} Đã cược xong rồi, chưa đến giờ cược tiếp! "
                f"Còn **{error.retry_after:.1f}s** nữa.",
                delete_after=6.0,
            )

    # ─────────────────────────────────────────────────────────────────
    # Y!LVUOTNGUC — 5% TỰ DO | 95% NHÂN 3 ÁN + TAG ADMIN
    # ─────────────────────────────────────────────────────────────────
    @commands.command(name="lvuotnguc", aliases=["lvn", "break"])
    @commands.cooldown(1, 300, commands.BucketType.user)
    @is_jailed_check()
    async def lvuotnguc_cmd(self, ctx: commands.Context) -> None:
        """Vượt ngục: 5% thoát thành công | 95% bị bắt lại (×3 án + tag Admin). Cooldown 5 phút."""
        if ctx.guild is None:
            return

        uid = str(ctx.author.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT clean_count FROM jail_records WHERE discord_id = $1",
            uid,
        )
        if row is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không có dữ liệu tù nhân.")
            return

        current = int(row["clean_count"])

        embed_attempt = discord.Embed(
            title="🏃 Kế Hoạch Vượt Ngục!",
            description=(
                f"{ctx.author.mention} đang lên kế hoạch đào tường vượt ngục...\n\n"
                "⚠️ **Rủi ro cực cao:**\n"
                "• 5% — Thoát thành công, trả tự do ngay!\n"
                f"• 95% — Bị bắt lại, án phạt nhân **×3** ({current} → {current*3})!\n\n"
                "*Đang thực hiện...*"
            ),
            color=COLOR_WARN,
        )
        msg = await ctx.send(embed=embed_attempt)

        success = random.random() < 0.05  # 5%

        if success:
            if isinstance(ctx.author, discord.Member):
                await release_member(self.bot, ctx.author)
            embed_result = discord.Embed(
                title="🎊 VƯỢT NGỤC THÀNH CÔNG!",
                description=(
                    f"🏃💨 {ctx.author.mention} **LỌT RÀO!**\n\n"
                    "Không ai ngăn được màk Tự do hoàn toàn — role và nickname đã khôi phục!\n"
                    "*(Đừng để bị bắt lại lần nữa nhé...)*"
                ),
                color=COLOR_FREE,
            )
            try:
                await msg.edit(embed=embed_result)
            except discord.HTTPException:
                await ctx.send(embed=embed_result)
        else:
            # Bị bắt lại — nhân 3 án
            new_count = current * 3
            await execute_db(
                self.bot,
                "UPDATE jail_records SET clean_count = $1 WHERE discord_id = $2",
                new_count, uid,
            )

            embed_result = discord.Embed(
                title="🚨 BỊ BẮT LẠI! TĂNG GẤP BA ÁN!",
                description=(
                    f"😭 {ctx.author.mention} **Bị bảo vệ tóm cổ ngay rào!**\n\n"
                    f"Án phạt nhân **×3**: {current} → **{new_count}** lần lau dọn!\n"
                    "Xưa chưa từng có ai vượt ngục ở đây mà thoát được... 🐕"
                ),
                color=COLOR_JAIL,
            )
            try:
                await msg.edit(embed=embed_result)
            except discord.HTTPException:
                await ctx.send(embed=embed_result)

            # Đăng lên Main Channel bêu rếu thay vì tag Admin
            main_channel = self.bot.get_channel(MAIN_CHANNEL_ID)
            if isinstance(main_channel, discord.TextChannel):
                try:
                    await main_channel.send(
                        f"📢 **TIN NÓNG HỔI:** Tù nhân {ctx.author.mention} vừa có một pha đào tường vượt ngục chuồng chó đi vào lòng đất! 🤡\n"
                        f"Kế hoạch ngu ngốc bị phát hiện tại trận! Kết quả: Lôi xệch về chuồng, án phạt tăng x3 lên tới **{new_count}** lần cọ toilet. Cười ẻ!!! 😂"
                    )
                except discord.HTTPException:
                    pass
            
            self.bot.loop.create_task(notify_cooldown(ctx, 300.0, "lvuotnguc"))

    @lvuotnguc_cmd.error
    async def lvuotnguc_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            minutes = error.retry_after / 60
            await ctx.send(
                f"⏳ {ctx.author.mention} Vừa thử vượt ngục rồi! "
                f"Còn **{minutes:.1f} phút** nữa mới được thử lại.",
                delete_after=8.0,
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JailGames(bot))

