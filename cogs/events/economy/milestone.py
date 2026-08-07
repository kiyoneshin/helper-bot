"""
milestone.py — Hệ thống Cột Mốc Sự Kiện (Event Battle Pass)
===========================================================
Lệnh kqua để xem tiến trình
Lệnh knhanqua để nhận phần thưởng
"""

from __future__ import annotations

import json
import logging
from typing import Any

import discord
from discord.ext import commands

from cogs.common.db import (
    execute_db,
    fetchrow_db,
    get_or_create_event_profile,
    add_event_points,
)

log = logging.getLogger("Milestone")

# Cấu hình ID Role (Có thể thay đổi lại ID thực tế của server)
ROLE_DOI_CAO_PHIM = 111111111111111111
ROLE_HUYEN_THOAI = 222222222222222222

ITEM_NAMES = {
    "timeout_1m": "Thẻ Cấm Ngôn (1p)",
    "item_1": "Thẻ Bí Ẩn",
    "shield_card": "Thẻ Bảo Hộ",
    "disconnect_card": "Thẻ Sút Voice",
    "fake_ban_card": "Thẻ Ban Ảo",
    "thief_card": "Thẻ Đạo Tặc",
    "ghost_ping_card": "Thẻ Trêu Ghẹo",
    "jail_card": "Thẻ Bỏ Tù",
}

EVENT_MILESTONES = {
    5000: {"name": "Khởi Động", "points": 0, "items": {"timeout_1m": 1}, "tickets": 10},
    12000: {"name": "Nông Dân Chăm Chỉ", "points": 0, "items": {"item_1": 1, "shield_card": 1}, "tickets": 0},
    25000: {"name": "Lươn Lẹo Bậc Trung", "points": 1500, "items": {"disconnect_card": 1}, "tickets": 0},
    40000: {"name": "Tinh Anh Server", "points": 0, "items": {"fake_ban_card": 1}, "title": "🛡️ Đội Cào Phím", "tickets": 0},
    60000: {"name": "Bàn Tay Đen Tối", "points": 3000, "items": {"thief_card": 1, "ghost_ping_card": 1}, "tickets": 0},
    75000: {"name": "Tuyệt Đỉnh F2P", "points": 10000, "items": {}, "title": "🌟 Tuyệt Đỉnh F2P", "tickets": 0},
    100000: {"name": "Chúa Tể Sự Kiện", "points": 0, "items": {"jail_card": 2}, "title": "🌌 Chúa Tể Sự Kiện", "tickets": 0},
}


async def _init_milestone_tables(bot: commands.Bot) -> None:
    """Cập nhật DB event_profiles thêm cột claimed_milestones nếu chưa có."""
    await execute_db(
        bot,
        "ALTER TABLE event_profiles ADD COLUMN IF NOT EXISTS claimed_milestones JSONB DEFAULT '[]'::jsonb;"
    )


