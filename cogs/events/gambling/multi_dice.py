"""
multi_dice.py — Cog Xúc Xắc Quần Hùng (Multi Dice PvP)
=======================================================
Lệnh: kmultidice <tiền_cược> [@user1] [@user2]...

4 Giai Đoạn:
  1. Chiêu mộ: Ping danh sách, bấm nút đồng ý / bỏ chạy (60s).
  2. Sảnh công khai: Ai thích thì vào (60s, tối đa 10 người).
  3. Lắc xúc xắc đồng thời: Có animation chống rate-limit (30s + 20s reveal).
  4. Kết quả: Thuế 2 đầu, chia tiền theo tier (1/2/3 người thắng), mở khóa.

Cơ cấu thuế:
  - Vào sảnh: Trừ bet, nhưng chỉ bet*0.95 vào pot.
  - Chia thưởng: Pot*0.95 = DP (distributable pot).
  """

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    add_event_points,
    deduct_event_points,
    get_or_create_event_profile,
    update_task_progress,
)

log = logging.getLogger("MultiDice")

# ─────────────────────────────────────────────────────────────────────────────
# HẰNG SỐ
DICE_GIF = "<a:Yb_tt_xucxac:1526669924448079955>"
DICE_NUMS: dict[int, str] = {
    1: "<:gambling_dice_1:1536019570849091706>",
    2: "<:gambling_dice_2:1536019573252554894>",
    3: "<:gambling_dice_3:1536019575768875200>",
    4: "<:gambling_dice_4:1536019579304808619>",
    5: "<:gambling_dice_5:1536019581301424158>",
    6: "<:gambling_dice_6:1536019583264362566>"
}

MAX_PLAYERS       = 10
INVITE_TIMEOUT    = 30
LOBBY_TIMEOUT     = 45
SPECTATOR_TIMEOUT = 45    # giây cho khán giả đặt cược
ROLL_TIMEOUT      = 20    # giây trước khi bot tự lắc cho kẻ AFK
REVEAL_DELAY      = 10    # giây kể từ click_time để cả 2 xúc xắc hiện ra
ANIM_INTERVAL     = 2     # giây giữa mỗi lần update embed

COLOR_INFO   = 0xFFD700
COLOR_WIN    = 0x00FF00
COLOR_LOSE   = 0xFF0000
COLOR_WAIT   = 0x7289DA


# ─────────────────────────────────────────────────────────────────────────────
# DB HELPERS (tự khai báo để không phụ thuộc circular import)
# ─────────────────────────────────────────────────────────────────────────────

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
    """Hỗ trợ hậu tố k (×1.000) và m (×1.000.000), số thập phân."""
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
            f"Ví chỉ có **{balance:,}**, mà đòi cược **{amount:,}**? Nghèo mà ham!"
        )
    return amount, None


def _is_busy(bot: commands.Bot, user_id: int) -> bool:
    active: set[int] = getattr(bot, "active_players", set())
    return user_id in active


def _lock_user(bot: commands.Bot, user_id: int) -> None:
    active: set[int] = getattr(bot, "active_players", set())
    active.add(user_id)
    setattr(bot, "active_players", active)


def _unlock_user(bot: commands.Bot, user_id: int) -> None:
    active: set[int] = getattr(bot, "active_players", set())
    active.discard(user_id)
    setattr(bot, "active_players", active)


# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

class PlayerInfo:
    """Dữ liệu một người chơi trong ván Multi Dice."""

    __slots__ = ("user_id", "pot_contribution", "d1", "d2", "click_time", "auto_rolled")

    def __init__(self, user_id: int, pot_contribution: int) -> None:
        self.user_id = user_id
        self.pot_contribution = pot_contribution  # bet * 0.95, tiền thực vào pot
        self.d1: Optional[int] = None
        self.d2: Optional[int] = None
        self.click_time: Optional[float] = None
        self.auto_rolled: bool = False

    @property
    def total(self) -> int:
        return (self.d1 or 0) + (self.d2 or 0)

    @property
    def has_rolled(self) -> bool:
        return self.click_time is not None

    @property
    def is_revealed(self) -> bool:
        if self.click_time is None:
            return False
        return (time.time() - self.click_time) >= REVEAL_DELAY


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: GIAI ĐOẠN 1 — INVITE
# ─────────────────────────────────────────────────────────────────────────────

