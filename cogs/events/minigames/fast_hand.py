import discord
import random
from datetime import datetime, timezone
import logging

from cogs.common.db import add_event_points

log = logging.getLogger("FastHand")

ITEMS_POOL = {
    "👑": "Vương Miện Cuti",
    "🦊": "Cáo Nhỏ Đi Lạc",
    "💎": "Viên Đá Vô Cực",
    "🍡": "Xiên Que Trà Sữa",
    "🌸": "Hoa Anh Đào Mùa Xuân",
    "🧸": "Gấu Bông Bị Bỏ Quên",
    "🦋": "Hồ Điệp Băng Giá",
    "🍀": "Cỏ Bốn Lá May Mắn",
    "🌙": "Vầng Trăng Khuyết",
    "⭐": "Ngôi Sao Băng",
    "🔮": "Quả Cầu Tiên Tri",
    "🎀": "Nơ Hồng Điệu Đà",
    "🎸": "Cây Đàn Bị Bỏ Quên",
    "🎨": "Bảng Màu Ma Thuật",
    "🍕": "Miếng Pizza Cuối Cùng",
    "🍔": "Burger Ngập Phô Mai",
    "🍣": "Sushi Cá Hồi Tươi",
    "🍦": "Kem Ốc Quế Tan Chảy",
    "☕": "Ly Cà Phê Đắng",
    "🍎": "Trái Táo Độc",
    "🍓": "Dâu Tây Ngọt Ngào",
    "🍉": "Dưa Hấu Khổng Lồ",
    "🥑": "Quả Bơ Siêu To",
    "🍄": "Nấm Ma Thuật",
    "🦄": "Sừng Kỳ Lân",
    "🐉": "Vảy Rồng Thần",
    "🐶": "Cún Con Dễ Thương",
    "🐱": "Mèo Con Đáng Yêu",
    "🐼": "Gấu Trúc Mũm Mĩm",
    "🐙": "Bạch Tuộc Alien"
}

class FastHandButton(discord.ui.Button):
    def __init__(self, emoji_str: str, custom_id: str, row: int):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji_str, custom_id=custom_id, row=row)

    async def callback(self, interaction: discord.Interaction):
        if isinstance(self.view, FastHandView) and self.custom_id is not None:
            await self.view.handle_click(interaction, self.custom_id)

class FastHandView(discord.ui.View):
    def __init__(self, bot, core_cog, target_id: str, target_name: str):
        super().__init__(timeout=30.0)
        self.bot = bot
        self.core_cog = core_cog
        self.target_id = target_id
        self.target_name = target_name
        self.message: discord.Message | None = None
        self.winner: discord.Member | discord.User | None = None

    async def handle_click(self, interaction: discord.Interaction, clicked_id: str):
        # Nếu đã có người thắng trước đó thì bỏ qua các click khác
        if self.winner is not None:
            return

        # Bấm sai
        if clicked_id != self.target_id:
            await interaction.response.send_message(
                "<:symbol_wrong:1536289315867598849> Sai rồi! Hoa mắt chóng mặt rồi à chiến thần ơi, nhìn kỹ lại đi!", 
                ephemeral=True
            )
            return
            
        # Bấm đúng
        self.winner = interaction.user
        
        # Khóa toàn bộ nút
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        # Cộng 150 điểm cho người thắng
        success = await add_event_points(self.bot, str(interaction.user.id), 150, is_earned=True)
        if not success:
            log.error(f"Lỗi cộng điểm cho {interaction.user.id} trong FastHand")
            
        # Cập nhật thông báo chiến thắng (màu xanh lá)
        if self.message:
            embed = self.message.embeds[0] if self.message.embeds else discord.Embed()
            embed.color = 0x57f287
            embed.title = "🎉 TÌM THẤY BẢO VẬT!"
            embed.description = f"🎉 Chiến thần {interaction.user.mention} đã tìm thấy **{self.target_name}** trong đống đổ nát và nhận **150 điểm**!"
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

        # Cleanup RAM và trạng thái core
        self.core_cog.last_minigame_end = datetime.now(timezone.utc)
        self.core_cog.is_minigame_running = False
        
        await interaction.response.send_message("🎉 Chúc mừng bạn đã nhanh tay chọn đúng!", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        # Nếu đã có người thắng thì không làm gì thêm
        if self.winner is not None:
            return
            
        # Khóa nút
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        # Hết giờ không ai tìm thấy
        if self.message:
            embed = self.message.embeds[0] if self.message.embeds else discord.Embed()
            embed.description = "💨 Bảo vật đã tan biến vào hư không! Hẹn các chiến thần ở lần đánh úp sau."
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

        # Cleanup RAM
        self.core_cog.last_minigame_end = datetime.now(timezone.utc)
        self.core_cog.is_minigame_running = False


async def start_fast_words_game(bot, channel: discord.abc.Messageable, core_cog):
    """Khởi chạy minigame Truy Tìm Bảo Vật (Fast Hand)"""
    all_emojis = list(ITEMS_POOL.keys())
    target_emoji = random.choice(all_emojis)
    target_name = ITEMS_POOL[target_emoji]
    
    # Rút ra 15 emoji khác để làm mồi nhử (Distractors)
    all_emojis.remove(target_emoji)
    distractor_emojis = random.sample(all_emojis, 15)
    
    # Trộn 16 emoji
    game_emojis = [target_emoji] + distractor_emojis
    random.shuffle(game_emojis)
    
    target_id = ""
    view = FastHandView(bot, core_cog, target_id="", target_name=target_name)
    
    # Tạo 16 nút (4 hàng, mỗi hàng 4 nút)
    for idx, em in enumerate(game_emojis):
        row = idx // 4
        # custom_id ngẫu nhiên chống hack
        btn_id = str(random.randint(1000000, 9999999))
        if em == target_emoji:
            target_id = btn_id
            
        btn = FastHandButton(emoji_str=em, custom_id=btn_id, row=row)
        view.add_item(btn)
        
    # Gán target_id vào view sau khi đã trộn
    view.target_id = target_id
    
    embed = discord.Embed(
        title="🚨 TRUY TÌM BẢO VẬT ANGELIC ໒꒱",
        description=(
            f"Trời đất chuyển vần! Một cơn gió lạ vừa thổi bay bảo vật của server vào đống đổ nát!\n\n"
            f"Hãy tìm ngay: **{target_name} ({target_emoji})**\n\n"
            f"*Chiến thần nào có đôi mắt tinh tường và cánh tay nhanh nhất nhấn đúng nút dưới đây sẽ ẵm trọn **150 điểm thưởng**!*"
        ),
        color=0x9b59b6
    )
    
    try:
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
    except Exception as e:
        log.error(f"Lỗi gửi tin nhắn fast_hand: {e}")
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
