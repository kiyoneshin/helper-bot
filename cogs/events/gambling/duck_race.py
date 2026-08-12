"""
duck_race.py — Cog Đua Vịt Sự Kiện (Scheduled Duck Race)
=========================================================
Chu kỳ: Mỗi 4 tiếng một lần (0h, 4h, 8h, 12h, 16h, 20h — giờ Việt Nam UTC+7)
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from cogs.common.db import (
    add_event_points,
    deduct_event_points,
    execute_db,
    fetchrow_db,
    get_or_create_event_profile,
    query_db,
)

log = logging.getLogger("DuckRace")

UTC7 = timezone(timedelta(hours=7))

RACE_CHANNEL_ID = 1529937900031054028

RACE_HOURS_UTC7 = {0, 4, 8, 12, 16, 20}
LOCK_MINUTE     = 55
START_MINUTE    = 0

TRACK_LENGTH    = 20
ANIM_STEPS      = 20
ANIM_INTERVAL   = 1.5

COLOR_INFO   = 0xFFD700
COLOR_WIN    = 0x00FF00
COLOR_LOSE   = 0xFF4444
COLOR_RACE   = 0x7289DA
COLOR_LOCK   = 0xFF6B6B

DUCKS: dict[str, str] = {
    "do":   "🔴 Đỏ",
    "xanh": "🔵 Xanh",
    "vang": "🟡 Vàng",
    "hong": "💖 Hồng",
    "yon":  "🦆 Yon",
}
DUCK_EMOJI: dict[str, str] = {
    "do":   "🔴",
    "xanh": "🔵",
    "vang": "🟡",
    "hong": "💖",
    "yon":  "🦆",
}

DUCK_ALIASES: dict[str, str] = {
    "do": "do", "đỏ": "do", "red": "do",
    "xanh": "xanh", "blue": "xanh",
    "vang": "vang", "vàng": "vang", "yellow": "vang",
    "hong": "hong", "hồng": "hong", "pink": "hong",
    "yon": "yon",
}


async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    row = await get_or_create_event_profile(bot, user_id)
    return int(row["points"] or 0) if row else 0


async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    if delta > 0:
        return await add_event_points(bot, user_id, delta, is_earned=False)
    elif delta < 0:
        return await deduct_event_points(bot, user_id, abs(delta))
    return True


def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str]]:
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
        return None, f"Ví còn đúng **{balance:,}** mà đòi cược **{amount:,}**? Nghèo mà ham!"
    return amount, None


async def _init_duck_table(bot: commands.Bot) -> None:
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS duck_bets (
            discord_id TEXT PRIMARY KEY,
            duck_color TEXT NOT NULL,
            bet_amount BIGINT NOT NULL
        );
        """,
    )
    log.info("Bảng duck_bets đã sẵn sàng.")


async def _get_pool_stats(bot: commands.Bot) -> dict[str, int]:
    rows = await query_db(
        bot,
        "SELECT duck_color, COALESCE(SUM(bet_amount), 0) AS total FROM duck_bets GROUP BY duck_color",
    )
    stats: dict[str, int] = {k: 0 for k in DUCKS}
    for row in rows:
        color = row["duck_color"]
        if color in stats:
            stats[color] = int(row["total"])
    return stats


def _build_pool_embed(stats: dict[str, int], title: str, color: int, footer: str) -> discord.Embed:
    total_pool = sum(stats.values())
    embed = discord.Embed(title=title, color=color)
    lines: list[str] = []
    for key, label in DUCKS.items():
        duck_pool = stats[key]
        if duck_pool > 0 and total_pool > 0:
            odds = (total_pool * 0.95) / duck_pool
            odds_str = f"1 ăn **{odds:.2f}x**"
        else:
            odds_str = "1 ăn **∞** *(chưa ai cược)*"
        lines.append(f"{DUCK_EMOJI[key]} **{label}**: {duck_pool:,} — {odds_str}")
    embed.add_field(
        name=f"💰 Tổng Pool: {total_pool:,}",
        value="\n".join(lines),
        inline=False,
    )
    embed.set_footer(text=footer)
    return embed


