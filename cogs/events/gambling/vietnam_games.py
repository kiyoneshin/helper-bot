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
        return None, "Tiền cược phải lớn hơn **0** nha mấy khứa!"
    if amount > balance:
        return None, (
            f"Ví còn đúng **{balance:,}** mà đòi cược **{amount:,}**? Nghèo mà ham!"
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
            f"❌ {ctx.author.mention} Đang ngồi sòng khác rồi cha nội! Chốt kèo bên kia xong đi rồi qua đây đú tiếp."
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
                f"❌ {ctx.author.mention} Bấm bậy bạ gì vậy? Dùng `tai` hoặc `xiu`.\n"
                "Cú pháp: `y!tx <tai/xiu> <tiền_cược>`"
            )
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
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
            await ctx.send(f"❌ {ctx.author.mention} Sập nguồn cơ sở dữ liệu, thử lại sau!")
            return

        new_balance = balance + delta

        # ── Xây dựng Giao diện Embed ────────────────────────────────────
        choice_str = "TÀI" if choice == "tai" else "XỈU"
        
        if is_bao:
            embed_title = "🌪️ Tài Xỉu — Bão Lũ Quét Sạch!"
            embed_color = COLOR_LOSE
            dice_desc = f"Kết quả: **[ {d1} ]  [ {d2} ]  [ {d3} ]**  **BÃO ({total})**"
            result_name = "🔴 Kết quả"
            result_val = f"{delta:,}  *(Đi bụi do dính Bão!)*"
        else:
            embed_title = "🎲 Tài Xỉu (Sic Bo)"
            embed_color = COLOR_WIN if is_win else COLOR_LOSE
            dice_desc = f"Kết quả: **[ {d1} ]  [ {d2} ]  [ {d3} ]**  Tổng: **{total} ({outcome_desc})**"
            
            if is_win:
                result_name = "🟢 Kết quả"
                result_val = f"+{delta:,}  *(Húp +95%)*"
            else:
                result_name = "🔴 Kết quả"
                result_val = f"{delta:,}  *(Mút trọn)*"

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
            await ctx.send(f"❌ {ctx.author.mention} Chơi mà không ném tiền à? Cú pháp: `y!tx <tai/xiu> <tiền_cược>`")

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
        total_pool: dict[str, int],
        player_count: int,
        time_left: int,
    ) -> discord.Embed:
        """Dựng Embed Lobby với tổng tiền cược toàn bàn và đồng hồ đếm ngược."""
        embed = discord.Embed(
            title="🎲 Bàn Bầu Cua Tôm Cá",
            description=(
                "Nhanh tay gõ xuống kênh chat để cược: `<tên_con_vật> <số_tiền>`\n"
                "Tay nhanh hơn não thì cược nhiều con 1 dòng luôn (cách nhau dấu phẩy).\n"
                "Gồm 6 con: **Bầu, Cua, Tôm, Cá, Nai, Gà**\n"
                "Ví dụ: `bầu 100k, cua 1.5m` hoặc chốt từng dòng riêng `cá 500k`."
            ),
            color=0xFFD700,
        )
        # Bảng tổng cược toàn bàn
        pool_lines = " \u2003 ".join(
            f"{self.BC_EMOJIS[k]} **{total_pool[k]:,}**" if total_pool[k] else f"{self.BC_EMOJIS[k]} `---`"
            for k in self.BC_KEYS
        )
        embed.add_field(name="📊 Tổng Tiền Bàn", value=pool_lines, inline=False)
        embed.add_field(
            name="👥 Người tham gia",
            value=f"**{player_count}** người đã cược",
            inline=True,
        )
        embed.add_field(
            name="⏳ Đóng sảnh sau",
            value=f"**{time_left} giây**  `[ 🎲 ] [ 🎲 ] [ 🎲 ]`",
            inline=True,
        )
        embed.set_footer(text="Angelic Casino • Bầu Cua Tôm Cá 🌸")
        return embed

    @commands.command(name="baucua", aliases=["bc"])
    async def baucua_cmd(self, ctx: commands.Context) -> None:
        """
        Trò chơi Bầu Cua Tôm Cá (MULTIPLAYER).
        Giai đoạn 1: Sảnh cược 30 giây — TOÀN BỘ người dùng trong kênh có thể tham gia.
        Giai đoạn 2: Tung xúc xắc, trả thưởng cá nhân từng người.
        """
        if await _check_busy(self.bot, ctx):
            return

        _lock_user(self.bot, ctx.author.id)

        # ── Khởi tạo dữ liệu đa người chơi ──────────────────────────────────
        # player_bets: { user_id → { animal_key → tổng đã cược } }
        player_bets: dict[int, dict[str, int]] = {}
        # total_pool: tổng tiền cược của toàn bàn theo từng linh vật
        total_pool: dict[str, int] = {k: 0 for k in self.BC_KEYS}

        LOBBY_DURATION = 30

        # Gửi lobby lần đầu
        lobby_msg = await ctx.send(
            embed=self._build_lobby_embed(total_pool, 0, LOBBY_DURATION)
        )

        async def baucua_listener(msg: discord.Message):
            # Bỏ qua tin nhắn từ bot hoặc ngoài kênh
            if msg.author.bot or msg.channel.id != ctx.channel.id:
                return

            # Dùng findall để bắt mọi cược trong một tin nhắn (ví dụ: bầu 10k cua 20k)
            # \s* giúp bắt được cả trường hợp dính liền như "bầu10k"
            matches = re.findall(
                r"(bau|b\u1ea7u|cua|tom|t\u00f4m|ca|c\u00e1|nai|ga|g\u00e0)\s*([0-9km.]+)",
                msg.content.lower(),
            )
            if not matches:
                return

            sender_id = msg.author.id
            sender_uid = str(sender_id)
            placed_any = False

            for animal_raw, amount_raw in matches:
                key_tuple = self.BC_ANIMALS.get(animal_raw)
                if not key_tuple:
                    continue
                key = key_tuple[0]

                # Lấy số dư realtime
                cur_bal = await _get_balance(self.bot, sender_uid)
                amount, err = _parse_bet(amount_raw, cur_bal)

                if err or amount is None:
                    try:
                        await msg.reply(
                            f"❌ {msg.author.mention} {err}",
                            delete_after=5,
                        )
                    except discord.HTTPException:
                        pass
                    continue

                ok = await _apply_delta(self.bot, sender_uid, -amount)
                if not ok:
                    try:
                        await msg.reply(
                            f"❌ {msg.author.mention} Đỗ nghèo khỉ mà đòi cược thêm **{amount:,}** à?",
                            delete_after=5,
                        )
                    except discord.HTTPException:
                        pass
                    continue

                # Ghi nhận cược (cập nhật dict an toàn trong asyncio)
                if sender_id not in player_bets:
                    player_bets[sender_id] = {k: 0 for k in self.BC_KEYS}
                player_bets[sender_id][key] += amount
                total_pool[key] += amount
                placed_any = True

            if placed_any:
                try:
                    await msg.add_reaction("✅")
                except discord.HTTPException:
                    pass

        # Đăng ký listener lắng nghe song song
        self.bot.add_listener(baucua_listener, "on_message")

        try:
            # Vòng lặp cập nhật UI 5 giây 1 lần
            for i in range(6):
                await asyncio.sleep(5)
                now_left = LOBBY_DURATION - (i + 1) * 5
                try:
                    await lobby_msg.edit(
                        embed=self._build_lobby_embed(
                            total_pool, len(player_bets), now_left
                        )
                    )
                except discord.HTTPException:
                    pass
                
            # Đợi một chút để các tin nhắn cuối cùng xử lý xong
            await asyncio.sleep(0.5)
            
        finally:
            self.bot.remove_listener(baucua_listener, "on_message")
            _unlock_user(self.bot, ctx.author.id)

        # ── Giai đoạn 2: Chốt sảnh & Kết quả ────────────────────────────────
        if not player_bets:
            try:
                await lobby_msg.edit(
                    embed=discord.Embed(
                        title="🎲 Bầu Cua Tôm Cá",
                        description="Không có ai đặt cược. Trò chơi kết thúc!",
                        color=0x808080,
                    )
                )
            except discord.HTTPException:
                pass
            return

        # Tung 3 xúc xắc
        dice: list[str] = [random.choice(self.BC_KEYS) for _ in range(3)]
        roll_counts: dict[str, int] = {k: dice.count(k) for k in self.BC_KEYS}
        dice_display = "  ".join(f"**[ {self.BC_EMOJIS[d]} ]**" for d in dice)

        # Chốt Embed Lobby — hiển thị kết quả xúc xắc
        try:
            closed_embed = discord.Embed(
                title="🎲 Bầu Cua Tôm Cá — Đã Chốt!",
                description=f"Kết quả xúc xắc:\n\n{dice_display}",
                color=0xFF8C00,
            )
            pool_lines = " \u2003 ".join(
                f"{self.BC_EMOJIS[k]} **{total_pool[k]:,}**" if total_pool[k] else f"{self.BC_EMOJIS[k]} `---`"
                for k in self.BC_KEYS
            )
            closed_embed.add_field(name="📊 Tổng Tiền Bàn", value=pool_lines, inline=False)
            closed_embed.set_footer(text="Angelic Casino • Bầu Cua Tôm Cá 🌸")
            await lobby_msg.edit(embed=closed_embed)
        except discord.HTTPException:
            pass

        # Gửi thông báo kết quả chung
        await ctx.send(
            f"🎲 **Sòng đã mở:** {dice_display}\n"
            f"*(Đang chia tiền cho {len(player_bets)} con bạc...)*"
        )

        # ── Vòng lặp trả thưởng cá nhân từng người ───────────────────────────
        for player_id, bets in player_bets.items():
            # Tính tổng payout (gốc + lãi) cho người này
            total_payout = 0
            for key, bet_amount in bets.items():
                if bet_amount == 0:
                    continue
                count = roll_counts.get(key, 0)
                if count > 0:
                    total_payout += bet_amount + bet_amount * count

            if total_payout > 0:
                await _apply_delta(self.bot, str(player_id), total_payout)

            total_wagered = sum(bets.values())
            net_gain = total_payout - total_wagered
            final_balance = await _get_balance(self.bot, str(player_id))

            # Tóm tắt từng con vật người này đã cược
            bet_lines: list[str] = []
            for key in self.BC_KEYS:
                if bets[key] <= 0:
                    continue
                emoji = self.BC_EMOJIS[key]
                count = roll_counts.get(key, 0)
                line = f"{emoji} Cược: **{bets[key]:,}**"
                if count > 0:
                    payout = bets[key] + bets[key] * count
                    line += f" → ✅ Trúng {count}x → +**{payout:,}**"
                else:
                    line += " → ❌"
                bet_lines.append(line)

            result_desc = f"{dice_display}\n\n" + "\n".join(bet_lines)

            is_profit = net_gain > 0
            embed_color = 0x00FF00 if is_profit else (0x808080 if net_gain == 0 else 0xFF0000)
            result_field_name = "🟢 Kết quả" if is_profit else ("🔴 Kết quả" if net_gain < 0 else "⚪ Kết quả")
            result_field_val = (
                f"+{net_gain:,}  *(Húp)*" if net_gain > 0
                else (f"{net_gain:,}  *(Mút trọn)*" if net_gain < 0 else "Hoà vốn")
            )

            # Lấy User object để set_author
            user: discord.User | None = self.bot.get_user(player_id)
            author_name = user.display_name if user else f"User#{player_id}"
            author_avatar = user.display_avatar.url if user else discord.Embed.Empty  # type: ignore[attr-defined]

            result_embed = discord.Embed(
                title="🎲 Bầu Cua Tôm Cá — Kết Quả",
                description=result_desc,
                color=embed_color,
            )
            result_embed.set_author(name=f"{author_name} — baucua", icon_url=author_avatar)
            result_embed.add_field(name=result_field_name, value=result_field_val, inline=False)
            result_embed.add_field(name="💳 Số dư mới", value=f"{final_balance:,}", inline=False)
            result_embed.set_footer(text="Angelic Casino • Bầu Cua Tôm Cá 🌸")

            try:
                await ctx.send(embed=result_embed)
            except discord.HTTPException:
                pass

# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VietnamGames(bot))
