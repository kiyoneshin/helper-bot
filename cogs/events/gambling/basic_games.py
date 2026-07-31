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

COLOR_WIN     = 0x00FF00   # 🟢 Thắng / Sống sót
COLOR_LOSE    = 0xFF0000   # 🔴 Thua / Tử trận
COLOR_JACKPOT = 0xFFD700   # 🌟 Jackpot / Side / Đứng xu

# =============================================================================
# HỆ THỐNG KHÓA HÀNH ĐỘNG (COMMAND LOCK)
# =============================================================================
async def _check_busy(bot: commands.Bot, ctx: commands.Context) -> bool:
    """Kiểm tra xem người chơi có đang vướng một game tương tác nào không."""
    active_players = getattr(bot, 'active_players', set())
    if ctx.author.id in active_players:
        await ctx.send(
            f"❌ {ctx.author.mention} Đang ngồi sòng khác rồi cha nội! Chốt kèo bên kia xong đi rồi qua đây đú tiếp."
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

# =============================================================================
# COG CHÍNH
# =============================================================================

class BasicGames(commands.Cog):
    """Casino co ban: coinflip, cups, dice, roulette."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Khởi tạo biến lưu danh sách người chơi trên Bot nếu chưa có
        if not hasattr(self.bot, 'active_players'):
            setattr(self.bot, 'active_players', set())

    # =========================================================================
    # 1. COINFLIP (Game tức thời - Không cần khóa, nhưng bị chặn nếu đang khóa)
    # =========================================================================
    @commands.hybrid_command(name="coinflip", aliases=["cf"])
    async def coinflip_cmd(self, ctx: commands.Context, choice: str, bet_raw: str):
        if await _check_busy(self.bot, ctx): return
        
        choice = choice.lower().strip()
        if choice not in ("h", "t"):
            await ctx.send(f"❌ {ctx.author.mention} Bấm bậy bạ gì vậy? Dùng `h` (Ngửa) hoặc `t` (Sấp).\nCú pháp: `y!cf <h/t> <tiền_cược>`")
            return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        outcome = random.choices(["win", "lose", "side"], weights=[44.0, 55.0, 1.0], k=1)[0]
        # ... logic tính delta & color ...
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
            await ctx.send(f"❌ {ctx.author.mention} Sập nguồn cơ sở dữ liệu, thử lại sau!")
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
        embed.add_field(name="💰 Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Coinflip 🌸")
        delay = 10.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)

    @coinflip_cmd.error
    async def coinflip_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ {ctx.author.mention} Chơi mà không ném tiền à? Cú pháp: `y!cf <h/t> <tiền_cược>`")

    # =========================================================================
    # 2. CUPS (Game tương tác - Cần khóa hành động)
    # =========================================================================
    @commands.hybrid_command(name="cups")
    async def cups_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        end_time = int(time.time()) + 30
        embed = discord.Embed(
            description=f"Cục màu trắng ở đâu? ◽ **1, 2** hay **3** ?\nNhanh tay lẹ mắt nhào vô trước <t:{end_time}:R>!\n\n🥤  🥤  🥤\n",
            color=0xffb6c1,
        )
        embed.set_author(name=f"{ctx.author.display_name} — cups", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Ngâm quá sòng trả lại tiền")

        # Khóa người chơi
        _lock_user(self.bot, ctx.author.id)

        view = CupsView(bot=self.bot, author=ctx.author, bet=bet, balance=balance)
        try:
            view.message = await ctx.send(embed=embed, view=view)
        except Exception:
            # Mở khóa nếu lỗi không gửi được tin nhắn
            _unlock_user(self.bot, ctx.author.id)

    @cups_cmd.error
    async def cups_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ {ctx.author.mention} Dốc hết hầu bao đi! Cú pháp: `y!cups <tiền_cược>`")

    # =========================================================================
    # 3. DICE 7 (Game tức thời)
    # =========================================================================
    @commands.hybrid_command(name="dice")
    async def dice_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        face = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[16.75, 16.75, 16.75, 16.5, 16.5, 16.5, 0.25], k=1)[0]
        # ... logic tính điểm ...
        PAYOUT = {
            1: (-1.00, "1️⃣", COLOR_LOSE,    "Mút trọn (Mất 100%)"),
            2: (-0.50, "2️⃣", COLOR_LOSE,    "Cắt nửa vầng trăng (Mất 50%)"),
            3: (-0.25, "3️⃣", COLOR_LOSE,    "Rớt miếng thịt (Mất 25%)"),
            4: ( 0.25, "4️⃣", COLOR_WIN,     "Húp tí xíu (+25%)"),
            5: ( 0.50, "5️⃣", COLOR_WIN,     "Húp vừa vừa (+50%)"),
            6: ( 1.00, "6️⃣", COLOR_WIN,     "Lụm chẵn (+100%)"),
            7: ( 7.00, "🌟", COLOR_JACKPOT, "JACKPOT NỔ HŨ (+700%)!"),
        }
        mult, face_emoji, color, desc = PAYOUT[face]
        delta = round(mult * bet)

        ok = await _apply_delta(self.bot, uid, delta)
        if not ok:
            await ctx.send(f"❌ {ctx.author.mention} Nhà cái đang kẹt mạng, thử lại sau!")
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
        embed.add_field(name="💰 Tiền cược", value=f"{bet:,}", inline=False)
        embed.add_field(name=f"{outcome_emoji} Kết quả", value=result_line, inline=False)
        embed.add_field(name="💳 Số dư mới", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Angelic Casino • Dice 7 🌸")
        delay = 10.0 if ctx.channel.id == 1498711783223853101 else None
        if delay is not None:
            await ctx.send(embed=embed, delete_after=delay)
        else:
            await ctx.send(embed=embed)

    @dice_cmd.error
    async def dice_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ {ctx.author.mention} Ném tiền vô mâm đi chứ! Cú pháp: `y!dice <tiền_cược>`")

    # =========================================================================
    # 4. ROULETTE (Game tương tác - Cần khóa hành động)
    # =========================================================================
    @commands.hybrid_command(name="roulette", aliases=["shot"])
    async def roulette_cmd(self, ctx: commands.Context, bet_raw: str):
        if await _check_busy(self.bot, ctx): return

        uid = str(ctx.author.id)
        balance = await _get_balance(self.bot, uid)
        bet, err = _parse_bet(bet_raw, balance)
        if err or bet is None:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return

        ok = await _apply_delta(self.bot, uid, -bet)
        if not ok:
            await ctx.send(f"❌ {ctx.author.mention} Lỗi DB, không tạm giữ tiền cược được!")
            return
            
        new_balance = balance - bet

        end_time = int(time.time()) + 60
        embed = discord.Embed(
            title="🔫 Cò Quay Tử Thần",
            description=(
                "Ổ đạn 6 buồng, chỉ có 1 viên đạn thật. Bóp cò là không có đường lui.\n\n"
                "Sống sót càng lâu, húp càng đẫm. Dám chơi lớn không? 💥\n\n"
                "**Hệ số thưởng:**\n"
                "Lần 1: x1.1\nLần 2: x1.3\nLần 3: x1.8\nLần 4: x2.7\nLần 5: x5\n\n"
                f"⏳ **Hành động trước:** <t:{end_time}:R>"
            ),
            color=0x2b2d31,
        )
        embed.set_author(name=f"{ctx.author.display_name} — roulette", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="💰 Tiền cược (đang giữ)", value=f"{bet:,}", inline=False)
        embed.add_field(name="💳 Số dư hiện tại", value=f"{new_balance:,}", inline=False)
        embed.set_footer(text="Ngâm quá sòng tự động chốt lãi.")

        # Khóa người chơi
        _lock_user(self.bot, ctx.author.id)

        view = RouletteView(bot=self.bot, author=ctx.author, bet=bet, original_balance=balance)
        try:
            view.message = await ctx.send(embed=embed, view=view)
        except Exception:
            _unlock_user(self.bot, ctx.author.id)

    @roulette_cmd.error
    async def roulette_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ {ctx.author.mention} Không cọc tiền ai cho chơi! Cú pháp: `y!shot <tiền_cược>`")


# =============================================================================
# VIEWS (MỞ KHÓA KHI KẾT THÚC)
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
            await interaction.response.send_message("❌ Mày đứng xem thôi, không phải sòng của mày!", ephemeral=True)
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
            title = "🥤 Cups — Lụm Lúa! 🎉"
            outcome_emoji = "🟢"
        else:
            delta = -self.bet
            await _apply_delta(self.bot, uid, delta)
            new_balance = self.balance + delta
            result_line = f"-{self.bet:,}  *(Mút trọn)*"
            color = COLOR_LOSE
            title = "🥤 Cups — Bị Lùa! 😢"
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
        if interaction.message and interaction.message.channel.id == 1498711783223853101:
            if interaction.message:
                await interaction.message.delete(delay=10.0)

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
        # Mở khóa người chơi khi hết giờ
        _unlock_user(self.bot, self.author.id)

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
                    title="🥤 Cups — Nhát Gan Bỏ Chạy!",
                    description=f"Ngâm quá 30 giây không dám bốc.\nTiền cược **{self.bet:,}** được **trả lại** nguyên vẹn.\n\n🥤  🥤  🥤",
                    color=0x95a5a6,
                )
                embed.set_author(name=f"{self.author.display_name} — cups", icon_url=self.author.display_avatar.url)
                embed.set_footer(text="Angelic Casino • Cups 🌸")
                await self.message.edit(embed=embed, view=self)
                if self.message.channel.id == 1498711783223853101:
                    if self.message:
                        await self.message.delete(delay=10.0)
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
            await interaction.response.send_message("❌ Nín thở ngồi xem thôi, không phải sòng của mày!", ephemeral=True)
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
            
            # Chết -> Mở khóa người chơi
            _unlock_user(self.bot, self.author.id)
            
            embed = discord.Embed(
                title="🔫 Cò Quay Tử Thần — Đăng Xuất! 💀",
                description="***PANG!*** 💥\n\nNằm mẹ nó rồi!\nSòng bạc tịch thu cược và cắn thêm **50** điểm vì làm bẩn sàn. 💀",
                color=COLOR_LOSE,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            embed.add_field(name="💰 Tiền cược", value=f"{self.bet:,}", inline=False)
            embed.add_field(name="🔴 Kết quả", value=f"-{self.bet:,}  *(Mút trọn) & Bị phạt 50*", inline=False)
            embed.add_field(name="💳 Số dư mới", value=f"{self.balance:,}", inline=False)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            await interaction.response.edit_message(embed=embed, view=self)
            if interaction.message and interaction.message.channel.id == 1498711783223853101:
                if interaction.message:
                    await interaction.message.delete(delay=10.0)
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
                title=f"🔫 Cò Quay Tử Thần — Sống Sót Lần {self.survived_rounds}!",
                description=(
                    "*lách cách...* Phew! 😮‍💨\n\n"
                    f"Bạn đã sống sót qua viên thứ **{self.survived_rounds}**!\n\n"
                    f"👉 **Húp ngay:** {current_win:,}  *(x{current_mult:.2f})*\n"
                    f"👉 **Đánh đổi mạng sống (x{next_mult:.2f}):** {round(self.bet * next_mult):,}\n\n"
                    f"⏳ **Hành động trước:** <t:{new_end_time}:R>\n"
                    "Muốn **Chốt lãi** ôm tiền về, hay tiếp tục **Bóp cò**?"
                ),
                color=COLOR_WIN,
            )
            embed.set_author(name=f"{self.author.display_name} — roulette", icon_url=self.author.display_avatar.url)
            embed.set_footer(text="Angelic Casino • Cò Quay Tử Thần 🌸")
            
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 Chốt lãi", style=discord.ButtonStyle.success, disabled=True, custom_id="cashout_btn")
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
            title = "🔫 Cò Quay Tử Thần — Hoàn Tiền"
            desc = "Trò chơi kết thúc do hết giờ. Tiền cược đã được hoàn trả."
            color = 0x95a5a6
            res_str = f"+0  *(Hoàn tiền)*"
            emo = "🟢"
        else:
            title = "🔫 Cò Quay Tử Thần — Húp An Toàn!"
            desc = f"Biết điều đấy! Ôm nhẹ **{payout:,}** về sau khi né được **{self.survived_rounds}** phát đạn."
            if auto_cashout and self.survived_rounds == 5:
                desc = f"BÀN TAY VÀNG TRONG LÀNG BÓP CÒ! Sống sót qua 5 viên lép!\nNổ hũ ẵm trọn **{payout:,}**."
            elif is_timeout:
                desc = f"Run tay ngâm lâu quá! Tự động chốt lãi an toàn.\n\nHúp **{payout:,}**."
            
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
            if interaction.message and interaction.message.channel.id == 1498711783223853101:
                if interaction.message:
                    await interaction.message.delete(delay=10.0)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self)
                if self.message.channel.id == 1498711783223853101:
                    if self.message:
                        await self.message.delete(delay=10.0)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        # Mở khóa người chơi khi hết giờ được gọi qua process_cashout
        await self.process_cashout(interaction=None, auto_cashout=False, is_timeout=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BasicGames(bot))