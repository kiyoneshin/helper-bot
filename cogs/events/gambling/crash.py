"""
crash.py — Cog Minigame "Quả Bóng Tham Lam" (Crash / Aviator)
==============================================================
Lệnh: kcrash
Cơ chế:
  - Lobby 30s: Người chơi đặt cược qua Button + Modal.
    Tiền bị trừ NGAY LẬP TỨC khi đặt thành công.
  - Game loop: Hệ số tăng dần theo thời gian thực.
    Chỉ update Discord mỗi ~1.5s để chống rate-limit.
  - Nổ: Crash point được tính ngay từ đầu (House Edge 5%).
    Ai chưa chốt lời -> mất trắng (tiền đã trừ từ Lobby).
    """

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    add_event_points,
    deduct_event_points,
    get_or_create_event_profile,
)

log = logging.getLogger("CrashGame")

COLOR_LOBBY  = 0xFFD700
COLOR_FLIGHT = 0x00BFFF
COLOR_CRASH  = 0xFF0000
COLOR_SAFE   = 0x00C851

LOBBY_DURATION  = 30
LOOP_SLEEP      = 1.5
MULTIPLIER_RATE = 0.08


async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    row = await get_or_create_event_profile(bot, user_id)
    if row is None:
        return 0
    return int(row["points"] or 0)


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
        return None, (
            f"Ví còn đúng **{balance:,}** mà đòi cược **{amount:,}**? Đỗ nghèo khỉ mà ham!"
        )
    return amount, None


def _generate_market_path(house_edge: float = 0.05) -> list[float]:
    path = [1.00]
    while True:
        change = random.uniform(0.60, 1.70)
        next_val = path[-1] * change
        path.append(next_val)
        
        if random.random() < house_edge:
            break
            
        if next_val <= 0.10:
            break
            
    return path


class BetModal(discord.ui.Modal, title="💰 Đặt Cược - Quả Bóng Tham Lam"):
    bet_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Số tiền cược (vd: 50k, 1.5m, 200000)",
        placeholder="Nhập số tiền...",
        min_length=1,
        max_length=20,
        required=True,
    )

    def __init__(
        self,
        bot: commands.Bot,
        lobby_view: "CrashLobbyView",
        players_bets: dict[int, int],
        lobby_message: discord.Message,
    ) -> None:
        super().__init__()
        self.bot           = bot
        self.lobby_view    = lobby_view
        self.players_bets  = players_bets
        self.lobby_message = lobby_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        uid     = str(interaction.user.id)
        user_id = interaction.user.id
        raw     = self.bet_input.value

        if user_id in self.players_bets:
            await interaction.response.send_message(
                f"Mày đã đặt cược **{self.players_bets[user_id]:,}** rồi! Tham vừa thôi, mỗi người cược 1 lần.",
                ephemeral=True,
            )
            return

        if not self.lobby_view.is_active:
            await interaction.response.send_message(
                "<:symbol_wrong:1536289315867598849> Sảnh đã đóng, hết chỗ chen chân rồi!",
                ephemeral=True,
            )
            return

        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(raw, balance)
        if err or bet is None:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536289315867598849> {interaction.user.mention} {err}",
                ephemeral=True,
            )
            return

        ok = await _apply_delta(self.bot, uid, -bet)
        if not ok:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536289315867598849> {interaction.user.mention} Trừ tiền thất bại - chắc do số dư không đủ. Kiểm tra lại túi đi!",
                ephemeral=True,
            )
            return

        self.players_bets[user_id] = bet
        
        from cogs.common.db import update_event_stat
        await update_event_stat(self.bot, uid, "casino_played", 1)
        log.info(
            "Crash lobby: %s dat cuoc %d",
            interaction.user.display_name, bet,
        )

        await interaction.response.send_message(
            f"<:symbol_right:1536289313959186472> **Ghi nhận!** Bạn đã xuống xác **{bet:,}** điểm.\n"
            "Tiền đã được nhà cái giữ. Chờ bóng bay nhé! 🚀",
            ephemeral=True,
        )

        try:
            await self.lobby_message.edit(
                embed=_build_lobby_embed(self.players_bets, self.lobby_view.time_left)
            )
        except discord.HTTPException:
            pass


