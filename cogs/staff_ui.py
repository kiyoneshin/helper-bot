import discord
from discord.ext import commands
import logging
import json
from typing import Optional

from cogs._staff_db import query_db
from cogs._staff_embeds import get_main_embed
from cogs._staff_views import MainView

log = logging.getLogger("StaffBot")

class StaffUICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.get_command("help"):
            self.bot.remove_command("help")

    @commands.command(name="menu", aliases=["staff", "bqt"])
    async def send_menu(self, ctx: commands.Context):
        """Lệnh hiển thị Menu giới thiệu Ban Quản Trị Angelic"""
        await ctx.send(embed=get_main_embed(), view=MainView(author_id=ctx.author.id))
        log.info(f"🌸 {ctx.author.display_name} vừa mở bảng Menu Staff.")

    @commands.command(name="checkdb")
    async def check_db(self, ctx: commands.Context):
        """Lệnh kiểm tra toàn bộ danh sách đang có trong Database"""
        try:
            records = await query_db(self.bot, "SELECT discord_id, role, display_name FROM profiles")
            if not records:
                await ctx.send("📭 **Database profiles đang TRỐNG!**\n➡️ Hãy lên Railway kiểm tra lại xem dữ liệu bạn nhập đã được ấn phím **Enter** để xác nhận lưu chưa nhé!")
                return
            
            msg = "**📋 Danh sách thực tế đang lưu trong Database:**\n"
            for r in records:
                msg += f"➡️ ID: `{r['discord_id']}` | Role: `{r['role']}` | Tên: **{r['display_name']}**\n"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="voters", aliases=["votelog", "xemvote"])
    async def check_voters(self, ctx: commands.Context, target: Optional[str] = None):
        """Lệnh kiểm tra xem ai đã vote cho ai và bao nhiêu điểm"""
        if not target:
            await ctx.send(
                "⚠️ **Vui lòng nhập ID hoặc ping nhân sự cần xem lịch sử vote!**\n"
                "➡️ Ví dụ chuẩn: `y!voters @Yon Yon Lon Ton` hoặc `y!voters 468428368828956692`"
            )
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()
        
        try:
            records = await query_db(self.bot, "SELECT display_name, role, votes, rating FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send("📭 **Không tìm thấy nhân sự này trong Database!**\n➡️ Vui lòng kiểm tra lại chính xác ID hoặc ping lại.")
                return
            
            row = records[0]
            name = row.get('display_name', 'Unnamed Staff')
            v_data = row.get('votes', {})
            votes_dict = {}
            if isinstance(v_data, str):
                try: votes_dict = json.loads(v_data)
                except Exception: votes_dict = {}
            elif isinstance(v_data, dict):
                votes_dict = v_data
            elif isinstance(v_data, list):
                for idx, s in enumerate(v_data):
                    if isinstance(s, (int, float)):
                        votes_dict[f"old_voter_{idx}"] = float(s)

            if not votes_dict:
                await ctx.send(f"⭐ Hồ sơ của **{name}** hiện tại **chưa có lượt đánh giá nào!**")
                return

            details = ""
            for idx, (voter_id, score) in enumerate(votes_dict.items(), 1):
                if voter_id.startswith("old_"):
                    details += f"**{idx}.** Người dùng ẩn danh *(Dữ liệu cũ)*: **{score} ⭐**\n"
                else:
                    details += f"**{idx}.** <@{voter_id}> (`{voter_id}`): **{score} ⭐**\n"
            
            desc_text = f"➡️ Điểm trung bình hiện tại: **⭐ {row.get('rating', 0.0)}/5.0** ({len(votes_dict)} lượt)\n\n**Chi tiết từng lượt vote:**\n{details}"
            embed = discord.Embed(
                title=f"📋 Lịch Sử Đánh Giá Của {name}",
                description=desc_text,
                color=0xffb6c1
            )
            embed.set_footer(text="Angelic Bot • Hệ thống tự động ngăn chặn vote lặp lại 2 lần!")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn Database: {e}")

    @commands.command(name="help", aliases=["huongdan", "lenh", "commands"])
    async def help_cmd(self, ctx: commands.Context):
        """Lệnh hiển thị danh sách toàn bộ các câu lệnh của Bot"""
        embed = discord.Embed(
            title="📖 Bảng Hướng Dẫn Câu Lệnh Angelic Bot ໒꒱",
            description="Dưới đây là toàn bộ các câu lệnh khả dụng mà bạn có thể sử dụng trên server:",
            color=0xffb6c1
        )
        
        embed.add_field(
            name="✨ Lệnh Giao Diện & Nhân Sự",
            value=(
                "➡️ `y!menu` (hoặc `y!staff`, `y!bqt`): Mở bảng giao diện xem danh sách và thông tin Ban Quản Trị.\n"
                "➡️ `y!voters <@user/ID>`: Xem chi tiết danh sách những ai đã vote cho một Staff và số điểm cụ thể.\n"
                "➡️ `y!checkdb`: Kiểm tra nhanh danh sách toàn bộ nhân sự đang được lưu trong Cơ Sở Dữ Liệu.\n"
                "➡️ `y!addstaff <id> <role> <tên>`: Thêm nhanh một nhân sự mới vào hệ thống Database."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📌 Lệnh Hệ Thống",
            value=(
                "➡️ `y!help` (hoặc `y!huongdan`): Hiển thị bảng hướng dẫn câu lệnh này."
            ),
            inline=False
        )
        
        embed.set_footer(text="Angelic Bot • Sử dụng mũi tên để điều hướng các menu dễ dàng hơn!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StaffUICog(bot))