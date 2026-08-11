import discord
from discord.ext import commands
from typing import Dict, Any, List
import time
import json
import logging

from cogs.common.db import query_db
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA
from cogs.common.item_config import ITEM_REGISTRY

log = logging.getLogger("Cooking")

# ID 71-80: Nấu Ăn
RECIPES = {
    71: [{"type": "tomato", "amount": 2}], # Salad Cà Chua (Instant Stamina)
    72: [{"type": "pumpkin", "amount": 2}], # Súp Bí Ngô (Stamina Regen)
    73: [{"type": "carp", "amount": 1}, {"type": "wheat", "amount": 1}], # Cơm Cuộn Cá (LB Drop Rate)
    74: [{"type": "strawberry", "amount": 2}], # Sinh Tố Dâu (LB Rarity)
    75: [{"type": "potato", "amount": 3}], # Khoai Tây Nghiền (Farm Yield)
    76: [{"type": "carp", "amount": 1}, {"type": "hardwood", "amount": 1}], # Cá Nướng Gỗ Thơm (Rare Wood)
    77: [{"type": "wheat", "amount": 1}, {"type": "coal", "amount": 2}], # Bánh Mì Thợ Mỏ (Rare Ore)
    78: [{"type": "pumpkin", "amount": 1}, {"type": "wheat", "amount": 1}], # Bánh Bí Ngô Hấp (Rare Fish)
    79: [{"type": "sunflower", "amount": 1}, {"type": "sap", "amount": 1}], # Trà Hướng Dương (Stamina Discount)
    80: [{"type": "lobster", "amount": 1}, {"type": "salmon", "amount": 1}, {"type": "potato", "amount": 1}, {"type": "tomato", "amount": 1}] # Lẩu Thập Cẩm (All)
}

CROP_TYPES = ["wheat", "sunflower", "star", "potato", "tomato", "strawberry", "pumpkin"]

def _find_ingredients_in_inventory(inventory: dict, req_type: str, amount: int) -> dict:
    """Trả về dict {item_id: amount_to_take} nếu đủ, ngược lại {}"""
    taken = {}
    remaining_needed = amount

    # Nông sản có chất lượng
    if req_type in CROP_TYPES:
        for quality in ["normal", "silver", "gold"]:
            item_id = f"{req_type}_{quality}"
            if item_id in inventory and inventory[item_id] > 0:
                take = min(inventory[item_id], remaining_needed)
                taken[item_id] = take
                remaining_needed -= take
                if remaining_needed <= 0:
                    break
    else:
        # Items thường (gỗ, cá, quặng)
        # Gỗ/Quặng: key là "wood", "coal", "carp", v.v. hoặc "fish_carp_normal"
        # Đổi thành kiểm tra linh hoạt
        for k, v in inventory.items():
            if k == req_type or k.startswith(f"fish_{req_type}") or k.startswith(f"ore_{req_type}"):
                if v > 0:
                    take = min(v, remaining_needed)
                    taken[k] = take
                    remaining_needed -= take
                    if remaining_needed <= 0:
                        break

    if remaining_needed > 0:
        return {} # Không đủ
    return taken

def _get_recipe_string(recipe_reqs: List[dict]) -> str:
    parts = []
    for req in recipe_reqs:
        parts.append(f"{req['amount']}x {req['type'].title()}")
    return ", ".join(parts)


class CookingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="cook", description="Nấu các món ăn đặc biệt từ nguyên liệu nông trại.")
    async def cook_cmd(self, ctx: commands.Context, food_id: int, amount: int = 1):
        """Lệnh nấu ăn. Cú pháp: kcook <id> [số_lượng]"""
        if amount <= 0:
            await ctx.send("<:symbol_wrong:1536629915598848072> Số lượng phải lớn hơn 0!")
            return

        if food_id not in RECIPES:
            await ctx.send("<:symbol_wrong:1536629915598848072> ID món ăn không hợp lệ! Hãy xem `krecipe` để biết ID món ăn (71-80).")
            return

        recipe = RECIPES[food_id]
        food_item = ITEM_REGISTRY[food_id]
        
        farm_data = await get_farm_data(self.bot, str(ctx.author.id))
        inventory = farm_data.setdefault("inventory", {})

        # Kiểm tra xem có đủ nguyên liệu cho TẤT CẢ số lượng không
        total_taken = {}
        # Clone inventory để giả lập trừ
        simulated_inv = inventory.copy()
        
        can_cook = True
        for _ in range(amount):
            for req in recipe:
                taken_for_req = _find_ingredients_in_inventory(simulated_inv, req['type'], req['amount'])
                if not taken_for_req:
                    can_cook = False
                    break
                # Trừ ảo
                for k, v in taken_for_req.items():
                    simulated_inv[k] -= v
                    total_taken[k] = total_taken.get(k, 0) + v
            if not can_cook:
                break

        if not can_cook:
            req_str = _get_recipe_string(recipe)
            await ctx.send(f"<:symbol_wrong:1536629915598848072> **Không đủ nguyên liệu!**\nĐể nấu **1x {food_item['icon']} {food_item['name']}** bạn cần: `{req_str}`.")
            return

        # Thực sự trừ nguyên liệu
        for k, v in total_taken.items():
            inventory[k] -= v
            if inventory[k] <= 0:
                del inventory[k]

        # Cộng món ăn vào inventory
        food_db_key = food_item["db_key"]
        inventory[food_db_key] = inventory.get(food_db_key, 0) + amount

        farm_data["inventory"] = inventory
        await save_farm_data(self.bot, str(ctx.author.id), farm_data)

        await ctx.send(f"<:symbol_00_cooking:1536007684241756291> Bạn đã nấu thành công **{amount}x {food_item['icon']} {food_item['name']}**!\n*(Nguyên liệu đã được trừ vào kho).*")
        log.info(f"{ctx.author.display_name} vừa nấu {amount}x {food_item['name']}.")

    @commands.hybrid_command(name="boost", description="Kiểm tra các hiệu ứng (Boost) đang kích hoạt.")
    async def boost_cmd(self, ctx: commands.Context):
        """Kiểm tra các hiệu ứng đang có."""
        user_id = str(ctx.author.id)
        
        records = await query_db(self.bot, "SELECT active_boosts, p2w_multiplier FROM event_profiles WHERE discord_id = $1", user_id)
        
        row = records[0] if records else {}
        boosts = row.get("active_boosts", {})
        if isinstance(boosts, str):
            try: boosts = json.loads(boosts)
            except: boosts = {}
            
        p2w = float(row.get("p2w_multiplier", 1.0))
        
        now = time.time()
        
        embed = discord.Embed(title="✨ Danh sách Hiệu Ứng (Boosts)", color=0xFFD700)
        
        from cogs.common.item_config import ITEM_REGISTRY

        # Mapping từ boost_key sang ID trong ITEM_REGISTRY
        boost_to_item = {
            "stamina_regen": 71,
            "lb_drop_rate": 72,
            "lb_rarity": 73,
            "farm_yield": 74,
            "rare_wood": 75,
            "rare_ore": 76,
            "rare_fish": 77,
            "stamina_discount": 78,
            "all_boost": 79
        }
        
        # P2W
        embed.add_field(name="👑 Đặc Quyền P2W", value=f"Hệ số nhân: **x{p2w}** điểm.", inline=False)
        active_count = 1
        for b_key, b_data in boosts.items():
            expires_at = b_data.get("expires_at", 0)
            if expires_at > now:
                active_count += 1
                b_val = b_data.get("value", 0)
                time_left = f"<t:{int(expires_at)}:R>"
                
                # Fetch actual name and emoji from ITEM_REGISTRY
                item_id = boost_to_item.get(b_key)
                if item_id and item_id in ITEM_REGISTRY:
                    meta = ITEM_REGISTRY[item_id]
                    name = f"{meta['icon']} {meta['name']} ({b_key})"
                else:
                    name = f"🔧 Hiệu ứng chưa rõ ({b_key})"
                
                if b_key == "stamina_regen":
                    desc = f"+ {int(b_val*100)}% Tốc độ hồi thể lực. Hết hạn: {time_left}"
                elif b_key == "lb_drop_rate":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ rơi Lootbox. Hết hạn: {time_left}"
                elif b_key == "lb_rarity":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ Lootbox hiếm. Hết hạn: {time_left}"
                elif b_key == "farm_yield":
                    desc = f"+ {b_val} Sản lượng thu hoạch. Hết hạn: {time_left}"
                elif b_key == "rare_wood":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ Gỗ hiếm. Hết hạn: {time_left}"
                elif b_key == "rare_ore":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ Quặng hiếm. Hết hạn: {time_left}"
                elif b_key == "rare_fish":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ Cá hiếm. Hết hạn: {time_left}"
                elif b_key == "stamina_discount":
                    desc = f"- {b_val} Thể lực tiêu hao. Hết hạn: {time_left}"
                elif b_key == "all_boost":
                    desc = f"+ {int(b_val*100)}% Tỉ lệ Đồ hiếm (Mọi H.động). Hết hạn: {time_left}"
                else:
                    desc = f"Giá trị: {b_val}. Hết hạn: {time_left}"
                    
                embed.add_field(name=name, value=desc, inline=False)

        # Hôn Nhân
        from cogs.common.db import get_marriage
        from cogs.events.social.marriage import RING_BUFFS
        mar = await get_marriage(self.bot, user_id)
        if mar:
            ring_id = mar.get("ring_id")
            pet_id = mar.get("pet_id")
            pet_level = mar.get("pet_level", 0)
            
            buffs = RING_BUFFS.get(ring_id, {"dtm_bonus": 0.0, "cd_reduction": 0.0, "work_bonus": 1.0})
            if buffs["cd_reduction"] > 0 or buffs["dtm_bonus"] > 0:
                ring_icon, ring_name = "💍", "Nhẫn Cưới"
                if ring_id and ring_id in ITEM_REGISTRY:
                    ring_meta = ITEM_REGISTRY[ring_id]
                    ring_icon = ring_meta["icon"]
                    ring_name = ring_meta["name"]
                    
                embed.add_field(name=f"{ring_icon} {ring_name}", value=f"- Giảm Cooldown: **{int(buffs['cd_reduction']*100)}%**\n- Tăng DTM: **{int(buffs['dtm_bonus']*100)}%**", inline=False)
                active_count += 1
                
            pet_cd = 0.0
            pet_dtm = 0.0
            if pet_level > 0:
                if pet_id == 45:
                    pet_dtm = min(pet_level * 0.015, 0.90)
                    pet_cd = min(pet_level * 0.0075, 0.45)
                elif pet_id == 46:
                    pet_dtm = pet_level * 0.01
                    pet_cd = pet_level * 0.005
                elif pet_id == 47:
                    pet_dtm = pet_level * 0.007
                    pet_cd = pet_level * 0.0035
            
            if pet_cd > 0 or pet_dtm > 0:
                embed.add_field(name="🐾 Thú Cưng", value=f"- Giảm Cooldown: **{pet_cd*100:.1f}%**\n- Tăng DTM: **{pet_dtm*100:.1f}%**", inline=False)
                active_count += 1
                
        if active_count == 0:
            embed.description = "Bạn hiện không có hiệu ứng nào đang hoạt động."
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CookingCog(bot))