class CrashLobbyView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        players_bets: dict[int, int],
        lobby_message_ref: list,
    ) -> None:
        super().__init__(timeout=float(LOBBY_DURATION))
        self.bot               = bot
        self.players_bets      = players_bets
        self.lobby_message_ref = lobby_message_ref
        self.is_active         = True
        self.time_left         = LOBBY_DURATION

    @discord.ui.button(
        label="💰 Đặt Cược",
        style=discord.ButtonStyle.primary,
        custom_id="crash_lobby_bet",
    )
    async def bet_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        lobby_msg = self.lobby_message_ref[0] if self.lobby_message_ref else None
        if lobby_msg is None:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Lỗi nội bộ sòng bài!", ephemeral=True)
            return

        modal = BetModal(
            bot=self.bot,
            lobby_view=self,
            players_bets=self.players_bets,
            lobby_message=lobby_msg,
        )
        await interaction.response.send_modal(modal)

    async def on_timeout(self) -> None:
        self.is_active = False
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()


class CrashActiveView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        players_bets: dict[int, int],
        cashed_out: dict[int, int],
    ) -> None:
        super().__init__(timeout=None)
        self.bot               = bot
        self.players_bets      = players_bets
        self.cashed_out        = cashed_out
        self.current_multiplier: float = 1.00
        self.is_crashed: bool          = False
        self._lock: asyncio.Lock       = asyncio.Lock()

    @discord.ui.button(
        label="📉 CẮT LỖ / CHỐT LỜI 📈",
        style=discord.ButtonStyle.success,
        custom_id="crash_cashout",
    )
    async def cashout_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        user_id = interaction.user.id

        async with self._lock:
            if self.is_crashed:
                await interaction.response.send_message(
                    "💀 **Mạng lag, bạn đã chết chìm!** Bóng nổ rồi, giờ này còn chốt cái gì nữa!",
                    ephemeral=True,
                )
                return

            if user_id not in self.players_bets:
                await interaction.response.send_message(
                    "<:symbol_wrong:1536289315867598849> Đã đứng ngó mà còn bấm bậy, có cược đâu mà đòi chốt!",
                    ephemeral=True,
                )
                return

            if user_id in self.cashed_out:
                already = self.cashed_out[user_id]
                await interaction.response.send_message(
                    f"⚠️ Bấm hoài! Đã chốt lời **{already:,}** điểm từ trước rồi cha nội.",
                    ephemeral=True,
                )
                return

            snapshot_mult = self.current_multiplier
            bet           = self.players_bets[user_id]
            payout        = int(bet * snapshot_mult)
            uid           = str(user_id)

            ok = await _apply_delta(self.bot, uid, payout)
            if not ok:
                await interaction.response.send_message(
                    "<:symbol_wrong:1536289315867598849> Sập nguồn DB khi chốt lời. Kêu Admin cứu!",
                    ephemeral=True,
                )
                return

            self.cashed_out[user_id] = payout
            profit = payout - bet
            
            # Achievements
            from cogs.common.db import update_event_stat
            if profit > 0:
                await update_event_stat(self.bot, uid, "casino_wins", 1)
            if snapshot_mult >= 10.0:
                await update_event_stat(self.bot, uid, "crash_x10", 1)

            log.info(
                "Crash cashout: user=%d mult=%.2f bet=%d payout=%d",
                user_id, snapshot_mult, bet, payout,
            )

        profit_display = payout - bet
        if snapshot_mult < 1.0:
            await interaction.response.send_message(
                f"⚠️ Bạn đã Cắt Lỗ ở hệ số **x{snapshot_mult:.2f}** (Lỗ **{abs(profit_display):,}** điểm). Còn hơn là mất trắng!",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"<:symbol_right:1536289313959186472> **Chốt lời thành công** nhảy dù kịp ở hệ số **x{snapshot_mult:.2f}**!\n"
                f"Vốn: **{bet:,}** -> Lụm lúa: **{payout:,}** "
                f"(+**{profit_display:,}** lãi) 🎉",
                ephemeral=True,
            )

    def mark_crashed(self) -> None:
        self.is_crashed = True
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()


