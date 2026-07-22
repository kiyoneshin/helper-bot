"""
basic_games.py — Cog Trò Chơi Cơ Bản Casino Angelic
=====================================================
Bao gồm 4 trò chơi:
  - Coinflip  : y!cf / y!coinflip <h/t> <tien_cuoc>
  - Cups      : y!cups <tien_cuoc>        (Interactive Button UI)
  - Dice 7    : y!dice <tien_cuoc>
  - Roulette  : y!shot / y!roulette <tien_cuoc> (Interactive Russian Roulette)
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

COLOR_WIN     = 0x00FF00   # 🟢 Thắng / Sống sót
COLOR_LOSE    = 0xFF0000   # 🔴 Thua / Tử trận
COLOR_JACKPOT = 0xFFD700   # 🌟 Jackpot / Side / Đứng xu

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
        amount = int(raw.replace(",", ""))
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


# =============================================================================
# COG CHINH
# =============================================================================

class BasicGames(commands.Cog):
    """Casino co ban: coinflip, cups, dice, roulette."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # 1. COINFLIP
    # =========================================================================
    @commands.hybrid_command(name="coinflip", aliases=["cf"])
    async def coinflip_cmd(self, ctx: commands.Context, choice: str, bet_raw: str):
        choice = choice.lower().strip()
        if choice not in ("h", "t"):
            await ctx.send("❌ Lựa chọn không hợp lệ! Dùng `h` (Ngửa) hoặc `t` (Sấp).\nCú pháp: `y!cf <h/t> <tiền_cược>`", ephemeral=False)
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        outcome = random.choices(["win", "lose", "side"], weights=[44.0, 55.0, 1.0], k=1)[0]

        if outcome == "win":
            payout = round(bet * 1.9)
            delta = payout - bet
            color = COLOR_WIN
            title = "🪙 Coinflip — Thắng!"
            outcome_emoji = "🟢"
            result_line = f"+{delta:,}  *(x1.9)*"
        elif outcome == "lose":
            delta = -bet
            color = COLOR_LOSE
            title = "🪙 Coinflip — Thua!"
            outcome_emoji = "🔴"
            result_line = f"-{bet:,}  *(Mất trắng)*"
        else:
            payout = round(bet * 5.0)
            delta = payout - bet
            color = COLOR_JACKPOT
            title = "🌟 Coinflip — Đứng Xu Jackpot! 🌟"
            outcome_emoji = "🌟"
            result_line = f"+{delta:,}  *(x5.0)*"

        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("⚠️ Lỗi cập nhật Database, thử lại sau!", ephemeral=True)
            return

        new_balance = balance + delta

        face_map = {"h": "NGỬA 🌕", "t": "SẤP 🌑"}
        your_pick = face_map[choice]
        if outcome == "side":
            landed = "ĐỨNG 🟡"
        elif outcome == "win":
            landed = face_map[choice]
        else:
            landed = face_map["t" if choice == "h" else "h"]

        embed = discord.Embed(title=title, color=color)
        embed.set_author(name=f"{ctx.author.display_name} — coinflip", icon_url=ctx.author.display_avatar.url)
        
        embed.add_field(name="🎯 Lựa chọn của bạn", value=your_pick, inline=True)
        embed.add_field(name="🪙 Kết quả đồng xu", value=landed, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        # 3 Hàng dọc
        embed.add_field(name="💰 Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)
        
        embed.set_footer(text="Angelic Casino • Coinflip 🌸")
        await ctx.send(embed=embed)

    @coinflip_cmd.error
    async def coinflip_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Thiếu tham số! Cú pháp: `y!cf <h/t> <tiền_cược>`", ephemeral=True)

    # =========================================================================
    # 2. CUPS
    # =========================================================================
    @commands.hybrid_command(name="cups")
    async def cups_cmd(self, ctx: commands.Context, bet_raw: str):
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        embed = discord.Embed(
            description="Cục màu trắng ở đâu? ◽ **1, 2** hay **3** ?\n\n🥤  🥤  🥤\n",
            color=0xffb6c1,
        )
        embed.set_author(name=f"{ctx.author.display_name} — cups", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Chọn trong 30 giây • Hết giờ sẽ hoàn tiền cược")

        view = CupsView(bot=self.bot, author=ctx.author, bet=bet, balance=balance)
        view.message = await ctx.send(embed=embed, view=view)

    @cups_cmd.error
    async def cups_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Thiếu tham số! Cú pháp: `y!cups <tiền_cược>`", ephemeral=True)

    # =========================================================================
    # 3. DICE 7
    # =========================================================================
    @commands.hybrid_command(name="dice")
    async def dice_cmd(self, ctx: commands.Context, bet_raw: str):
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        face = random.choices(
            [1, 2, 3, 4, 5, 6, 7],
            weights=[16.58, 16.58, 16.58, 16.58, 16.58, 16.58, 0.52],
            k=1
        )[0]

        PAYOUT = {
            1: (-1.00, "1️⃣", COLOR_LOSE,    "Mất 100% tiền cược"),
            2: (-0.50, "2️⃣", COLOR_LOSE,    "Mất 50% tiền cược"),
            3: (-0.25, "3️⃣", COLOR_LOSE,    "Mất 25% tiền cược"),
            4: ( 0.25, "4️⃣", COLOR_WIN,     "Ăn +25% tiền cược"),
            5: ( 0.50, "5️⃣", COLOR_WIN,     "Ăn +50% tiền cược"),
            6: ( 1.00, "6️⃣", COLOR_WIN,     "Ăn +100% tiền cược"),
            7: ( 7.00, "🌟", COLOR_JACKPOT, "JACKPOT +700% tiền cược!"),
        }

        mult, face_emoji, color, desc = PAYOUT[face]
        delta = round(mult * bet)

        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send("⚠️ Lỗi cập nhật Database, thử lại sau!", ephemeral=True)
            return

        new_balance = balance + delta

        if delta >= 0:
            result_line = f"+{delta:,}  *(x{1 + mult:.2f})*"
            outcome_emoji = "🌟" if face == 7 else "🟢"
        else:
            result_line = f"{delta:,}  *(-{abs(mult) * 100:.0f}%)*"
            outcome_emoji = "🔴"

        embed = discord.Embed(title="🎲 Dice", color=color)
        embed.set_author(name=f"{ctx.author.display_name} — dice", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="🎲 Kết quả lắc", value=f"{face_emoji} - {desc}", inline=False)
        
        # 3 Hàng dọc
        embed.add_field(name="💰 Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)

        embed.set_footer(text="Angelic Casino • Dice 7 🌸")
        await ctx.send(embed=embed)

    @dice_cmd.error
    async def dice_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Thiếu! Cú pháp: `y!dice <tiền_cược>`", ephemeral=True)

    # =========================================================================
    # 4. ROULETTE (RUSSIAN ROULETTE INTERACTIVE)
    # =========================================================================
    @commands.hybrid_command(name="roulette", aliases=["shot"])
    async def roulette_cmd(self, ctx: commands.Context, bet_raw: str):
        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(err, ephemeral=True)
            return

        # TRỪ TIỀN CƯỢC NGAY LẬP TỨC ĐỂ GIỮ CHỖ
        ok = await _apply_delta(self.bot, uid, -bet)
        if not ok:
            await ctx.send("⚠️ Lỗi cập nhật Database, không thể tạm giữ tiền cược!", ephemeral=True)
            return
            
        new_balance = balance - bet

        embed = discord.Embed(
            title="🔫 Cò Quay Tử Thần",
            description=(
                "Ổ đạn 6 buồng, chỉ có 1 viên đạn thật. Ổ đạn **không** xoay lại sau mỗi lần bóp cò.\n\n"
                "Sống sót càng lâu, tiền thưởng càng lớn. Dám chơi lớn không? 💥\n\n"
                "**Hệ số thưởng:**\n"
                "Lần 1: x1.01\n"
                "Lần 2: x1.1\n"
                "Lần 3: x1.5\n"
                "Lần 4: x2.5\n"
                "Lần 5: x4"
            ),
            color=0x2b2d31,
        )
        embed.set_author(name=f"{ctx.author.display_name} — roulette", icon_url=ctx.author.display_avatar.url)
        
        embed.add_field(name="💰 Tiền cược (đang giữ)", value=f"{bet:,}", inline=False)
        embed.add_field(name="💳 Số dư hiện tại", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Quá 60 giây không phản hồi sẽ tự động rút lui.")

        view = RouletteView(bot=self.bot, author=ctx.author, bet=bet, original_balance=balance)
        view.message = await ctx.send(embed=embed, view=view)

    @roulette_cmd.error
    async def roulette_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Thiếu tham số! Cú pháp: `y!shot <tiền_cược>`", ephemeral=True)


# =============================================================================
# VIEWS
# =============================================================================

class CupsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, bet: int, balance: int):
        super().__init__(timeout=30.0)
        self.bot = bot
        self.author = author
        self.bet = bet
        self.balance = balance
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Bạn không phải người chơi game này!", ephemeral=True)
            return False
        return True

    async def _resolve(self, interaction: discord.Interaction, chosen: int):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()

        correct = random.randint(1, 3)
        cups_display = ["🥤", "🥤", "🥤"]
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
            title = "🥤 Cups — Đoán Đúng! 🎉"
            outcome_emoji = "🟢"
        else:
            delta = -self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"-{self.bet:,}  *(Mất trắng)*"
            color = COLOR_LOSE
            title = "🥤 Cups — Đoán Sai! 😢"
            outcome_emoji = "🔴"

        embed = discord.Embed(
            title=title,
            description=f"Bạn chọn ly **{chosen}**. Cục màu trắng ở ly **{correct}**!\n\n{cups_line}\n",
            color=color,
        )
        embed.set_author(name=f"{self.author.display_name} — cups", icon_url=self.author.display_avatar.url)
        
        embed.add_field(name="💰 Tiền cược", value=f"{self.bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)
        
        embed.set_footer(text="Angelic Casino • Cups 🌸")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🥤 1", style=discord.ButtonStyle.secondary)
    async def cup_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 1)

    @discord.ui.button(label="🥤 2", style=discord.ButtonStyle.secondary)
    async def cup_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 2)

    @discord.ui.button(label="🥤 3", style=discord.ButtonStyle.secondary)
    async def cup_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, 3)

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
                    title="🥤 Cups — Hết Giờ!",
                    description=f"Bạn đã không chọn trong 30 giây.\nTiền cược **{self.bet:,}** được **hoàn lại**.\n\n🥤  🥤  🥤",
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
        
        self.multipliers = {
            0: 1.0,
            1: 1.01,
            2: 1.1,
            3: 1.5,
            4: 2.5,
            5: 4.0
        }

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Bạn không phải người chơi game này!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔫 Bóp cò", style=discord.ButtonStyle.danger)
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
            
            embed = discord.Embed(
                title="🔫 Cò Quay Tử Thần — Dính Đạn! 💀",
                description="***PANG!*** 💥\n\nBạn đã **gục ngã** trong vũng máu!\nToàn bộ tiền cược bị tịch thu, và bạn bị phạt thêm **50** điểm sự kiện vì quá liều lĩnh. 💀",
                color=COLOR_LOSE,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            
            embed.add_field(name="💰 Tiền cược", value=f"{self.bet:,}", inline=False)
            embed.add_field(name="🔴 Kết quả", value=f"-{self.bet:,}  *(Mất trắng) & Phạt 50*", inline=False)
            embed.add_field(name="💳 Số dư mới", value=f"{self.balance:,}", inline=False)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        else:
            self.survived_rounds += 1
            
            if self.survived_rounds == 5:
                await self.process_cashout(interaction, auto_cashout=True)
                return
            
            # Kích hoạt nút Rút lui khi đã bóp cò ít nhất 1 lần thành công
            for child in self.children:
                if isinstance(child, discord.ui.Button) and getattr(child, "custom_id", "") == "cashout_btn":
                    child.disabled = False
            
            current_mult = self.multipliers[self.survived_rounds]
            next_mult = self.multipliers[self.survived_rounds + 1]
            current_win = round(self.bet * current_mult)
            
            embed = discord.Embed(
                title=f"🔫 Cò Quay Tử Thần — Sống Sót Lần {self.survived_rounds}!",
                description=(
                    "*lách cách...* Phew! 😮‍💨\n\n"
                    f"Bạn đã sống sót qua viên thứ **{self.survived_rounds}**!\n\n"
                    f"👉 **Giải thưởng hiện tại:** {current_win:,}  *(x{current_mult:.2f})*\n"
                    f"👉 **Nếu bóp cò tiếp (x{next_mult:.2f}):** {round(self.bet * next_mult):,}\n\n"
                    "Bạn muốn **Rút lui** để ôm tiền về, hay tiếp tục **Bóp cò**?"
                ),
                color=COLOR_WIN,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 Rút lui", style=discord.ButtonStyle.success, disabled=True, custom_id="cashout_btn")
    async def cashout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_cashout(interaction, auto_cashout=False)

    async def process_cashout(self, interaction: Optional[discord.Interaction], auto_cashout: bool = False, is_timeout: bool = False):
        uid = str(self.author.id)
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
        
        mult = self.multipliers[self.survived_rounds]
        payout = round(self.bet * mult)
        
        await _apply_delta(self.bot, uid, payout)
        new_balance = self.balance + payout
        
        profit = payout - self.bet
        
        if self.survived_rounds == 0:
            title = "🔫 Cò Quay Tử Thần — Hoàn Tiền"
            desc = "Trò chơi kết thúc do hết giờ. Tiền cược đã được hoàn trả."
            color = 0x95a5a6
            res_str = f"+0  *(Hoàn tiền)*"
            emo = "🟢"
        else:
            title = "🔫 Cò Quay Tử Thần — Rút Lui Thành Công!"
            desc = f"Tuyệt vời! Bạn đã mang về **{payout:,}** sau khi sống sót qua **{self.survived_rounds}** viên đạn."
            if auto_cashout and self.survived_rounds == 5:
                desc = f"HUYỀN THOẠI! Lũy kế 5 viên đạn lép! Tự động rút lui với x4!\n\nBạn đã mang về **{payout:,}**."
            elif is_timeout:
                desc = f"Trò chơi hết giờ! Tự động rút lui an toàn.\n\nBạn đã mang về **{payout:,}**."
            
            color = COLOR_WIN
            res_str = f"+{profit:,}  *(x{mult:.2f})*"
            emo = "🟢"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
        
        embed.add_field(name="💰 Tiền cược", value=f"{self.bet:,}", inline=False)
        embed.add_field(name=f"{emo} Kết quả", value=res_str, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        await self.process_cashout(interaction=None, auto_cashout=False, is_timeout=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BasicGames(bot))