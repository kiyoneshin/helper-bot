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
            
        # Chỉ quan tâm tin nhắn có chứa embed
        if not message.embeds:
            return
            
        # Kiểm tra xem tin nhắn có components (buttons/selects) không
        has_components = len(message.components) > 0
        
        # Nếu KHÔNG CÓ nút bấm (ví dụ lệnh help, lệnh xem point, hoặc thông báo thường)
        if not has_components:
            # Xoá sau 5 phút (300 giây)
            await asyncio.sleep(300.0)
            try:
                await message.delete()
            except discord.NotFound:
                pass
        else:
            # Nếu CÓ nút bấm, ta không xoá ngay lập tức.
            # Ta sẽ chờ cho đến khi View hết hạn (timeout) hoặc các nút bị vô hiệu hoá.
            # Việc đó sẽ được xử lý trong on_message_edit.
            
            # (Lưu ý: Nếu một View không bao giờ bị disable qua code, nó sẽ tồn tại vĩnh viễn, 
            # nhưng phần lớn các lệnh general như y!shop, y!inv đều có on_timeout disable nút).
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.channel.id != self.casino_channel_id:
            return
            
        if not self.bot.user or after.author.id != self.bot.user.id:
            return
            
        if not after.embeds:
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
            # Bắt đầu đếm ngược 5 phút (300s) rồi xoá
            await asyncio.sleep(300.0)
            try:
                await after.delete()
            except discord.NotFound:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(CasinoCleanupCog(bot))
