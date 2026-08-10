import time
from typing import Any, Dict
import discord
from discord.ext import commands

from .config import SEEDS, STATUS_GROWING, STATUS_READY, STATUS_WITHERED, WATER_BONUS, QUALITY_EMOJIS
from .farm_db import water_all, harvest_all, calculate_crop_status, get_farm_data, remove_crop
from cogs.common.db import fetchval_db, deduct_event_points, add_event_points


class FarmView(discord.ui.View):
    """View chính của Nông Trại chứa các nút tương tác."""
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, farm_data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        # Dropdown gieo trồng đã được thay thế bằng lệnh kplant
        
    @discord.ui.button(label="Tưới Nước Tất Cả", emoji="<:symbol_watering_can:1536295381862715453>", style=discord.ButtonStyle.primary, row=0)
    async def water_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return
            
        ok, count = await water_all(self.bot, self.user_id)
        if count == 0:
            await interaction.response.send_message("💦 Không có cây nào đang trong giai đoạn phát triển cần tưới!", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"💦 Đã tưới nước cho **{count}** cây! (Thời gian sinh trưởng giảm {int(WATER_BONUS * 100)}%)", ephemeral=True)
        
    @discord.ui.button(label="Thu Hoạch", emoji="<:button_harvesting:1536007671445061763>", style=discord.ButtonStyle.success, row=1)
    async def harvest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return
            
        ok, report = await harvest_all(self.bot, self.user_id)
        harvested = report.get("harvested", {})
        withered = report.get("withered", 0)
        
        if not harvested and withered == 0:
            await interaction.response.send_message("🧺 Không có cây nào sẵn sàng để thu hoạch hoặc bị héo!", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        msg = []
        if harvested:
            details = []
            for item_id, qty in harvested.items():
                parts = item_id.split("_")
                quality = parts[-1] if len(parts) > 1 else "normal"
                seed_id = "_".join(parts[:-1]) if len(parts) > 1 else item_id
                
                seed_info = SEEDS.get(seed_id, {})
                seed_name = seed_info.get("name", seed_id)
                emoji = QUALITY_EMOJIS.get(quality, "")
                
                details.append(f"**{qty}x** {seed_name} {emoji}".strip())
                
            msg.append(f"<:symbol_right:1536289313959186472> Thu hoạch thành công: " + ", ".join(details))
            
        if withered > 0:
            msg.append(f"🥀 Đã dọn dẹp **{withered}** cây bị héo.")
            
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send("\n".join(msg), ephemeral=True)

    @discord.ui.button(label="Cuốc Bỏ", emoji="<:symbol_scythe:1536007681502875669>", style=discord.ButtonStyle.danger, row=1)
    async def clear_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return
            
        await interaction.response.send_modal(ClearSlotModal(self.bot, self.user_id, self.author, self))

    @discord.ui.button(label="Làm Mới", emoji="<:symbol_reload:1536007679640600648>", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)


class ClearSlotModal(discord.ui.Modal, title="Cuốc Bỏ Cây Trồng"):
    slot_input = discord.ui.TextInput(
        label="Nhập số thứ tự ô đất (VD: 1, 2, 3)",
        placeholder="Chỉ nhập số nguyên...",
        min_length=1,
        max_length=2,
        required=True
    )
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, view: FarmView):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.view_obj = view
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            slot_id = int(self.slot_input.value.strip())
        except ValueError:
            await interaction.response.send_message("<:symbol_wrong:1536289315867598849> Giá trị không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)
            return
            
        ok, msg = await remove_crop(self.bot, self.user_id, str(slot_id))
        if not ok:
            await interaction.response.send_message(f"<:symbol_wrong:1536289315867598849> {msg}", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"<:symbol_right:1536289313959186472> {msg} (Tại Ô {slot_id})", ephemeral=True)


def build_farm_embed(author: discord.Member | discord.User, farm_data: Dict[str, Any]) -> discord.Embed:
    """
    Render giao diện text hiển thị trực quan các ô đất.
    Thay đổi icon cây trồng dựa theo tiến trình sinh trưởng.
    """
    try:
        from .weather import get_current_weather
        weather = get_current_weather()
        weather_str = f"**Thời tiết hiện tại:** {weather['emoji']} **{weather['name']}**\n*{weather['desc']}*\n"
    except Exception:
        weather_str = ""

    embed = discord.Embed(
        title=f"🌻 Nông Trại Của {author.display_name}",
        description=f"Chào mừng bạn đến với khu vườn nhàn rỗi!\n\n{weather_str}",
        color=0x2ecc71
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660951791997071.gif")
    
    slots = farm_data.get("slots", 3)
    crops = farm_data.get("crops", {})
    
    current_time = int(time.time())
    
    # 1. Tạo Ma Trận 3x3
    grid_cells = []
    crop_details = []
    
    for i in range(1, 10): # Từ 1 đến 9
        if i > slots:
            grid_cells.append(f"[{i}] 🔒")
            continue
            
        slot_key = str(i)
        if slot_key not in crops:
            grid_cells.append(f"[{i}] 🟫")
            continue
            
        crop = crops[slot_key]
        seed_id = crop.get("seed")
        seed_info = SEEDS.get(seed_id)
        
        if not seed_info:
            grid_cells.append(f"[{i}] ❓")
            continue
            
        status, remaining = calculate_crop_status(crop, slot_key, crops)
        seed_name = seed_info["name"]
        seed_icon = seed_info["icon"]
        
        if status == STATUS_GROWING:
            planted_at = crop.get("planted_at", 0)
            watered = crop.get("watered", False)
            
            req_time = seed_info["grow_time_seconds"]
            if watered:
                req_time -= int(req_time * WATER_BONUS)
            
            # Tính Bonus Adjacency
            has_star = False
            ADJACENCY_MAP = {
                "1": ["2", "4"], "2": ["1", "3", "5"], "3": ["2", "6"],
                "4": ["1", "5", "7"], "5": ["2", "4", "6", "8"], "6": ["3", "5", "9"],
                "7": ["4", "8"], "8": ["5", "7", "9"], "9": ["6", "8"]
            }
            if slot_key in ADJACENCY_MAP:
                for neighbor_id in ADJACENCY_MAP[slot_key]:
                    if neighbor_id in crops and crops[neighbor_id].get("seed") == "star":
                        has_star = True
                        break
            if has_star:
                req_time -= int(req_time * 0.20)
            
            elapsed = current_time - planted_at
            progress = elapsed / req_time if req_time > 0 else 1.0
            
            if progress < 0.3:
                icon = "🌱"
            elif progress < 0.8:
                icon = "🌿"
            else:
                icon = seed_icon
                
            grid_cells.append(f"[{i}] {icon}")
            
            # Thêm vào danh sách chi tiết
            mins, secs = divmod(remaining, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                time_str = f"{hours}h {mins}m"
            else:
                time_str = f"{mins}m {secs}s"
                
            water_status = "💧" if watered else "🏜️"
            bonus_str = " (🌟 Cộng Hưởng)" if has_star else ""
            crop_details.append(f"**Ô {i}**: {seed_icon} {seed_name} — Còn {time_str} {water_status}{bonus_str}")
            
        elif status == STATUS_READY:
            grid_cells.append(f"[{i}] 🧺")
            crop_details.append(f"**Ô {i}**: {seed_icon} {seed_name} — **Sẵn sàng** 🧺")
            
        elif status == STATUS_WITHERED:
            grid_cells.append(f"[{i}] 🥀")
            crop_details.append(f"**Ô {i}**: {seed_icon} {seed_name} — **Đã héo** 🥀")
            
        else:
            grid_cells.append(f"[{i}] ❓")
            
    # Render Ma Trận
    matrix_str = f"**{grid_cells[0]}** | **{grid_cells[1]}** | **{grid_cells[2]}**\n"
    matrix_str += f"**{grid_cells[3]}** | **{grid_cells[4]}** | **{grid_cells[5]}**\n"
    matrix_str += f"**{grid_cells[6]}** | **{grid_cells[7]}** | **{grid_cells[8]}**\n"
    
    embed.add_field(name="Mảnh Đất Của Bạn", value=matrix_str, inline=False)
    
    if crop_details:
        embed.add_field(name="Chi tiết sinh trưởng", value="\n".join(crop_details), inline=False)
        
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660951791997071.gif")
    embed.set_footer(text="Dùng menu bên dưới để mua hạt giống hoặc tương tác với cây trồng.")
    
    return embed
