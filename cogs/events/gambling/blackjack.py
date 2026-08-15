import random
import logging
import asyncio
import json
import os
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import get_or_create_event_profile, add_event_points, deduct_event_points

log = logging.getLogger("Blackjack")

COLOR_WIN  = 0x00FF00
COLOR_LOSE = 0xFF0000
COLOR_TIE  = 0xFFFF00

CARD_EMOJIS = {
    "symbol_wrong": "1536629915598848072",
    "gambling_cards_clubs_01": "1537799002425262180",
    "gambling_cards_clubs_02": "1537799004254117989",
    "gambling_cards_clubs_03": "1537799007613485096",
    "gambling_cards_clubs_04": "1537799010528796772",
    "gambling_cards_clubs_05": "1537799013267411075",
    "gambling_cards_clubs_06": "1537799015947833385",
    "gambling_cards_clubs_07": "1537799017797394484",
    "gambling_cards_clubs_08": "1537799019659788399",
    "gambling_cards_clubs_09": "1537799021865869414",
    "gambling_cards_clubs_10": "1537799024227254313",
    "gambling_cards_clubs_11": "1537799026026483756",
    "gambling_cards_clubs_12": "1537799028228755527",
    "gambling_cards_clubs_13": "1537799030325907606",
    "gambling_cards_diamonds_01": "1537799032196300800",
    "gambling_cards_diamonds_02": "1537799034276814989",
    "gambling_cards_diamonds_03": "1537799035937882193",
    "gambling_cards_diamonds_04": "1537799037963739256",
    "gambling_cards_diamonds_05": "1537799049577758843",
    "gambling_cards_diamonds_06": "1537799052362518630",
    "gambling_cards_diamonds_07": "1537799054312869940",
    "gambling_cards_diamonds_08": "1537799056166883430",
    "gambling_cards_diamonds_09": "1537799058163367936",
    "gambling_cards_diamonds_10": "1537799060189225050",
    "gambling_cards_diamonds_11": "1537799062290567291",
    "gambling_cards_diamonds_12": "1537799064270274641",
    "gambling_cards_diamonds_13": "1537799066396786688",
    "gambling_cards_hearts_01": "1537799068418310217",
    "gambling_cards_hearts_02": "1537799070939353138",
    "gambling_cards_hearts_03": "1537799073401278527",
    "gambling_cards_hearts_04": "1537799075154501663",
    "gambling_cards_hearts_05": "1537799077675401286",
    "gambling_cards_hearts_06": "1537799079503859804",
    "gambling_cards_hearts_07": "1537799081231917066",
    "gambling_cards_hearts_08": "1537799083769602049",
    "gambling_cards_hearts_09": "1537799085728211006",
    "gambling_cards_hearts_10": "1537799087519432785",
    "gambling_cards_hearts_11": "1537799089616322610",
    "gambling_cards_hearts_12": "1537799091613073480",
    "gambling_cards_hearts_13": "1537799093756231851",
    "gambling_cards_spades_01": "1537799095685484606",
    "gambling_cards_spades_02": "1537799097527042229",
    "gambling_cards_spades_03": "1537799099330601032",
    "gambling_cards_spades_04": "1537799101733675139",
    "gambling_cards_spades_05": "1537799103663046686",
    "gambling_cards_spades_06": "1537799105961791488",
    "gambling_cards_spades_07": "1537799108155150396",
    "gambling_cards_spades_08": "1537799110382460989",
    "gambling_cards_spades_09": "1537799112395595826",
    "gambling_cards_spades_10": "1537799114518040586",
    "gambling_cards_spades_11": "1537799116904472686",
    "gambling_cards_spades_12": "1537799119127445606",
    "gambling_cards_spades_13": "1537799121803673736",
    "gambling_cards_x_basic_01": "1537799969300287579",
    "gambling_cards_x_basic_02": "1537799972072853554",
    "gambling_drawing_card": "1537803737421062205"
}

class Card:
    def __init__(self, suit: str, value: int):
        self.suit = suit
        self.value = value

    def point_value(self) -> int:
        if self.value > 10:
            return 10
        if self.value == 1:
            return 11
        return self.value

def calculate_score(cards: list[Card]) -> int:
    score = sum(c.point_value() for c in cards)
    aces = sum(1 for c in cards if c.value == 1)
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score

def get_card_emoji(bot: commands.Bot, card: Optional[Card], hidden: bool = False) -> str:
    if hidden or card is None:
        emoji_name = "gambling_cards_x_basic_01"
    else:
        emoji_name = f"gambling_cards_{card.suit}_{card.value:02d}"
        
    # 1. Kiểm tra trong bộ nhớ file JSON (ưu tiên cao nhất vì chính xác 100% ID)
    if emoji_name in CARD_EMOJIS:
        return f"<:{emoji_name}:{CARD_EMOJIS[emoji_name]}>"
        
    # 2. Nếu chưa có trong file, thử tìm bằng bot.emojis
    emoji = discord.utils.get(bot.emojis, name=emoji_name)
    if emoji:
        return str(emoji)
        
    # Nếu vẫn thất bại, trả về dạng text tạm để người dùng biết là thiếu
    return f"[:{emoji_name}:]"

