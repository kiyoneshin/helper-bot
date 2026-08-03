"""
profile.py — Lệnh Xem Hồ Sơ Cá Nhân (Profile) RPG
==================================================
Hiển thị căn cước công dân của người chơi trong hệ thống sự kiện.
"""
import discord
from discord.ext import commands
import random

from cogs.common.db import check_not_locked

# Import cấu hình tên công cụ (để chuyển từ Level sang Tên đẹp)
from cogs.events.woodcutting.woodcutting_config import AXE_NAMES
from cogs.events.mining.mining_config import PICKAXE_NAMES
from cogs.events.fishing.fishing_config import ROD_NAMES

async def fetch_user_profile_data(bot: commands.Bot, user_id: str) -> dict:
    """
    Hàm helper placeholder để lấy dữ liệu Profile của user.
    Hiện tại trả về dữ liệu mẫu (mock data).
    Bạn có thể đắp câu lệnh SQL query asyncpg vào đây sau.
    """
    # TODO: Tự viết câu lệnh SQL query vào DB của bạn ở đây
    # Ví dụ:
    # sql = "SELECT * FROM event_profiles WHERE discord_id = $1"
    # data = await bot.db_pool.fetchrow(sql, user_id)
    
    return {
        "title": "👑 Kẻ Lang Thang",  # Danh hiệu
        "marry_to": None,            # ID của người kết hôn, hoặc None nếu độc thân
        "points": 15000,             # Tiền/Điểm cơ bản
        "event_coin": 350,           # Tiền sự kiện (ví dụ: Coconuts)
        
        "axe_level": 2,              # Level rìu
        "pickaxe_level": 3,          # Level cuốc
        "rod_level": 1,              # Level cần câu
        
        "quests_completed": 12,      # Số Quest đã làm
        "crops_harvested": 150,      # Số cây đã thu hoạch
        "jail_count": 3,             # Số lần vào chuồng chó
    }

class ProfileCog(commands.Cog, name="Profile"):
    """👤 Căn Cước Công Dân RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="profile", aliases=["p", "pro"])
    @check_not_locked()
    async def profile_cmd(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """👤 Xem hồ sơ cá nhân của bạn hoặc người khác."""
        target = member or ctx.author
        
        # Gọi hàm helper lấy dữ liệu
        data = await fetch_user_profile_data(self.bot, str(target.id))
        
        # Tạo Embed với màu sắc ngẫu nhiên hoặc màu đặc trưng
        embed = discord.Embed(
            title=f"📜 Căn Cước Công Dân — {target.display_name}",
            description="*Hồ sơ thám hiểm và thành tích trong thế giới Angelic.*",
            color=target.color if target.color.value != 0 else discord.Color.random(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # 1. THÔNG TIN CHUNG
        marry_status = f"💍 Đã kết hôn với <@{data['marry_to']}>" if data.get("marry_to") else "💔 Độc thân vui tính"
        title_str = data.get("title", "Chưa có danh hiệu")
        
        embed.add_field(
            name="🎫 Thông Tin Cá Nhân",
            value=f"**Danh hiệu:** {title_str}\n**Tình trạng:** {marry_status}",
            inline=False
        )
        
        # 2. TÀI SẢN & KINH TẾ
        points = data.get("points", 0)
        coconuts = data.get("event_coin", 0)
        
        embed.add_field(
            name="💰 Tài Sản & Ngân Khố",
            value=f"💵 **Tiền/Điểm:** {points:,.0f}\n🥥 **Dừa Mùa Hè:** {coconuts:,.0f}",
            inline=True
        )
        
        # 3. CÔNG CỤ HÀNH NGHỀ (TOOLS)
        axe_lv = data.get("axe_level", 1)
        pick_lv = data.get("pickaxe_level", 1)
        rod_lv = data.get("rod_level", 1)
        
        # Lấy tên công cụ từ Config
        axe_name = AXE_NAMES.get(axe_lv, f"Lv{axe_lv}")
        pick_name = PICKAXE_NAMES.get(pick_lv, f"Lv{pick_lv}")
        rod_name = ROD_NAMES.get(rod_lv, f"Lv{rod_lv}")
        
        embed.add_field(
            name="🛠️ Hành Trang (Tools)",
            value=(
                f"🪓 **Rìu:** {axe_name}\n"
                f"⛏️ **Cuốc:** {pick_name}\n"
                f"🎣 **Cần Câu:** {rod_name}"
            ),
            inline=True
        )
        
        # 4. THỐNG KÊ HOẠT ĐỘNG
        quests = data.get("quests_completed", 0)
        crops = data.get("crops_harvested", 0)
        jail = data.get("jail_count", 0)
        
        embed.add_field(
            name="📊 Bảng Vàng Thành Tích",
            value=(
                f"🎯 **Nhiệm vụ:** {quests} Quests\n"
                f"🌱 **Nông trại:** {crops} Cây\n"
                f"🐕 **Vô chuồng chó:** {jail} Lần"
            ),
            inline=False
        )
        
        # Footer trang trí
        embed.set_footer(text="Angelic RPG • Hành trình không hồi kết 🌸")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
