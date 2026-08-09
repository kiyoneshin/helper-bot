import discord
import random
import asyncio
from datetime import datetime, timezone
import logging

from cogs.common.db import add_event_points

log = logging.getLogger("DiceLobby")

# Có thể thay đổi ID emoji động tùy thích
ROLLING_EMOJI = "<a:Yb_tt_xucxac:1234567890>"

class DiceLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.players = []
        self.message: discord.Message | None = None
        self.game_started = False
        self.ready_event = asyncio.Event()

    @discord.ui.button(label="🎲 Tham Gia Ngay", style=discord.ButtonStyle.success)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_started:
            await interaction.response.send_message("⚠️ Sảnh đã khóa sổ, chờ ván sau nhé!", ephemeral=True)
            return
            
        if any(p.id == interaction.user.id for p in self.players):
            await interaction.response.send_message("⚠️ Bạn đã ngồi trong sảnh rồi, chờ nhà cái lắc xúc xắc đi!", ephemeral=True)
            return
            
        self.players.append(interaction.user)
        
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.defer()
            return

        embed = interaction.message.embeds[0]
        player_list = "\n".join([f"• {p.mention}" for p in self.players])
        
        embed.set_field_at(0, name=f"👥 Danh sách tham gia ({len(self.players)}/10)", value=player_list, inline=False)
        
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.HTTPException:
            pass
            
        # Kiểm tra đủ 10 người
        if len(self.players) >= 10:
            self.game_started = True
            self.ready_event.set()
            self.stop()

    async def on_timeout(self):
        self.game_started = True
        self.ready_event.set()


async def start_dice_lobby_game(bot, channel: discord.abc.Messageable, core_cog):
    """Khởi chạy minigame Sảnh Xúc Xắc Nhân Phẩm"""
    embed = discord.Embed(
        title="🎲 SẢNH XÚC XẮC NHÂN PHẨM ANGELIC ໒꒱",
        description=(
            "Một sảnh cờ bạc siêu tốc vừa được mở ra! Hãy nhanh tay đăng ký để thử vận may!\n\n"
            "⏳ **Thời gian gom phòng:** 60 giây (hoặc khi đủ 10 người)\n"
            "<:gift_00_symbol:1536003307011842099> **Luật chơi:** Winner Takes All — Người đổ ra tổng điểm cao nhất ăn trọn **100 điểm thưởng**!\n"
            "🌟 **Đặc biệt:** Ai đổ ra bộ đôi hoàn hảo (1-1 hoặc 6-6) sẽ được thưởng nóng thêm **+50 điểm Nhân Phẩm Vô Cực**!"
        ),
        color=0xf1c40f
    )
    embed.add_field(name="👥 Danh sách tham gia (0/10)", value="*Chưa có ai tham gia...*", inline=False)

    view = DiceLobbyView()
    
    try:
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
    except Exception as e:
        log.error(f"Lỗi khi gửi tin nhắn DiceLobby: {e}")
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
        return

    # =================================================================
    # GIAI ĐOẠN 1: GOM PHÒNG (Chờ tối đa 60s)
    # =================================================================
    try:
        await asyncio.wait_for(view.ready_event.wait(), timeout=61.0)
    except asyncio.TimeoutError:
        pass
        
    view.stop()
    
    # Xử lý trường hợp sảnh trống
    if len(view.players) == 0:
        embed.description = "💨 Sảnh đóng cửa vì không có ai tham gia!"
        embed.color = 0x2f3136
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            await msg.edit(embed=embed, view=view)
        except discord.HTTPException:
            pass
            
        core_cog.last_minigame_end = datetime.now(timezone.utc)
        core_cog.is_minigame_running = False
        return

    # =================================================================
    # GIAI ĐOẠN 2: LẮC XÚC XẮC (3.5s)
    # =================================================================
    for item in view.children:
        if isinstance(item, discord.ui.Button):
            item.disabled = True
            
    embed.description = "🎰 **NHÀ CÁI ĐANG LẮC XÚC XẮC... CHỜ CHÚT NÀO!**"
    rolling_list = "\n".join([f"{p.mention} ── {ROLLING_EMOJI} Đang lắc..." for p in view.players])
    embed.set_field_at(0, name=f"👥 Danh sách tham gia ({len(view.players)}/10)", value=rolling_list, inline=False)
    
    try:
        await msg.edit(embed=embed, view=view)
    except discord.HTTPException:
        pass
        
    # Thời gian hồi hộp
    await asyncio.sleep(3.5)
    
    # =================================================================
    # GIAI ĐOẠN 3: CÔNG BỐ KẾT QUẢ VÀ TRAO THƯỞNG
    # =================================================================
    results = []
    max_total = -1
    
    for p in view.players:
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        is_perfect = (d1 == 1 and d2 == 1) or (d1 == 6 and d2 == 6)
        
        results.append({
            "user": p,
            "d1": d1,
            "d2": d2,
            "total": total,
            "is_perfect": is_perfect
        })
        
        if total > max_total:
            max_total = total
            
    # Lọc ra những người bằng điểm cao nhất
    winners = [r for r in results if r["total"] == max_total]
    winner = random.choice(winners)  # Nếu hòa, chọn ngẫu nhiên 1 người
    
    embed.color = 0x57f287
    embed.description = "🎰 **KẾT QUẢ SẢNH XÚC XẮC:**"
    
    result_lines = []
    for r in results:
        p = r["user"]
        line = f"{p.mention} ── 🎲 [{r['d1']}] + [{r['d2']}] = **{r['total']} điểm**"
        
        points_to_add = 0
        # Check thưởng nhân phẩm vô cực
        if r["is_perfect"]:
            line += " 🌟 *[Nhân Phẩm Vô Cực +50đ]*"
            points_to_add += 50
            
        # Check Winner Takes All
        if p.id == winner["user"].id:
            points_to_add += 100
            
        if points_to_add > 0:
            success = await add_event_points(bot, str(p.id), points_to_add, is_earned=True)
            if not success:
                log.error(f"Lỗi cộng điểm {points_to_add} cho {p.id}")
            
        result_lines.append(line)
        
    embed.set_field_at(0, name=f"👥 Danh sách tham gia ({len(view.players)}/10)", value="\n".join(result_lines), inline=False)
    embed.add_field(
        name="👑 CHÚA TỂ NHÂN PHẨM", 
        value=f"Vinh danh {winner['user'].mention} đã thắng áp đảo với **{max_total} điểm** và ẵm trọn giải thưởng!", 
        inline=False
    )
    
    try:
        await msg.edit(embed=embed, view=view)
    except discord.HTTPException:
        pass
        
    # Cleanup RAM
    core_cog.last_minigame_end = datetime.now(timezone.utc)
    core_cog.is_minigame_running = False
