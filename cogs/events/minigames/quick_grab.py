import discord
import random
from datetime import datetime, timezone
import logging

from cogs.common.db import add_event_points

log = logging.getLogger("QuickGrab")

class QuickGrabView(discord.ui.View):
    def __init__(self, bot, core_cog):
        super().__init__(timeout=30.0)
        self.bot = bot
        self.core_cog = core_cog
        self.winners = []  # Danh sách những người đã nhặt
        self.message: discord.Message | None = None
        self.rewards = [100, 50, 20]
        
    @discord.ui.button(label="👋 Nhặt Lấy", style=discord.ButtonStyle.success)
    async def grab_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        # Kiểm tra xem đã bấm chưa
        if any(w.id == user_id for w in self.winners):
            await interaction.response.send_message("Bạn đã nhặt phần quà của mình rồi! Hãy chừa lại cho người khác nhé.", ephemeral=True)
            return
            
        self.winners.append(interaction.user)
        rank = len(self.winners)
        points = self.rewards[rank - 1]
        
        # Cộng điểm thưởng
        success = await add_event_points(self.bot, str(user_id), points, is_earned=True)
        if success:
            medal = ["🥇", "🥈", "🥉"][rank - 1]
            await interaction.response.send_message(
                f"{medal} Chúc mừng! Bạn là người thứ **{rank}** nhặt được quà và nhận **{points} điểm**!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Có lỗi xảy ra khi cộng điểm, vui lòng báo Admin!", ephemeral=True)
            
        # Nếu đã đủ 3 người thì kết thúc
        if len(self.winners) >= 3:
            self.stop()
            await self.finish_game()

    async def on_timeout(self):
        await self.finish_game()
        
    async def finish_game(self):
        # Cập nhật lại trạng thái Core
        self.core_cog.last_minigame_end = datetime.now(timezone.utc)
        self.core_cog.is_minigame_running = False
        
        # Vô hiệu hóa nút
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                
        # Cập nhật Embed công bố
        if self.message:
            embed = self.message.embeds[0] if self.message.embeds else discord.Embed(color=0xfee75c)
            embed.title = "<:gift_00_symbol:1536003307011842099> Túi quà khổng lồ đã được nhặt hết!"
            
            if self.winners:
                desc = "**Danh sách 3 chiến thần nhanh tay nhất:**\n\n"
                medals = ["🥇", "🥈", "🥉"]
                for i, w in enumerate(self.winners):
                    desc += f"{medals[i]} {w.mention} ── **+{self.rewards[i]} điểm**\n"
                embed.description = desc
            else:
                embed.description = "Rất tiếc, không có ai nhanh tay nhặt được quà."
                
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


async def start_quick_grab(bot, channel: discord.abc.Messageable, core_cog):
    """Khởi chạy minigame Nhặt Lộc Siêu Tốc"""
    embed = discord.Embed(
        title="Một túi quà khổng lồ vừa rơi xuống lộp bộp từ trên trời!",
        description="Nhanh tay nhấn nút bên dưới để nhặt quà nhé. Chỉ dành cho **3 người** nhanh nhất!",
        color=0xfee75c
    )
    view = QuickGrabView(bot, core_cog)
    
    try:
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
    except Exception as e:
        log.error(f"Lỗi khi gửi tin nhắn QuickGrab: {e}")
        # Reset trạng thái nếu lỗi không gửi được
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
