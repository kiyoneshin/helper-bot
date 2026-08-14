"""
basic_games.py — Cog Trò Chơi Cơ Bản Casino Angelic
=====================================================
Bao gồm 4 trò chơi:
  - Coinflip  : kcf / kcoinflip <h/t> <tien_cuoc>
  - Cups      : kcups <tien_cuoc>        (Interactive Button UI)
  - Dice 7    : kdice <tien_cuoc>
  - Roulette  : kshot / kroulette <tien_cuoc> (Interactive Russian Roulette)
  """

import random
import logging
import time
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    get_or_create_event_profile,
    add_event_points,
    deduct_event_points,
)

log = logging.getLogger("BasicGames")

COLOR_WIN     = 0x00FF00   # Thắng / Sống sót
COLOR_LOSE    = 0xFF0000   # Thua / Tử trận
COLOR_JACKPOT = 0xFFD700   # Jackpot / Side / Đứng xu

# =============================================================================
# HỆ THỐNG KHÓA HÀNH ĐỘNG (COMMAND LOCK)
# =============================================================================
async def _check_busy(bot: commands.Bot, ctx: commands.Context) -> bool:
    """Kiểm tra xem người chơi có đang vướng một game tương tác nào không."""
    active_players = getattr(bot, 'active_players', set())
    if ctx.author.id in active_players:
        await ctx.send(
            f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Đang ngồi sòng khác rồi cha nội! Chốt kèo bên kia xong đi rồi qua đây đú tiếp."
        )
        return True
    return False

def _lock_user(bot: commands.Bot, user_id: int):
    """Khóa người chơi (Đưa vào danh sách đang chơi)"""
    active_players: set = getattr(bot, 'active_players', set())
    active_players.add(user_id)
    setattr(bot, 'active_players', active_players)

def _unlock_user(bot: commands.Bot, user_id: int):
    """Mở khóa người chơi"""
    active_players: set = getattr(bot, 'active_players', set())
    active_players.discard(user_id)
    setattr(bot, 'active_players', active_players)

# =============================================================================
# DB HELPERS
# =============================================================================
async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    """Lấy số dư hiện tại."""
    row = await get_or_create_event_profile(bot, user_id)
    if row is None:
        return 0
    return int(row["points"] or 0)

async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    """Cộng/Trừ điểm an toàn."""
    if delta > 0:
        return await add_event_points(bot, user_id, delta, is_earned=False)
    elif delta < 0:
        return await deduct_event_points(bot, user_id, abs(delta))
    return True

def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str], bool]:
    """
    Parse chuỗi tiền cược. Hỗ trợ hậu tố k (nghìn) và m (triệu).
    Hỗ trợ từ khóa 'all' để cược toàn bộ số dư.
    Trả về (amount, None, is_all) nếu hợp lệ, hoặc (None, error_msg, False) nếu không.
    is_all=True khi dùng từ khóa 'all' — cần hiện cửa sổ xác nhận.
    """
    cleaned = raw.lower().replace(",", "").strip()

    # ── Từ khóa 'all' ──────────────────────────────────────────────
    if cleaned in ("all", "max", "het", "hết"):
        if balance <= 0:
            return None, "Í quá, ví trống rỗng! Đi cày kiếm điểm rồi quay lại nhé.", False
        return balance, None, True  # is_all=True → cần confirm

    # ── Số thường ────────────────────────────────────────────────
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


# =============================================================================
# BET CONFIRM VIEW — Hiện khi user cược 'all'
# =============================================================================

