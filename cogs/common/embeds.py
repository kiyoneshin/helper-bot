import discord
import json
import logging
from typing import Optional

log = logging.getLogger("StaffEmbeds")

def get_main_embed() -> discord.Embed:
    """Tạo Embed chào mừng gọn gàng ở trang đầu tiên của Menu BQT"""
    embed = discord.Embed(
        title="🏠 Chào mừng đến với Angelic ໒꒱",
        description=(
            "Tiếng chuông nhà thờ khẽ ngân vang, cánh cổng thiên đường đã mở rộng chào đón bạn! ଘ(੭ˊᵕˋ)੭\n"
            "Hãy biến nơi đây thành mái nhà bình yên để cùng trò chuyện, chơi game, chữa lành và lưu giữ những kỷ niệm đẹp nhé.\n\n"
            "*🌸 Vui lòng chọn menu phía dưới để làm quen với danh sách Ban Quản Trị!*"
        ),
        color=0xffb6c1
    )
    return embed


def get_rules_embed() -> discord.Embed:
    """Tạo Embed hiển thị bảng luật riêng cho lệnh krule"""
    embed = discord.Embed(
        title="📜 ĐIỀU LỆ SERVER ANGELIC ໒꒱",
        description=(
            "**1. Văn hóa ứng xử & Giao tiếp:**\n"
            "• Tôn trọng tất cả thành viên và Ban Quán Trị. Đùa giỡn có chừng mực, nghiêm cấm các hành vi toxic, nói xấu sau lưng, gây war, drama hoặc lôi kéo mâu thuẫn cá nhân vào server.\n"
            "• **Hạn chế tối đa nói tục và đùa giỡn nhạy cảm (sex joke).** Tùy thuộc vào mức độ vi phạm, bot và staff sẽ xử lý từ cảnh cáo, mute (tắt tiếng) cho đến ban (khóa tài khoản) vĩnh viễn.\n\n"
            
            "**2. Nội dung nhạy cảm & Cấm kỵ:**\n"
            "• Tuyệt đối không gửi các nội dung liên quan đến NSFW (đồi trụy) và máu me/kinh dị. Server không phải là không gian chia sẻ các nội dung này. Nếu muốn gửi, bạn chỉ được phép hoạt động trong đúng kênh quy định: <#1512138257771532469>.\n\n"
            
            "**3. Các lằn ranh đỏ (BAN THẲNG TAY KHÔNG PHÚC KHẢO):**\n"
            "• **Phân biệt vùng miền (PBVM):** Khóa tài khoản vĩnh viễn ngay lập tức.\n"
            "• **Phân biệt chủng tộc (PBCT):** Nhẹ thì mute cảnh cáo, nặng sẽ ban thẳng.\n"
            "• **Sử dụng công cụ phá hoại:** Nghiêm cấm xài các loại tool spam, nuke, raid server.\n"
            "• Mạo danh người khác hoặc giả mạo danh nghĩa của Staff.\n\n"
            
            "**4. Giữ gìn trật tự & An toàn chung:**\n"
            "• Không spam tin nhắn, emoji, sticker, gif hoặc cố tình liên tục tag (ping) gây phiền hà, khó chịu cho người khác.\n"
            "• Cấm mọi hình thức quảng cáo server khác, chia sẻ link ngoài khi chưa được Admin cho phép.\n"
            "• Cấm các hành vi mua bán, giao dịch, trao đổi thương mại trong server dưới mọi hình thức để tránh lừa đảo.\n\n"
            
            "**5. Quy định về Không gian chung & Kênh hỗ trợ:**\n"
            "• Chat đúng chủ đề và mục đích của từng kênh. Không tự ý vào phá room voice hoặc làm phiền không gian riêng của người khác.\n"
            "• Không spam ticket hoặc tự ý mở ticket khi không thực sự cần thiết. Luôn luôn tuân thủ và hợp tác theo lời nhắc nhở/hướng dẫn của Staff.\n\n"
            
            "**<:symbol_alert:1537546957885542450> 6. Quy định đặc biệt về Hệ thống Role Độ tuổi:**\n"
            "• Khi bạn tự chọn (pick) role liên quan đến độ tuổi của bản thân, **bắt buộc phải chọn đúng số tuổi thật**. Nếu hệ thống hoặc Ban Quản Trị phát hiện bất kỳ hành vi khai gian tuổi nào, tài khoản đó sẽ bị **BAN vĩnh viễn khỏi server ngay lập tức** (Quy định này áp dụng nghiêm túc cho tất cả mọi người, kể cả Staff)."
        ),
        color=0xffb6c1
    )
    embed.set_footer(text="Angelic Bot • Hãy tuân thủ luật để xây dựng một môi trường văn minh nhé! 🌸")
    return embed


def build_embed(user_data: dict, member: Optional[discord.Member] = None, photo_index: int = 0) -> discord.Embed:
    """Tạo Embed hiển thị Profile của Staff"""
    display_name = user_data.get('display_name', 'Unnamed Staff')
    role_name = user_data.get('role', 'staff')

    embed = discord.Embed(
        title=f"✨ {display_name} ✨",
        color=0xffb6c1
    )

    # --- Phần mô tả: dòng vị trí + danh sách tags ---
    tags = user_data.get('tags', [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    tags_text = "\n".join(f"♱ {t}" for t in tags) if tags else "(trống)"
    embed.description = f"**Vị trí:** {role_name.upper()}\n\n**Tags**\n{tags_text}"

    description_value = user_data.get('description') or "(trống)"
    contact_value = user_data.get('contact') or "(trống)"

    embed.add_field(name="Giới thiệu bản thân", value=description_value, inline=False)
    embed.add_field(name="Liên hệ", value=contact_value, inline=False)

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
            log.warning(f"Phát hiện URL ảnh không hợp lệ trong DB, tự động bỏ qua: {img_url}")

    # --- Footer ---
    total_photos = max(1, len(photos))
    embed.set_footer(text=f"Ảnh {photo_index + 1}/{total_photos}")
    return embed