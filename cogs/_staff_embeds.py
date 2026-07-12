import discord
import json
import logging
from typing import Optional

log = logging.getLogger("StaffEmbeds")

def get_main_embed() -> discord.Embed:
    """Tạo Embed chào mừng và luật server ở trang đầu tiên"""
    embed = discord.Embed(
        title="🏠 Chào mừng đến với Angelic ໒꒱",
        description=(
            "Tiếng chuông nhà thờ khẽ ngân vang, cánh cổng thiên đường đã mở rộng chào đón bạn! ଘ(੭ˊᵕˋ)੭\n"
            "Hãy biến nơi đây thành mái nhà bình yên để cùng trò chuyện, chơi game, chữa lành và lưu giữ những kỷ niệm đẹp nhé.\n\n"
            "📜 **TÓM TẮT LUẬT SERVER (CẦN NHỚ KỸ):**\n"
            "**1. Văn hóa giao tiếp:** Tôn trọng tất cả mọi người, đùa giỡn có chừng mực. Nghiêm cấm gây war, drama hay mạo danh người khác.\n"
            "**2. Lằn ranh đỏ (BAN thẳng):** Tuyệt đối không Phân biệt vùng miền/chủng tộc, sài tool phá hoại (spam/nuke/raid), hoặc mua bán trái phép.\n"
            "**3. Nội dung nhạy cảm:** Hạn chế tối đa nói tục. Cấm gửi nội dung NSFW, máu me ở kênh chung (chỉ được gửi trong 🔞｜𝐓𝐎𝐗𝐈𝐂).\n"
            "**4. Giữ gìn trật tự:** Không spam (tin nhắn, ping, sticker, ticket). Cấm quảng cáo link ngoài khi chưa được phép.\n"
            "**5. Không gian chung:** Trò chuyện đúng chủ đề từng kênh, không phá room voice của người khác và tuân thủ lời nhắc của Staff.\n\n"
            "➡️ *Vui lòng chọn menu phía dưới để làm quen với danh sách Ban Quản Trị!*"
        ),
        color=0xffb6c1
    )
    return embed


def build_embed(user_data: dict, member: Optional[discord.Member] = None, photo_index: int = 0) -> discord.Embed:
    """Tạo Embed hiển thị Profile của Staff"""
    display_name = user_data.get('display_name', 'Unnamed Staff')
    role_name = user_data.get('role', 'staff').upper()
    
    embed = discord.Embed(
        title=f"✨ {display_name} ✨",
        color=0xffb6c1
    )
    
    tags = user_data.get('tags', [])
    if isinstance(tags, str):
        try: 
            tags = json.loads(tags)
        except Exception: 
            tags = []
        
    if tags:
        embed.description = "\n".join(f"♱ {t}" for t in tags)
    else:
        embed.description = "*Chưa có thông tin giới thiệu.*"
        
    if member and member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)
        
    photos = user_data.get('photos', [])
    if isinstance(photos, str):
        try: 
            photos = json.loads(photos)
        except Exception: 
            photos = []
        
    if photos and len(photos) > photo_index:
        img_url = str(photos[photo_index]).strip()
        if img_url.startswith("http://") or img_url.startswith("https://"):
            embed.set_image(url=img_url)
        else:
            log.warning(f"⚠️ Phát hiện URL ảnh không hợp lệ trong DB, tự động bỏ qua: {img_url}")
            
    total_photos = max(1, len(photos))
    embed.set_footer(text=f"Vị trí: {role_name} • Ảnh {photo_index + 1}/{total_photos}")
    return embed