class BetConfirmView(discord.ui.View):
    """
    Embed xác nhận trước khi cược toàn bộ số dư.
    callback_fn: coroutine(ctx, bet) — được gọi khi người chơi xác nhận.
    """
    def __init__(self, ctx: commands.Context, bet: int, callback_fn):
        super().__init__(timeout=60.0)
        self.ctx = ctx
        self.bet = bet
        self.callback_fn = callback_fn
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Chưa đến lượt bạn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Xác nhận cược all", style=discord.ButtonStyle.danger, emoji="<:symbol_right:1536629912515903578>")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        for item in self.children:
            item.disabled = True  # type: ignore
        await interaction.response.edit_message(view=self)
        # Khởi chạy game
        await self.callback_fn(self.ctx, self.bet)

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary, emoji="<:symbol_wrong:1536629915598848072>")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="<:symbol_wrong:1536629915598848072> Đã hủy cược. Tiền vẫn ở trong ví, chưa bị mất!",
            embed=None, view=None
        )

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="<a:symbol_clock:1537570144375541870> Hết giờ xác nhận. Tiền vẫn an toàn trong ví!",
                    embed=None, view=None
                )
            except discord.HTTPException:
                pass


async def _send_confirm(ctx: commands.Context, bet: int, callback_fn) -> None:
    """Gửi embed xác nhận cược all và đợi người dùng phản hồi."""
    embed = discord.Embed(
        title="<:symbol_alert:1537546957885542450> Xác nhận cược toàn bộ",
        description=(
            f"{ctx.author.mention} Đầy cả ví ra cược hết!\n\n"
            f"<:symbol_money_bag:1537567538097954896> **Số tiền sẽ cược:** **{bet:,.0f}** điểm\n\n"
            "<:symbol_right:1536629912515903578> Nhấn **Xác nhận** để vào sòng, hoặc <:symbol_wrong:1536629915598848072> **Hủy** để rút lui."
        ),
        color=0xFF8C00,
    )
    embed.set_footer(text="🕒 Hết 20 giây tự động hủy")
    view = BetConfirmView(ctx, bet, callback_fn)
    view.message = await ctx.send(embed=embed, view=view)


# =============================================================================
# COG CHÍNH
# =============================================================================

