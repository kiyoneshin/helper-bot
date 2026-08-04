"""
banking.py — Hệ thống Ngân Hàng & Vay Nợ Sự Kiện
===================================================
Quản lý các lệnh y!vayno, y!trano và tính lãi hàng ngày (tasks.loop).
Phạt vỡ nợ: Khóa lệnh nếu số dư hiện tại - tổng nợ < 0 liên tiếp trong 2 ngày.
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone, timedelta

from cogs.common.db import (
    execute_db,
    fetchrow_db,
    query_db,
    get_or_create_event_profile
)

log = logging.getLogger("Banking")
UTC7 = timezone(timedelta(hours=7))

# Kênh gửi thông báo đòi nợ
DEBT_CHANNEL_ID = 1498711783223853101
INTEREST_RATE = 0.01  # Lãi suất ngày (1%)

def parse_amount(arg: str, max_val: float) -> tuple[float, str]:
    arg = arg.lower().strip()
    if arg in ["all", "max"]:
        return max_val, ""
    
    # Cho phép nhập dạng 1k, 1m
    mult = 1.0
    if arg.endswith("k"):
        mult = 1_000.0
        arg = arg[:-1]
    elif arg.endswith("m"):
        mult = 1_000_000.0
        arg = arg[:-1]
    
    try:
        val = float(arg) * mult
        if val <= 0:
            return 0, "Số tiền phải lớn hơn 0."
        return val, ""
    except ValueError:
        return 0, "Số tiền không hợp lệ."

async def force_divorce(bot: commands.Bot, discord_id: str):
    """
    Hàm giả lập (mock) để ép ly hôn khi vỡ nợ.
    Sau này sẽ triển khai logic xóa/cập nhật bảng Marry tại đây.
    """
    log.info(f"[Banking] Đã gọi force_divorce cho user {discord_id}")
    # Ví dụ: await execute_db(bot, "DELETE FROM marriages WHERE user1 = $1 OR user2 = $1", discord_id)
    pass

class BankingCog(commands.Cog):
    """🏦 Hệ thống Ngân Hàng & Vay Nợ"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_interest_loop.start()

    async def cog_unload(self) -> None:
        self.daily_interest_loop.cancel()

    @commands.hybrid_command(name="vayno", aliases=["vay", "loan"])
    async def vayno_cmd(self, ctx: commands.Context, so_tien: str):
        """Vay nợ ngân hàng. Hạn mức: 50% tổng tài sản tích lũy."""
        uid = str(ctx.author.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        
        if profile and profile.get("is_locked"):
            await ctx.send("❌ Tài khoản của bạn đang bị khóa do vỡ nợ, không thể vay thêm!")
            return

        total_earned = float(profile.get("total_earned", 0.0)) if profile else 0.0
        current_debt = float(profile.get("debt", 0.0)) if profile else 0.0
        
        max_loan = total_earned * 0.5
        available_loan = max(0.0, max_loan - current_debt)

        if available_loan <= 0:
            await ctx.send(f"❌ {ctx.author.mention} Bạn đã hết hạn mức vay! (Hạn mức: **{max_loan:,.0f}**, Đang nợ: **{current_debt:,.0f}**)")
            return

        amount, err = parse_amount(so_tien, available_loan)
        if err:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return
            
        if amount > available_loan:
            await ctx.send(f"❌ {ctx.author.mention} Hạn mức còn lại của bạn chỉ là **{available_loan:,.0f}** điểm.")
            return

        # Thực hiện vay
        sql = '''
            UPDATE event_profiles
            SET points = points + $2,
                debt = debt + $2
            WHERE discord_id = $1
            RETURNING points, debt;
        '''
        row = await fetchrow_db(self.bot, sql, uid, amount)
        if row:
            new_pts = row["points"]
            new_debt = row["debt"]
            embed = discord.Embed(
                title="🏦 Ngân Hàng Angelic — Giải Ngân",
                description=f"✅ Giao dịch vay nợ thành công!\n\n💸 **Số tiền vay:** `{amount:,.0f}` điểm\n💰 **Số dư mới:** `{new_pts:,.0f}` điểm\n📉 **Tổng nợ hiện tại:** `{new_debt:,.0f}` điểm",
                color=0x00FF00
            )
            embed.set_footer(text="Lãi suất vay là 1%/ngày. Hãy nhớ y!trano nhé!")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Đã có lỗi xảy ra khi vay nợ.")

    @commands.hybrid_command(name="trano", aliases=["tra", "payloan"])
    async def trano_cmd(self, ctx: commands.Context, so_tien: str):
        """Trả nợ ngân hàng."""
        uid = str(ctx.author.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        
        current_debt = float(profile.get("debt", 0.0)) if profile else 0.0
        current_points = float(profile.get("points", 0.0)) if profile else 0.0
        
        if current_debt <= 0:
            await ctx.send(f"✅ {ctx.author.mention} Bạn không có khoản nợ nào để trả!")
            return
            
        if current_points <= 0:
            await ctx.send(f"❌ {ctx.author.mention} Bạn không có tiền trong ví để trả nợ!")
            return

        # Trả tối đa là min(số nợ, số tiền trong ví)
        max_payable = min(current_debt, current_points)
        amount, err = parse_amount(so_tien, max_payable)
        if err:
            await ctx.send(f"❌ {ctx.author.mention} {err}")
            return
            
        if amount > current_debt:
            amount = current_debt # Không cho trả dư
            
        if amount > current_points:
            await ctx.send(f"❌ {ctx.author.mention} Số dư ví không đủ! (Ví đang có: **{current_points:,.0f}**)")
            return

        sql = '''
            UPDATE event_profiles
            SET points = points - $2,
                debt = debt - $2
            WHERE discord_id = $1
            RETURNING points, debt, is_locked, negative_streak;
        '''
        row = await fetchrow_db(self.bot, sql, uid, amount)
        if row:
            new_pts = row["points"]
            new_debt = row["debt"]
            is_locked = row["is_locked"]
            
            desc = f"✅ Đã thanh toán nợ thành công!\n\n💸 **Đã trả:** `{amount:,.0f}` điểm\n💰 **Ví còn:** `{new_pts:,.0f}` điểm\n📉 **Nợ còn lại:** `{new_debt:,.0f}` điểm"
            
            # Nếu trả nợ giúp (points - debt) >= 0 thì mở khóa (nếu đang bị khóa)
            if (new_pts - new_debt) >= 0:
                await execute_db(self.bot, "UPDATE event_profiles SET is_locked = FALSE, negative_streak = 0 WHERE discord_id = $1", uid)
                if is_locked:
                    desc += "\n\n🔓 **Tài khoản của bạn đã được MỞ KHÓA vì đã thoát khỏi tình trạng âm vốn!**"

            embed = discord.Embed(
                title="🏦 Ngân Hàng Angelic — Trả Nợ",
                description=desc,
                color=0x00FF00
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Đã có lỗi xảy ra khi trả nợ.")

    @tasks.loop(hours=24)
    async def daily_interest_loop(self):
        """
        Quét mỗi ngày 1 lần.
        Tính lãi suất và kiểm tra phạt vỡ nợ.
        """
        log.info("[Banking] Bắt đầu chạy quét lãi suất hàng ngày...")
        
        # 1. Tính lãi suất (cho ai chưa bị tính lãi hôm nay)
        # 2. Kiểm tra vỡ nợ (points - debt < 0)
        
        sql_get = "SELECT discord_id, points, debt, negative_streak, is_locked FROM event_profiles WHERE debt > 0;"
        rows = await query_db(self.bot, sql_get)
        
        today = datetime.now(UTC7).date()
        
        debt_channel = self.bot.get_channel(DEBT_CHANNEL_ID)
        
        for r in rows:
            uid = r["discord_id"]
            pts = float(r["points"])
            debt = float(r["debt"])
            streak = int(r["negative_streak"])
            is_locked = r["is_locked"]
            
            # Áp lãi kép 1%
            new_debt = debt * (1.0 + INTEREST_RATE)
            
            # Kiểm tra trạng thái vốn
            # "khi số dư hiện tại - tổng nợ < 0 liên tiếp trong 2 ngày"
            new_streak = streak
            if pts - new_debt < 0:
                new_streak += 1
            else:
                new_streak = 0
                
            new_locked = is_locked
            just_locked = False
            
            if new_streak >= 2 and not is_locked:
                new_locked = True
                just_locked = True
                # Bắt đầu phạt
                await force_divorce(self.bot, uid)
                
            # Cập nhật DB
            await execute_db(
                self.bot,
                '''
                UPDATE event_profiles 
                SET debt = $2, negative_streak = $3, is_locked = $4, last_interest_date = $5
                WHERE discord_id = $1
                ''',
                uid, new_debt, new_streak, new_locked, today
            )
            
            # Gắn còi báo động đòi nợ nếu vừa bị khóa
            if just_locked and isinstance(debt_channel, discord.TextChannel):
                await debt_channel.send(
                    f"🚨🚨 **CẢNH BÁO VỠ NỢ** 🚨🚨\n"
                    f"<@{uid}> đã âm vốn liên tiếp 2 ngày! Ngân hàng đã **SIẾT TÀI SẢN & KHÓA TÀI KHOẢN**.\n"
                    f"Trạng thái Hôn Nhân đã bị hủy bỏ! Yêu cầu sử dụng lệnh `y!trano` để thanh toán khoản nợ **{new_debt:,.0f}** ngay lập tức!"
                )
                
        log.info("[Banking] Hoàn tất quét lãi suất hàng ngày.")

    @daily_interest_loop.before_loop
    async def before_daily_interest(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(BankingCog(bot))
