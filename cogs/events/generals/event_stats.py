"""
event_stats.py — Quản lý điểm số & Bảng xếp hạng sự kiện
======================================================
Cung cấp các lệnh kpoint (xem ví) và ketop (bảng xếp hạng).
"""
import discord
from discord.ext import commands
from typing import Any

from cogs.common.db import get_or_create_event_profile, query_db, update_task_progress

from typing import Any, Optional

class TopLeaderboardView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: Optional[discord.Guild], current_page: str = "total"):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.guild = guild
        self.current_page = current_page
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        
        btn_total = discord.ui.Button(
            label="Đua Top (Cày Cuốc)", 
            style=discord.ButtonStyle.primary if self.current_page == "total" else discord.ButtonStyle.secondary,
            disabled=(self.current_page == "total")
        )
        btn_total.callback = self.show_total
        self.add_item(btn_total)
        
        btn_points = discord.ui.Button(
            label="Thần Bài (Số Dư)", 
            style=discord.ButtonStyle.primary if self.current_page == "points" else discord.ButtonStyle.secondary,
            disabled=(self.current_page == "points")
        )
        btn_points.callback = self.show_points
        self.add_item(btn_points)

    async def _generate_embed(self) -> discord.Embed:
        if self.current_page == "total":
            sql = """
                SELECT discord_id, total_earned, points 
                FROM event_profiles 
                WHERE total_earned > 0 
                ORDER BY total_earned DESC 
                LIMIT 10;
            """
            title = "🏆 Bảng Xếp Hạng Đua Top Cày Cuốc ໒꒱"
            desc_prefix = "Vinh danh Top 10 chiến thần tích lũy điểm cày cuốc:\n\n"
            footer = "Bảng xếp hạng dựa trên tổng điểm cày được (không bị trừ khi mua shop) 🌸"
        else:
            sql = """
                SELECT discord_id, total_earned, points 
                FROM event_profiles 
                WHERE points > 0 
                ORDER BY points DESC 
                LIMIT 10;
            """
            title = "<a:gambling_slot_machine_pixel:1536322200838340628> Bảng Xếp Hạng Thần Bài (Số Dư) ໒꒱"
            desc_prefix = "Vinh danh Top 10 đại gia nắm giữ nhiều tiền nhất server:\n\n"
            footer = "Bảng xếp hạng dựa trên số dư hiện tại 🌸"
            
        rows = await query_db(self.bot, sql)
        
        embed = discord.Embed(title=title, color=0xffb6c1)
        if not rows:
            embed.description = "Bảng xếp hạng hiện đang trống!"
        else:
            medals = ["🥇", "🥈", "🥉"]
            leaderboard_text = ""
            for idx, row in enumerate(rows):
                rank_icon = medals[idx] if idx < 3 else f"**#{idx + 1}.**"
                user_id = row["discord_id"]
                t_pts = row["total_earned"]
                c_pts = row["points"]
                
                if self.current_page == "total":
                    leaderboard_text += f"{rank_icon} <@{user_id}>\n└ 🏆 Tổng cày: **`{t_pts:,}`** điểm *(Dư: `{c_pts:,}`)*\n\n"
                else:
                    leaderboard_text += f"{rank_icon} <@{user_id}>\n└ 💰 Số dư: **`{c_pts:,}`** điểm *(Cày được: `{t_pts:,}`)*\n\n"
                    
            embed.description = desc_prefix + leaderboard_text
            
        icon_url = self.guild.icon.url if self.guild and self.guild.icon else None
        if icon_url:
            embed.set_thumbnail(url=icon_url)
        embed.set_footer(text=footer)
        return embed

    async def show_total(self, interaction: discord.Interaction):
        self.current_page = "total"
        self._update_buttons()
        emb = await self._generate_embed()
        await interaction.response.edit_message(embed=emb, view=self)
        
    async def show_points(self, interaction: discord.Interaction):
        self.current_page = "points"
        self._update_buttons()
        emb = await self._generate_embed()
        await interaction.response.edit_message(embed=emb, view=self)


class EventStatsCog(commands.Cog):
    """Cog Quản lý điểm số và Bảng xếp hạng Sự Kiện."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="point", aliases=["bal", "vi"])
    async def point_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        """Kiểm tra số dư và tổng điểm sự kiện của bạn (hoặc người khác)."""
        target = member or ctx.author
        uid = str(target.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        
        if not profile:
            if target == ctx.author:
                await ctx.send("Không thể lấy dữ liệu hồ sơ sự kiện của bạn lúc này. Vui lòng thử lại sau!")
            else:
                await ctx.send("Không thể lấy dữ liệu hồ sơ sự kiện của người này. Có thể họ chưa tham gia!")
            return

        points = profile.get("points", 0)
        total_earned = profile.get("total_earned", 0)
        p2w = float(profile.get("p2w_multiplier", 1.0))
        
        if p2w <= 1.0:
            rank = "Dân Cày Chay 👥"
        elif p2w < 1.75:
            rank = "Đại Gia Tầm Trung 🌸"
        else:
            rank = "Chúa Tể P2W 👑"

        embed = discord.Embed(
            title=f"<:symbol_credit_card:1536308433693712404> Ví Sự Kiện Angelic — {target.display_name}",
            description=f"Hạng của họ: **{rank}**" if target != ctx.author else f"Hạng của bạn: **{rank}**",
            color=0xffb6c1
        )
        embed.add_field(
            name="🪙 Số dư hiện tại",
            value=f"`{points:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="🏆 Tổng điểm tích lũy",
            value=f"`{total_earned:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="⚡ Hệ số P2W",
            value=f"`x{p2w:.2f}`",
            inline=True
        )
        
        debt = profile.get("debt", 0.0)
        max_loan = total_earned * 0.5
        
        if debt > 0:
            embed.add_field(
                name="💸 Nợ ngân hàng",
                value=f"`{debt:,.0f}` điểm",
                inline=False
            )
        embed.add_field(
            name="🏦 Hạn mức vay",
            value=f"`{max_loan:,.0f}` điểm",
            inline=True if debt == 0 else False
        )
        
        embed.set_footer(text=f"Gõ {ctx.prefix}shop để xem cửa hàng đổi quà nhé! 🌸")
        await ctx.send(embed=embed)
        
        # Nhiệm vụ
        await update_task_progress(self.bot, uid, "check_bal", 1)

    @commands.hybrid_command(name="etop", aliases=["evtop", "eventtop", "eventop"])
    async def etop_cmd(self, ctx: commands.Context) -> None:
        """Xem Bảng Xếp Hạng Đua Top Điểm Sự Kiện."""
        try:
            view = TopLeaderboardView(self.bot, ctx.guild)
            emb = await view._generate_embed()
            await ctx.send(embed=emb, view=view)
            
            # Nhiệm vụ
            await update_task_progress(self.bot, ctx.author.id, "check_top", 1)
        except Exception as e:
            import traceback
            with open("error_etop.txt", "w") as f:
                f.write(traceback.format_exc())
            await ctx.send(f"Đã xảy ra lỗi: {e}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventStatsCog(bot))
