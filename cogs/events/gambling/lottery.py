"""
lottery.py — Cog Xổ Số Sự Kiện (Scheduled Lottery)
===================================================
Trò chơi xổ số diễn ra mỗi ngày 1 lần vào đúng 18:00 (UTC+7).
Người chơi có thể mua vé số. Giá vé cố định là 50 điểm/vé.
Giới hạn: Mỗi người tối đa 200 vé.
Tổng Hũ (Pot) = Số vé bán ra * 75 điểm.
Thuật toán: Weighted Random (Random có trọng số theo số lượng vé).
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
    fetchval_db,
    query_db,
)

log = logging.getLogger("Lottery")

UTC7 = timezone(timedelta(hours=7))

# Cấu hình Xổ Số
LOTTERY_TIME_HOUR = 18
LOTTERY_TIME_MINUTE = 0
TICKET_PRICE = 50
POT_MULTIPLIER = 75
MAX_TICKETS_PER_USER = 200

LOTTERY_CHANNEL_ID = 1529937900031054028

COLOR_GOLD = 0xFFD700


# =====================================================================
# HELPER RIÊNG — Gọi được từ shop_cog.py mà không lặp code
# =====================================================================
async def buy_lottery_tickets(
    bot: commands.Bot,
    uid: str,
    amount: int,
    is_locked: bool,
) -> tuple[bool, str]:
    """
    Thực hiện mua vé xổ số. Tách khỏi Cog để dùng lại ở shop_cog.py.
    Returns: (success: bool, message: str)
    """
    if is_locked:
        return False, "🔒 Sòng đang đóng cửa quay số, chen ngang làm gì!"

    if amount <= 0:
        return False, "<:symbol_wrong:1536629915598848072> Mua 0 vé thì trúng gió à? Nhập số đàng hoàng vô!"

    current_tickets = await fetchval_db(bot, "SELECT tickets FROM lottery_tickets WHERE discord_id = $1", uid)
    current_tickets = int(current_tickets) if current_tickets else 0

    if current_tickets + amount > MAX_TICKETS_PER_USER:
        return False, (
            f"<:symbol_wrong:1536629915598848072> Tham lam vừa thôi! Đang có **{current_tickets}** vé rồi, mua thêm **{amount}** là lố luật "
            f"{MAX_TICKETS_PER_USER} vé của sòng!"
        )

    cost = amount * TICKET_PRICE
    ok = await deduct_event_points(bot, uid, cost)
    if not ok:
        return False, f"<:symbol_wrong:1536629915598848072> Ví rỗng tuẼh mà đòi đú **{amount}** vé? Kiếm thêm **{cost:,}** điểm rồi quay lại!"

    await execute_db(
        bot,
        """
        INSERT INTO lottery_tickets (discord_id, tickets) VALUES ($1, $2)
        ON CONFLICT (discord_id) DO UPDATE SET tickets = lottery_tickets.tickets + EXCLUDED.tickets
        """,
        uid, amount
    )

    return True, (
        f"<:symbol_right:1536629912515903578> Chốt kèo! Đã múc **{amount:,}** vé (bay mất **{cost:,}** điểm).\n"
        f"Trong tay đang có **{current_tickets + amount:,}** vé, chuẩn bị đổi đời thôi!"
    )


async def _init_lottery_tables(bot: commands.Bot) -> None:
    """Khởi tạo bảng Xổ Số nếu chưa có."""
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS lottery_tickets (
            discord_id TEXT PRIMARY KEY,
            tickets INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS lottery_history (
            id SERIAL PRIMARY KEY,
            winner_id TEXT,
            prize BIGINT,
            draw_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    log.info("Bảng lottery_tickets và lottery_history đã sẵn sàng.")


class Lottery(commands.Cog):
    """Cog Xổ Số Sự Kiện — Quay thưởng lúc 18:00 hàng ngày."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.is_locked: bool = False
        self._drawn_today: bool = False
        self._scheduler.start()

    async def cog_unload(self) -> None:
        self._scheduler.cancel()

    # ─────────────────────────────────────────────────────────────────────────
    # TASK QUAY THƯỞNG (MỖI PHÚT CHECK 1 LẦN)
    # ─────────────────────────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def _scheduler(self) -> None:
        now = datetime.now(UTC7)
        hour = now.hour
        minute = now.minute

        # Reset flag khi qua ngày mới (sau 18:00) - ví dụ lúc 00:00
        if hour == 0 and minute == 0:
            self._drawn_today = False

        if hour == LOTTERY_TIME_HOUR and minute == LOTTERY_TIME_MINUTE:
            if not self._drawn_today:
                self._drawn_today = True
                await self._do_draw()

    @_scheduler.before_loop
    async def _before_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await _init_lottery_tables(self.bot)
        log.info("Lottery scheduler đã khởi động!")

    async def _do_draw(self) -> None:
        """Thực hiện quay thưởng Xổ Số."""
        self.is_locked = True
        log.info("Bắt đầu quay thưởng Xổ Số...")

        channel = self.bot.get_channel(LOTTERY_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            log.error(f"Không tìm thấy kênh xổ số ID {LOTTERY_CHANNEL_ID}")
            channel = None

        # 1. Lấy toàn bộ vé
        rows = await query_db(self.bot, "SELECT discord_id, tickets FROM lottery_tickets WHERE tickets > 0")
        
        if not rows:
            if channel:
                await channel.send("🎟️ **KỲ QUAY XỔ SỐ HÔM NAY:** Ế chỏng vó, không ai mua vé nên khỏi quay! 😢")
            self.is_locked = False
            return

        total_tickets = sum(int(row["tickets"]) for row in rows)
        total_prize = total_tickets * POT_MULTIPLIER

        if channel:
            await channel.send(
                f"<a:gambling_slot_machine_pixel:1536322200838340628> **XỔ SỐ BẮT ĐẦU QUAY!** <a:gambling_slot_machine_pixel:1536322200838340628>\n"
                f"Tổng số vé đã bán: **{total_tickets:,}** vé\n"
                f"Tổng Hũ (Pot): **{total_prize:,}** điểm\n"
                f"Ai sẽ là người ẵm trọn số tiền này? 🤞 Đang quay..."
            )
            await asyncio.sleep(3)

        # 2. Weighted Random
        population = [str(row["discord_id"]) for row in rows]
        weights = [int(row["tickets"]) for row in rows]
        
        winner_id = random.choices(population, weights=weights, k=1)[0]
        
        # 3. Trả thưởng
        await add_event_points(self.bot, winner_id, total_prize, is_earned=True)
        
        # 4. Lưu lịch sử
        await execute_db(
            self.bot,
            "INSERT INTO lottery_history (winner_id, prize, draw_time) VALUES ($1, $2, CURRENT_TIMESTAMP)",
            winner_id, total_prize
        )
        
        # 5. Xóa dữ liệu cũ
        await execute_db(self.bot, "TRUNCATE TABLE lottery_tickets")
        
        # 6. Vinh danh
        if channel:
            winner_tickets = next(int(r["tickets"]) for r in rows if str(r["discord_id"]) == winner_id)
            win_rate = (winner_tickets / total_tickets) * 100

            embed = discord.Embed(
                title="🎉 KẾT QUẢ XỔ SỐ KIẾN THIẾT ANGELIC 🎉",
                description=(
                    f"<:symbol_trophy:1537550568665649232> **CHÚC MỪNG TỶ PHÚ MỚI:** <@{winner_id}>\n\n"
                    f"💰 **Giải Thưởng:** `{total_prize:,}` points!\n"
                    f"🎟️ **Số vé người này mua:** `{winner_tickets:,}` vé (Tỉ lệ trúng: `{win_rate:.2f}%`)\n\n"
                    f"*(Hũ đã được làm sạch. Chúc các bạn may mắn lần sau!)*"
                ),
                color=COLOR_GOLD
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1513465012344193088/1530151669336113252/money-make.gif?ex=6a64884a&is=6a6336ca&hm=4fdeb63b9958abcc8bacb62d8827043cfda571377f00d920a1214ca9a0d3a7c5&")
            await channel.send(content=f"ĐỘC ĐẮC! <@{winner_id}>", embed=embed)

        self.is_locked = False
        log.info(f"Đã quay thưởng xong. Winner: {winner_id}, Prize: {total_prize}")

    # ─────────────────────────────────────────────────────────────────────────
    # LỆNH NGƯỜI CHƠI
    # ─────────────────────────────────────────────────────────────────────────

    @commands.hybrid_group(name="xoso", aliases=["lottery", "xs"], fallback="info")
    async def xoso_cmd(self, ctx: commands.Context) -> None:
        """Xem thông tin Xổ Số Sự Kiện."""
        uid = str(ctx.author.id)

        # 1. Tính tổng hũ
        total_tickets = await fetchval_db(self.bot, "SELECT SUM(tickets) FROM lottery_tickets")
        total_tickets = int(total_tickets) if total_tickets else 0
        pot = total_tickets * POT_MULTIPLIER

        # 2. Lấy vé của user
        user_tickets = await fetchval_db(self.bot, "SELECT tickets FROM lottery_tickets WHERE discord_id = $1", uid)
        user_tickets = int(user_tickets) if user_tickets else 0

        # 3. Lấy người trúng kỳ trước
        last_winner_row = await fetchrow_db(
            self.bot, 
            "SELECT winner_id, prize FROM lottery_history ORDER BY id DESC LIMIT 1"
        )
        last_winner_str = "Chưa có"
        if last_winner_row:
            lw_id = last_winner_row["winner_id"]
            lw_prize = int(last_winner_row["prize"])
            last_winner_str = f"<@{lw_id}> ── **{lw_prize:,}** điểm"

        # 4. Tính toán thời gian kỳ tới
        now = datetime.now(UTC7)
        draw_time = now.replace(hour=LOTTERY_TIME_HOUR, minute=LOTTERY_TIME_MINUTE, second=0, microsecond=0)
        if now >= draw_time:
            draw_time += timedelta(days=1)
        draw_timestamp = int(draw_time.timestamp())

        # 5. Build Embed
        embed = discord.Embed(
            title="🎟️ Xổ Số Sự Kiện Angelic 🎟️",
            description=(
                f"Trò chơi may rủi quốc dân! Mua vé, nín thở và chờ kết quả vào **18:00 (UTC+7)** mỗi ngày.\n"
                f"*(Giá vé càng nhiều người mua, tổng Hũ càng to do được nhà cái trợ giá thêm 50%!)*"
            ),
            color=COLOR_GOLD
        )
        embed.add_field(
            name="<:symbol_money:1537466097282842775> Giá vé",
            value=f"**{TICKET_PRICE:,}** điểm / vé\n*(Tối đa {MAX_TICKETS_PER_USER} vé)*",
            inline=True
        )
        embed.add_field(
            name="💰 Tổng Hũ (Pot)",
            value=f"**{pot:,}** điểm",
            inline=True
        )
        embed.add_field(
            name="🕒 Kỳ quay tiếp theo",
            value=f"<t:{draw_timestamp}:R>",
            inline=False
        )
        embed.add_field(
            name="🎯 Vé của bạn",
            value=f"**{user_tickets:,}** / {MAX_TICKETS_PER_USER} vé",
            inline=True
        )
        embed.add_field(
            name="🎉 Người thắng kỳ trước",
            value=last_winner_str,
            inline=False
        )
        embed.set_footer(text="Gõ kxoso mua <sl> hoặc kxoso ban <sl> để tham gia.")

        await ctx.send(embed=embed)

    @xoso_cmd.command(name="mua", aliases=["buy"])
    async def mua_cmd(self, ctx: commands.Context, amount: int) -> None:
        """Mua vé số. Cú pháp: kxoso mua <số_lượng>"""
        uid = str(ctx.author.id)
        # Gọi helper dùng chung với shop_cog.py để không lặp code
        ok, msg = await buy_lottery_tickets(self.bot, uid, amount, self.is_locked)
        await ctx.send(f"{ctx.author.mention} {msg}", delete_after=8.0)

    @xoso_cmd.command(name="ban", aliases=["sell"])
    async def ban_cmd(self, ctx: commands.Context, amount: int) -> None:
        """Bán vé số lại cho hệ thống (hoàn tiền gốc). Cú pháp: kxoso ban <số_lượng>"""
        if self.is_locked:
            await ctx.send(f"🔒 {ctx.author.mention} Máy đang xổ mà đòi trả vé à? Chơi dơ vậk", delete_after=5.0)
            return

        if amount <= 0:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Bán 0 vé thì sòng mua kiểu gì? Bấm lại!", delete_after=5.0)
            return

        uid = str(ctx.author.id)
        
        # Lấy số vé hiện tại
        current_tickets = await fetchval_db(self.bot, "SELECT tickets FROM lottery_tickets WHERE discord_id = $1", uid)
        current_tickets = int(current_tickets) if current_tickets else 0

        if current_tickets < amount:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Gáy to vậy? Trong tay có mỗi **{current_tickets}** vé mà đòi bán tới **{amount}** vé à!", delete_after=5.0)
            return

        refund = amount * TICKET_PRICE

        if current_tickets == amount:
            await execute_db(self.bot, "DELETE FROM lottery_tickets WHERE discord_id = $1", uid)
        else:
            await execute_db(self.bot, "UPDATE lottery_tickets SET tickets = tickets - $2 WHERE discord_id = $1", uid, amount)

        await add_event_points(self.bot, uid, refund, is_earned=False)

        await ctx.send(
            f"♻️ {ctx.author.mention} Bán lúa non à? Sòng thu hồi **{amount:,}** vé, hoàn lại **{refund:,}** điểm.\n"
            f"Giờ chỉ còn **{current_tickets - amount:,}** vé thôi nhé!",
            delete_after=5.0
        )

    # Lệnh Admin test
    @commands.command(name="forcedraw", hidden=True)
    @commands.has_permissions(administrator=True)
    async def forcedraw_cmd(self, ctx: commands.Context) -> None:
        """[Admin] Bắt buộc quay thưởng ngay lập tức."""
        await ctx.send("🛑 [Admin] Bắt buộc quay xổ số ngay lập tức...")
        await self._do_draw()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Lottery(bot))
