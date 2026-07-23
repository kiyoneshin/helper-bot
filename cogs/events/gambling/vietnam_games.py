"""
vietnam_games.py — Cog Trò Chơi Dân Gian Việt Nam
==================================================
Lệnh: y!taixiu / y!tx <tai/xiu> <tien_cuoc>
"""

import random
import logging
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    get_or_create_event_profile,
    add_event_points,
    deduct_event_points,
)

log = logging.getLogger("VietnamGames")

COLOR_WIN  = 0x00FF00
COLOR_LOSE = 0xFF0000

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS TIỀN TỆ
# ─────────────────────────────────────────────────────────────────────────────

async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    """Lấy số dư hiện tại của người dùng."""
    row = await get_or_create_event_profile(bot, user_id)
    if row is None:
        return 0
    return int(row["points"] or 0)


async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    """
    Cộng (delta > 0) hoặc Trừ (delta < 0) tiền một cách an toàn.
    Trả về True nếu thành công, False nếu không đủ tiền để trừ.
    """
    if delta > 0:
        return await add_event_points(bot, user_id, delta, is_earned=False)
    elif delta < 0:
        return await deduct_event_points(bot, user_id, abs(delta))
    return True  # delta == 0


def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str]]:
    """
    Parse chuỗi tiền cược.
    Trả về (amount, None) nếu hợp lệ, hoặc (None, error_msg) nếu không.
    """
    try:
        amount = int(raw.replace(",", "").replace(".", ""))
    except ValueError:
        return None, f"`{raw}` không phải số hợp lệ!"
    if amount <= 0:
        return None, "Tiền cược phải lớn hơn **0**!"
    if amount > balance:
        return None, (
            f"Bạn không đủ số dư!\n"
            f"Số dư hiện tại: **{balance:,}**, bạn muốn cược: **{amount:,}**."
        )
    return amount, None

# ─────────────────────────────────────────────────────────────────────────────
# COG CHÍNH
# ─────────────────────────────────────────────────────────────────────────────

class VietnamGames(commands.Cog):
    """🎲 Cog chứa các trò chơi dân gian (Tài Xỉu...)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="taixiu",
        aliases=["tx"],
        description="Chơi Tài Xỉu (Sic Bo) — y!tx <tai/xiu> <tiền_cược>",
    )
    async def taixiu_cmd(self, ctx: commands.Context, choice: str, bet_raw: str) -> None:
        """
        Trò chơi Tài Xỉu (Sic Bo).
        - Lắc 3 viên xúc xắc.
        - Bão (3 viên giống nhau): Cái ăn tất (người chơi thua 100%).
        - Tài (11-17), Xỉu (4-10): Trả thưởng 1 ăn 0.95.
        """
        choice = choice.lower().strip()
        if choice not in ("tai", "xiu"):
            await ctx.send(
                "Lựa chọn không hợp lệ! Hãy dùng `tai` hoặc `xiu`.\n"
                "Cú pháp: `y!tx <tai/xiu> <tiền_cược>`",
                ephemeral=True,
            )
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # ── Cơ chế xúc xắc ──────────────────────────────────────────────
        d1, d2, d3 = [random.randint(1, 6) for _ in range(3)]
        total = d1 + d2 + d3
        is_bao = (d1 == d2 == d3)

        # ── Phân định Thắng / Thua ──────────────────────────────────────
        is_win = False
        outcome_desc = ""
        
        if is_bao:
            # Bão -> Thua luôn
            is_win = False
            outcome_desc = "BÃO"
            delta = -bet
        else:
            if 4 <= total <= 10:
                actual_result = "xiu"
                outcome_desc = "XỈU"
            else:
                actual_result = "tai"
                outcome_desc = "TÀI"
            
            if choice == actual_result:
                is_win = True
                # Thắng: nhận lại gốc và lời 95%
                delta = round(bet * 0.95)
            else:
                is_win = False
                delta = -bet

        # ── Cập nhật DB ──────────────────────────────────────────────────
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("Lỗi cập nhật Database, thử lại sau!", ephemeral=True)
            return

        new_balance = balance + delta

        # ── Xây dựng Giao diện Embed ────────────────────────────────────
        choice_str = "TÀI" if choice == "tai" else "XỈU"
        
        if is_bao:
            embed_title = "🌪️ Tài Xỉu — Bão Lũ Quét Sạch!"
            embed_color = COLOR_LOSE
            dice_desc = f"Kết quả: **[ {d1} ]  [ {d2} ]  [ {d3} ]**  **BÃO ({total})**"
            result_name = "🔴 Kết quả"
            result_val = f"{delta:,}  *(Mất sạch do dính Bão!)*"
        else:
            embed_title = "🎲 Tài Xỉu (Sic Bo)"
            embed_color = COLOR_WIN if is_win else COLOR_LOSE
            dice_desc = f"Kết quả: **[ {d1} ]  [ {d2} ]  [ {d3} ]**  Tổng: **{total} ({outcome_desc})**"
            
            if is_win:
                result_name = "🟢 Kết quả"
                result_val = f"+{delta:,}  *(+95% tiền cược)*"
            else:
                result_name = "🔴 Kết quả"
                result_val = f"{delta:,}  *(Mất trắng)*"

        embed = discord.Embed(
            title=embed_title,
            description=dice_desc,
            color=embed_color,
        )
        embed.set_author(
            name=f"{ctx.author.display_name} — taixiu",
            icon_url=ctx.author.display_avatar.url,
        )

        # 3 Field Hàng Dọc
        embed.add_field(name="🎯 Lựa chọn của bạn", value=f"{choice_str} - {bet:,}", inline=False)
        embed.add_field(name=result_name, value=result_val, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)

        embed.set_footer(text="Angelic Casino • Tài Xỉu 🌸")

        await ctx.send(embed=embed)

    @taixiu_cmd.error
    async def taixiu_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❌ Thiếu tham số! Cú pháp: `y!tx <tai/xiu> <tiền_cược>`",
                ephemeral=True,
            )

# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VietnamGames(bot))
