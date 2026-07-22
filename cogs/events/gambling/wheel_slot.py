"""
wheel_slot.py — Cog Vòng Quay May Mắn (Wheel of Fortune)
=========================================================
Lệnh: y!wheel <tien_cuoc>

Vòng quay gồm 16 ô theo tỷ lệ:
  🟪 Tím      (1 ô,  6.25%) → x9.0  (+800%)
  🟩 Xanh lá  (1 ô,  6.25%) → x1.8  (+80%)
  🟥 Đỏ       (1 ô,  6.25%) → -100%
  🟨 Vàng     (1 ô,  6.25%) → -100% + 1 Vé Xổ Số
  🟧 Cam      (4 ô, 25.00%) → -50%
  🟫 Nâu      (4 ô, 25.00%) → -75%
  🟦 Xanh dương (4 ô, 25.00%) → -90%
"""

import random
import logging
from collections import deque
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    get_or_create_event_profile,
    add_event_points,
    deduct_event_points,
)

log = logging.getLogger("WheelSlots")

# ─────────────────────────────────────────────────────────────────────────────
# HẰNG SỐ MÀU SẮC EMBED
# ─────────────────────────────────────────────────────────────────────────────
COLOR_WIN     = 0x00FF00   # 🟢 Thắng
COLOR_LOSE    = 0xFF0000   # 🔴 Thua
COLOR_SPECIAL = 0xFFD700   # 🌟 Tím / Vàng đặc biệt

# ─────────────────────────────────────────────────────────────────────────────
# CẤU HÌNH VÒNG QUAY
# ─────────────────────────────────────────────────────────────────────────────

# Bảng phần thưởng: {emoji: (multiplier, is_win, has_ticket, description)}
WHEEL_CONFIG: dict[str, tuple[float, bool, bool, str]] = {
    "🟪": ( 9.00, True,  False, "x9.0 tiền cược — Thắng Lớn!"),
    "🟩": ( 1.80, True,  False, "x1.8 tiền cược — Thắng Nhẹ"),
    "🟥": (-1.00, False, False, "Mất 100% tiền cược"),
    "🟨": (-1.00, False, True,  "Mất 100% tiền cược + 🎟️ +1 Vé Xổ Số"),
    "🟧": (-0.50, False, False, "Mất 50% tiền cược"),
    "🟫": (-0.75, False, False, "Mất 75% tiền cược"),
    "🟦": (-0.90, False, False, "Mất 90% tiền cược"),
}

# Danh sách 16 ô gốc (theo tỷ lệ)
BASE_WHEEL: list[str] = [
    "🟪",                         # 1 ô Tím
    "🟩",                         # 1 ô Xanh lá
    "🟥",                         # 1 ô Đỏ
    "🟨",                         # 1 ô Vàng
    "🟧", "🟧", "🟧", "🟧",      # 4 ô Cam
    "🟫", "🟫", "🟫", "🟫",      # 4 ô Nâu
    "🟦", "🟦", "🟦", "🟦",      # 4 ô Xanh dương
]

# Trọng số tương ứng với thứ tự WHEEL_CONFIG (dùng cho random.choices)
WHEEL_POPULATION = list(WHEEL_CONFIG.keys())   # ["🟪","🟩","🟥","🟨","🟧","🟫","🟦"]
WHEEL_WEIGHTS    = [6.25, 6.25, 6.25, 6.25, 25.0, 25.0, 25.0]

# ─────────────────────────────────────────────────────────────────────────────
# TỌA ĐỘ 16 Ô TRÊN LƯỚI 7×7 (tính từ (row=0,col=0) ở góc trái-trên của phần body)
# Thứ tự: theo chiều kim đồng hồ. (0,3) = ô ngay dưới mũi tên → luôn là kết quả.
# ─────────────────────────────────────────────────────────────────────────────
TRACK: list[tuple[int, int]] = [
    (0, 3), (0, 4), (1, 5), (2, 6),
    (3, 6), (4, 6), (5, 5), (6, 4),
    (6, 3), (6, 2), (5, 1), (4, 0),
    (3, 0), (2, 0), (1, 1), (0, 2),
]

CENTER = (3, 3)  # Tâm vòng quay


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS TIỀN TỆ
# ─────────────────────────────────────────────────────────────────────────────

async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    """Lấy số dư điểm hiện tại của người dùng từ event_profiles."""
    row = await get_or_create_event_profile(bot, user_id)
    if row is None:
        return 0
    return int(row["points"] or 0)