def _build_lobby_embed(
    players_bets: dict[int, int],
    time_left: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="🎈 Quả Bóng Tham Lam — Sảnh Chờ",
        description=(
            "Nhấn **💰 Đặt Cược** để tham gia nhảy dù.\n"
            "Tiền sẽ bị **trừ ngay** khi đặt mâm thành công.\n"
            "Bóng sẽ bay sau khi sảnh đóng — biết chốt lời đúng lúc thì sống, tham thì chết thảm!\n\n"
            "🏠 **House Edge 5%** — Crash Point tính ngẫu nhiên bao minh bạch."
        ),
        color=COLOR_LOBBY,
    )
    embed.add_field(name="⏳ Sảnh đóng sau", value=f"**{time_left} giây**", inline=True)
    embed.add_field(name="👥 Con bạc tham gia", value=f"**{len(players_bets)}** mạng", inline=True)

    if players_bets:
        lines = [f"<@{uid}> → **{bet:,}** điểm" for uid, bet in players_bets.items()]
        embed.add_field(name="📋 Bảng Cược", value="\n".join(lines), inline=False)

    embed.set_footer(text="Angelic Casino • Crash 🚀")
    return embed


def _build_flight_embed(
    current_multiplier: float,
    prev_multiplier: float,
    players_bets: dict[int, int],
    cashed_out: dict[int, int],
) -> discord.Embed:
    if current_multiplier >= 1.0:
        bar_len    = min(20, int(current_multiplier * 3))
        bar_filled = "🟩" * bar_len + "⬜" * (20 - bar_len)
    else:
        bar_len    = min(20, int((1.0 - current_multiplier) * 10))
        bar_filled = "🟥" * bar_len + "⬜" * (20 - bar_len)

    if current_multiplier > prev_multiplier:
        icon = "📈"
        color = 0x00FF00
    elif current_multiplier < prev_multiplier:
        icon = "📉"
        color = 0xFF4500
    else:
        icon = "➖"
        color = COLOR_FLIGHT

    embed = discord.Embed(
        title=f"🚀 Bóng Đang Bay... {icon}",
        description=(
            f"## x{current_multiplier:.2f}\n"
            f"`{bar_filled}`\n\n"
            "Nhấn **📉 CẮT LỖ / CHỐT LỜI 📈** để bỏ túi an toàn!"
        ),
        color=color,
    )

    if cashed_out:
        safe_lines = []
        for uid, payout in cashed_out.items():
            bet    = players_bets.get(uid, 0)
            profit = payout - bet
            safe_lines.append(f"<@{uid}> <:symbol_right:1536289313959186472> **+{profit:,}**")
        embed.add_field(name="🏆 Đã Lụm Lúa", value="\n".join(safe_lines), inline=False)

    still_flying = [uid for uid in players_bets if uid not in cashed_out]
    if still_flying:
        embed.add_field(name="🎈 Còn Đang Bay", value="\n".join(f"<@{uid}>" for uid in still_flying), inline=False)

    embed.set_footer(text="Angelic Casino • Crash 🚀  |  Chốt lúc nào là do cái đầu của bạn!")
    return embed