class InviteView(discord.ui.View):
    """Giai đoạn 1: Những người được ping bấm Tham Gia hoặc Bỏ Chạy."""

    def __init__(
        self,
        host: discord.Member,
        invitees: list[discord.Member],
        bet: int,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=float(INVITE_TIMEOUT))
        self.host = host
        self.invitees = invitees
        self.bet = bet
        self.bot = bot
        # None = chưa quyết, True = đồng ý, False = từ chối
        self.statuses: dict[int, Optional[bool]] = {m.id: None for m in invitees}
        self.confirmed: list[discord.Member] = []
        self.message: Optional[discord.Message] = None
        self._done = asyncio.Event()
        self.end_time = int(time.time()) + INVITE_TIMEOUT

    def _all_decided(self) -> bool:
        return all(v is not None for v in self.statuses.values())

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="<:gambling_dice:1537539887769591828> Xúc Xắc Quần Hùng — Chiêu Mộ Anh Tài",
            description=(
                f"{self.host.mention} đang kéo mồi!\n"
                f"Cược: **{self.bet:,}**/người *(trừ 5% thuế vào sảnh)*\n\n"
                "<:symbol_locked:1537566880066441296> **Sảnh đã chốt!**\n" if self._done.is_set() else f"<:symbol_hour_glass:1537570149215899658> **Chốt kèo:** <t:{self.end_time}:R>\n"
                "Dám vào thì bấm, nhát thì né:"
            ),
            color=COLOR_INFO,
        )
        lines: list[str] = []
        for m in self.invitees:
            s = self.statuses.get(m.id)
            icon = "<:symbol_right:1536629912515903578>" if s is True else ("<:symbol_wrong:1536629915598848072>" if s is False else "<:symbol_hour_glass:1537570149215899658>")
            lines.append(f"{icon} {m.mention}")
        embed.add_field(name="Danh Sách Được Kéo Mồi", value="\n".join(lines), inline=False)
        embed.set_footer(text=f"Bỏ chạy coi chừng mất mặt")
        return embed

    @discord.ui.button(label="Tham Gia", style=discord.ButtonStyle.success, custom_id="md_invite_join", emoji="<:symbol_right:1536629912515903578>")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        uid = interaction.user.id
        if uid not in self.statuses:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Mày không nằm trong danh sách, lui ra!", delete_after=5.0)
            return
        if self.statuses[uid] is True:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đã vào rồi, bấm loạn làm gì!", delete_after=5.0)
            return
        if self.statuses[uid] is False:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đã bỏ chạy rồi, lần sau đừng hèn!", delete_after=5.0)
            return

        # Kiểm tra bận
        if _is_busy(self.bot, uid):
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đang chơi game khác rồi! Kết thúc game đó trước."
            , delete_after=5.0)
            return

        # Kiểm tra tiền
        bal = await _get_balance(self.bot, str(uid))
        if bal < self.bet:
            self.statuses[uid] = False
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Ví có **{bal:,}** mà đòi cược **{self.bet:,}**? Nghèo mà ham! Gạch tên."
            , delete_after=5.0)
        else:
            ok = await _apply_delta(self.bot, str(uid), -self.bet)
            if not ok:
                self.statuses[uid] = False
                await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Lỗi DB! Thử lại sau.", delete_after=5.0)
            else:
                self.statuses[uid] = True
                _lock_user(self.bot, uid)
                member = interaction.user
                if isinstance(member, discord.Member):
                    self.confirmed.append(member)
                await interaction.response.send_message(
                    f"<:symbol_right:1536629912515903578> {interaction.user.mention} Chốt! Đã trừ **{self.bet:,}**. Ngồi chờ sảnh mở."
                , delete_after=5.0)

        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass

        if self._all_decided():
            self._done.set()

    @discord.ui.button(label="Bỏ Chạy", style=discord.ButtonStyle.danger, custom_id="md_invite_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        uid = interaction.user.id
        if uid not in self.statuses:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Không liên quan!", delete_after=5.0)
            return
        if self.statuses[uid] is not None:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đã chốt rồi, không thay đổi được!", delete_after=5.0)
            return

        self.statuses[uid] = False
        await interaction.response.send_message(f"🏃 {interaction.user.mention} Nhát gan thật. Thoát kèo.", delete_after=5.0)

        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass

        if self._all_decided():
            self._done.set()

    async def on_timeout(self) -> None:
        for uid, status in self.statuses.items():
            if status is None:
                self.statuses[uid] = False
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        self._done.set()
        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: GIAI ĐOẠN 2 — PUBLIC LOBBY
# ─────────────────────────────────────────────────────────────────────────────

class PublicLobbyView(discord.ui.View):
    """Giai đoạn 2: Sảnh công khai, ai thích vào thì bấm."""

    def __init__(
        self,
        initial_players: list[discord.Member],
        bet: int,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=float(LOBBY_TIMEOUT))
        self.bet = bet
        self.bot = bot
        self.players: list[discord.Member] = list(initial_players)
        self.player_ids: set[int] = {m.id for m in initial_players}
        self.message: Optional[discord.Message] = None
        self._closed = asyncio.Event()
        self.end_time = int(time.time()) + LOBBY_TIMEOUT

    def build_embed(self) -> discord.Embed:
        count = len(self.players)
        spots = MAX_PLAYERS - count
        embed = discord.Embed(
            title="<:gambling_dice:1537539887769591828> Xúc Xắc Quần Hùng — Sòng Đã Mở!",
            description=(
                f"Mại dô mại dô! Tay nhanh hơn não!\n"
                f"Cược: **{self.bet:,}**/người *(trừ 5% thuế vào sảnh)*\n\n"
                "<:symbol_locked:1537566880066441296> **Sảnh đã chốt!**" if self._closed.is_set() else f"**Còn {spots} chỗ trống** — Đủ {MAX_PLAYERS} người hoặc đến <t:{self.end_time}:R> thì chốt!"
            ),
            color=COLOR_INFO,
        )
        if self.players:
            embed.add_field(
                name=f"👥 Danh Sách Hiện Tại ({count}/{MAX_PLAYERS})",
                value="\n".join(f"• {m.mention}" for m in self.players),
                inline=False,
            )
        embed.set_footer(text="Đóng hụi đi! Chờ lâu mất chỗ.")
        return embed

    @discord.ui.button(label="Vào Bàn", style=discord.ButtonStyle.primary, custom_id="md_lobby_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        uid = interaction.user.id

        if uid in self.player_ids:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Mày đã ngồi bàn rồi, bấm loạn làm gì!", delete_after=5.0)
            return
        if len(self.players) >= MAX_PLAYERS:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Bàn đầy rồi! Trễ mất rồi.", delete_after=5.0)
            return
        if _is_busy(self.bot, uid):
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đang chơi game khác rồi! Kết thúc trước đã."
            , delete_after=5.0)
            return

        bal = await _get_balance(self.bot, str(uid))
        if bal < self.bet:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Ví có **{bal:,}** mà đòi cược **{self.bet:,}**? Nghèo mà ham!"
            , delete_after=5.0)
            return

        ok = await _apply_delta(self.bot, str(uid), -self.bet)
        if not ok:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Lỗi DB! Thử lại sau.", delete_after=5.0)
            return

        _lock_user(self.bot, uid)
        self.player_ids.add(uid)
        member = interaction.user
        if isinstance(member, discord.Member):
            self.players.append(member)

        await interaction.response.send_message(
            f"<:symbol_right:1536629912515903578> {interaction.user.mention} Đóng hụi! Trừ **{self.bet:,}**. Ngồi xuống chờ."
        , delete_after=5.0)

        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass

        if len(self.players) >= MAX_PLAYERS:
            self._closed.set()
            self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        self._closed.set()
        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: GIAI ĐOẠN 3 — ROLL
