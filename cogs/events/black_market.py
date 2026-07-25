import discord
from discord.ext import commands
import logging
import json
import asyncio
from typing import Optional

from cogs.common.db import fetchrow_db, execute_db

log = logging.getLogger("BlackMarket")

# =====================================================================
# I. DANH SÁCH VẬT PHẨM CHỢ ĐEN
# =====================================================================
BLACK_MARKET_ITEMS = {
    "jail_card": {"name": "Thẻ Tống Giam 🚔", "description": "Gửi 1 người vào chuồng chó (tương đương y!phattu)"},
    "free_card": {"name": "Thẻ Đặc Xá 🕊️", "description": "Cứu người khác khỏi tù hoặc tự cứu mình (tương đương y!thatu)"},
    "timeout_1m": {"name": "Búa Gõ 1 Phút 🔨", "description": "Timeout mục tiêu 1 phút"},
    "timeout_5m": {"name": "Búa Gõ 5 Phút 🔨", "description": "Timeout mục tiêu 5 phút"},
    "nickname_change": {"name": "Thẻ Đổi Tên 🤡", "description": "Buộc mục tiêu đổi biệt danh thành một tên tấu hài ngẫu nhiên"},
    "disconnect_card": {"name": "Thẻ Rút Phích Cắm 🔌", "description": "Đá văng mục tiêu khỏi Voice Channel ngay lập tức"},
    "shield_card": {"name": "Thẻ Miễn Nhiễm 🛡️", "description": "Tự động chặn 1 lần bị người khác dùng thẻ xấu lên mình"},
    "thief_card": {"name": "Bao Tay Đạo Chích 🧤", "description": "Trộm ngẫu nhiên 50-500 điểm sự kiện của mục tiêu"},
    "fake_ban_card": {"name": "Trát Hầu Tòa 📜", "description": "Gửi một Embed dọa ban vĩnh viễn cực kỳ nghiêm trọng rồi chốt là đùa"},
    "ghost_ping_card": {"name": "Bom Ảo Giác 💣", "description": "Bot gửi tin nhắn tag mục tiêu rồi xóa ngay lập tức 3 lần liên tục"}
}


class BlackMarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="use", aliases=["dung", "xai"])
    async def use_item(self, ctx: commands.Context, item_id: str, target: Optional[discord.Member] = None):
        """Sử dụng vật phẩm từ túi đồ (inventory) lên bản thân hoặc người khác"""
        # Đưa item_id về chữ thường để tránh lỗi viết hoa/thường
        item_id = item_id.lower()
        
        # 1. Kiểm tra & Báo lỗi (Xóa tin nhắn sau 5s)
        if item_id not in BLACK_MARKET_ITEMS:
            await ctx.send(f"❌ Vật phẩm `{item_id}` không tồn tại trong hệ thống!", delete_after=5.0)
            return
            
        item_name = BLACK_MARKET_ITEMS[item_id]["name"]
        uid = str(ctx.author.id)

        # Truy vấn túi đồ (inventory) từ DB
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        
        # Parse JSON an toàn (xử lý NULL)
        inv = {}
        if row and row['inventory']:
            try:
                inv = json.loads(row['inventory']) if isinstance(row['inventory'], str) else row['inventory']
            except Exception as e:
                log.error(f"Lỗi parse inventory JSON của user {uid}: {e}")
                
        # Kiểm tra số lượng
        quantity = inv.get(item_id, 0)
        if quantity <= 0:
            await ctx.send(f"❌ Bạn không có **{item_name}** trong túi đồ!", delete_after=5.0)
            return

        # 2. Logic Trừ Item
        inv[item_id] -= 1
        if inv[item_id] <= 0:
            del inv[item_id]  # Xóa khỏi dict nếu hết để dọn dẹp DB

        # Cập nhật lại cột inventory
        await execute_db(
            self.bot, 
            "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", 
            uid, 
            json.dumps(inv)
        )

        # Gửi thông báo Embed thành công
        target_display = target.mention if target else "bản thân"
        embed = discord.Embed(
            description=f"✨ {ctx.author.mention} vừa sử dụng thành công **{item_name}** lên {target_display}!",
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

        # === THỰC THI TÁC DỤNG VẬT PHẨM (ĐANG ĐƯỢC COMMENT LẠI) ===
        # if item_id == "jail_card":
        #     if not target:
        #         await ctx.send("❌ Bạn cần chỉ định mục tiêu để tống giam!", delete_after=5.0)
        #         return
        #     # Logic giam giữ: vd gọi cogs moderation/jail...
        #     pass
        # 
        # elif item_id == "free_card":
        #     # Logic tha tù: vd gọi cogs moderation/jail...
        #     pass
        # 
        # elif item_id in ["timeout_1m", "timeout_5m"]:
        #     if not target:
        #         await ctx.send("❌ Bạn cần chỉ định mục tiêu để gõ búa!", delete_after=5.0)
        #         return
        #     import datetime
        #     mins = 1 if item_id == "timeout_1m" else 5
        #     try:
        #         duration = datetime.timedelta(minutes=mins)
        #         await target.timeout(duration, reason=f"Bị {ctx.author.name} dùng búa gõ")
        #         await ctx.send(f"🔨 Đã gõ đầu {target.mention} {mins} phút!")
        #     except discord.Forbidden:
        #         await ctx.send("❌ Lỗi: Bot không có đủ quyền (Role thấp hơn mục tiêu) để timeout!", delete_after=5.0)
        # 
        # elif item_id == "nickname_change":
        #     if not target:
        #         await ctx.send("❌ Cần chỉ định mục tiêu đổi tên!", delete_after=5.0)
        #         return
        #     try:
        #         import random
        #         funny_names = ["Kẻ Tấu Hài 🤡", "Chúa Tể Hề 🎪", "Chú Bé Đần 💩", "Hạt Nhài 🌻"]
        #         new_name = random.choice(funny_names)
        #         await target.edit(nick=new_name, reason="Dính Thẻ Đổi Tên")
        #         await ctx.send(f"🤡 Đã phù phép biến {target.mention} thành **{new_name}**!")
        #     except discord.Forbidden:
        #         await ctx.send("❌ Lỗi: Bot không đủ quyền đổi nickname của mục tiêu này!", delete_after=5.0)
        # 
        # elif item_id == "disconnect_card":
        #     if not target or not target.voice:
        #         await ctx.send("❌ Mục tiêu hiện không ở trong Voice Channel nào!", delete_after=5.0)
        #         return
        #     try:
        #         await target.move_to(None, reason="Dính Thẻ Rút Phích Cắm")
        #         await ctx.send(f"🔌 Đã rút phích cắm {target.mention} khỏi Voice Channel!")
        #     except discord.Forbidden:
        #         await ctx.send("❌ Lỗi: Bot không đủ quyền đá mục tiêu khỏi Voice!", delete_after=5.0)
        # 
        # elif item_id == "shield_card":
        #     # Cấp cờ shield vào DB cho user để chặn các thẻ khác trong tương lai
        #     pass
        # 
        # elif item_id == "thief_card":
        #     if not target:
        #         await ctx.send("❌ Mục tiêu đâu để trộm?", delete_after=5.0)
        #         return
        #     import random
        #     stolen_amount = random.randint(50, 500)
        #     # Thực thi trừ điểm target, cộng điểm author qua execute_db...
        #     await ctx.send(f"🧤 Kẻ gian {ctx.author.mention} đã lẻn trộm `{stolen_amount}` điểm từ {target.mention}!")
        # 
        # elif item_id == "fake_ban_card":
        #     if not target: 
        #         await ctx.send("❌ Vui lòng tag người để hù dọa!", delete_after=5.0)
        #         return
        #     fake_embed = discord.Embed(
        #         title="🚨 LỆNH CẤM TOÀN MÁY CHỦ 🚨",
        #         description=f"Tài khoản {target.mention} đã vi phạm nghiêm trọng luật lệ Server.\nQuá trình cấm sẽ bắt đầu trong giây lát...",
        #         color=0xff0000
        #     )
        #     msg = await ctx.send(embed=fake_embed)
        #     await asyncio.sleep(2)
        #     fake_embed.description = f"Tài khoản {target.mention} chuẩn bị bị cấm..."
        #     await msg.edit(embed=fake_embed)
        #     await asyncio.sleep(2)
        #     joke_embed = discord.Embed(
        #         title="🤡 BỊ LỪA RỒI NHÁ!",
        #         description=f"Đùa tí làm gì căng {target.mention} ơi =)))",
        #         color=0xffff00
        #     )
        #     await msg.edit(embed=joke_embed)
        # 
        # elif item_id == "ghost_ping_card":
        #     if not target: 
        #         await ctx.send("❌ Tag ai đó để spam ping đi nào!", delete_after=5.0)
        #         return
        #     for _ in range(3):
        #         msg = await ctx.send(target.mention)
        #         await msg.delete()
        #         await asyncio.sleep(0.5)

async def setup(bot):
    await bot.add_cog(BlackMarketCog(bot))
