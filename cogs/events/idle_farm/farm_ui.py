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
            
        farm_data = await get_farm_data(self.bot, user_id)
        max_slots = farm_data.get("slots", 3)
        crops = farm_data.get("crops", {})
        
        empty_slot = None
        for i in range(1, max_slots + 1):
            if str(i) not in crops:
                empty_slot = i
                break
                
        if not empty_slot:
            await interaction.response.send_message("❌ Nông trại của bạn đã hết đất trống! Vui lòng thu hoạch hoặc cuốc bỏ cây héo.", ephemeral=True)
            return
            
        ok, msg = await plant_seed(self.bot, user_id, str(empty_slot), selected_seed)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        # Cập nhật Embed & View
        new_farm_data = await get_farm_data(self.bot, user_id)
        new_embed = build_farm_embed(view.author, new_farm_data)
        
        # Tạo View mới để cập nhật số lượng hạt giống trong dropdown
        new_view = FarmView(self.bot, user_id, view.author, new_farm_data)
        
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        
        seed_info = SEEDS.get(selected_seed, {})
        seed_name = seed_info.get('name', selected_seed)
        await interaction.followup.send(f"✅ Bạn đã gieo **{seed_name}** tại Ô {empty_slot}!", ephemeral=True)


class FarmView(discord.ui.View):
    """View chính của Nông Trại chứa các nút tương tác."""
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, farm_data: Dict[str, Any]):
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
    
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, view: FarmView):
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


def build_farm_embed(author: discord.Member, farm_data: Dict[str, Any]) -> discord.Embed:
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
    
    farm_display = []
    current_time = int(time.time())
    
    for i in range(1, slots + 1):
        slot_key = str(i)
        if slot_key in crops:
            crop = crops[slot_key]
            seed_id = crop.get("seed")
            seed_info = SEEDS.get(seed_id)
            
            if not seed_info:
                farm_display.append(f"🟫 **[ Ô {i}: Lỗi dữ liệu hạt giống ]**")
                continue
                
            status, remaining = calculate_crop_status(crop)
            seed_name = seed_info["name"]
            seed_icon = seed_info["icon"]
            
            if status == STATUS_GROWING:
                planted_at = crop.get("planted_at", 0)
                watered = crop.get("watered", False)
                
                req_time = seed_info["grow_time_seconds"]
                if watered:
                    req_time -= int(req_time * WATER_BONUS)
                
                elapsed = current_time - planted_at
                progress = elapsed / req_time if req_time > 0 else 1.0
                
                if progress < 0.3:
                    icon = "🌱"
                    desc = "Mới trồng"
                elif progress < 0.8:
                    icon = "🌿"
                    desc = "Đang lớn"
                else:
                    icon = seed_icon
                    desc = "Sắp chín"
                
                # Format thời gian còn lại (giờ/phút/giây)
                mins, secs = divmod(remaining, 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    time_str = f"{hours}h {mins}m"
                else:
                    time_str = f"{mins}m {secs}s"
                    
                water_status = "💧" if watered else "🏜️"
                farm_display.append(f"{icon} **[ Ô {i}: {seed_name} - {desc} ]** — Còn {time_str} {water_status}")
                
            elif status == STATUS_READY:
                farm_display.append(f"{seed_icon} **[ Ô {i}: {seed_name} - Sẵn sàng ]** 🧺")
                
            elif status == STATUS_WITHERED:
                farm_display.append(f"🥀 **[ Ô {i}: {seed_name} - Đã héo ]** (Thu hoạch để dọn dẹp)")
                
            else:
                farm_display.append(f"🟫 **[ Ô {i}: Lỗi trạng thái ]**")
        else:
            farm_display.append(f"🟫 **[ Ô {i}: Đất Trống ]**")
            
    embed.add_field(name="Mảnh Đất Của Bạn", value="\n".join(farm_display), inline=False)
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng menu bên dưới để mua hạt giống hoặc tương tác với cây trồng.")
    
    return embed