# ─────────────────────────────────────────────────────────────────────────────

class RollView(discord.ui.View):
    """Giai đoạn 3: Mỗi người bấm nút lắc; animation hiện ra dần."""

    def __init__(self, player_infos: dict[int, PlayerInfo]) -> None:
        super().__init__(timeout=float(ROLL_TIMEOUT + REVEAL_DELAY + 10))
        self.player_infos = player_infos
        self.roll_order: list[int] = []  # user_id theo thứ tự bấm
        self.message: Optional[discord.Message] = None
        self._all_rolled = asyncio.Event()
        self.end_time = int(time.time()) + ROLL_TIMEOUT

    def build_embed(self) -> discord.Embed:
        """Render trạng thái animation hiện tại — gọi mỗi ANIM_INTERVAL giây."""
        embed = discord.Embed(
            title="<:gambling_dice:1537539887769591828> Xúc Xắc Quần Hùng — Đang Lắc!",
            description=(
                "Ai dám lắc trước, kẻ đó có lợi thế tie-break!\n"
                f"Qua <t:{self.end_time}:R> không bấm thì Bot lắc thay — đừng trách."
            ),
            color=COLOR_WAIT,
        )
        now = time.time()
        lines: list[str] = []

        # Người đã bấm — theo thứ tự bấm
        shown: set[int] = set()
        for uid in self.roll_order:
            info = self.player_infos[uid]
            shown.add(uid)
            elapsed = now - (info.click_time or now)
            if elapsed < 5:
                dice_str = f"{DICE_GIF} {DICE_GIF}"
            elif elapsed < REVEAL_DELAY:
                d1e = DICE_NUMS.get(info.d1 or 1, "?")
                dice_str = f"**{d1e}** {DICE_GIF}"
            else:
                d1e = DICE_NUMS.get(info.d1 or 1, "?")
                d2e = DICE_NUMS.get(info.d2 or 1, "?")
                total = info.total
                auto = " *(bot lắc)*" if info.auto_rolled else ""
                dice_str = f"**{d1e} + {d2e} = {total}**{auto}"
            lines.append(f"<:gambling_dice:1537539887769591828> <@{uid}> ── {dice_str}")

        # Người chưa bấm
        for uid in self.player_infos:
            if uid not in shown:
                lines.append(f"<:symbol_hour_glass:1537570149215899658> <@{uid}> ── *Đang chờ bấm nút...*")

        rolled_count = len(self.roll_order)
        total_count = len(self.player_infos)
        embed.add_field(
            name=f"Bảng Đấu ({rolled_count}/{total_count} đã lắc)",
            value="\n".join(lines) if lines else "(trống)",
            inline=False,
        )
        embed.set_footer(text="Chờ xúc xắc dừng quay... • Angelic Casino 🌸")
        return embed

    @discord.ui.button(label="Lắc Xúc Xắc", style=discord.ButtonStyle.primary, custom_id="md_roll", emoji="<:gambling_dice:1537539887769591828>")
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        uid = interaction.user.id
        if uid not in self.player_infos:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Mày không ngồi bàn này!", delete_after=5.0)
            return

        info = self.player_infos[uid]
        if info.has_rolled:
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Lắc rồi! Nhìn màn hình chờ đi.", delete_after=5.0)
            return

        info.click_time = time.time()
        info.d1 = random.randint(1, 6)
        info.d2 = random.randint(1, 6)
        self.roll_order.append(uid)

        await interaction.response.send_message(
            f"<:gambling_dice:1537539887769591828> {interaction.user.mention} Đã lắc! Xúc xắc đang quay... đợi kết quả hiện ra."
        , delete_after=5.0)

        if all(p.has_rolled for p in self.player_infos.values()):
            self._all_rolled.set()


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: GIAI ĐOẠN 2.5 — SPECTATOR BETTING (KHÁN GIẢ CÁ CƯỢC)
# ─────────────────────────────────────────────────────────────────────────────

