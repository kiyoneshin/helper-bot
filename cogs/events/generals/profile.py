"""
profile.py — Lệnh Xem Hồ Sơ Cá Nhân (Profile) RPG
==================================================
Hiển thị căn cước công dân của người chơi trong hệ thống sự kiện.
"""
import discord
from discord.ext import commands
from typing import Optional
import random

from cogs.common.db import check_not_locked, fetchrow_db, get_or_create_event_profile
import json

# Import cấu hình tên công cụ (để chuyển từ Level sang Tên đẹp)
from cogs.events.woodcutting.woodcutting_config import AXE_NAMES
from cogs.events.mining.mining_config import PICKAXE_NAMES
from cogs.events.fishing.fishing_config import ROD_NAMES
from cogs.events.economy.milestone import EVENT_MILESTONES

async def fetch_user_profile_data(bot: commands.Bot, user_id: str) -> dict:
    """Lấy dữ liệu thực tế từ event_profiles."""
    await get_or_create_event_profile(bot, user_id)
    sql = "SELECT points, event_coins, total_earned, title, marry_to, farm_data, stats, claimed_milestones FROM event_profiles WHERE discord_id = $1"
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
        
    db_title = row["title"]
    if not db_title or db_title == "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang":
        db_title = "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang"
        claimed_str = row.get("claimed_milestones")
        if claimed_str:
            claimed = json.loads(claimed_str) if isinstance(claimed_str, str) else claimed_str
            max_moc = 0
            for moc, m_data in EVENT_MILESTONES.items():
                if (moc in claimed or str(moc) in claimed) and "title" in m_data:
                    if moc > max_moc:
                        max_moc = moc
                        db_title = m_data["title"]
                        
            # Sync ngược lại vào DB nếu tìm thấy title cao hơn
            if db_title != "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang":
                bot.loop.create_task(
                    getattr(bot, "db_pool").execute("UPDATE event_profiles SET title = $1 WHERE discord_id = $2", db_title, user_id)
                )
        
    return {
        "title": db_title,
        "marry_to": row["marry_to"],
        "points": float(row["points"] or 0.0),
        "event_coins": float(row["event_coins"] or 0.0),
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
    """Căn Cước Công Dân RPG."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="profile", aliases=["p", "pro", "ep"])
    async def profile_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """[Sự Kiện] Xem thông tin cá nhân, Số dư, Thú cưng, Thẻ đặc quyền."""
        if member:
            target_member = member
        elif isinstance(ctx.author, discord.Member):
            target_member = ctx.author
        else:
            return await ctx.send("Lệnh này chỉ dùng trong server!")

        pool = getattr(self.bot, "db_pool", None)
        if not pool:
            return await ctx.send("Lỗi: Không thể kết nối đến cơ sở dữ liệu.")
            
        # Gọi hàm helper lấy dữ liệu
        data = await fetch_user_profile_data(self.bot, str(target_member.id))
        
        # Tạo Embed với màu sắc ngẫu nhiên hoặc màu đặc trưng
        embed = discord.Embed(
            title=f"Căn Cước Công Dân — {target_member.display_name}",
            description="*Hồ sơ thám hiểm và thành tích trong thế giới Angelic.*",
        )
        embed.set_thumbnail(url=target_member.display_avatar.url)
        
        # 1. THÔNG TIN CHUNG
        from cogs.common.item_config import ITEM_REGISTRY
        from cogs.common.db import get_marriage
        
        marry_status = "<:symbol_heart_breaking:1536296911655673936> Độc thân vui tính"
        if data.get("marry_to"):
            mar = await get_marriage(self.bot, str(target_member.id))
            ring_icon = "<:icon_02_ring:1536017180951318528>"
            if mar:
                ring_id = mar.get("ring_id")
                if ring_id and ring_id in ITEM_REGISTRY:
                    ring_icon = ITEM_REGISTRY[ring_id]["icon"]
            marry_status = f"{ring_icon} Đã kết hôn với <@{data['marry_to']}>"
            
        title_str = data.get("title", "Chưa có danh hiệu")
        
        embed.add_field(
            name="<:symbol_id_card:1536320112565555240> Thông Tin Cá Nhân",
            value=f"**Danh hiệu:** {title_str}\n**Tình trạng:** {marry_status}",
            inline=False
        )
        
        # 2. TÀI SẢN & KINH TẾ
        points = data.get("points", 0)
        event_coins = data.get("event_coins", 0)
        total_earned = data.get("total_earned", 0)
        
        embed.add_field(
            name="<:symbol_money_bag:1537567538097954896> Tài Sản & Ngân Khố",
            value=(
                f"<:symbol_money:1537466097282842775> **Số dư:** {int(points):,.0f} <:symbol_points_p:1538282388507987989>\n"
                f"<:symbol_point_e:1538282386351984660> **Điểm Tích Lũy:** {int(event_coins):,.0f} <:symbol_point_e:1538282386351984660>\n"
                f"<:symbol_point_l:1538301121909755964> **Tổng Cày Cuốc:** {int(total_earned):,.0f} <:symbol_point_l:1538301121909755964>"
            ),
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
            name="<:symbol_00_crafting:1536007686389235733> Hành Trang (Tools)",
            value=(
                f"<:symbol_00_woodcutting:1536007697491558491> **Rìu:** {axe_name}\n"
                f"<:symbol_00_mining:1536007694920585356> **Cuốc:** {pick_name}\n"
                f"<:symbol_00_fishing:1536007692437422171> **Cần Câu:** {rod_name}"
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
            name="Bảng Vàng Thành Tích",
            value=(
                f"<:symbol_boards:1536007665153474681> **Nhiệm vụ (Quests):** {quests}\n"
                f"<:icon_04_seed:1536017185057546242> **Cây trồng (Harvests):** {crops}\n"
                f"<:symbol_00_woodcutting:1536007697491558491> **Chặt gỗ (Works):** {works}\n"
                f"<:symbol_00_mining:1536007694920585356> **Đập đá (Mines):** {mines}\n"
                f"<:symbol_00_fishing:1536007692437422171> **Câu cá (Fishes):** {fishes}\n"
                f"<a:pet_cat:1535998182029398046> **Vô chuồng chó (Jails):** {jail} Lần"
            ),
            inline=False
        )
        
        # Footer trang trí
        embed.set_footer(text="Angelic RPG • Hành trình không hồi kết 🌸")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
