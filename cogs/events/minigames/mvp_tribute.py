import discord
import asyncio
from datetime import datetime, timezone
import random
import logging

from cogs.common.db import add_event_points, fetchrow_db

log = logging.getLogger("MVPTribute")

async def start_mvp_tribute_game(bot, channel: discord.abc.Messageable, core_cog):
    """Khởi chạy minigame Tôn Vinh MVP 10 Phút"""
    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
        return
    # =================================================================
    # GIAI ĐOẠN 1: TRUY VẤN SQL TÌM MVP 10 PHÚT QUA
    # =================================================================
    mvp_user = None

    sql_10m = """
        SELECT discord_id FROM event_profiles 
        WHERE last_chat_time >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC' - INTERVAL '10 minutes')
        ORDER BY current_streak DESC, daily_chat_count DESC LIMIT 1;
    """
    row = await fetchrow_db(bot, sql_10m)

    if not row:
        sql_daily = """
            SELECT discord_id FROM event_profiles 
            WHERE daily_chat_count > 0 
            ORDER BY daily_chat_count DESC LIMIT 1;
        """
        row = await fetchrow_db(bot, sql_daily)

    if row:
        try:
            mvp_user = channel.guild.get_member(int(row["discord_id"]))
        except Exception:
            pass

    if not mvp_user:
        async for last_msg in channel.history(limit=10):
            if not last_msg.author.bot and isinstance(last_msg.author, discord.Member):
                mvp_user = last_msg.author
                break
            
    if not mvp_user:
        log.error("Không tìm thấy bất kỳ ai hợp lệ để làm MVP, hủy game.")
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
        return

    # =================================================================
    # GIAI ĐOẠN 2: THÔNG BÁO VINH DANH & KHỞI ĐỘNG (30 GIÂY)
    # =================================================================
    embed = discord.Embed(
        title="🌟 VINH DANH MVP CHAT — 10 PHÚT QUA!",
        description=(
            f"Xin được vinh danh chiến thần {mvp_user.mention} — người đã năng nổ buôn chuyện nhiệt huyết nhất trong 10 phút vừa qua!\n\n"
            f"⏳ **Thử thách chớp nhoáng (30 giây):**\n"
            f"Tất cả thành viên đang online hãy nhanh tay gõ chính xác cú pháp dưới đây lên kênh chat:\n"
            f"👉 `tui iu {mvp_user.mention}` (Nhớ tag đúng tài khoản của MVP nhé!)\n\n"
            f"<:gift_00_symbol:1536003307011842099> **Phần thưởng:**\n"
            f"• Ai gõ đúng và nhanh sẽ được cộng ngay **+50 điểm** sự kiện!\n"
            f"• 👑 **Đặc quyền MVP:** Không cần gõ, ngồi mát ăn bát vàng! Nhận ngay 10% hoa hồng (+5 điểm) từ mỗi câu chúc của mọi người! 🌸"
        ),
        color=0xff80df
    )
    embed.add_field(name="👥 Danh sách chúc mừng (0 người)", value="*Chưa có ai chúc...*", inline=False)
    
    try:
        msg = await channel.send(embed=embed)
    except Exception as e:
        log.error(f"Lỗi gửi tin nhắn MVPTribute: {e}")
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
        return

    congratulators = set()
    congrats_list = []
    
    loop = asyncio.get_event_loop()
    end_time = loop.time() + 30.0

    def check_func(m: discord.Message) -> bool:
        if m.channel.id != channel.id:
            return False
        if m.author.bot:
            return False
        if m.author.id == mvp_user.id:
            return False
        if m.author.id in congratulators:
            return False
            
        content_lower = m.content.lower()
        if "tui iu" not in content_lower:
            return False
            
        if mvp_user.id not in m.raw_mentions:
            return False
            
        return True

    # =================================================================
    # GIAI ĐOẠN 3: LẮNG NGHE TIN NHẮN TƯƠNG TÁC THEO THỜI GIAN THỰC
    # =================================================================
    while loop.time() < end_time:
        timeout = max(0.1, end_time - loop.time())
        try:
            m = await bot.wait_for('message', check=check_func, timeout=timeout)
            
            # Ghi nhận người chúc
            congratulators.add(m.author.id)
            congrats_list.append(m.author)
            
            try:
                await m.add_reaction("💖")
            except discord.HTTPException:
                pass
                
            # Cộng điểm
            await add_event_points(bot, str(m.author.id), 50, is_earned=True)
            await add_event_points(bot, str(mvp_user.id), 5, is_earned=True)
            
            # Cập nhật Field
            new_field_val = "\n".join([f"• {u.mention}" for u in congrats_list])
            embed.set_field_at(0, name=f"👥 Danh sách chúc mừng ({len(congratulators)} người)", value=new_field_val, inline=False)
            
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass
                
        except asyncio.TimeoutError:
            break

    # =================================================================
    # GIAI ĐOẠN 4: TỔNG KẾT & TRAO QUÀ CHUNG CUỘC
    # =================================================================
    total_commission = len(congratulators) * 5
    
    embed.color = 0x57f287
    embed.description = (
        f"Xin được vinh danh chiến thần {mvp_user.mention} — người đã năng nổ buôn chuyện nhiệt huyết nhất trong 10 phút vừa qua!\n\n"
        f"**ĐÃ HẾT GIỜ!** Cảm ơn tình cảm của cả server dành cho MVP!\n"
        f"**MVP:** Nhận được **+{total_commission} điểm** hoa hồng từ {len(congratulators)} lời chúc!"
    )
    
    try:
        await msg.edit(embed=embed)
    except discord.HTTPException:
        pass

    core_cog.last_minigame_end = datetime.now(timezone.utc)
    core_cog.is_minigame_running = False