class SpectatorBetModal(discord.ui.Modal, title="<:symbol_money_2:1537567535229050970> Đặt Cược Khán Đài"):
    """Modal nhập số tiền cược của khán giả."""

    bet_input = discord.ui.TextInput(
        label="Số tiền cược",
        placeholder="VD: 500, 10k, 1.5m...",
        required=True,
        max_length=20,
    )

    def __init__(self, view: "SpectatorBetView", player_id: int) -> None:
        super().__init__()
        self.view_ref = view
        self.player_id = player_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        uid = interaction.user.id
        raw = str(self.bet_input.value)

        balance = await _get_balance(self.view_ref.bot, str(uid))
        bet, err = _parse_bet(raw, balance)
        if err or bet is None:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} {err or 'Số tiền không hợp lệ!'}", delete_after=5.0
            )
            return

        ok = await _apply_delta(self.view_ref.bot, str(uid), -bet)
        if not ok:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Lỗi DB khi trừ tiền — thử lại!", delete_after=5.0
            )
            return

        # Cộng dồn vào dictionary
        if uid not in self.view_ref.spectator_bets:
            self.view_ref.spectator_bets[uid] = {}
            _lock_user(self.view_ref.bot, uid)
            self.view_ref.locked_spectators.add(uid)

        bets_dict = self.view_ref.spectator_bets[uid]
        bets_dict[self.player_id] = bets_dict.get(self.player_id, 0) + bet

        player_name = self.view_ref.player_names.get(self.player_id, f"<@{self.player_id}>")
        total_on_player = bets_dict[self.player_id]
        await interaction.response.send_message(
            f"<:symbol_right:1536629912515903578> {interaction.user.mention} Cược **{bet:,}** vào **{player_name}**! "
            f"(Tổng trên người này: **{total_on_player:,}**)",
            delete_after=5.0,
        )

        # Cập nhật embed
        try:
            if self.view_ref.message:
                await self.view_ref.message.edit(embed=self.view_ref.build_embed(), view=self.view_ref)
        except discord.HTTPException:
            pass


