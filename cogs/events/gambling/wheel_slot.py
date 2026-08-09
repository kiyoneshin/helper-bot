"""
wheel_slot.py — Cog Vòng Quay May Mắn (Wheel of Fortune)
=========================================================
Lệnh: kwheel <tien_cuoc>

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
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    get_or_create_event_profile,
    add_event_points,
    deduct_event_points,
    update_task_progress,
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
    "🟪": ( 9.00, True,  False, "x9.0 tiền cược — Nổ Hũ Trúng Máng!"),
    "🟩": ( 1.80, True,  False, "x1.8 tiền cược — Húp Nhẹ"),
    "🟥": (-1.00, False, False, "Mút Trọn (Mất 100%)"),
    "🟨": (-1.00, False, True,  "Mút Trọn + 🎟️ An ủi 1 Vé Xổ Số"),
    "🟧": (-0.50, False, False, "Cắt nửa vầng trăng (Mất 50%)"),
    "🟫": (-0.75, False, False, "Đi bụi (Mất 75%)"),
    "🟦": (-0.90, False, False, "Còn đúng cái nịt (Mất 90%)"),
}

# Mảng vòng quay CỐ ĐỊNH (16 ô, 4 chu kỳ theo chiều kim đồng hồ)
# Mỗi chu kỳ kết thúc bằng 1 ô đặc biệt; cơ cấu = 100% chuẩn xác.
BASE_WHEEL: list[str] = [
    "🟦", "🟧", "🟫", "🟨",   # Chu kỳ 1  → kết thúc: Vàng  (6.25%)
    "🟦", "🟧", "🟫", "🟪",   # Chu kỳ 2  → kết thúc: Tím   (6.25%)
    "🟦", "🟧", "🟫", "🟥",   # Chu kỳ 3  → kết thúc: Đỏ    (6.25%)
    "🟦", "🟧", "🟫", "🟩",   # Chu kỳ 4  → kết thúc: Xanh lá (6.25%)
]
# Tổng: 4× Xanh dương (25%), 4× Cam (25%), 4× Nâu (25%),
#       1× Vàng, 1× Tím, 1× Đỏ, 1× Xanh lá (mỗi loại 6.25%)

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


def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str], bool]:
    """
    Parse chuỗi tiền cược. Hỗ trợ hậu tố k (nghìn) và m (triệu).
    Hỗ trợ từ khóa 'all' để cược toàn bộ số dư.
    Trả về (amount, None, is_all) nếu hợp lệ, hoặc (None, error_msg, False) nếu không.
    """
    cleaned = raw.lower().replace(",", "").strip()
    if cleaned in ("all", "max", "het", "hết"):
        if balance <= 0:
            return None, "Í quá, ví trống rỗng! Đi cày kiếm điểm rồi quay lại nhé.", False
        return balance, None, True
    try:
        if cleaned.endswith("m"):
            amount = int(float(cleaned[:-1]) * 1_000_000)
        elif cleaned.endswith("k"):
            amount = int(float(cleaned[:-1]) * 1_000)
        else:
            amount = int(float(cleaned))
    except ValueError:
        return None, f"`{raw}` không phải số hợp lệ!", False
    if amount <= 0:
        return None, "Tiền cược phải lớn hơn **0** nha mấy khứa!", False
    if amount > balance:
        return None, (
            f"Ví còn đúng **{balance:,}** mà đòi cược **{amount:,}**? Nghèo mà ham!"
        ), False
    return amount, None, False



# ─────────────────────────────────────────────────────────────────────────────
# THUẬT TOÁN RENDER MA TRẬN VÒNG QUAY 7×8
# ─────────────────────────────────────────────────────────────────────────────

def _render_wheel(stop_idx: int) -> str:
    """
    Render lưới 7×8 từ mảng BASE_WHEEL cố định với chỉ số dừng `stop_idx`.

    Thuật toán Slice Rotation:
    1. display_wheel = BASE_WHEEL[stop_idx:] + BASE_WHEEL[:stop_idx]
       → display_wheel[0] luôn là ô kết quả (nằm ngay dưới mũi tên 🔻).
    2. Điền 16 emoji theo thứ tự TRACK vào lưới 7×7.
    3. Ô trung tâm (3,3) = ⬜, ô trống = ⬛.
    4. Thêm dòng mũi tên "⬛ ⬛ ⬛ 🔻 ⬛ ⬛ ⬛" lên đầu.
    """
    # Bước 1 — Xoay mảng cố định bằng slice, không shuffle
    arranged: list[str] = BASE_WHEEL[stop_idx:] + BASE_WHEEL[:stop_idx]

    # Bước 2 — Xây dựng lưới 7 hàng × 7 cột
    DARK         = "⬛"
    CENTER_EMOJI = "⬜"
    grid: list[list[str]] = [[DARK] * 7 for _ in range(7)]

    for idx, (r, c) in enumerate(TRACK):
        grid[r][c] = arranged[idx]

    # Điền tâm vòng quay
    cr, cc = CENTER
    grid[cr][cc] = CENTER_EMOJI

    # Bước 3 — Render thành chuỗi
    arrow_row = "⬛⬛⬛🔻⬛⬛⬛"
    body_rows  = ["".join(row) for row in grid]
    return arrow_row + "\n" + "\n".join(body_rows)


# ─────────────────────────────────────────────────────────────────────────────
# THUẬT TOÁN MÁY XẺNG (SLOTS)
# ─────────────────────────────────────────────────────────────────────────────

SLOT_SYMBOLS = ["💎", "💯", "🍀", "<:gift_00_symbol:1536003307011842099>", "✨"]

def _generate_slots() -> list[str]:
    """Sinh mảng 5 emoji cho trò chơi Slots dựa trên tỉ lệ Hạng Giải."""
    tier = random.choices(['lose', '3_match', '4_match', '5_match'], weights=[81.5, 14.0, 4.0, 0.5], k=1)[0]
    target = random.choice(SLOT_SYMBOLS)
    
    if tier == '5_match':
        slots = [target] * 5
    elif tier == '4_match':
        other = random.choice([s for s in SLOT_SYMBOLS if s != target])
        slots = [target] * 4 + [other]
    elif tier == '3_match':
        others = random.choices([s for s in SLOT_SYMBOLS if s != target], k=2)
        slots = [target] * 3 + others
    else:
        # lose: đảm bảo không có biểu tượng nào xuất hiện >= 3 lần
        while True:
            slots = random.choices(SLOT_SYMBOLS, k=5)
            counts = {s: slots.count(s) for s in set(slots)}
            if max(counts.values()) < 3:
                break
                
    random.shuffle(slots)
    return slots


def _evaluate_slots(slots_list: list[str]) -> tuple[float, str]:
    """Đánh giá mảng emoji và trả về hệ số (Multiplier) cùng Mô tả."""
    counts = {s: slots_list.count(s) for s in set(slots_list)}
    max_sym = max(counts, key=lambda k: counts[k])
    max_count = counts[max_sym]
    
    if max_count == 5:
        payouts = {"💎": 25.0, "💯": 20.0, "🍀": 18.0, "<:gift_00_symbol:1536003307011842099>": 16.0, "✨": 15.0}
        mult = payouts[max_sym]
        return mult, f"x{mult:.1f} - JACKPOT 5 {max_sym}! Đổi đời rồiiii!"
    elif max_count == 4:
        payouts = {"💎": 5.0, "💯": 4.5, "🍀": 4.0, "<:gift_00_symbol:1536003307011842099>": 3.5, "✨": 3.0}
        mult = payouts[max_sym]
        return mult, f"x{mult:.1f} - Lụm 4 {max_sym}!"
    elif max_count == 3:
        payouts = {"💎": 1.8, "💯": 1.6, "🍀": 1.5, "<:gift_00_symbol:1536003307011842099>": 1.3, "✨": 1.2}
        mult = payouts[max_sym]
        return mult, f"x{mult:.1f} - Vớt vát 3 {max_sym}!"
    else:
        return -1.0, "Thua sạch, nhà cái xin nhẹ!"


# =============================================================================
# COG CHÍNH
# =============================================================================

class WheelSlots(commands.Cog):
    """Cog Vòng Quay May Mắn của Angelic Casino."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH CHÍNH: kwheel
    # ─────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="wheel",
        aliases=["vqmm"],
        description="Quay vòng may mắn — Cú pháp: wheel <tiền_cược>",
    )
    async def wheel_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Vòng Quay May Mắn — 16 ô màu, xác suất có trọng số.

        Tỷ lệ thắng tổng cộng: 12.5%
        Tỷ lệ thua tổng cộng : 87.5%
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        if is_all:
            async def _run(ctx: commands.Context, bet: int):
                await self._exec_wheel(ctx, bet, uid, balance)
            from cogs.events.gambling.basic_games import _send_confirm
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_wheel(ctx, bet, uid, balance)

    @wheel_cmd.error
    async def wheel_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"❌ {ctx.author.mention} Quay tay bằng không khí à? Cú pháp: `{ctx.prefix}wheel <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp wheel`")


    async def _exec_wheel(self, ctx: commands.Context, bet: int, uid: str, balance: int) -> None:
        """Logic thực thi game wheel."""
        stop_idx: int = random.randint(0, len(BASE_WHEEL) - 1)
        winning_emoji: str = BASE_WHEEL[stop_idx]

        mult, is_win, has_ticket, desc = WHEEL_CONFIG[winning_emoji]

        # ── Tính delta điểm ───────────────────────────────────────────────
        delta = round(mult * bet)

        # ── Cập nhật DB ───────────────────────────────────────────────────
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send(f"❌ {ctx.author.mention} Sập nguồn cơ sở dữ liệu, thử lại sau!")
            return

        new_balance = balance + delta

        # ── Render ma trận vòng quay (slice rotation, không shuffle) ─────
        wheel_grid = _render_wheel(stop_idx)

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
        delay = 30.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)
            
        await update_task_progress(self.bot, uid, "gamble_any", 1)


    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH MÁY XẺNG: kslots
    # ─────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="slots",
        aliases=["mayxeng"],
        description="Chơi Máy Xẻng (Slots) — Cú pháp: slots <tiền_cược>",
    )
    async def slots_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Trò chơi Máy Xẻng (Slots).
        - Đảm bảo tỷ lệ chính xác tuyệt đối bằng thuật toán Outcome-First.
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        if is_all:
            async def _run(ctx: commands.Context, bet: int):
                await self._exec_slots(ctx, bet, uid, balance)
            from cogs.events.gambling.basic_games import _send_confirm
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_slots(ctx, bet, uid, balance)

    @slots_cmd.error
    async def slots_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"❌ {ctx.author.mention} Đút xèng vào máy đi chứ! Cú pháp: `{ctx.prefix}slots <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp slots`")


    async def _exec_slots(self, ctx: commands.Context, bet: int, uid: str, balance: int) -> None:
        """Logic thực thi game slots."""
        # ── Sinh kết quả & Đánh giá ────────────────────────────────────
        slots = _generate_slots()
        mult, desc = _evaluate_slots(slots)

        # ── Tính delta tiền ──────────────────────────────────────────────
        delta = round(mult * bet)

        # ── Cập nhật DB ──────────────────────────────────────────────────
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send(f"❌ {ctx.author.mention} Sập nguồn cơ sở dữ liệu, thử lại sau!")
            return

        new_balance = balance + delta

        # ── Xây dựng Giao diện Embed ─────────────────────────────────────
        # Mô tả hiển thị (RPG Style): ◖ 💎 ✨ 💯 💯 💎 ◗
        slots_display = f"◖ {' '.join(slots)} ◗"
        
        if mult >= 15.0:
            embed_color = COLOR_SPECIAL
            result_name = "🌟 Kết quả"
            result_val = f"+{delta:,}  *({desc})*"
        elif mult > 0:
            embed_color = COLOR_WIN
            result_name = "🟢 Kết quả"
            result_val = f"+{delta:,}  *({desc})*"
        else:
            embed_color = COLOR_LOSE
            result_name = "🔴 Kết quả"
            result_val = f"{delta:,}  *({desc})*"

        embed = discord.Embed(
            title="🎰 Máy Xẻng (Slots)",
            description=f"**Kết quả:**\n\n{slots_display}",
            color=embed_color,
        )
        embed.set_author(
            name=f"{ctx.author.display_name} — slots",
            icon_url=ctx.author.display_avatar.url,
        )

        # 3 Field Hàng Dọc
        embed.add_field(name="💰 Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=result_name, value=result_val, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)

        embed.set_footer(text="Angelic Casino • Máy Xẻng 🌸")
        delay = 30.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)
            
        await update_task_progress(self.bot, uid, "slots", 1)
        await update_task_progress(self.bot, uid, "gamble_any", 1)



# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WheelSlots(bot))