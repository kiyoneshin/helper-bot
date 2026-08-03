"""
profile.py — Lệnh Xem Hồ Sơ Cá Nhân (Profile) RPG
==================================================
Hiển thị căn cước công dân của người chơi trong hệ thống sự kiện.
"""
import discord
from discord.ext import commands
import random

from cogs.common.db import check_not_locked, fetchrow_db, get_or_create_event_profile
import json

# Import cấu hình tên công cụ (để chuyển từ Level sang Tên đẹp)
from cogs.events.woodcutting.woodcutting_config import AXE_NAMES
from cogs.events.mining.mining_config import PICKAXE_NAMES
from cogs.events.fishing.fishing_config import ROD_NAMES

async def fetch_user_profile_data(bot: commands.Bot, user_id: str) -> dict:
    """Lấy dữ liệu thực tế từ event_profiles."""
    await get_or_create_event_profile(bot, user_id)
    sql = "SELECT points, total_earned, title, marry_to, farm_data, stats FROM event_profiles WHERE discord_id = $1"
    row = await fetchrow_db(bot, sql, user_id)
    
    if not row:
        return {}
        
    farm_data = row["farm_data"]
    if farm_data:
        if isinstance(farm_data, str): farm_data = json.loads(farm_data)
    else:
        farm_data = {}
        
    stats = row["stats"]
    if stats:
        if isinstance(stats, str): stats = json.loads(stats)
    else:
        stats = {}
        
    return {
        "title": row["title"] or "👑 Kẻ Lang Thang",
        "marry_to": row["marry_to"],
        "points": float(row["points"] or 0.0),
        "total_earned": float(row["total_earned"] or 0.0),
        
        "axe_level": int(farm_data.get("axe_level", 1)),
        "pickaxe_level": int(farm_data.get("pickaxe_level", 1)),
        "rod_level": int(farm_data.get("rod_level", 1)),
        
        "quests_completed": int(stats.get("quests", 0)),
        "crops_harvested": int(stats.get("crops", 0)),
        "jail_count": int(stats.get("jails", 0)),
        "works_done": int(stats.get("works", 0)),
        "mines_done": int(stats.get("mines", 0)),
        "fishes_done": int(stats.get("fishes", 0)),
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
        total_earned = data.get("total_earned", 0)
        
        embed.add_field(
            name="💰 Tài Sản & Ngân Khố",
            value=f"💵 **Số dư (Khả dụng):** {points:,.0f}\n🏆 **Tổng Điểm (Milestones):** {total_earned:,.0f}",
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
        works = data.get("works_done", 0)
        mines = data.get("mines_done", 0)
        fishes = data.get("fishes_done", 0)
        
        embed.add_field(
            name="📊 Bảng Vàng Thành Tích",
            value=(
                f"🎯 **Nhiệm vụ (Quests):** {quests}\n"
                f"🌱 **Cây trồng (Harvests):** {crops}\n"
                f"🪓 **Chặt gỗ (Works):** {works}\n"
                f"⛏️ **Đập đá (Mines):** {mines}\n"
                f"🎣 **Câu cá (Fishes):** {fishes}\n"
                f"🐕 **Vô chuồng chó (Jails):** {jail} Lần"
            ),
            inline=False
        )
        
        # Footer trang trí
        embed.set_footer(text="Angelic RPG • Hành trình không hồi kết 🌸")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