def _build_crash_embed(
    crash_point: float,
    players_bets: dict[int, int],
    cashed_out: dict[int, int],
) -> discord.Embed:
    if crash_point < 1.00:
        title = "📉 BÙM! CHÁY TÀI KHOẢN📉"
    else:
        title = "💥 BÙM! BÓNG ĐÃ NỔ 💥"

    embed = discord.Embed(
        title=title,
        description=(
            f"Hệ số nổ chính thức: **x{crash_point:.2f}**\n\n"
            "Những kẻ tham lam đã bị trừng phạt. Ai chốt kịp thì mở champagne gáy thôi!"
        ),
        color=COLOR_CRASH,
    )

    if cashed_out:
        gold_lines = []
        for uid, payout in cashed_out.items():
            bet    = players_bets.get(uid, 0)
            profit = payout - bet
            if payout >= bet:
                gold_lines.append(
                    f"<@{uid}> • Vốn **{bet:,}** → Thu về **{payout:,}** (+**{profit:,}** húp đẫm)"
                )
            else:
                gold_lines.append(
                    f"<@{uid}> • Vốn **{bet:,}** → Còn **{payout:,}** (Cắt lỗ **{abs(profit):,}**)"
                )
        embed.add_field(
            name="🏅 Bảng Vàng — Nhảy Dù Kịp",
            value="\n".join(gold_lines),
            inline=False,
        )
    else:
        embed.add_field(
            name="🏅 Bảng Vàng",
            value="*Đứt bóng toàn tập! Nhà cái mút trọn sòng!* 🏦",
            inline=False,
        )

    losers = {uid: bet for uid, bet in players_bets.items() if uid not in cashed_out}
    if losers:
        loser_lines = [
            f"<@{uid}> • Mất trắng **{bet:,}** điểm 💸" for uid, bet in losers.items()
        ]
        embed.add_field(
            name="⚰️ Cột Trụ Sòng Bạc — Tham Lam Chết Chìm",
            value="\n".join(loser_lines),
            inline=False,
        )

    embed.set_footer(text="Angelic Casino • Crash 🚀  |  Tham thì thâm!")
    return embed


