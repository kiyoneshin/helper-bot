"""
vietnam_games.py — Cog Trò Chơi Dân Gian Việt Nam
==================================================
Lệnh: y!taixiu / y!tx <tai/xiu> <tien_cuoc>
       y!baucua / y!bc (Theo dõi bằng chat thời gian thực)
"""

import asyncio
import random
import re
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
    Parse chuỗi tiền cược. Hỗ trợ hậu tố k (nghìn) và m (triệu).
    Ví dụ: 50k = 50,000 | 1.5m = 1,500,000 | 100,000
    Trả về (amount, None) nếu hợp lệ, hoặc (None, error_msg) nếu không.
    """
    cleaned = raw.lower().replace(",", "").strip()
    try:
        if cleaned.endswith("m"):
            amount = int(float(cleaned[:-1]) * 1_000_000)
        elif cleaned.endswith("k"):
            amount = int(float(cleaned[:-1]) * 1_000)
        else:
            amount = int(float(cleaned))
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
# HỆ THỐNG KHÓA HÀNH ĐỘNG (COMMAND LOCK)
# ─────────────────────────────────────────────────────────────────────────────

async def _check_busy(bot: commands.Bot, ctx: commands.Context) -> bool:
    """Kiểm tra người chơi có đang vướng game tương tác nào không."""
    active_players: set = getattr(bot, 'active_players', set())
    if ctx.author.id in active_players:
        await ctx.send(
            f"{ctx.author.mention}, bạn đang có trò chơi chưa kết thúc! Hãy hoàn tất hước đó trước.",
            ephemeral=True
        )
        return True
    return False

def _lock_user(bot: commands.Bot, user_id: int) -> None:
    """Khóa người chơi (thêm vào danh sách đang chơi)."""
    active_players: set = getattr(bot, 'active_players', set())
    active_players.add(user_id)
    setattr(bot, 'active_players', active_players)

def _unlock_user(bot: commands.Bot, user_id: int) -> None:
    """Mở khóa người chơi."""
    active_players: set = getattr(bot, 'active_players', set())
    active_players.discard(user_id)
    setattr(bot, 'active_players', active_players)

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
                "Thiếu! Cú pháp: `y!tx <tai/xiu> <tiền_cược>`",
                ephemeral=True,
            )

    # =========================================================================
    # BẦU CUA TÔM CÁ
    # =========================================================================

    # Cấu hình 6 linh vật: key nhập (bao gồm tiếng Việt) → (kóa chuẩn, emoji)
    BC_ANIMALS: dict[str, tuple[str, str]] = {
        "bau":  ("bau",  "🎃"),   # Bầu
        "bầu": ("bau",  "🎃"),
        "cua":  ("cua",  "🦀"),   # Cua
        "tom":  ("tom",  "🦐"),   # Tôm
        "tôm": ("tom",  "🦐"),
        "ca":   ("ca",   "🐟"),   # Cá
        "cá":  ("ca",   "🐟"),
        "nai":  ("nai",  "🦌"),   # Nai
        "ga":   ("ga",   "🐓"),   # Gà
        "gà":  ("ga",   "🐓"),
    }
    BC_KEYS   = ["bau", "cua", "tom", "ca", "nai", "ga"]
    BC_EMOJIS = {
        "bau": "🎃", "cua": "🦀", "tom": "🦐",
        "ca":  "🐟", "nai": "🦌", "ga":  "🐓",
    }

    def _build_lobby_embed(
        self,
        bets: dict[str, int],
        time_left: int,
    ) -> discord.Embed:
        """Dựng Embed Lobby với bảng cược hiện tại và đồng hồ đếm ngược."""
        embed = discord.Embed(
            title="🎲 Bàn Bầu Cua Tôm Cá",
            description=(
                "Gõ xuống kênh chat để cược: `<tên_con_vật> <số_tiền>`\n"
                "Bạn có thể cược nhiều con trên 1 dòng (cách nhau dấu phẩy) hoặc gõ từng dòng riêng! *(Hỗ trợ k, m)*\n"
                "Ví dụ: `bầu 100k, cua 1.5m` hoặc nhắn `cá 500k` vào từng dòng riêng."
            ),
            color=0xFFD700,
        )
        # Bảng cược hiện tại
        bet_lines = " \u2003 ".join(
            f"{self.BC_EMOJIS[k]} **{bets[k]:,}**" if bets[k] else f"{self.BC_EMOJIS[k]} `---`"
            for k in self.BC_KEYS
        )
        embed.add_field(name="📊 Bảng Cược", value=bet_lines, inline=False)
        embed.add_field(
            name="⏳ Đóng sảnh sau",
            value=f"**{time_left} giây** — `[ 🎲 ] [ 🎲 ] [ 🎲 ]`",
            inline=False,
        )
        embed.set_footer(text="Angelic Casino • Bầu Cua Tôm Cá 🌸")
        return embed

    @commands.command(name="baucua", aliases=["bc"])
    async def baucua_cmd(self, ctx: commands.Context) -> None:
        """
        Trò chơi Bầu Cua Tôm Cá.
        Giai đoạn 1: Sảnh cược 30 giây nhận lệnh từ chat.
        Giai đoạn 2: Kết quả 3 xúc xắc và trả thưởng.
        """
        if await _check_busy(self.bot, ctx):
            return

        uid = str(ctx.author.id)
        _lock_user(self.bot, ctx.author.id)

        # Đặt cược: {kóa: tổng_tiền}
        bets: dict[str, int] = {k: 0 for k in self.BC_KEYS}
        LOBBY_DURATION = 30
        start_time = asyncio.get_event_loop().time()

        # Gửi lobby lần đầu
        lobby_msg = await ctx.send(embed=self._build_lobby_embed(bets, LOBBY_DURATION))
        # Mốc cập nhật: tại giây còn lại 20, 10, 5 (tuyệt đối tới sắt thời gian)
        update_at: set[int] = {20, 10, 5}
        last_update_secs = LOBBY_DURATION

        try:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                time_left = max(0, int(LOBBY_DURATION - elapsed))

                if time_left <= 0:
                    break

                # Đợi tin nhắn mới từ chính người chơi trong kênh đó
                remaining = max(1.0, LOBBY_DURATION - (asyncio.get_event_loop().time() - start_time))
                try:
                    msg: discord.Message = await self.bot.wait_for(
                        "message",
                        timeout=remaining,
                        check=lambda m: (
                            m.author.id == ctx.author.id
                            and m.channel.id == ctx.channel.id
                        ),
                    )
                except asyncio.TimeoutError:
                    break

                # — Parse cược từ nội dung tin nhắn —
                # Tách theo dấu phẩy hoặc xuống dòng
                segments = re.split(r"[,\n]", msg.content)
                placed_any = False

                for seg in segments:
                    seg = seg.strip()
                    if not seg:
                        continue
                    # Tìm cặp (con_vật, số_tiền)
                    match = re.search(
                        r"(bau|b\u1ea7u|cua|tom|t\u00f4m|ca|c\u00e1|nai|ga|g\u00e0)\s+([0-9km.]+)",
                        seg.lower(),
                    )
                    if not match:
                        continue

                    animal_raw, amount_raw = match.group(1), match.group(2)
                    key, _ = self.BC_ANIMALS[animal_raw]

                    # Lấy số dư mới nhất trước khi trừ
                    cur_bal = await _get_balance(self.bot, uid)
                    amount, err = _parse_bet(amount_raw, cur_bal)
                    if err or amount is None:
                        try:
                            await msg.add_reaction("❌")
                        except discord.HTTPException:
                            pass
                        continue

                    ok = await _apply_delta(self.bot, uid, -amount)
                    if not ok:
                        try:
                            await msg.add_reaction("❌")
                        except discord.HTTPException:
                            pass
                        continue

                    bets[key] += amount
                    placed_any = True
                    try:
                        await msg.add_reaction("✅")
                    except discord.HTTPException:
                        pass

                # Cập nhật UI định kỳ (chống rate limit)
                now_left = max(0, int(LOBBY_DURATION - (asyncio.get_event_loop().time() - start_time)))
                should_update = placed_any or (now_left in update_at and now_left != last_update_secs)
                if should_update:
                    last_update_secs = now_left
                    update_at.discard(now_left)
                    try:
                        await lobby_msg.edit(embed=self._build_lobby_embed(bets, now_left))
                    except discord.HTTPException:
                        pass

        finally:
            _unlock_user(self.bot, ctx.author.id)

        # ── Giai đoạn 2: Kết quả ───────────────────────────────────────
        if not any(bets.values()):
            await lobby_msg.edit(
                embed=discord.Embed(
                    title="🎲 Bầu Cua Tôm Cá",
                    description="Không có ai đặt cược. Trò chơi kết thúc!",
                    color=0x808080,
                )
            )
            return

        # Tung 3 xúc xắc
        dice: list[str] = [random.choice(self.BC_KEYS) for _ in range(3)]
        roll_counts: dict[str, int] = {k: dice.count(k) for k in self.BC_KEYS}

        # Tính tổng thắng (lãi net, không tính gốc đã trừ trước)
        total_payout = 0
        for key, bet_amount in bets.items():
            if bet_amount == 0:
                continue
            count = roll_counts.get(key, 0)
            if count > 0:
                # Trả lại gốc + x (count) lần lãi
                total_payout += bet_amount + bet_amount * count
            # Nếu count == 0: tiền gốc đã bị trừ từ trước, không hoàn

        if total_payout > 0:
            await _apply_delta(self.bot, uid, total_payout)

        total_wagered  = sum(bets.values())
        net_gain       = total_payout - total_wagered   # lười (+) hoặc lỗ (-)
        final_balance  = await _get_balance(self.bot, uid)

        # Xây dựng Embed kết quả
        dice_display = "  ".join(f"**[ {self.BC_EMOJIS[d]} ]**" for d in dice)

        # Tóm tắt cược
        bet_summary_lines: list[str] = []
        for key in self.BC_KEYS:
            if bets[key] > 0:
                count = roll_counts.get(key, 0)
                emoji = self.BC_EMOJIS[key]
                line = f"{emoji} Cược: **{bets[key]:,}**"
                if count > 0:
                    payout = bets[key] + bets[key] * count
                    line += f" → ✅ Trúng {count}x ⇒ +**{payout:,}**"
                else:
                    line += " → ❌"
                bet_summary_lines.append(line)

        result_desc = (
            f"{dice_display}\n\n"
            + "\n".join(bet_summary_lines)
        )

        is_profit = net_gain > 0
        embed_color = 0x00FF00 if is_profit else (0x808080 if net_gain == 0 else 0xFF0000)
        result_field_name = "🟢 Kết quả" if is_profit else ("🔴 Kết quả" if net_gain < 0 else "⚪ Kết quả")
        if net_gain >= 0:
            result_field_val = f"+{net_gain:,}  *(Thắng :-)*"
        else:
            result_field_val = f"{net_gain:,}  *(Thua)*"

        result_embed = discord.Embed(
            title="🎲 Bầu Cua Tôm Cá — Kết Quả",
            description=result_desc,
            color=embed_color,
        )
        result_embed.set_author(
            name=f"{ctx.author.display_name} — baucua",
            icon_url=ctx.author.display_avatar.url,
        )
        result_embed.add_field(name=result_field_name, value=result_field_val, inline=False)
        result_embed.add_field(name="💳 Số dư mới", value=f"{final_balance:,}", inline=False)
        result_embed.set_footer(text="Angelic Casino • Bầu Cua Tôm Cá 🌸")

        await ctx.send(embed=result_embed)

# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VietnamGames(bot))