def _lock_user(bot: commands.Bot, user_id: int):
    active_players: set = getattr(bot, 'active_players', set())
    active_players.add(user_id)
    setattr(bot, 'active_players', active_players)

def _unlock_user(bot: commands.Bot, user_id: int):
    active_players: set = getattr(bot, 'active_players', set())
    active_players.discard(user_id)
    setattr(bot, 'active_players', active_players)

async def _check_busy(bot: commands.Bot, ctx: commands.Context) -> bool:
    active_players = getattr(bot, 'active_players', set())
    if ctx.author.id in active_players:
        await ctx.send(
            f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Đang vướng sòng khác rồi cha nội! Chốt kèo bên kia xong đi rồi qua đây."
        )
        return True
    return False

def _parse_bet(raw: str, balance: int) -> tuple[Optional[int], Optional[str], bool]:
    cleaned = raw.lower().replace(",", "").strip()
    if cleaned in ("all", "max", "het", "hết"):
        if balance <= 0:
            return None, "Ví trống rỗng! Đi cày kiếm điểm rồi quay lại nhé.", False
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
        return None, f"Cược {amount:,} mà ví chỉ có {balance:,}?! Bốc phét ít thôi.", False
    return amount, None, False

async def _get_balance(bot: commands.Bot, user_id: str) -> int:
    row = await get_or_create_event_profile(bot, user_id)
    return int(row["points"] or 0) if row else 0

async def _apply_delta(bot: commands.Bot, user_id: str, delta: int) -> bool:
    if delta > 0:
        return await add_event_points(bot, user_id, delta, is_earned=False)
    elif delta < 0:
        return await deduct_event_points(bot, user_id, abs(delta))
    return True

class BlackjackView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, bet: int, deck: list[Card], p_hand: list[Card], d_hand: list[Card], balance: int):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.author = author
        self.bet = bet
        self.deck = deck
        self.p_hand = p_hand
        self.d_hand = d_hand
        self.balance = balance
        self.message: Optional[discord.Message] = None
        self.game_over = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("<:symbol_ban:1537546960003801319> Nín thở ngồi xem thôi, không phải sòng của m", ephemeral=True)
            return False
        return True

    def build_embed(self, show_dealer: bool = False, result_msg: str = "") -> discord.Embed:
        p_score = calculate_score(self.p_hand)
        p_cards = " ".join(get_card_emoji(self.bot, c) for c in self.p_hand)

        d_cards = []
        if show_dealer:
            d_score = calculate_score(self.d_hand)
            d_cards = " ".join(get_card_emoji(self.bot, c) for c in self.d_hand)
            d_score_str = f"[{d_score}]"
        else:
            d_score = calculate_score([self.d_hand[0]])
            d_cards = f"{get_card_emoji(self.bot, self.d_hand[0])} {get_card_emoji(self.bot, None, hidden=True)}"
            d_score_str = f"[{d_score} + ?]"

        color = 0x2b2d31
        if self.game_over:
            if "thắng" in result_msg.lower() or "húp" in result_msg.lower() or "win" in result_msg.lower() or "blackjack" in result_msg.lower() or "nhà cái quắc" in result_msg.lower():
                color = COLOR_WIN
            elif "thua" in result_msg.lower() or "quắc" in result_msg.lower() or "nhà cái lớn hơn" in result_msg.lower():
                color = COLOR_LOSE
            else:
                color = COLOR_TIE

        embed = discord.Embed(
            description=f"**{self.author.display_name}**, bạn đã cược **{self.bet:,}** cho ván Blackjack này!\n\n"
                        f"**Nhà cái** {d_score_str}\n{d_cards}\n\n"
                        f"**{self.author.display_name}** [{p_score}]\n{p_cards}\n\n"
                        f"{result_msg}",
            color=color
        )
        embed.set_author(name=f"{self.author.display_name} — Blackjack", icon_url=self.author.display_avatar.url)
        embed.set_footer(text="Angelic Casino • Blackjack 🌸")
        return embed

    async def finish_game(self, interaction: discord.Interaction, result_msg: str):
        self.game_over = True
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        self.stop()
        _unlock_user(self.bot, self.author.id)

        embed = self.build_embed(show_dealer=True, result_msg=result_msg)
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Tiếp", emoji="<:gambling_drawing_card:1537803737421062205>", style=discord.ButtonStyle.primary)
    async def hit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        card = self.deck.pop()
        self.p_hand.append(card)
        p_score = calculate_score(self.p_hand)

        if p_score > 21:
            await self.finish_game(interaction, f"<:symbol_wrong:1536629915598848072> **Quắc (Bust)!** Vượt quá 21 <:symbol_points_p:1538282388507987989>. Bạn mất **{self.bet:,}**!")
        else:
            embed = self.build_embed(show_dealer=False)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Dừng", emoji="<:symbol_wrong:1536629915598848072>", style=discord.ButtonStyle.danger)
    async def stay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p_score = calculate_score(self.p_hand)

        # Dealer AI Logic
        while True:
            d_score = calculate_score(self.d_hand)
            if d_score > p_score:
                # Bot wins
                break
            elif d_score == p_score:
                # Bot decides to hit or stay based on tie
                if d_score >= 17:
                    break
                # Bot might try to win if < 17
            
            # Probability calculation
            safe_cards = 0
            total_cards = len(self.deck)
            for c in self.deck:
                temp_hand = self.d_hand + [c]
                if calculate_score(temp_hand) <= 21:
                    safe_cards += 1
            
            safe_prob = safe_cards / total_cards
            if safe_prob > 0.5:
                # Draw
                self.d_hand.append(self.deck.pop())
            else:
                # Surrender / Stay
                break

        d_score = calculate_score(self.d_hand)
        
        if d_score > 21:
            await _apply_delta(self.bot, str(self.author.id), self.bet * 2)
            msg = f"<:symbol_right:1536629912515903578> **Nhà cái Quắc!** Bạn thắng **{self.bet:,}**!"
        elif d_score > p_score:
            msg = f"<:symbol_wrong:1536629915598848072> **Nhà cái lớn hơn!** Bạn mất **{self.bet:,}**!"
        elif d_score < p_score:
            await _apply_delta(self.bot, str(self.author.id), self.bet * 2)
            msg = f"<:symbol_right:1536629912515903578> **Bạn lớn hơn!** Nhà cái đầu hàng. Bạn thắng **{self.bet:,}**!"
        else:
            await _apply_delta(self.bot, str(self.author.id), self.bet)
            msg = f"**Hòa (Push)!** Bạn được hoàn lại **{self.bet:,}**."

        await self.finish_game(interaction, msg)

    async def on_timeout(self) -> None:
        _unlock_user(self.bot, self.author.id)
        if not self.game_over:
            # Player loses bet on timeout
            for child in getattr(self, "children", []):
                if hasattr(child, "disabled"):
                    child.disabled = True
            try:
                if hasattr(self, "message") and getattr(self, "message", None):
                    embed = self.build_embed(show_dealer=True, result_msg=f"<:symbol_hour_glass:1537570149215899658> **Hết thời gian!** Ngâm bài quá lâu nên bạn bị xử thua. Mất **{self.bet:,}**.")
                    await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

class BlackjackGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="blackjack", aliases=["bj"], description="Chơi Blackjack (Xì Dách) với Nhà cái thông minh")
    async def blackjack_cmd(self, ctx: commands.Context, bet_amount: Optional[str] = None):
        if bet_amount is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> **Lỗi!** Bạn chưa nhập số tiền cược.\n*Ví dụ:* `{ctx.clean_prefix}bj 10k` hoặc `{ctx.clean_prefix}bj all`")
            return

        if await _check_busy(self.bot, ctx):
            return

        balance = await _get_balance(self.bot, str(ctx.author.id))
        bet, err, is_all = _parse_bet(bet_amount, balance)
        if err or bet is None:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {err}")
            return

        _lock_user(self.bot, ctx.author.id)

        # Deduct bet upfront
        ok = await _apply_delta(self.bot, str(ctx.author.id), -bet)
        if not ok:
            _unlock_user(self.bot, ctx.author.id)
            await ctx.send("<:symbol_wrong:1536629915598848072> Lỗi trừ tiền, vui lòng thử lại!")
            return

        # Initialize Deck
        suits = ["spades", "hearts", "clubs", "diamonds"]
        deck = [Card(suit, val) for suit in suits for val in range(1, 14)]
        random.shuffle(deck)

        p_hand = [deck.pop(), deck.pop()]
        d_hand = [deck.pop(), deck.pop()]

        view = BlackjackView(self.bot, ctx.author, bet, deck, p_hand, d_hand, balance - bet)
        
        # Check instant Blackjack
        p_score = calculate_score(p_hand)
        d_score = calculate_score(d_hand)
        
        if p_score == 21:
            view.game_over = True
            _unlock_user(self.bot, ctx.author.id)
            for child in view.children:
                child.disabled = True
                
            if d_score == 21:
                # Tie
                await _apply_delta(self.bot, str(ctx.author.id), bet)
                result_msg = f"**Hòa (Push)!** Bạn được hoàn lại **{bet:,}**."
            else:
                win_amount = int(bet * 0.95)
                await _apply_delta(self.bot, str(ctx.author.id), bet + win_amount)
                result_msg = f"**Bạn thắng **{win_amount:,}**!"
                
            embed = view.build_embed(show_dealer=True, result_msg=result_msg)
            await ctx.send(embed=embed, view=view)
            return

        embed = view.build_embed(show_dealer=False)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        
async def setup(bot: commands.Bot):
    await bot.add_cog(BlackjackGame(bot))
