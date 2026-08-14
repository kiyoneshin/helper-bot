import asyncio
import discord
from discord.ext import commands

class CasinoCleanupCog(commands.Cog):
    """Cog xử lý tự động xoá tin nhắn trong kênh Casino (phiên bản 2)."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.casino_channel_id = 1498711783223853101

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Chỉ áp dụng ở kênh Casino
        if message.channel.id != self.casino_channel_id:
            return
            
        # Chỉ quan tâm tin nhắn của Bot
        if not self.bot.user or message.author.id != self.bot.user.id:
            return
            
        # Kiểm tra xem đây có phải là tin nhắn welcome không (dựa vào text)
        content_lower = message.content.lower()
        is_welcome = "chào mừng" in content_lower or "queo căm" in content_lower or "lốp ăng giê líc xin chào" in content_lower
        if is_welcome:
            return
            
        # Kiểm tra tin nhắn Giveaway (không xoá)
        is_giveaway = False
        if "giveaway đã kết thúc" in content_lower or "chúc mừng" in content_lower or "không có ai tham gia hợp lệ" in content_lower or "đang cấu hình" in content_lower:
            is_giveaway = True
        for emb in message.embeds:
            title = emb.title or ""
            author_name = emb.author.name if emb.author and emb.author.name else ""
            if "Giveaway" in title or "Giveaway" in author_name or "Thiết lập Giveaway" in title:
                is_giveaway = True
                break
        if is_giveaway:
            return

        # Kiểm tra xem tin nhắn có components (buttons/selects) không
        has_components = len(message.components) > 0
        
        # Nếu KHÔNG CÓ nút bấm (ví dụ lệnh help, lệnh xem point, hoặc thông báo thường)
        if not has_components:
            # Phân loại Kết quả cá cược hay thông báo thường
            is_gambling_result = False
            keywords = ["tài xỉu", "bầu cua", "dice", "tàu bay", "crash", "roulette", "coinflip", "cups", "xổ số", "kết quả", "cốc", "ly", "shot", "ngửa", "blackjack", "bj", "xì dách"]
            
            for emb in message.embeds:
                text_to_check = f"{emb.title or ''} {emb.author.name if emb.author else ''} {emb.description or ''}".lower()
                if any(kw in text_to_check for kw in keywords):
                    is_gambling_result = True
                    break
                    
            if not is_gambling_result:
                if any(kw in content_lower for kw in keywords):
                    is_gambling_result = True
            
            delay = 30.0 if is_gambling_result else 120.0
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except discord.NotFound:
                pass
        else:
            # Nếu CÓ nút bấm, ta không xoá ngay lập tức.
            # Ta sẽ chờ cho đến khi View hết hạn (timeout) hoặc các nút bị vô hiệu hoá.
            # Việc đó sẽ được xử lý trong on_message_edit.
            
            # (Lưu ý: Nếu một View không bao giờ bị disable qua code, nó sẽ tồn tại vĩnh viễn, 
            # nhưng phần lớn các lệnh general như kshop, kinv đều có on_timeout disable nút).
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.channel.id != self.casino_channel_id:
            return
            
        if not self.bot.user or after.author.id != self.bot.user.id:
            return
            
        content_lower = after.content.lower()
        is_welcome = "chào mừng" in content_lower or "queo căm" in content_lower or "lốp ăng giê líc xin chào" in content_lower
        if is_welcome:
            return
            
        # Kiểm tra tin nhắn Giveaway (không xoá)
        is_giveaway = False
        if "giveaway đã kết thúc" in content_lower or "chúc mừng" in content_lower or "không có ai tham gia hợp lệ" in content_lower or "đang cấu hình" in content_lower:
            is_giveaway = True
        for emb in after.embeds:
            title = emb.title or ""
            author_name = emb.author.name if emb.author and emb.author.name else ""
            if "Giveaway" in title or "Giveaway" in author_name or "Thiết lập Giveaway" in title:
                is_giveaway = True
                break
        if is_giveaway:
            return

        # Kiểm tra xem tin nhắn có components không
        if len(after.components) == 0:
            return
            
        # Kiểm tra xem TẤT CẢ các component (button/select) đã bị disable chưa
        all_disabled = True
        for action_row in after.components:
            for child in getattr(action_row, "children", []):
                # Trích xuất thuộc tính disabled của child (hoạt động với discord.py components)
                if not getattr(child, "disabled", False):
                    all_disabled = False
                    break
            if not all_disabled:
                break
                
        # Nếu tất cả đã bị vô hiệu hoá (vd: View đã timeout)
        if all_disabled:
            is_gambling_result = False
            keywords = [
                "tài xỉu", "bầu cua", "dice", "tàu bay", "crash", "roulette", "coinflip", "cups", "xổ số", "kết quả", "cốc", "ly", "shot", "ngửa",
                "bảo vật", "nhặt lộc", "chúc mừng", "chúa tể", "nhân phẩm", "mvp", "danh sách", "tham gia", "vinh danh", "tan biến", "blackjack", "bj", "xì dách"
            ]
            
            for emb in after.embeds:
                text_to_check = f"{emb.title or ''} {emb.author.name if emb.author else ''} {emb.description or ''}".lower()
                if any(kw in text_to_check for kw in keywords):
                    is_gambling_result = True
                    break
                    
            if not is_gambling_result:
                if any(kw in content_lower for kw in keywords):
                    is_gambling_result = True
            
            if is_gambling_result:
                await asyncio.sleep(30.0)
                
            try:
                await after.delete()
            except discord.NotFound:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(CasinoCleanupCog(bot))