def _build_race_track(positions: dict[str, int], finished: Optional[list[str]] = None) -> str:
    lines = ["```", "🏁 VẠCH ĐÍCH", "=" * (TRACK_LENGTH + 10)]
    for key, label in DUCKS.items():
        pos = positions[key]
        emoji = DUCK_EMOJI[key]
        name_part = f"{emoji} {label:<6}"
        if pos >= TRACK_LENGTH:
            bar = "=" * TRACK_LENGTH + " 🏁"
            crown = " 🏆" if (finished and key in finished) else " <:symbol_right:1536629912515903578>"
            row = f"{name_part}: {bar}{crown}"
        else:
            bar = "=" * pos + "🦆" + "-" * (TRACK_LENGTH - pos)
            row = f"{name_part}: {bar}"
        lines.append(row)
    lines.append("```")
    return "\n".join(lines)


class DuckRace(commands.Cog):
    """Cog Đua Vịt Sự Kiện — Chạy tự động mỗi 4 tiếng."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.is_locked: bool = False
        self.is_racing: bool = False
        self._lock_fired: set[int] = set()
        self._race_fired: set[int] = set()
        self._scheduler.start()

    async def cog_unload(self) -> None:
        self._scheduler.cancel()

    @tasks.loop(minutes=1)
    async def _scheduler(self) -> None:
        now = datetime.now(UTC7)
        hour = now.hour
        minute = now.minute

        if minute == LOCK_MINUTE:
            target_race_hour = (hour + 1) % 24
            
            if target_race_hour in RACE_HOURS_UTC7 and target_race_hour not in self._lock_fired:
                self._lock_fired.add(target_race_hour)
                await self._do_lock(target_race_hour)

        elif minute == START_MINUTE:
            if hour in RACE_HOURS_UTC7 and hour not in self._race_fired:
                self._race_fired.add(hour)
                
                # Dọn dẹp trạng thái khóa của ca đua trước (4 tiếng trước) để chuẩn bị cho chu kỳ sau
                prev_race_hour = (hour - 4) % 24
                self._lock_fired.discard(prev_race_hour)
                self._race_fired.discard(prev_race_hour)
                
                await self._do_race()

    @_scheduler.before_loop
    async def _before_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await _init_duck_table(self.bot)
        log.info("🦆 DuckRace scheduler đã khởi động!")

    async def _do_lock(self, hour_utc7: int) -> None:
        self.is_locked = True
        channel = self.bot.get_channel(RACE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Không tìm thấy kênh đua vịt!")
            return

        stats = await _get_pool_stats(self.bot)
        total_pool = sum(stats.values())

        if total_pool == 0:
            await channel.send(
                "🛑 **ĐÃ ĐÓNG SỔ ĐẶT CƯỢC!** Giải đua vịt sẽ bắt đầu sau 5 phút...\n"
                "*(Không ai thèm cược — đua cho vui thôi à!)*"
            )
        else:
            embed = _build_pool_embed(
                stats,
                title="🛑 ĐÃ ĐÓNG SỔ ĐẶT CƯỢC!",
                color=COLOR_LOCK,
                footer="Giải đua vịt sẽ bắt đầu sau 5 phút... Không thể đặt hoặc hủy cược nữa!",
            )
            embed.description = (
                "Bàn tay đã rút lại, ví đã đóng khóa!\n"
                "5 phút nữa các tay đua lông vũ sẽ xuất phát. Hồi hộp chưa? 🦆"
            )
            await channel.send(
                "🛑 **ĐÃ ĐÓNG SỔ ĐẶT CƯỢC!** Giải đua vịt sẽ bắt đầu sau 5 phút...",
                embed=embed,
            )

    async def _do_race(self) -> None:
        self.is_racing = True
        channel = self.bot.get_channel(RACE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Không tìm thấy kênh đua vịt!")
            self.is_locked = False
            self.is_racing = False
            return

        stats = await _get_pool_stats(self.bot)
        total_pool = sum(stats.values())
        all_bets = await query_db(self.bot, "SELECT discord_id, duck_color, bet_amount FROM duck_bets")

        await channel.send(
            "🏁 **KHỞI TRANH ĐƯỜNG ĐUA!** Các tay đua lông vũ đã sẵn sàng!\n"
            "Ai cược ai bây giờ chỉ biết nín thở mà chờ... 🦆💨"
        )
        await asyncio.sleep(2)

        positions: dict[str, int] = {k: 0 for k in DUCKS}
        speeds: dict[str, float] = {k: random.uniform(0.55, 1.0) for k in DUCKS}
        winners: list[str] = []

        try:
            race_msg = await channel.send(_build_race_track(positions))
        except discord.HTTPException:
            self.is_locked = False
            self.is_racing = False
            return

        step = 0
        while not winners:
            await asyncio.sleep(ANIM_INTERVAL)
            step += 1

            for key in DUCKS:
                if positions[key] < TRACK_LENGTH:
                    if random.random() < speeds[key]:
                        positions[key] = min(positions[key] + 1, TRACK_LENGTH)

            finishers = [k for k, p in positions.items() if p >= TRACK_LENGTH]
            if finishers:
                winners = finishers

            # Safeguard: tối đa 60 bước
            if step >= 60 and not winners:
                max_pos = max(positions.values())
                winners = [k for k, p in positions.items() if p == max_pos]
                for w in winners:
                    positions[w] = TRACK_LENGTH

            try:
                await race_msg.edit(content=_build_race_track(positions, winners if winners else None))
            except discord.HTTPException:
                pass

        await asyncio.sleep(2)
        await self._payout(channel, winners, stats, total_pool, all_bets)

        await execute_db(self.bot, "DELETE FROM duck_bets")
        self.is_locked = False
        self.is_racing = False
        log.info(f"🦆 Đua vịt kết thúc. Winners: {winners}")

    async def _payout(
        self,
        channel: discord.TextChannel,
        winners: list[str],
        stats: dict[str, int],
        total_pool: int,
        all_bets: list,
    ) -> None:
        total_winner_pool = sum(stats.get(w, 0) for w in winners)
        winners_labels = " & ".join([DUCKS[w] for w in winners])
        winners_emojis = "".join([DUCK_EMOJI[w] for w in winners])

        embed = discord.Embed(
            title=f"{winners_emojis} {winners_labels} VỀ ĐÍCH NHẤT! 🏆",
            description=(
                f"Vịt **{winners_labels}** vừa cán đích trong vinh quang!\n"
                f"Tổng Pool: **{total_pool:,}** — Thuế nhà cái (5%): **{int(total_pool * 0.05):,}**\n"
                f"Quỹ thưởng khả dụng (DP): **{int(total_pool * 0.95):,}**"
            ),
            color=COLOR_WIN,
        )

        if total_winner_pool == 0:
            embed.add_field(
                name="😭 Không ai cược phe này",
                value="Quỹ thưởng không chia được — tiền bay về trời!",
                inline=False,
            )
            await channel.send(embed=embed)
            return

        dp = int(total_pool * 0.95)
        odds = dp / total_winner_pool

        embed.add_field(
            name="<:symbol_chart:1536317815336869918> Hệ Số Thực Tế",
            value=f"1 ăn **{odds:.3f}x** *(Tổng DP {dp:,} / Pool vịt thắng {total_winner_pool:,})*",
            inline=False,
        )
        await channel.send(embed=embed)
        await asyncio.sleep(1)

        winners_notified: list[str] = []
        for row in all_bets:
            if row["duck_color"] not in winners:
                continue
            uid = str(row["discord_id"])
            bet_amount = int(row["bet_amount"])
            payout = int(bet_amount * odds)
            await _apply_delta(self.bot, uid, payout)
            profit = payout - bet_amount
            winners_notified.append(
                f"<@{uid}> cược **{bet_amount:,}** → nhận **{payout:,}** *(+{profit:,})*"
            )

        if winners_notified:
            chunk_size = 10
            for i in range(0, len(winners_notified), chunk_size):
                chunk = winners_notified[i : i + chunk_size]
                payout_embed = discord.Embed(
                    title=f"💰 Bảng Vàng Thắng Cược — {winners_labels}",
                    description="\n".join(chunk),
                    color=COLOR_WIN,
                )
                await channel.send(embed=payout_embed)
                await asyncio.sleep(1)
        else:
            await channel.send(
                "*(Không có người thắng vì không ai cược con vịt chiến thắng.)*"
            )

    # ── LỆNH NGƯỜI CHƠI ───────────────────────────────────────────────────

    @commands.command(name="betvit", aliases=["bv", "bevit"])
    async def betvit_cmd(self, ctx: commands.Context, color_raw: str, bet_raw: str) -> None:
        """Đặt cược vào một chú vịt. Cú pháp: kbetvit <màu> <tiền>"""
        if self.is_locked:
            await ctx.send(
                f"🔒 {ctx.author.mention} Sổ đã đóng rồi cha nội! "
                "Đợi xong kỳ đua này rồi cược vào kỳ sau nhé."
            )
            return

        color_key = DUCK_ALIASES.get(color_raw.lower().strip())
        if color_key is None:
            valid = ", ".join(f"`{k}`" for k in DUCKS)
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Vịt gì vậy? Không nhận ra **{color_raw}**!\n"
                f"Các con vịt hợp lệ: {valid}"
            )
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} {err}")
            return

        existing = await fetchrow_db(
            self.bot,
            "SELECT duck_color, bet_amount FROM duck_bets WHERE discord_id = $1",
            uid,
        )
        if existing is not None:
            ex_color = str(existing["duck_color"])
            ex_label = DUCKS.get(ex_color, ex_color)
            ex_emoji = DUCK_EMOJI.get(ex_color, "<:gambling_duck:1536019587844546671>")
            ex_bet = int(existing['bet_amount'])
            
            if ex_color != color_key:
                await ctx.send(
                    f"⚠️ {ctx.author.mention} Mày đã cược vào {ex_emoji} **{ex_label}** "
                    f"({ex_bet:,}) rồi!\n"
                    "Muốn đổi con khác thì `khuybet` để rút về trước đã."
                )
                return
            else:
                ok = await _apply_delta(self.bot, uid, -bet)
                if not ok:
                    await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lỗi DB khi trừ tiền — thử lại sau!")
                    return

                new_bet = ex_bet + bet
                status = await execute_db(
                    self.bot,
                    "UPDATE duck_bets SET bet_amount = $1 WHERE discord_id = $2",
                    new_bet, uid
                )
                if status is None:
                    await _apply_delta(self.bot, uid, bet)
                    await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lỗi DB khi ghi cược — tiền đã hoàn lại!")
                    return
                    
                embed = discord.Embed(
                    title=f"💉 Đã Bơm Thêm Máu!",
                    description=(
                        f"{ctx.author.mention} vừa dồn thêm **{bet:,}** vào {ex_emoji} **{ex_label}**.\n"
                        f"Tổng cược hiện tại vào con này là: **{new_bet:,}** điểm."
                    ),
                    color=COLOR_INFO,
                )
                await ctx.send(embed=embed)
                return

        # (Trường hợp cược mới tinh)
        ok = await _apply_delta(self.bot, uid, -bet)
        if not ok:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lỗi DB khi trừ tiền — thử lại sau!")
            return

        status = await execute_db(
            self.bot,
            "INSERT INTO duck_bets (discord_id, duck_color, bet_amount) VALUES ($1, $2, $3)",
            uid,
            color_key,
            bet,
        )
        if status is None:
            await _apply_delta(self.bot, uid, bet)
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lỗi DB khi ghi cược — tiền đã hoàn lại!")
            return

        duck_label = DUCKS[color_key]
        duck_emoji = DUCK_EMOJI[color_key]
        embed = discord.Embed(
            title=f"{duck_emoji} Đặt Cược Thành Công!",
            description=(
                f"{ctx.author.mention} đã chốt kèo vào **{duck_label}**!\n"
                f"Tiền đặt: **{bet:,}** (đã trừ khỏi ví ngay)\n"
                f"Số dư còn lại: **{balance - bet:,}**\n\n"
                "Muốn rút về? Gõ `khuybet` trước khi sổ đóng."
            ),
            color=COLOR_INFO,
        )
        embed.set_footer(text="Angelic Casino • Đua Vịt Sự Kiện 🦆")
        await ctx.send(embed=embed)

    @betvit_cmd.error
    async def betvit_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Thiếu thông tin kèo!\n"
                "Cú pháp: `kbetvit <màu_vịt> <tiền_cược>`\n"
                "Các vịt: `do`, `xanh`, `vang`, `hong`, `yon`\n"
                "Ví dụ: `kbetvit yon 500k`"
            )

    @commands.command(name="huybet", aliases=["hb", "cancelbet"])
    async def huybet_cmd(self, ctx: commands.Context) -> None:
        """Hủy cược hiện tại và nhận lại 100% tiền. Cú pháp: khuybet"""
        if self.is_locked:
            await ctx.send(
                f"🔒 {ctx.author.mention} Hết đường rút rồi — sổ đã đóng!\n"
                "Đợi xong kỳ đua xem vận may thế nào đi."
            )
            return

        uid = str(ctx.author.id)
        existing = await fetchrow_db(
            self.bot,
            "SELECT duck_color, bet_amount FROM duck_bets WHERE discord_id = $1",
            uid,
        )
        if existing is None:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Mày chưa có kèo nào để hủy cả!\n"
                "Dùng `kbetvit <màu> <tiền>` để đặt cược."
            )
            return

        bet_amount = int(existing["bet_amount"])
        color_key = str(existing["duck_color"])
        duck_label = DUCKS.get(color_key, color_key)
        duck_emoji = DUCK_EMOJI.get(color_key, "<:gambling_duck:1536019587844546671>")

        await execute_db(self.bot, "DELETE FROM duck_bets WHERE discord_id = $1", uid)
        await _apply_delta(self.bot, uid, bet_amount)

        await ctx.send(
            f"♻️ {ctx.author.mention} Đã hủy kèo vào {duck_emoji} **{duck_label}**!\n"
            f"Hoàn lại **{bet_amount:,}** về ví. Suy nghĩ kỹ trước khi cược lần sau nhé! 😄"
        )

    @commands.command(name="xemvit", aliases=["xv", "duckpool"])
    async def xemvit_cmd(self, ctx: commands.Context) -> None:
        """Xem tổng pool cược và odds ước tính. Cú pháp: kxemvit"""
        stats = await _get_pool_stats(self.bot)
        total_pool = sum(stats.values())

        uid = str(ctx.author.id)
        my_bet = await fetchrow_db(
            self.bot,
            "SELECT duck_color, bet_amount FROM duck_bets WHERE discord_id = $1",
            uid,
        )

        lock_status = (
            "🔒 **SỔ ĐÃ ĐÓNG** — đang chờ khởi tranh!"
            if self.is_locked
            else "<:symbol_right:1536629912515903578> Đang nhận cược"
        )

        embed = _build_pool_embed(
            stats,
            title="🦆 Bảng Cược Đua Vịt Sự Kiện",
            color=COLOR_INFO,
            footer="Odds tính trên pool realtime — có thể thay đổi khi người khác cược thêm!",
        )
        embed.description = (
            f"Tổng tiền hiện có trên bàn: **{total_pool:,}**\n"
            f"Trạng thái: {lock_status}\n\n"
            "Odds ước tính dựa theo pool realtime!"
        )

        if my_bet is not None:
            my_color = str(my_bet["duck_color"])
            my_amount = int(my_bet["bet_amount"])
            my_label = DUCKS.get(my_color, my_color)
            my_emoji = DUCK_EMOJI.get(my_color, "<:gambling_duck:1536019587844546671>")
            embed.add_field(
                name="🎯 Cược Của Bạn",
                value=f"{my_emoji} **{my_label}** — {my_amount:,}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎯 Cược Của Bạn",
                value="Chưa đặt cược. Dùng `kbetvit <màu> <tiền>` nào!",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="forceduck", hidden=True)
    @commands.has_permissions(administrator=True)
    async def forceduck_cmd(self, ctx: commands.Context, action: str = "race") -> None:
        """[Admin] Force trigger đua vịt để test: lock / race / reset"""
        action = action.lower().strip()
        if action == "lock":
            await ctx.send("🛑 [Admin] Force khoá sổ...")
            await self._do_lock(0)
        elif action == "race":
            if self.is_racing:
                await ctx.send("⚠️ Đang có cuộc đua chạy rồi!")
                return
            await ctx.send("🏁 [Admin] Force khởi tranh...")
            await self._do_race()
        elif action == "reset":
            await execute_db(self.bot, "DELETE FROM duck_bets")
            self.is_locked = False
            self.is_racing = False
            self._lock_fired.clear()
            self._race_fired.clear()
            await ctx.send("<:symbol_right:1536629912515903578> [Admin] Reset bảng cược + mở khoá hoàn tất.")
        else:
            await ctx.send("Hành động không hợp lệ. Dùng: `lock`, `race`, `reset`")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DuckRace(bot))