async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    """
    Cộng (delta > 0) hoặc Trừ (delta < 0) điểm một cách an toàn.
    Trả về True nếu thành công, False nếu không đủ điểm để trừ.
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
        return None, f"❌ `{raw}` không phải số nguyên hợp lệ!"
    if amount <= 0:
        return None, "❌ Tiền cược phải lớn hơn **0**!"
    if amount > balance:
        return None, (
            f"❌ Bạn không đủ số dư!\n"
            f"Số dư hiện tại: **{balance:,}**, bạn muốn cược: **{amount:,}**."
        )
    return amount, None


# ─────────────────────────────────────────────────────────────────────────────
# THUẬT TOÁN RENDER MA TRẬN VÒNG QUAY 7×8
# ─────────────────────────────────────────────────────────────────────────────

def _render_wheel(winning_emoji: str) -> str:
    """
    Tạo chuỗi văn bản 8 dòng (1 dòng mũi tên + 7 dòng body 7 ô) mô phỏng
    vòng quay theo phong cách EPIC RPG.

    Thuật toán:
    1. Shuffle bản sao của BASE_WHEEL để tạo bàn quay ngẫu nhiên.
    2. Xoay deque sao cho winning_emoji nằm tại index 0 (vị trí (0,3) dưới mũi tên).
    3. Điền 16 emoji đã xoay vào đúng 16 tọa độ TRACK trên lưới 7×7.
    4. Ô trung tâm (3,3) luôn là ⬜. Ô trống là ▪️.
    5. Nối hàng mũi tên "▪️ ▪️ ▪️ 🔻 ▪️ ▪️ ▪️" lên đầu.
    """
    # Bước 1 — Tạo bàn quay ngẫu nhiên
    wheel: list[str] = list(BASE_WHEEL)
    random.shuffle(wheel)

    # Bước 2 — Xoay sao cho winning_emoji ở index 0
    # Nếu emoji xuất hiện nhiều lần, chọn lần đầu tiên tìm thấy.
    try:
        pivot = wheel.index(winning_emoji)
    except ValueError:
        # Trường hợp an toàn: bổ sung emoji vào đầu nếu bị mất trong quá trình shuffle
        wheel[0] = winning_emoji
        pivot = 0

    dq: deque[str] = deque(wheel)
    dq.rotate(-pivot)  # xoay trái pivot bước → index 0 = winning_emoji
    arranged: list[str] = list(dq)

    # Bước 3 — Xây dựng lưới 7 hàng × 7 cột, mặc định ▪️
    DARK   = "▪️"
    CENTER_EMOJI = "⬜"
    grid: list[list[str]] = [[DARK] * 7 for _ in range(7)]

    # Điền 16 ô theo TRACK
    for idx, (r, c) in enumerate(TRACK):
        grid[r][c] = arranged[idx]

    # Điền tâm vòng quay
    cr, cc = CENTER
    grid[cr][cc] = CENTER_EMOJI

    # Bước 4 — Render thành chuỗi văn bản
    arrow_row = "▪️ ▪️ ▪️ 🔻 ▪️ ▪️ ▪️"
    body_rows = [" ".join(row) for row in grid]

    return arrow_row + "\n" + "\n".join(body_rows)


# =============================================================================
# COG CHÍNH
# =============================================================================

class WheelSlots(commands.Cog):
    """🎡 Cog Vòng Quay May Mắn của Angelic Casino."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH CHÍNH: y!wheel
    # ─────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="wheel",
        description="Quay vòng may mắn — y!wheel <tiền_cược>",
    )
    async def wheel_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Vòng Quay May Mắn — 16 ô màu, xác suất có trọng số.

        Tỷ lệ thắng tổng cộng: 12.5%
        Tỷ lệ thua tổng cộng : 87.5%
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # ── Quay vòng → chọn kết quả ─────────────────────────────────────
        winning_emoji: str = random.choices(
            population=WHEEL_POPULATION,
            weights=WHEEL_WEIGHTS,
            k=1,
        )[0]

        mult, is_win, has_ticket, desc = WHEEL_CONFIG[winning_emoji]

        # ── Tính delta điểm ───────────────────────────────────────────────
        delta = round(mult * bet)

        # ── Cập nhật DB ───────────────────────────────────────────────────
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("⚠️ Lỗi cập nhật Database, thử lại sau!", ephemeral=True)
            return

        new_balance = balance + delta

        # ── Render ma trận vòng quay ──────────────────────────────────────
        wheel_grid = _render_wheel(winning_emoji)

        # ── Xác định màu Embed & emoji kết quả ───────────────────────────
        if winning_emoji in ("🟪", "🟨"):
            embed_color = COLOR_SPECIAL
        elif is_win:
            embed_color = COLOR_WIN
        else:
            embed_color = COLOR_LOSE

        if is_win:
            result_emoji = "🌟" if winning_emoji == "🟪" else "🟢"
        else:
            result_emoji = "🔴"

        # ── Xây dựng dòng kết quả ─────────────────────────────────────────
        if delta >= 0:
            result_value = f"+{delta:,}  *({desc})*"
        else:
            result_value = f"{delta:,}  *({desc})*"

        if has_ticket:
            result_value += "\n🎟️ **+1 Vé Xổ Số** — Chúc mừng! Hãy dùng vé này để tham gia xổ số!"

        # ── Dựng Embed ────────────────────────────────────────────────────
        embed = discord.Embed(
            title="🎡 Vòng Quay May Mắn",
            description=f"**Kết quả:** {winning_emoji}\n\n{wheel_grid}",
            color=embed_color,
        )
        embed.set_author(
            name=f"{ctx.author.display_name} — wheel",
            icon_url=ctx.author.display_avatar.url,
        )

        # 3 field hàng dọc
        embed.add_field(name="💰 Tiền cược",       value=f"{bet:,}",         inline=False)
        embed.add_field(name=f"{result_emoji} Kết quả", value=result_value,  inline=False)
        embed.add_field(name="💳 Số dư mới",       value=f"{new_balance:,}", inline=False)

        embed.set_footer(text="Angelic Casino • Vòng Quay May Mắn 🌸")
        await ctx.send(embed=embed)

    @wheel_cmd.error
    async def wheel_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❌ Thiếu tham số! Cú pháp: `y!wheel <tiền_cược>`",
                ephemeral=True,
            )


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WheelSlots(bot))