class MilestoneCog(commands.Cog):
    """🎁 Cog quản lý Hệ Thống Cột Mốc Sự Kiện (Event Battle Pass)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Tự động init column khi cog load
        await _init_milestone_tables(self.bot)

    @commands.hybrid_command(name="qua", aliases=["reward", "milestone"])
    async def milestone_cmd(self, ctx: commands.Context) -> None:
        """🎁 Xem tiến trình Cột Mốc Sự Kiện (Event Battle Pass)"""
        uid = str(ctx.author.id)
        row = await fetchrow_db(
            self.bot,
            "SELECT total_earned, claimed_milestones FROM event_profiles WHERE discord_id = $1",
            uid
        )
        
        if row:
            total_earned = float(row["total_earned"]) if row["total_earned"] else 0.0
            raw_claimed = row["claimed_milestones"]
            if raw_claimed:
                claimed_milestones = json.loads(raw_claimed) if isinstance(raw_claimed, str) else raw_claimed
            else:
                claimed_milestones = []
        else:
            total_earned = 0.0
            claimed_milestones = []
            
        embed = discord.Embed(
            title="🎁 TIẾN TRÌNH CỘT MỐC SỰ KIỆN 🎁",
            description=f"Tổng điểm đã cày: **{total_earned:,.2f}** điểm\n*(Tiến trình được tính dựa trên tổng điểm cày cuốc, không bị giảm khi tiêu xài)*\n",
            color=0xffb6c1
        )
        
        for moc_diem, data in EVENT_MILESTONES.items():
            name = data["name"]
            
            percent = min(100, int((total_earned / moc_diem) * 100))
            blocks = percent // 10
            bar = "█" * blocks + "-" * (10 - blocks)
            
            # Xử lý format claimed_milestones để tránh lỗi so sánh string/int
            claimed = str(moc_diem) in claimed_milestones or moc_diem in claimed_milestones
            
            if claimed:
                status = "✅ Đã nhận"
            elif total_earned >= moc_diem:
                status = "🎁 Có thể nhận (Gõ knhanqua)"
            else:
                status = "🔒 Chưa đạt"
                
            rewards = []
            if data.get("points"):
                rewards.append(f"**{data['points']:,}** điểm")
            if data.get("tickets"):
                rewards.append(f"**{data['tickets']}** vé số")
            if data.get("role_id"):
                rewards.append("Role Độc Quyền")
            for item, qty in data.get("items", {}).items():
                item_name = ITEM_NAMES.get(item, item)
                rewards.append(f"**{qty}x** {item_name}")
                
            reward_str = " • ".join(rewards) if rewards else "Không có"
            
            # Hàm format bỏ `.0` nếu không cần thiết
            def _fmt(val: float) -> str:
                s = f"{val:,.2f}"
                if s.endswith(".00"): return s[:-3]
                if s.endswith("0"): return s[:-1]
                return s
            
            embed.add_field(
                name=f"Mốc {_fmt(float(moc_diem))} — {name}",
                value=f"`[{bar}]` {percent}% ({_fmt(total_earned)}/{_fmt(float(moc_diem))})\nTrạng thái: **{status}**\nQuà: {reward_str}",
                inline=False
            )
            
        embed.set_footer(text="Gõ knhanqua để hốt hết quà có thể nhận!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nhanqua", aliases=["claim"])
    async def claim_cmd(self, ctx: commands.Context) -> None:
        """🎁 Nhận tất cả phần thưởng từ các cột mốc đã đạt được."""
        uid = str(ctx.author.id)
        
        # Đảm bảo profile có tồn tại trong db
        await get_or_create_event_profile(self.bot, uid)
        
        row = await fetchrow_db(
            self.bot,
            "SELECT total_earned, claimed_milestones, inventory FROM event_profiles WHERE discord_id = $1",
            uid
        )
        
        if not row:
            await ctx.send("❌ Không tìm thấy hồ sơ của bạn trong hệ thống sự kiện!")
            return
            
        total_earned = float(row["total_earned"]) if row["total_earned"] else 0.0
        
        raw_claimed = row["claimed_milestones"]
        if raw_claimed:
            claimed_milestones = json.loads(raw_claimed) if isinstance(raw_claimed, str) else raw_claimed
        else:
            claimed_milestones = []
            
        raw_inv = row["inventory"]
        if raw_inv:
            inventory = json.loads(raw_inv) if isinstance(raw_inv, str) else raw_inv
        else:
            inventory = {}
            
        valid_milestones = []
        for moc_diem, data in EVENT_MILESTONES.items():
            str_moc = str(moc_diem)
            if total_earned >= moc_diem and str_moc not in claimed_milestones and moc_diem not in claimed_milestones:
                valid_milestones.append((moc_diem, data))
                
        if not valid_milestones:
            await ctx.send("❌ Bạn chưa đạt mốc mới nào hoặc đã nhận hết quà rồi!", ephemeral=True)
            return
            
        total_points = 0.0
        total_tickets = 0
        received_items = {}
        roles_to_add = []
        
        for moc_diem, data in valid_milestones:
            # Ghi nhận vào DB bằng format string
            claimed_milestones.append(str(moc_diem))
            
            if data.get("points"):
                total_points += float(data["points"])
                
            if data.get("tickets"):
                total_tickets += int(data["tickets"])
                
            if data.get("title"):
                roles_to_add.append(data["title"])  # Reuse the variable name but store titles now
                
            for item, qty in data.get("items", {}).items():
                inventory[item] = inventory.get(item, 0) + qty
                received_items[item] = received_items.get(item, 0) + qty
                
        # Thực hiện cộng điểm và cập nhật DB cuối luồng
        if total_points > 0:
            await add_event_points(self.bot, uid, total_points, is_earned=False)
            
        if total_tickets > 0:
            await execute_db(
                self.bot,
                """
                INSERT INTO lottery_tickets (discord_id, tickets) VALUES ($1, $2)
                ON CONFLICT (discord_id) DO UPDATE SET tickets = lottery_tickets.tickets + EXCLUDED.tickets
                """,
                uid, total_tickets
            )
            
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET claimed_milestones = $1::jsonb, inventory = $2::jsonb WHERE discord_id = $3",
            json.dumps(claimed_milestones), json.dumps(inventory), uid
        )
        
        # Cấp danh hiệu
        if roles_to_add:
            latest_title = roles_to_add[-1] # Lấy danh hiệu của mốc cao nhất
            await execute_db(
                self.bot,
                "UPDATE event_profiles SET title = $1 WHERE discord_id = $2",
                latest_title, uid
            )
                
        # Build success embed
        embed = discord.Embed(
            title="🎉 NHẬN THƯỞNG CỘT MỐC THÀNH CÔNG 🎉",
            description=f"Chúc mừng {ctx.author.mention} đã xuất sắc vượt qua các cột mốc mới!\n**Chi tiết phần thưởng:**",
            color=0x57f287
        )
        
        def _fmt(val: float) -> str:
            s = f"{val:,.2f}"
            if s.endswith(".00"): return s[:-3]
            if s.endswith("0"): return s[:-1]
            return s
            
        if total_points > 0:
            embed.add_field(name="Điểm Thưởng", value=f"+**{_fmt(total_points)}** điểm", inline=True)
            
        if total_tickets > 0:
            embed.add_field(name="Vé Xổ Số", value=f"+**{total_tickets}** vé", inline=True)
            
        if roles_to_add and ctx.guild is not None:
            role_mentions = []
            for r_id in roles_to_add:
                r = ctx.guild.get_role(r_id)
                if r:
                    role_mentions.append(r.mention)
                else:
                    role_mentions.append(f"<@&{r_id}>")
            if role_mentions:
                embed.add_field(name="Danh Hiệu", value=", ".join(role_mentions), inline=True)
            
        if received_items:
            item_list = [f"**{qty}x** {ITEM_NAMES.get(item, item)}" for item, qty in received_items.items()]
            embed.add_field(name="Vật Phẩm", value="\n".join(item_list), inline=False)
            
        embed.set_footer(text="Tiếp tục cày cuốc để chinh phục những cột mốc tiếp theo nhé! 🌸")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MilestoneCog(bot))