class SpectatorBetView(discord.ui.View):
    """Giai đoạn 2.5: Khán giả đặt cược người thắng."""

    def __init__(
        self,
        final_players: list[discord.Member],
        bet: int,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=float(SPECTATOR_TIMEOUT))
        self.final_players = final_players
        self.player_ids: set[int] = {m.id for m in final_players}
        self.player_names: dict[int, str] = {m.id: m.display_name for m in final_players}
        self.bet = bet
        self.bot = bot
        self.message: Optional[discord.Message] = None
        self._closed = asyncio.Event()
        self.end_time = int(time.time()) + SPECTATOR_TIMEOUT

        # Key: spectator_user_id, Value: {player_user_id: total_bet}
        self.spectator_bets: dict[int, dict[int, int]] = {}
        self.locked_spectators: set[int] = set()

        # Build Select Menu
        select = discord.ui.Select(
            placeholder="👉 Chọn người bạn muốn cược...",
            custom_id="md_spectator_select",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=m.display_name,
                    value=str(m.id),
                    description=f"Cược {m.display_name} sẽ thắng",
                )
                for m in final_players
            ],
        )
        select.callback = self._select_callback
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="<:items_00_lottery_ticket:1537566232897650811> Khán Đài Đỏ Đen — Ai Thắng Ai Thua?",
            description=(
                "Người ngoài sàn cũng có thể hốt bạc!\n"
                "Chọn 1 hoặc nhiều tay chơi bạn nghĩ sẽ thắng, rồi đặt cược vào.\n"
                + ("<:symbol_locked:1537566880066441296> **Đã chốt sổ!**" if self._closed.is_set() else f"<:symbol_hour_glass:1537570149215899658> Chốt sổ: <t:{self.end_time}:R>")
            ),
            color=COLOR_INFO,
        )

        # Tổng hợp cược vào từng player
        pool_by_player: dict[int, int] = {}
        for spec_bets in self.spectator_bets.values():
            for pid, amt in spec_bets.items():
                pool_by_player[pid] = pool_by_player.get(pid, 0) + amt

        lines: list[str] = []
        total_spec_pool = sum(pool_by_player.values())
        for m in self.final_players:
            pool_on = pool_by_player.get(m.id, 0)
            count = sum(1 for sb in self.spectator_bets.values() if m.id in sb)
            if pool_on > 0:
                lines.append(f"• {m.mention} — **{pool_on:,}** (từ {count} khán giả)")
            else:
                lines.append(f"• {m.mention} — *chưa ai cược*")

        embed.add_field(
            name=f"👥 Danh Sách Tay Chơi ({len(self.final_players)} người)",
            value="\n".join(lines),
            inline=False,
        )
        if total_spec_pool > 0:
            embed.add_field(
                name="<:symbol_money_2:1537567535229050970> Tổng Pot Khán Đài",
                value=f"**{total_spec_pool:,}** điểm",
                inline=False,
            )
        embed.set_footer(text="Cược bao nhiêu cửa cũng được, cộng dồn tuỳ thích!")
        return embed

    async def _select_callback(self, interaction: discord.Interaction) -> None:
        uid = interaction.user.id

        # Không cho người chơi chính tự cược chính mình
        if uid in self.player_ids:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Mày đang trên sàn, đặt cược cái gì!",
                delete_after=5.0,
            )
            return

        # Kiểm tra bận (chỉ chặn nếu đang chơi game KHÁC, không phải đang cược khán đài)
        if _is_busy(self.bot, uid) and uid not in self.locked_spectators:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Đang bận game khác rồi!",
                delete_after=5.0,
            )
            return

        selected_player_id = int(interaction.data["values"][0])  # type: ignore[index]
        modal = SpectatorBetModal(view=self, player_id=selected_player_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Hủy cược (Hoàn tiền)", style=discord.ButtonStyle.danger, custom_id="md_spectator_cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        uid = interaction.user.id
        if uid not in self.spectator_bets or not self.spectator_bets[uid]:
            await interaction.response.send_message(
                f"<:symbol_wrong:1536629915598848072> {interaction.user.mention} Mày có cược gì đâu mà hủk",
                delete_after=5.0,
            )
            return

        total_refund = sum(self.spectator_bets[uid].values())
        await _apply_delta(self.bot, str(uid), total_refund)
        del self.spectator_bets[uid]

        if uid in self.locked_spectators:
            _unlock_user(self.bot, uid)
            self.locked_spectators.discard(uid)

        await interaction.response.send_message(
            f"♻️ {interaction.user.mention} Rút hết cược, hoàn **{total_refund:,}** vào ví!",
            delete_after=5.0,
        )

        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True  # type: ignore[union-attr]
        self._closed.set()
        try:
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# COG CHÍNH
# ─────────────────────────────────────────────────────────────────────────────

class MultiDice(commands.Cog):
    """Cog Xúc Xắc Quần Hùng — PvP Multi Dice."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="multidice", aliases=["md", "quanhung"])
    async def multidice_cmd(
        self,
        ctx: commands.Context,
        bet_raw: str,
        *mentions: discord.Member,
    ) -> None:
        """
        Xúc Xắc Quần Hùng — Cược PvP cùng bạn bè.
        Cú pháp: kmultidice <tiền_cược> [@user1] [@user2]...
        """
        host = ctx.author
        if not isinstance(host, discord.Member):
            await ctx.send("Chỉ dùng được trong server!", ephemeral=True)
            return

        # ── Kiểm tra host bận ───────────────────────────────────────────
        if _is_busy(self.bot, host.id):
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {host.mention}, đang chơi game khác rồi! Kết thúc trước đã."
            )
            return

        # ── Validate tiền cược ──────────────────────────────────────────
        host_bal = await _get_balance(self.bot, str(host.id))
        bet, err = _parse_bet(bet_raw, host_bal)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {host.mention} {err or 'Tiền cược không hợp lệ!'}")
            return

        # ── Lọc danh sách được mời ──────────────────────────────────────
        invitees: list[discord.Member] = []
        seen: set[int] = {host.id}
        for m in mentions:
            if not m.bot and m.id not in seen and len(invitees) < MAX_PLAYERS - 1:
                seen.add(m.id)
                invitees.append(m)

        # ── Khóa host & trừ tiền ────────────────────────────────────────
        _lock_user(self.bot, host.id)
        ok = await _apply_delta(self.bot, str(host.id), -bet)
        if not ok:
            _unlock_user(self.bot, host.id)
            await ctx.send("Lỗi DB! Thử lại sau.", ephemeral=True)
            return

        # Khóa trước những người được mời (mở lại nếu họ từ chối)
        # BỎ KHÓA NHỮNG NGƯỜI ĐƯỢC MỜI ĐỂ HỌ KHÔNG BỊ BUSY KHI BẤM JOIN
        # for m in invitees:
        #     _lock_user(self.bot, m.id)

        # Theo dõi toàn bộ người đã khóa để mở ở finally
        locked_set: set[int] = {host.id}

        final_players: list[discord.Member] = []

        try:
            # ── GIAI ĐOẠN 1: INVITE ──────────────────────────────────────
            confirmed_from_invite: list[discord.Member] = [host]

            if invitees:
                invite_view = InviteView(host, invitees, bet, self.bot)
                invite_msg = await ctx.send(embed=invite_view.build_embed(), view=invite_view)
                invite_view.message = invite_msg
                
                try:
                    await asyncio.wait_for(invite_view._done.wait(), timeout=float(INVITE_TIMEOUT))
                except asyncio.TimeoutError:
                    invite_view.stop()
                    await invite_view.on_timeout()

                try:
                    await invite_msg.delete()
                except discord.HTTPException:
                    pass

                confirmed_from_invite.extend(invite_view.confirmed)
                # Thêm những người đã bấm Tham Gia vào locked_set để tí nữa mở khóa
                for m in invite_view.confirmed:
                    locked_set.add(m.id)

            # ── GIAI ĐOẠN 2: PUBLIC LOBBY ────────────────────────────────
            lobby_view = PublicLobbyView(confirmed_from_invite, bet, self.bot)
            lobby_msg = await ctx.send(embed=lobby_view.build_embed(), view=lobby_view)
            lobby_view.message = lobby_msg
            
            try:
                await asyncio.wait_for(lobby_view._closed.wait(), timeout=float(LOBBY_TIMEOUT))
            except asyncio.TimeoutError:
                lobby_view.stop()
                await lobby_view.on_timeout()

            try:
                await lobby_msg.delete()
            except discord.HTTPException:
                pass

            final_players = lobby_view.players
            # Cập nhật locked_set với những người mới vào ở phase 2
            for m in final_players:
                locked_set.add(m.id)

            # Kiểm tra đủ 2 người
            if len(final_players) < 2:
                for m in final_players:
                    await _apply_delta(self.bot, str(m.id), bet)
                await ctx.send(
                    "Không đủ 2 người tham gia. Hủy kèo! Tiền hoàn lại hết."
                    "\nThảo nào ế, chẳng ai chịu vào!"
                )
                return

            # ── GIAI ĐOẠN 2.5: SPECTATOR BETTING ─────────────────────────
            spec_view = SpectatorBetView(final_players, bet, self.bot)
            spec_msg = await ctx.send(embed=spec_view.build_embed(), view=spec_view)
            spec_view.message = spec_msg

            try:
                await asyncio.wait_for(spec_view._closed.wait(), timeout=float(SPECTATOR_TIMEOUT))
            except asyncio.TimeoutError:
                spec_view.stop()
                await spec_view.on_timeout()

            try:
                await spec_msg.delete()
            except discord.HTTPException:
                pass

            spectator_bets = dict(spec_view.spectator_bets)
            spec_locked = set(spec_view.locked_spectators)
            locked_set.update(spec_locked)

            # ── GIAI ĐOẠN 3: ROLL DICE ───────────────────────────────────
            pot_per = int(bet * 0.95)
            player_infos: dict[int, PlayerInfo] = {
                m.id: PlayerInfo(m.id, pot_per) for m in final_players
            }

            roll_view = RollView(player_infos)
            roll_msg = await ctx.send(embed=roll_view.build_embed(), view=roll_view)
            roll_view.message = roll_msg

            roll_start = time.time()

            async def _auto_roll_task() -> None:
                try:
                    await asyncio.wait_for(roll_view._all_rolled.wait(), timeout=float(ROLL_TIMEOUT))
                except asyncio.TimeoutError:
                    late_t = time.time()
                    for uid, info in player_infos.items():
                        if not info.has_rolled:
                            info.click_time = late_t
                            info.d1 = random.randint(1, 6)
                            info.d2 = random.randint(1, 6)
                            info.auto_rolled = True
                            roll_view.roll_order.append(uid)
                    roll_view._all_rolled.set()
                    
                    try:
                        new_embed = roll_view.build_embed()
                        if roll_view.message:
                            await roll_view.message.edit(embed=new_embed)
                    except discord.HTTPException:
                        pass

            async def _animation_loop() -> None:
                while True:
                    await asyncio.sleep(ANIM_INTERVAL)
                    
                    # Kiểm tra tất cả đã reveal
                    all_done = (
                        all(p.has_rolled for p in player_infos.values())
                        and all(p.is_revealed for p in player_infos.values())
                    )

                    try:
                        new_embed = roll_view.build_embed()
                        if roll_view.message:
                            await roll_view.message.edit(embed=new_embed)
                    except discord.HTTPException:
                        pass

                    if all_done:
                        break

            auto_task = asyncio.create_task(_auto_roll_task())
            anim_task = asyncio.create_task(_animation_loop())
            
            max_wait = ROLL_TIMEOUT + REVEAL_DELAY + 15
            try:
                await asyncio.wait_for(anim_task, timeout=max_wait)
            except asyncio.TimeoutError:
                pass
            finally:
                auto_task.cancel()
                anim_task.cancel()

            # Khoá nút lắc
            roll_view.stop()
            for child in roll_view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            try:
                final_roll_embed = roll_view.build_embed()
                final_roll_embed.title = "<:gambling_dice:1537539887769591828> Xúc Xắc Quần Hùng — Đã Chốt Điểm!"
                if roll_view.message:
                    await roll_view.message.edit(embed=final_roll_embed, view=roll_view)
            except discord.HTTPException:
                pass

            # ── GIAI ĐOẠN 4: KẾT QUẢ ────────────────────────────────────
            try:
                if roll_msg:
                    await roll_msg.delete()
            except discord.HTTPException:
                pass
            
            await self._resolve_game(ctx, final_players, player_infos, bet, spectator_bets)

        finally:
            for uid in locked_set:
                _unlock_user(self.bot, uid)

    @multidice_cmd.error
    async def multidice_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lắc xí ngầu tập thể mà không có cắc bạc nào à? Cú pháp: `{ctx.prefix}md <tiền_cược> <@user1> <@user2>...`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp md`")


    async def _resolve_game(
        self,
        ctx: commands.Context,
        players: list[discord.Member],
        player_infos: dict[int, PlayerInfo],
        bet: int,
        spectator_bets: Optional[dict[int, dict[int, int]]] = None,
    ) -> None:
        """Giai đoạn 4: Tính thuế, chia tiền, gửi embed tổng kết."""
        n = len(players)
        total_pot = sum(info.pot_contribution for info in player_infos.values())
        dp = int(total_pot * 0.95)  # Distributable Pot sau thuế thắng 5%
        entry_tax = n * bet - total_pot
        winner_tax = total_pot - dp

        # Xếp hạng: total DESC, click_time ASC (sớm hơn = ưu tiên khi bằng điểm)
        ranked: list[PlayerInfo] = sorted(
            player_infos.values(),
            key=lambda p: (-p.total, p.click_time or float("inf")),
        )

        # Cơ cấu giải thưởng
        if n <= 4:
            prize_ratios: list[float] = [1.0]
        elif n <= 7:
            prize_ratios = [0.7, 0.3]
        else:
            prize_ratios = [0.5, 0.3, 0.2]

        winners_data: list[tuple[PlayerInfo, int]] = []
        for i, ratio in enumerate(prize_ratios):
            if i >= len(ranked):
                break
            prize = int(dp * ratio)
            winners_data.append((ranked[i], prize))
            await _apply_delta(self.bot, str(ranked[i].user_id), prize)

        losers: list[PlayerInfo] = ranked[len(winners_data):]

        # ── Xây Embed Tổng Kết ───────────────────────────────────────────
        embed = discord.Embed(
            title="<:symbol_trophy:1537550568665649232> Xúc Xắc Quần Hùng — Bảng Vàng Phong Thần",
            color=COLOR_WIN,
        )

        # Bảng điểm toàn sân
        all_lines: list[str] = []
        medals = ["<:symbol_medal_gold:1537550996664885328>", "<:symbol_medal_silver:1537552840514347048>", "<:symbol_medal_bronze:1537552838412992712>"]
        for i, info in enumerate(ranked):
            d1e = DICE_NUMS.get(info.d1 or 1, "?")
            d2e = DICE_NUMS.get(info.d2 or 1, "?")
            auto = " *(bot lắc thay)*" if info.auto_rolled else ""
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            all_lines.append(
                f"{medal} <@{info.user_id}> — {d1e}+{d2e} = **{info.total}**{auto}"
            )
        embed.add_field(name="<:symbol_chart:1536317815336869918> Bảng Điểm Toàn Sân", value="\n".join(all_lines), inline=False)

        # Người thắng
        win_lines: list[str] = []
        for idx, (info, prize) in enumerate(winners_data):
            m_icon = medals[idx] if idx < len(medals) else f"#{idx+1}"
            win_lines.append(f"{m_icon} <@{info.user_id}> ẵm trọn **+{prize:,}**")
        embed.add_field(name="<:symbol_confetti:1537570146313306183> Bảng Vàng Phong Thần", value="\n".join(win_lines), inline=False)

        # Người thua
        if losers:
            lose_lines = [
                f"💀 <@{info.user_id}> cúng sạch **{bet:,}**" for info in losers
            ]
            embed.add_field(
                name="😭 Cột Trụ Sòng Bạc — Mút Trọn",
                value="\n".join(lose_lines),
                inline=False,
            )

        # ── Trả Thưởng Khán Giả ──────────────────────────────────────────
        rank1_id = ranked[0].user_id if ranked else None
        if spectator_bets and rank1_id is not None:
            total_spec_pool = 0
            for sb in spectator_bets.values():
                total_spec_pool += sum(sb.values())

            if total_spec_pool > 0:
                spec_dp = int(total_spec_pool * 0.95)
                spec_tax = total_spec_pool - spec_dp

                # Tổng tiền cược vào người Rank 1
                total_on_winner = 0
                for sb in spectator_bets.values():
                    total_on_winner += sb.get(rank1_id, 0)

                spec_lines: list[str] = []
                if total_on_winner > 0:
                    spec_odds = spec_dp / total_on_winner
                    for spec_uid, sb in spectator_bets.items():
                        bet_on_winner = sb.get(rank1_id, 0)
                        if bet_on_winner > 0:
                            payout = int(bet_on_winner * spec_odds)
                            await _apply_delta(self.bot, str(spec_uid), payout)
                            profit = payout - sum(sb.values())
                            sign = "+" if profit >= 0 else ""
                            spec_lines.append(
                                f"<:items_00_lottery_ticket:1537566232897650811> <@{spec_uid}> cược **{bet_on_winner:,}** → nhận **{payout:,}** ({sign}{profit:,})"
                            )
                        else:
                            lost = sum(sb.values())
                            spec_lines.append(f"💸 <@{spec_uid}> cược lệch — mất trọn **{lost:,}**")
                else:
                    for spec_uid, sb in spectator_bets.items():
                        lost = sum(sb.values())
                        spec_lines.append(f"💸 <@{spec_uid}> cược lệch — mất trọn **{lost:,}**")
                    spec_odds = 0.0

                spec_header = f"Tổng Pot Khán Đài: **{total_spec_pool:,}** — Thuế (5%): **{spec_tax:,}**"
                if total_on_winner > 0:
                    spec_header += f" — Odds: **{spec_odds:.2f}x**"

                embed.add_field(
                    name="<:items_00_lottery_ticket:1537566232897650811> Khán Đài Đỏ Đen",
                    value=spec_header + "\n" + "\n".join(spec_lines[:10]),
                    inline=False,
                )

        # Thuế nhà cái
        embed.add_field(
            name="🏦 Nhà Cái Đã Cắn",
            value=(
                f"Thuế vào sảnh (5%/người): **{entry_tax:,}**\n"
                f"Thuế thưởng (5% quỹ): **{winner_tax:,}**\n"
                f"Tổng phế: **{entry_tax + winner_tax:,}** — Sòng bài luôn thắng!"
            ),
            inline=False,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None)
        embed.set_footer(text="Angelic Casino • Xúc Xắc Quần Hùng 🌸")

        # Nhiệm vụ
        for p in players:
            await update_task_progress(self.bot, p.id, "dice", 1)
            await update_task_progress(self.bot, p.id, "gamble_any", 1)

        delay = 30.0 if ctx.channel.id == 1498711783223853101 else None

        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)

        # Mở khóa khán giả
        if spectator_bets:
            for spec_uid in spectator_bets:
                _unlock_user(self.bot, spec_uid)



# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MultiDice(bot))