class CrashGame(commands.Cog):
    """Cog Minigame Crash/Aviator — Quả Bóng Tham Lam."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: set[int] = set()

    @commands.command(name="crash", aliases=["cr"])
    async def crash_cmd(self, ctx: commands.Context) -> None:
        channel_id = ctx.channel.id

        if channel_id in self.active_games:
            await ctx.send(
                "⚠️ Kênh này đang có 1 sòng Crash diễn ra rồi!\n"
                "Chờ sòng hiện tại chốt sổ hoặc tạt ngang qua kênh khác nhé.",
                delete_after=5.0,
            )
            return

        self.active_games.add(channel_id)
        market_path: list[float] = _generate_market_path()
        log.info("Crash game bat dau: channel=%d path_len=%d", channel_id, len(market_path))

        players_bets: dict[int, int] = {}
        cashed_out:   dict[int, int] = {}

        try:
            await self._run_lobby(ctx, players_bets, cashed_out, market_path)
        finally:
            self.active_games.discard(channel_id)
            log.info("Crash game ket thuc: channel=%d", channel_id)

    @crash_cmd.error
    async def crash_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536289315867598849> {ctx.author.mention} Tính lên tàu bay dạo không vé hả? Cú pháp: `{ctx.prefix}crash <tiền_cược>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp crash`")
        elif isinstance(error, commands.CommandInvokeError):
            log.error("Loi crash_cmd: %s", error.original, exc_info=True)
            await ctx.send(
                "<:symbol_wrong:1536289315867598849> Đã xảy ra lỗi nội bộ làm sập sòng Crash. "
                "Phiên chơi bị huỷ kèo và ván mới có thể bắt đầu.",
                delete_after=10.0,
            )


    async def _run_lobby(
        self,
        ctx: commands.Context,
        players_bets: dict[int, int],
        cashed_out: dict[int, int],
        market_path: list[float],
    ) -> None:
        lobby_message_ref: list = []

        lobby_view = CrashLobbyView(
            bot=self.bot,
            players_bets=players_bets,
            lobby_message_ref=lobby_message_ref,
        )

        lobby_msg = await ctx.send(
            embed=_build_lobby_embed(players_bets, LOBBY_DURATION),
            view=lobby_view,
        )
        lobby_message_ref.append(lobby_msg)

        start_ts   = time.monotonic()
        checkpoints: set[int] = {20, 10, 5}

        while True:
            elapsed   = time.monotonic() - start_ts
            time_left = max(0, int(LOBBY_DURATION - elapsed))
            lobby_view.time_left = time_left

            if time_left <= 0:
                break

            if time_left in checkpoints:
                checkpoints.discard(time_left)
                try:
                    await lobby_msg.edit(embed=_build_lobby_embed(players_bets, time_left))
                except discord.HTTPException:
                    pass

            await asyncio.sleep(1.0)

        lobby_view.is_active = False
        lobby_view.stop()

        try:
            closing_embed = _build_lobby_embed(players_bets, 0)
            closing_embed.title = "🎈 Sảnh Đã Đóng — Bóng Chuẩn Bị Bak"
            closing_embed.color = 0xFF8C00
            closing_view = discord.ui.View()
            disabled_btn  = discord.ui.Button(
                label="💰 Đặt Cược",
                style=discord.ButtonStyle.primary,
                disabled=True,
            )
            closing_view.add_item(disabled_btn)
            await lobby_msg.edit(embed=closing_embed, view=closing_view)
        except discord.HTTPException:
            pass

        if not players_bets:
            empty_embed = discord.Embed(
                title="🎈 Quả Bóng Tham Lam",
                description="Ế ẩm quá không ai chịu cược. Giải tán sòng!",
                color=0x808080,
            )
            empty_embed.set_footer(text="Angelic Casino • Crash 🚀")
            try:
                await lobby_msg.edit(embed=empty_embed, view=None)
            except discord.HTTPException:
                pass
            return

        await self._run_flight(ctx, lobby_msg, players_bets, cashed_out, market_path)

    async def _run_flight(
        self,
        ctx: commands.Context,
        game_message: discord.Message,
        players_bets: dict[int, int],
        cashed_out: dict[int, int],
        market_path: list[float],
    ) -> None:
        active_view = CrashActiveView(
            bot=self.bot,
            players_bets=players_bets,
            cashed_out=cashed_out,
        )

        prev_multiplier = 1.00
        try:
            await game_message.edit(
                embed=_build_flight_embed(1.00, prev_multiplier, players_bets, cashed_out),
                view=active_view,
            )
        except discord.HTTPException as exc:
            log.warning("Khong the chuyen sang Flight View: %s", exc)

        for i, current_multiplier in enumerate(market_path):
            active_view.current_multiplier = current_multiplier

            if i == len(market_path) - 1:
                active_view.mark_crashed()
                await self._resolve_crash(
                    game_message, players_bets, cashed_out, current_multiplier, active_view
                )
                return

            try:
                await game_message.edit(
                    embed=_build_flight_embed(current_multiplier, prev_multiplier, players_bets, cashed_out),
                    view=active_view,
                )
            except discord.HTTPException:
                pass

            prev_multiplier = current_multiplier
            await asyncio.sleep(LOOP_SLEEP)

    async def _resolve_crash(
        self,
        game_message: discord.Message,
        players_bets: dict[int, int],
        cashed_out: dict[int, int],
        crash_point: float,
        active_view: CrashActiveView,
    ) -> None:
        log.info(
            "Crash resolved: crash_point=%.4f cashed_out=%d/%d",
            crash_point, len(cashed_out), len(players_bets),
        )

        crash_embed = _build_crash_embed(crash_point, players_bets, cashed_out)

        try:
            await game_message.edit(embed=crash_embed, view=active_view)
            if game_message.channel.id == 1498711783223853101:
                await game_message.delete(delay=30.0)
        except discord.HTTPException as exc:
            log.warning("Khong the update Crash Embed cuoi: %s", exc)
            try:
                msg = await game_message.channel.send(embed=crash_embed)
                if msg.channel.id == 1498711783223853101:
                    await msg.delete(delay=30.0)
            except discord.HTTPException:
                pass



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CrashGame(bot))
