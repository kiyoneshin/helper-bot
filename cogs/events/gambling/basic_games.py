"""
basic_games.py -- Cog Tro Choi Co Ban Casino Angelic
Gom 4 tro choi:
  - Coinflip  : y!cf / y!coinflip <h/t> <tien_cuoc>
  - Cups      : y!cups <tien_cuoc>        (Interactive Button UI)
  - Dice 7    : y!dice <tien_cuoc>
  - Roulette  : y!shot / y!roulette <tien_cuoc>
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

log = logging.getLogger("BasicGames")

# Mau sac Embed
COLOR_WIN     = 0x00FF00   # Thang / Song sot
COLOR_LOSE    = 0xFF0000   # Thua / Tu tran
COLOR_JACKPOT = 0xFFD700   # Jackpot / Side


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    """Lay so du diem hien tai cua user tu event_profiles."""
    row = await get_or_create_event_profile(bot, user_id)
    if row is None:
        return 0
    return int(row["points"] or 0)


async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    """
    Cong (delta > 0) hoac Tru (delta < 0) diem mot cach an toan.
    Tra ve True neu thanh cong, False neu khong du diem de tru.
    """
    if delta > 0:
        return await add_event_points(bot, user_id, delta, is_earned=False)
    elif delta < 0:
        return await deduct_event_points(bot, user_id, abs(delta))
    return True  # delta == 0


def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str]]:
    """
    Parse chuoi tien cuoc.
    Tra ve (amount, None) neu hop le, hoac (None, error_msg) neu khong hop le.
    """
    try:
        amount = int(raw)
    except ValueError:
        return None, f"\u274c `{raw}` khong phai so nguyen hop le!"
    if amount <= 0:
        return None, "\u274c Tien cuoc phai lon hon **0**!"
    if amount > balance:
        return None, (
            f"\u274c Ban khong du diem! "
            f"So du hien tai: **{balance:,}** diem, "
            f"ban muon cuoc: **{amount:,}** diem."
        )
    return amount, None


# =============================================================================
# COG CHINH
# =============================================================================

class BasicGames(commands.Cog):
    """Casino co ban: coinflip, cups, dice, roulette."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ──────────────────────────────────────────────────────────────────────────
    # 1. COINFLIP
    # ──────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="coinflip",
        aliases=["cf"],
        description="Tung dong xu -- y!cf <h/t> <tien_cuoc>",
    )
    async def coinflip_cmd(
        self,
        ctx: commands.Context,
        choice: str,
        bet_raw: str,
    ) -> None:
        """
        Tung dong xu voi Weighted RNG.
        Chon h (Heads/Ngua) hoac t (Tails/Sap).

        Xac suat: Thang 44% -- Thua 55% -- Dung Xu 1%
        Thuong  : Thang x1.9 -- Dung xu x5.0
        """
        choice = choice.lower().strip()
        if choice not in ("h", "t"):
            await ctx.send(
                "\u274c Lua chon khong hop le! Dung `h` (Ngua) hoac `t` (Sap).\n"
                "Cu phap: `y!cf <h/t> <tien_cuoc>`",
                ephemeral=True,
            )
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # -- Weighted RNG --------------------------------------------------
        outcome: str = random.choices(
            population=["win", "lose", "side"],
            weights=[44.0, 55.0, 1.0],
            k=1,
        )[0]

        # -- Tinh toan delta diem -----------------------------------------
        if outcome == "win":
            payout   = round(bet * 1.9)
            delta    = payout - bet
            color    = COLOR_WIN
            title    = "\U0001fa99 Coinflip -- Thang!"
            outcome_emoji = "\U0001f7e2"
            result_line   = f"+{delta:,} diem  *(x1.9 tong)*"
        elif outcome == "lose":
            delta    = -bet
            color    = COLOR_LOSE
            title    = "\U0001fa99 Coinflip -- Thua!"
            outcome_emoji = "\U0001f534"
            result_line   = f"-{bet:,} diem"
        else:  # side jackpot
            payout   = round(bet * 5.0)
            delta    = payout - bet
            color    = COLOR_JACKPOT
            title    = "\U0001f31f Coinflip -- Dung Xu Jackpot! \U0001f31f"
            outcome_emoji = "\U0001f31f"
            result_line   = f"+{delta:,} diem  *(x5.0 tong)*"

        # -- Cap nhat DB --------------------------------------------------
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("\u26a0\ufe0f Loi cap nhat Database, thu lai sau!", ephemeral=True)
            return

        new_balance = balance + delta

        # -- Hien thi mat dong xu ----------------------------------------
        face_map  = {"h": "NGUA \U0001f315", "t": "SAP \U0001f311"}
        your_pick = face_map[choice]
        if outcome == "side":
            landed = "DUNG \U0001f7e1"
        elif outcome == "win":
            landed = face_map[choice]
        else:
            landed = face_map["t" if choice == "h" else "h"]

        # -- Embed --------------------------------------------------------
        embed = discord.Embed(title=title, color=color)
        embed.set_author(
            name=f"{ctx.author.display_name} \u2014 coinflip",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.add_field(name="\U0001f3af Lua chon cua ban", value=your_pick,             inline=True)
        embed.add_field(name="\U0001fa99 Ket qua dong xu",  value=landed,                inline=True)
        embed.add_field(name="\u200b",                      value="\u200b",              inline=True)
        embed.add_field(name="\U0001f4b0 Tien cuoc",        value=f"{bet:,} diem",       inline=True)
        embed.add_field(name=f"{outcome_emoji} Ket qua",    value=result_line,           inline=True)
        embed.add_field(name="\U0001f4b3 So du moi",        value=f"{new_balance:,} diem", inline=True)
        embed.set_footer(text="Angelic Casino \u2022 Coinflip \U0001f338")
        await ctx.send(embed=embed)

    @coinflip_cmd.error
    async def coinflip_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("\u274c Thieu tham so! Cu phap: `y!cf <h/t> <tien_cuoc>`", ephemeral=True)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. CUPS (Interactive Button UI)
    # ──────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="cups",
        description="Doan ly chua bao vat -- y!cups <tien_cuoc>",
    )
    async def cups_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Trao Ly -- Chon dung ly chua ngoc de thang.

        Xac suat: 33.33% thang / 66.67% thua
        Thuong  : Thang x2.3
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        embed = discord.Embed(
            description=(
                "Cuc mau trang o dau? \u25fd **1, 2** hay **3** ?\n\n"
                "\U0001f964  \U0001f964  \U0001f964\n"
            ),
            color=0xffb6c1,
        )
        embed.set_author(
            name=f"{ctx.author.display_name} \u2014 cups",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.set_footer(text="Chon trong 30 giay \u2022 Het gio se hoan tien cuoc")

        view = CupsView(
            bot=self.bot,
            author=ctx.author,
            bet=bet,
            balance=balance,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @cups_cmd.error
    async def cups_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("\u274c Thieu tham so! Cu phap: `y!cups <tien_cuoc>`", ephemeral=True)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. DICE 7 MAT
    # ──────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="dice",
        description="Lac xuc xac 7 mat -- y!dice <tien_cuoc>",
    )
    async def dice_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Xuc Xac 7 Mat dac biet.

        Mat 1: -100%  | Mat 2: -50%  | Mat 3: -25%
        Mat 4: +25%   | Mat 5: +50%  | Mat 6: +100%
        Mat 7: +700% (Jackpot, ty le 5.56%)
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # -- Weighted RNG --------------------------------------------------
        face: int = random.choices(
            population=[1, 2, 3, 4, 5, 6, 7],
            weights=[15.74, 15.74, 15.74, 15.74, 15.74, 15.74, 5.56],
            k=1,
        )[0]

        # -- Payout table -------------------------------------------------
        PAYOUT: dict[int, tuple[float, str, int, str]] = {
            1: (-1.00, "1\ufe0f\u20e3", COLOR_LOSE,    "Mat 1 \u2014 Mat 100%"),
            2: (-0.50, "2\ufe0f\u20e3", COLOR_LOSE,    "Mat 2 \u2014 Mat 50%"),
            3: (-0.25, "3\ufe0f\u20e3", COLOR_LOSE,    "Mat 3 \u2014 Mat 25%"),
            4: ( 0.25, "4\ufe0f\u20e3", COLOR_WIN,     "Mat 4 \u2014 An +25%"),
            5: ( 0.50, "5\ufe0f\u20e3", COLOR_WIN,     "Mat 5 \u2014 An +50%"),
            6: ( 1.00, "6\ufe0f\u20e3", COLOR_WIN,     "Mat 6 \u2014 An +100%"),
            7: ( 7.00, "7\ufe0f\u20e3", COLOR_JACKPOT, "\U0001f31f Mat 7 \u2014 JACKPOT +700%!"),
        }

        mult, face_emoji, color, label = PAYOUT[face]
        delta = round(mult * bet)

        # -- Cap nhat DB --------------------------------------------------
        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("\u26a0\ufe0f Loi cap nhat Database, thu lai sau!", ephemeral=True)
            return

        new_balance = balance + delta

        if delta >= 0:
            result_line   = f"+{delta:,} diem  *(x{1 + mult:.2f} tong)*"
            outcome_emoji = "\U0001f31f" if face == 7 else "\U0001f7e2"
        else:
            result_line   = f"{delta:,} diem  *(mat {abs(mult) * 100:.0f}%)*"
            outcome_emoji = "\U0001f534"

        embed = discord.Embed(title=f"\U0001f3b2 Dice 7 \u2014 {label}", color=color)
        embed.set_author(
            name=f"{ctx.author.display_name} \u2014 dice",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.add_field(name="\U0001f3b2 Ket qua lac",     value=f"{face_emoji}  **{label}**", inline=False)
        embed.add_field(name="\U0001f4b0 Tien cuoc",       value=f"{bet:,} diem",              inline=True)
        embed.add_field(name=f"{outcome_emoji} Ket qua",   value=result_line,                  inline=True)
        embed.add_field(name="\U0001f4b3 So du moi",       value=f"{new_balance:,} diem",      inline=True)
        embed.set_footer(text="Angelic Casino \u2022 Dice 7 \U0001f338")
        await ctx.send(embed=embed)

    @dice_cmd.error
    async def dice_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("\u274c Thieu tham so! Cu phap: `y!dice <tien_cuoc>`", ephemeral=True)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. ROULETTE (CO QUAY TU THAN)
    # ──────────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="roulette",
        aliases=["shot"],
        description="Co quay tu than -- y!shot <tien_cuoc>",
    )
    async def roulette_cmd(self, ctx: commands.Context, bet_raw: str) -> None:
        """
        Co Quay Tu Than -- O dan 6 vien, 1 vien that.

        Song sot (83.33%): +12% tien cuoc
        Dinh dan (16.67%): Mat 100% tien cuoc + tru them 50 diem su kien
        """
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # -- Weighted RNG --------------------------------------------------
        outcome: str = random.choices(
            population=["survive", "die"],
            weights=[83.33, 16.67],
            k=1,
        )[0]

        # -- Xu ly ket qua ------------------------------------------------
        if outcome == "survive":
            delta = round(bet * 0.12)
            ok = await _apply_delta(self.bot, uid, delta)
            if not ok:
                await ctx.send("\u26a0\ufe0f Loi cap nhat Database, thu lai sau!", ephemeral=True)
                return

            new_balance = balance + delta
            embed = discord.Embed(
                title="\U0001f52b Co Quay Tu Than \u2014 Song Sot!",
                description=(
                    "*lach cach...* Phew! \U0001f62e\u200d\U0001f4a8\n\n"
                    "Ban da **vuot qua** vong co quay tu than va nhan duoc thuong!\n"
                    "Tay ban dang run... nhung tui tien thi day hon roi! \U0001f4aa"
                ),
                color=COLOR_WIN,
            )
            embed.set_author(
                name=f"{ctx.author.display_name} \u2014 roulette",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.add_field(name="\U0001f4b0 Tien cuoc",   value=f"{bet:,} diem",         inline=True)
            embed.add_field(name="\U0001f7e2 Tien thuong", value=f"+{delta:,} diem  *(+12%)*", inline=True)
            embed.add_field(name="\U0001f4b3 So du moi",   value=f"{new_balance:,} diem", inline=True)

        else:  # die
            # Buoc 1: Tru tien cuoc
            ok_bet = await _apply_delta(self.bot, uid, -bet)

            # Buoc 2: Tru them 50 diem su kien (phat bo sung)
            # deduct_event_points dam bao khong am so du
            PENALTY_PTS = 50
            await deduct_event_points(self.bot, uid, PENALTY_PTS)

            if not ok_bet:
                await ctx.send("\u26a0\ufe0f Loi cap nhat Database, thu lai sau!", ephemeral=True)
                return

            new_balance = max(0, balance - bet)
            embed = discord.Embed(
                title="\U0001f52b Co Quay Tu Than \u2014 Dinh Dan! \U0001f480",
                description=(
                    "***PANG!*** \U0001f4a5\n\n"
                    "Ban da **guc nga** trong vung mau!\n"
                    "Toan bo tien cuoc bi tich thu, va ban con bi phat them "
                    f"**{PENALTY_PTS} diem su kien** vi da lieu linh qua muc. \U0001f480"
                ),
                color=COLOR_LOSE,
            )
            embed.set_author(
                name=f"{ctx.author.display_name} \u2014 roulette",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.add_field(name="\U0001f4b0 Tien cuoc",    value=f"{bet:,} diem",              inline=True)
            embed.add_field(name="\U0001f534 Ket qua",      value=f"-{bet:,} diem  *(-100%)*",  inline=True)
            embed.add_field(name="\U0001f480 Phat bo sung", value=f"-{PENALTY_PTS} diem event", inline=True)
            embed.add_field(name="\U0001f4b3 So du moi",    value=f"{new_balance:,} diem",      inline=False)

        embed.set_footer(text="Angelic Casino \u2022 Co Quay Tu Than \U0001f338")
        await ctx.send(embed=embed)

    @roulette_cmd.error
    async def roulette_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("\u274c Thieu tham so! Cu phap: `y!shot <tien_cuoc>`", ephemeral=True)


# =============================================================================
# CUPS VIEW -- INTERACTIVE UI
# =============================================================================

class CupsView(discord.ui.View):
    """
    View 3 nut bam cho tro choi Trao Ly.
    Timeout 30 giay -> hoan tien tu dong.
    """

    def __init__(
        self,
        bot: commands.Bot,
        author: discord.Member | discord.User,
        bet: int,
        balance: int,
    ) -> None:
        super().__init__(timeout=30.0)
        self.bot     = bot
        self.author  = author
        self.bet     = bet
        self.balance = balance
        self.message: Optional[discord.Message] = None

    # -- Bao mat: chi nguoi goi lenh moi duoc bam --------------------------
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "\u274c Ban khong phai nguoi choi game nay!", ephemeral=True
            )
            return False
        return True

    # -- Xu ly khi nguoi choi chon 1 trong 3 ly ----------------------------
    async def _resolve(self, interaction: discord.Interaction, chosen: int) -> None:
        """Tinh ket qua, cap nhat DB va chinh sua Embed."""
        # Disable tat ca nut ngay lap tuc
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()

        # RNG: chon ly dung (1-3)
        correct = random.randint(1, 3)

        # Dung dong hien thi 3 ly
        cups_display = ["\U0001f964", "\U0001f964", "\U0001f964"]
        cups_display[correct - 1] = "\u25fd"  # danh dau ly dung
        cups_line = "  ".join(cups_display)

        uid = str(self.author.id)

        if chosen == correct:
            payout = round(self.bet * 2.3)
            delta  = payout - self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"+{delta:,} diem  *(x2.3 tong)*"
            color = COLOR_WIN
            title = "\U0001f964 Cups \u2014 Doan Dung! \U0001f389"
            outcome_emoji = "\U0001f7e2"
        else:
            delta = -self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"-{self.bet:,} diem"
            color = COLOR_LOSE
            title = "\U0001f964 Cups \u2014 Doan Sai! \U0001f622"
            outcome_emoji = "\U0001f534"

        embed = discord.Embed(
            title=title,
            description=(
                f"Ban da chon ly **{chosen}**. "
                f"Cuc mau trang o ly **{correct}**!\n\n"
                f"{cups_line}\n"
            ),
            color=color,
        )
        embed.set_author(
            name=f"{self.author.display_name} \u2014 cups",
            icon_url=self.author.display_avatar.url,
        )
        embed.add_field(name="\U0001f3af Ly ban chon",      value=f"Ly **{chosen}**",           inline=True)
        embed.add_field(name="\u25fd Ly dung",              value=f"Ly **{correct}**",           inline=True)
        embed.add_field(name="\u200b",                      value="\u200b",                      inline=True)
        embed.add_field(name="\U0001f4b0 Tien cuoc",        value=f"{self.bet:,} diem",          inline=True)
        embed.add_field(name=f"{outcome_emoji} Ket qua",    value=result_line,                   inline=True)
        embed.add_field(name="\U0001f4b3 So du moi",        value=f"{new_balance:,} diem",       inline=True)
        embed.set_footer(text="Angelic Casino \u2022 Cups \U0001f338")

        await interaction.response.edit_message(embed=embed, view=self)

    # -- 3 nut bam ----------------------------------------------------------

    @discord.ui.button(label="\U0001f964 1", style=discord.ButtonStyle.secondary)
    async def cup_1(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._resolve(interaction, 1)

    @discord.ui.button(label="\U0001f964 2", style=discord.ButtonStyle.secondary)
    async def cup_2(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._resolve(interaction, 2)

    @discord.ui.button(label="\U0001f964 3", style=discord.ButtonStyle.secondary)
    async def cup_3(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._resolve(interaction, 3)

    # -- Timeout: hoan tien & disable nut ----------------------------------
    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message:
            try:
                embed = discord.Embed(
                    title="\U0001f964 Cups \u2014 Het Gio!",
                    description=(
                        "Ban da khong chon trong thoi gian 30 giay.\n"
                        f"Tien cuoc **{self.bet:,} diem** duoc **hoan lai** cho ban.\n\n"
                        "\U0001f964  \U0001f964  \U0001f964"
                    ),
                    color=0x95a5a6,
                )
                embed.set_author(
                    name=f"{self.author.display_name} \u2014 cups",
                    icon_url=self.author.display_avatar.url,
                )
                embed.set_footer(text="Angelic Casino \u2022 Cups \U0001f338")
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BasicGames(bot))
