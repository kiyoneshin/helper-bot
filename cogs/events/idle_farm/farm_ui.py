import typing
import time
from typing import Any, Dict
import discord
from discord.ext import commands

from .config import SEEDS, STATUS_GROWING, STATUS_READY, STATUS_WITHERED, WATER_BONUS, QUALITY_EMOJIS
from .farm_db import plant_seed, water_all, harvest_all, calculate_crop_status, get_farm_data, remove_crop
from cogs.common.db import fetchval_db, deduct_event_points, add_event_points

class PlantSeedSelect(discord.ui.Select):
    """Dropdown Menu hiển thị hạt giống đang có trong túi đồ để trồng."""
    
    def __init__(self, bot: commands.Bot, farm_data: Dict[str, Any]):
        self.bot = bot
        options = []
        inventory = farm_data.get("inventory", {})
        
        has_seeds = False
        for item_id, count in inventory.items():
            if item_id.startswith("seed_") and count > 0:
                seed_id = item_id[5:] # bỏ "seed_"
                seed_info = SEEDS.get(seed_id)
                if seed_info:
                    has_seeds = True
                    options.append(
                        discord.SelectOption(
                            label=f"Gieo: {seed_info['name']} (Còn {count})",
                            value=seed_id,
                            emoji=seed_info['icon']
                        )
                    )
                    
        if not has_seeds:
            options.append(
                discord.SelectOption(
                    label="Túi đồ rỗng! (Dùng y!farmshop để mua)",
                    value="empty",
                    emoji="🪹"
                )
            )
            
        super().__init__(
            placeholder="🌱 Chọn hạt giống để gieo trồng...",
            min_values=1,
            max_values=1,
            options=options[:25], # Max 25 options
            row=0,
            disabled=not has_seeds
        )
        
    async def callback(self, interaction: discord.Interaction):
        view: "FarmView" = self.view  # type: ignore
        user_id = str(interaction.user.id)
        
        if user_id != view.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return

        selected_seed = self.values[0]
        if selected_seed == "empty":
            return
            
        seed_info = typing.cast(typing.Dict[str, typing.Any], dict(SEEDS.get(selected_seed, {})))
        await interaction.response.send_modal(PlantSlotModal(self.bot, user_id, view.author, selected_seed, seed_info, view))

class PlantSlotModal(discord.ui.Modal):
    slot_input = discord.ui.TextInput(
        label="Nhập số thứ tự ô đất (1-9)",
        placeholder="Chỉ nhập số nguyên...",
        min_length=1,
        max_length=2,
        required=True
    )
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, seed_id: str, seed_info: dict, view: "FarmView"):
        super().__init__(title=f"Gieo: {seed_info.get('name', seed_id)}")
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.seed_id = seed_id
        self.seed_info = seed_info
        self.view_obj = view
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            slot_id = int(self.slot_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Số ô không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)
            return
            
        farm_data = await get_farm_data(self.bot, self.user_id)
        max_slots = farm_data.get("slots", 3)
        crops = farm_data.get("crops", {})
        
        if slot_id < 1 or slot_id > max_slots:
            await interaction.response.send_message(f"❌ Ô số {slot_id} chưa được mở khóa! (Bạn đang có {max_slots} ô)", ephemeral=True)
            return
            
        if str(slot_id) in crops:
            await interaction.response.send_message(f"❌ Ô số {slot_id} đã có cây trồng rồi!", ephemeral=True)
            return
            
        ok, msg = await plant_seed(self.bot, self.user_id, str(slot_id), self.seed_id)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        
        seed_name = self.seed_info.get('name', self.seed_id)
        await interaction.followup.send(f"✅ Bạn đã gieo **{seed_name}** tại Ô {slot_id}!", ephemeral=True)

class FarmView(discord.ui.View):
    """View chính của Nông Trại chứa các nút tương tác."""
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, farm_data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.add_item(PlantSeedSelect(bot, farm_data))
        
    @discord.ui.button(label="Tưới Nước Tất Cả", emoji="💧", style=discord.ButtonStyle.primary, row=1)
    async def water_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
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
        
    @discord.ui.button(label="Thu Hoạch", emoji="🧺", style=discord.ButtonStyle.success, row=1)
    async def harvest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
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
                
            msg.append(f"✅ Thu hoạch thành công: " + ", ".join(details))
            
        if withered > 0:
            msg.append(f"🥀 Đã dọn dẹp **{withered}** cây bị héo.")
            
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send("\n".join(msg), ephemeral=True)

    @discord.ui.button(label="Cuốc Bỏ", emoji="⛏️", style=discord.ButtonStyle.danger, row=1)
    async def clear_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
            return
            
        await interaction.response.send_modal(ClearSlotModal(self.bot, self.user_id, self.author, self))

    @discord.ui.button(label="Làm Mới", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Bạn không thể tương tác với nông trại của người khác!", ephemeral=True)
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
            await interaction.response.send_message("❌ Giá trị không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)
            return
            
        ok, msg = await remove_crop(self.bot, self.user_id, str(slot_id))
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        new_farm_data = await get_farm_data(self.bot, self.user_id)
        new_embed = build_farm_embed(self.author, new_farm_data)
        
        new_view = FarmView(self.bot, self.user_id, self.author, new_farm_data)
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(f"✅ {msg} (Tại Ô {slot_id})", ephemeral=True)


def build_farm_embed(author: discord.Member | discord.User, farm_data: Dict[str, Any]) -> discord.Embed:
    """
    Render giao diện text hiển thị trực quan các ô đất.
    Thay đổi icon cây trồng dựa theo tiến trình sinh trưởng.
    """
    embed = discord.Embed(
        title=f"🌻 Nông Trại Của {author.display_name}",
        description="Chào mừng bạn đến với khu vườn nhàn rỗi! Hãy chăm chỉ trồng trọt để kiếm thêm thu nhập nhé.",
        color=0x2ecc71
    )
    
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
        
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng menu bên dưới để mua hạt giống hoặc tương tác với cây trồng.")
    
    return embed