class BasicGames(commands.Cog):
    """Casino co ban: coinflip, cups, dice, roulette."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if not hasattr(self.bot, 'active_players'):
            setattr(self.bot, 'active_players', set())

    # =========================================================================
    # 1. COINFLIP (Game tức thời)
    # =========================================================================
    @commands.hybrid_command(name="coinflip", aliases=["cf"])
    async def coinflip_cmd(self, ctx: commands.Context, choice: str, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        choice = choice.lower().strip()
        if choice not in ("h", "t"):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Bấm bậy bạ gì vậy? Dùng `h` (Ngửa) hoặc `t` (Sấp).\nCú pháp: `{ctx.prefix}cf <h/t> <tiền_cược | all>`")
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} {err}")
            return

        # Cược 'all' → hiện confirm trước
        async def _run(ctx: commands.Context, bet: int):
            await self._exec_coinflip(ctx, choice, bet, uid, balance)

        if is_all:
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_coinflip(ctx, choice, bet, uid, balance)

    @coinflip_cmd.error
    async def coinflip_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Chơi mà không ném tiền à? Cú pháp: `{ctx.prefix}cf <h/t> <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp cf`")


    async def _exec_coinflip(self, ctx: commands.Context, choice: str, bet: int, uid: str, balance: int):
        """Logic thực thi game coinflip sau khi đã xác nhận."""
        outcome = random.choices(["win", "lose", "side"], weights=[44.0, 55.0, 1.0], k=1)[0]
        if outcome == "win":
            payout = round(bet * 1.9)
            delta = payout - bet
            color = COLOR_WIN
            title = "Coinflip — Thắng!"
            outcome_emoji = "<:symbol_right:1536629912515903578>"
            result_line = f"+{delta:,}  *(x1.9)*"
        elif outcome == "lose":
            delta = -bet
            color = COLOR_LOSE
            title = "Coinflip — Thua!"
            outcome_emoji = "<:symbol_wrong:1536629915598848072>"
            result_line = f"-{bet:,}  *(Mất trắng)*"
        else:
            payout = round(bet * 5.0)
            delta = payout - bet
            color = COLOR_JACKPOT
            title = "<:symbol_confetti:1537570146313306183> Coinflip — Đứng Xu Jackpot! <:symbol_confetti:1537570146313306183>"
            outcome_emoji = "<:gambling_sidecoin:1536290493800120380>"
            result_line = f"+{delta:,}  *(x5.0)*"

        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Sập nguồn cơ sở dữ liệu, thử lại sau!")
            return

        new_balance = balance + delta
        face_map = {"h": "<:gambling_headscoin:1536019591191330837> NGỬA", "t": "<:gambling_tailscoin:1536019595838758922> SẤP"}
        your_pick = face_map[choice]
        if outcome == "side":
            landed = "ĐỨNG"
        elif outcome == "win":
            landed = face_map[choice]
        else:
            landed = face_map["t" if choice == "h" else "h"]

        embed = discord.Embed(title=title, color=color)
        embed.set_author(name=f"{ctx.author.display_name} — coinflip", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Lựa chọn của bạn", value=your_pick, inline=True)
        embed.add_field(name="Kết quả đồng xu", value=landed, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Coinflip 🌸")
        delay = 30.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)


    # =========================================================================
    # 2. CUPS (Game tương tác - Cần khóa hành động)
    # =========================================================================
    @commands.hybrid_command(name="cups")
    async def cups_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} {err}")
            return

        async def _run(ctx: commands.Context, bet: int):
            await self._exec_cups(ctx, bet, uid, balance)

        if is_all:
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_cups(ctx, bet, uid, balance)

    @cups_cmd.error
    async def cups_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Dốc hết hầu bao đi! Cú pháp: `{ctx.prefix}cups <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp cups`")


    async def _exec_cups(self, ctx: commands.Context, bet: int, uid: str, balance: int):
        """Logic thực thi game cups."""
        end_time = int(time.time()) + 30
        embed = discord.Embed(
            description=f"Cục màu trắng ở đâu? ◽ **1, 2** hay **3** ?\nNhanh tay lẹ mắt nhào vô trước <t:{end_time}:R>!\n\n<:gambling_cup:1536019568697409667>  <:gambling_cup:1536019568697409667>  <:gambling_cup:1536019568697409667>\n",
            color=0xffb6c1,
        )
        embed.set_author(name=f"{ctx.author.display_name} — cups", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Ngâm quá sòng trả lại tiền")
        _lock_user(self.bot, ctx.author.id)
        view = CupsView(bot=self.bot, author=ctx.author, bet=bet, balance=balance)
        try:
            view.message = await ctx.send(embed=embed, view=view)
        except Exception:
            _unlock_user(self.bot, ctx.author.id)



    # =========================================================================
    # 3. DICE 7 (Game tức thời)
    # =========================================================================
    @commands.hybrid_command(name="dice")
    async def dice_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} {err}")
            return

        async def _run(ctx: commands.Context, bet: int):
            await self._exec_dice(ctx, bet, uid, balance)

        if is_all:
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_dice(ctx, bet, uid, balance)

    @dice_cmd.error
    async def dice_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lắc xúc xắc bằng niềm tin à? Cú pháp: `{ctx.prefix}dice <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp dice`")


    async def _exec_dice(self, ctx: commands.Context, bet: int, uid: str, balance: int):
        """Logic thực thi game dice."""
        face = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[16.75, 16.75, 16.75, 16.5, 16.5, 16.5, 0.25], k=1)[0]
        # ... logic tính điểm ...
        PAYOUT = {
            1: (-1.00, "<:gambling_dice_1:1536019570849091706>", COLOR_LOSE,    "Mút trọn (Mất 100%)"),
            2: (-0.50, "<:gambling_dice_2:1536019573252554894>", COLOR_LOSE,    "Cắt nửa vầng trăng (Mất 50%)"),
            3: (-0.25, "<:gambling_dice_3:1536019575768875200>", COLOR_LOSE,    "Rớt miếng thịt (Mất 25%)"),
            4: ( 0.25, "<:gambling_dice_4:1536019579304808619>", COLOR_WIN,     "Húp tí xíu (+25%)"),
            5: ( 0.50, "<:gambling_dice_5:1536019581301424158>", COLOR_WIN,     "Húp vừa vừa (+50%)"),
            6: ( 1.00, "<:gambling_dice_6:1536019583264362566>", COLOR_WIN,     "Lụm chẵn (+100%)"),
            7: ( 7.00, "<:gambling_dice_7:1536019585365446716>", COLOR_JACKPOT, "JACKPOT NỔ HŨ (+700%)!"),
        }
        mult, face_emoji, color, desc = PAYOUT[face]
        delta = round(mult * bet)

        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Nhà cái đang kẹt mạng, thử lại sau!")
            return

        new_balance = balance + delta

        if delta >= 0:
            result_line = f"+{delta:,}  *(x{1 + mult:.2f})*"
            outcome_emoji = "<:gambling_dice_7:1536019585365446716>" if face == 7 else "<:symbol_right:1536629912515903578>"
        else:
            result_line = f"{delta:,}  *(-{abs(mult) * 100:.0f}%)*"
            outcome_emoji = "<:symbol_wrong:1536629915598848072>"

        embed = discord.Embed(title="<:gambling_dice:1537539887769591828> Dice", color=color)
        embed.set_author(name=f"{ctx.author.display_name} — dice", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="<:gambling_dice:1537539887769591828> Kết quả lắc", value=f"{face_emoji} - {desc}", inline=False)
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Dice 7 🌸")
        delay = 30.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)


    # =========================================================================
    # 4. ROULETTE (Game tương tác - Cần khóa hành động)
    # =========================================================================
    @commands.hybrid_command(name="roulette", aliases=["shot"])
    async def roulette_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err, is_all = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} {err}")
            return

        async def _run(ctx: commands.Context, bet: int):
            await self._exec_roulette(ctx, bet, uid, balance)

        if is_all:
            await _send_confirm(ctx, bet, _run)
        else:
            await self._exec_roulette(ctx, bet, uid, balance)

    @roulette_cmd.error
    async def roulette_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Cầm súng mà không mang đạn (tiền) à? Cú pháp: `{ctx.prefix}shot <tiền_cược | all>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}ehelp shot`")


    async def _exec_roulette(self, ctx: commands.Context, bet: int, uid: str, balance: int):
        """Logic thực thi game roulette."""
        ok = await _apply_delta(self.bot, uid, -bet)
        if not ok:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Lỗi DB, không tạm giữ tiền cược được!")
            return

        new_balance = balance - bet
        end_time = int(time.time()) + 60
        embed = discord.Embed(
            title="<a:gambling_00_russian_roulette:1536019552889077860> Cò Quay Tử Thần",
            description=(
                "Ổ đạn 6 buồng, chỉ có 1 viên đạn thật. Bóp cò là không có đường lui.\n\n"
                "Sống sót càng lâu, húp càng đẫm. Dám chơi lớn không?\n\n"
                "**Hệ số thưởng:**\n"
                "Lần 1: x1.1\nLần 2: x1.3\nLần 3: x1.8\nLần 4: x2.7\nLần 5: x5\n\n"
                f"<:symbol_hour_glass:1537570149215899658> **Hành động trước:** <t:{end_time}:R>"
            ),
            color=0x2b2d31,
        )
        embed.set_author(name=f"{ctx.author.display_name} — roulette", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược (đang giữ)", value=f"{bet:,}", inline=False)
        embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư hiện tại", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Ngâm quá sòng tự động chốt lãi.")
        _lock_user(self.bot, ctx.author.id)
        view = RouletteView(bot=self.bot, author=ctx.author, bet=bet, original_balance=balance)
        try:
            view.message = await ctx.send(embed=embed, view=view)
        except Exception:
            _unlock_user(self.bot, ctx.author.id)




# =============================================================================
# VIEWS (MỞ KHÓA KHI KẾT THÚC)
# =============================================================================

class CupsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, bet: int, balance: int):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.author = author
        self.bet = bet
        self.balance = balance
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("<:symbol_ban:1537546960003801319> Mày đứng xem thôi, không phải sòng của màk", ephemeral=True)
            return False
        return True

    async def _resolve(self, interaction: discord.Interaction, chosen: int):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
        
        # Mở khóa người chơi
        _unlock_user(self.bot, self.author.id)

        correct = random.randint(1, 3)
        cups_display = ["<:gambling_cup:1536019568697409667>", "<:gambling_cup:1536019568697409667>", "<:gambling_cup:1536019568697409667>"]
        cups_display[correct - 1] = "◽"
        cups_line = "  ".join(cups_display)

        uid = str(self.author.id)

        if chosen == correct:
            payout = round(self.bet * 2.3)
            delta = payout - self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"+{delta:,}  *(x2.3)*"
            color = COLOR_WIN
            title = "<:gambling_cup:1536019568697409667> Cups — Lụm Lúa! <:symbol_confetti:1537570146313306183>"
            outcome_emoji = "<:symbol_right:1536629912515903578>"
        else:
            delta = -self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"-{self.bet:,}  *(Mút trọn)*"
            color = COLOR_LOSE
            title = "<:gambling_cup:1536019568697409667> Cups — Bị Lùa!"
            outcome_emoji = "<:symbol_wrong:1536629915598848072>"

        embed = discord.Embed(
            title=title,
            description=f"Bạn chọn ly **{chosen}**. Cục màu trắng ở ly **{correct}**!\n\n{cups_line}\n",
            color=color,
        )
        embed.set_author(name=f"{self.author.display_name} — cups", icon_url=self.author.display_avatar.url)
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược", value=f"{self.bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Cups 🌸")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="1", emoji="<:gambling_cup:1536019568697409667>", style=discord.ButtonStyle.secondary)
    async def cup_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 1)

    @discord.ui.button(label="2", emoji="<:gambling_cup:1536019568697409667>", style=discord.ButtonStyle.secondary)
    async def cup_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 2)

    @discord.ui.button(label="3", emoji="<:gambling_cup:1536019568697409667>", style=discord.ButtonStyle.secondary)
    async def cup_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 3)

    async def on_timeout(self):
        # Mở khóa người chơi khi hết giờ
        _unlock_user(self.bot, self.author.id)

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
            title="<:gambling_cup:1536019568697409667> Cups — Nhát Gan Bỏ Chạk",
            description=f"Ngâm quá 30 giây không dám bốc.\nTiền cược **{self.bet:,}** được **trả lại** nguyên vẹn.\n\n<:gambling_cup:1536019568697409667>  <:gambling_cup:1536019568697409667>  <:gambling_cup:1536019568697409667>",
            color=0x95a5a6,
        )
                embed.set_author(name=f"{self.author.display_name} — cups", icon_url=self.author.display_avatar.url)
                embed.set_footer(text="Angelic Casino • Cups 🌸")
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


class RouletteView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, bet: int, original_balance: int):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.author = author
        self.bet = bet
        self.balance = original_balance - bet
        self.message: Optional[discord.Message] = None
        self.survived_rounds = 0
        self.chamber = [True] + [False] * 5
        random.shuffle(self.chamber)
        self.multipliers = {0: 1.0, 1: 1.1, 2: 1.3, 3: 1.8, 4: 2.7, 5: 5.0}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("<:symbol_ban:1537546960003801319> Nín thở ngồi xem thôi, không phải sòng của màk", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Bóp cò", emoji="<a:gambling_00_russian_roulette:1536019552889077860>", style=discord.ButtonStyle.danger)
    async def pull_trigger(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(self.author.id)
        bullet = self.chamber.pop()
        
        if bullet:
            PENALTY_PTS = 50
            await deduct_event_points(self.bot, uid, PENALTY_PTS)
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            self.stop()
            
            # Chết -> Mở khóa người chơi
            _unlock_user(self.bot, self.author.id)
            
            embed = discord.Embed(
                title="<a:gambling_00_russian_roulette:1536019552889077860> Cò Quay Tử Thần — Đăng Xuất!",
                description="***PANG!*** \n\nNằm mẹ nó rồi!\nSòng bạc tịch thu cược và cắn thêm **50** điểm vì làm bẩn sàn. 💀",
                color=COLOR_LOSE,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược", value=f"{self.bet:,}", inline=False)
            embed.add_field(name="<:symbol_wrong:1536629915598848072> Kết quả", value=f"-{self.bet:,}  *(Mút trọn) & Bị phạt 50*", inline=False)
            embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư mới", value=f"{self.balance:,}", inline=False)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            self.survived_rounds += 1
            if self.survived_rounds == 5:
                await self.process_cashout(interaction, auto_cashout=True)
                return
            
            for child in self.children:
                if isinstance(child, discord.ui.Button) and getattr(child, "custom_id", "") == "cashout_btn":
                    child.disabled = False
            
            current_mult = self.multipliers[self.survived_rounds]
            next_mult = self.multipliers[self.survived_rounds + 1]
            current_win = round(self.bet * current_mult)
            
            new_end_time = int(time.time()) + 60
            embed = discord.Embed(
                title=f"<a:gambling_00_russian_roulette:1536019552889077860> Cò Quay Tử Thần — Sống Sót Lần {self.survived_rounds}!",
                description=(
                    "*lách cách...* Phew!\n\n"
                    f"Bạn đã sống sót qua viên thứ **{self.survived_rounds}**!\n\n"
                    f"**Húp ngay:** {current_win:,}  *(x{current_mult:.2f})*\n"
                    f"**Đánh đổi mạng sống (x{next_mult:.2f}):** {round(self.bet * next_mult):,}\n\n"
                    f"<:symbol_hour_glass:1537570149215899658> **Hành động trước:** <t:{new_end_time}:R>\n"
                    "Muốn **Chốt lãi** ôm tiền về, hay tiếp tục **Bóp cò**?"
                ),
                color=COLOR_WIN,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Chốt lãi", emoji="<:symbol_money_bag:1537567538097954896>", style=discord.ButtonStyle.success, disabled=True, custom_id="cashout_btn")
    async def cashout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_cashout(interaction, auto_cashout=False)

    async def process_cashout(self, interaction: Optional[discord.Interaction], auto_cashout: bool = False, is_timeout: bool = False):
        uid = str(self.author.id)
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
        
        # Rút lui / Auto Cashout -> Mở khóa người chơi
        _unlock_user(self.bot, self.author.id)
        
        mult = self.multipliers[self.survived_rounds]
        payout = round(self.bet * mult)
        
        await _apply_delta(self.bot, uid, payout)
        new_balance = self.balance + payout
        profit = payout - self.bet
        
        if self.survived_rounds == 0:
            title = "<a:gambling_00_russian_roulette:1536019552889077860> Cò Quay Tử Thần — Hoàn Tiền"
            desc = "Trò chơi kết thúc do hết giờ. Tiền cược đã được hoàn trả."
            color = 0x95a5a6
            res_str = f"+0  *(Hoàn tiền)*"
            emo = "<:symbol_right:1536629912515903578>"
        else:
            title = "<a:gambling_00_russian_roulette:1536019552889077860> Cò Quay Tử Thần — Húp An Toàn!"
            desc = f"Biết điều đấk Ôm nhẹ **{payout:,}** về sau khi né được **{self.survived_rounds}** phát đạn."
            if auto_cashout and self.survived_rounds == 5:
                desc = f"BÀN TAY VÀNG TRONG LÀNG BÓP CÒ! Sống sót qua 5 viên lép!\nNổ hũ ẵm trọn **{payout:,}**."
            elif is_timeout:
                desc = f"Run tay ngâm lâu quá! Tự động chốt lãi an toàn.\n\nHúp **{payout:,}**."
            
            color = COLOR_WIN
            res_str = f"+{profit:,}  *(x{mult:.2f})*"
            emo = "<:symbol_right:1536629912515903578>"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Tiền cược", value=f"{self.bet:,}", inline=False)
        embed.add_field(name=f"{emo} Kết quả", value=res_str, inline=False)
        embed.add_field(name="<:symbol_credit_card:1536308433693712404> Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        # Mở khóa người chơi khi hết giờ được gọi qua process_cashout
        await self.process_cashout(interaction=None, auto_cashout=False, is_timeout=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BasicGames(bot))