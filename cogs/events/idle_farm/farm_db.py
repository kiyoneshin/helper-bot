"""
farm_db.py — Xử lý logic Database và thời gian cho Idle Farm
============================================================
Các hàm tương tác với JSONB `farm_data` trong `event_profiles`.
"""

import json
import time
import random
import logging
from typing import Any, Dict, Tuple

from discord.ext import commands

from cogs.common.db import fetchval_db, execute_db, get_or_create_event_profile, add_event_points
from . import config

log = logging.getLogger("FarmDB")

async def get_farm_data(bot: commands.Bot, user_id: str) -> Dict[str, Any]:
    """
    Lấy dữ liệu farm của user từ Database (cột farm_data kiểu JSONB).
    Nếu chưa có, trả về cấu trúc mặc định: {"slots": 3, "crops": {}}
    """
    default_data: Dict[str, Any] = {
        "slots": 3,
        "crops": {},
        "inventory": {},
        "stamina": 100,
        "last_stamina_update": int(time.time()),
        "pickaxe_level": 1,
        "rod_level": 1,
    }
    
    try:
        # Đảm bảo profile tồn tại trước khi select
        await get_or_create_event_profile(bot, user_id)
        
        # Hàm fetchval_db đã bắt sẵn exception nếu thiếu cột farm_data, lúc đó sẽ trả về None
        raw_data = await fetchval_db(
            bot, 
            "SELECT farm_data FROM event_profiles WHERE discord_id = $1", 
            user_id
        )
        
        if not raw_data:
            return default_data
            
        data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        
        if not isinstance(data, dict):
            return default_data
            
        # Khôi phục các keys mặc định nếu bị thiếu
        if "slots" not in data:
            data["slots"] = 3
        if "crops" not in data:
            data["crops"] = {}
        if "inventory" not in data:
            data["inventory"] = {}
        if "stamina" not in data:
            data["stamina"] = 100
        if "last_stamina_update" not in data:
            data["last_stamina_update"] = int(time.time())
        if "pickaxe_level" not in data:
            data["pickaxe_level"] = 1
        if "rod_level" not in data:
            data["rod_level"] = 1
            
        return data
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        log.warning(f"Lỗi parse farm_data cho {user_id}: {e}")
        return default_data

async def get_and_update_stamina(bot: commands.Bot, user_id: str) -> int:
    """
    Tính toán và cập nhật thể lực hiện tại dựa trên thời gian đã trôi qua.
    Chống gian lận: elapsed time bị kẹp tối đa bằng thời gian cần để đầy thể lực.
    Trả về stamina hiện tại sau khi đã hồi.
    """
    from cogs.events.mining.mining_config import MAX_STAMINA, STAMINA_REGEN_RATE, STAMINA_REGEN_INTERVAL_SECONDS

    farm_data = await get_farm_data(bot, user_id)
    now = int(time.time())

    current_stamina: int = int(farm_data.get("stamina", MAX_STAMINA))
    last_update: int    = int(farm_data.get("last_stamina_update", now))

    # Anti-cheat: clamp elapsed thành tối đa đủ để fill hết thể lực
    max_seconds_needed = (MAX_STAMINA - current_stamina) * STAMINA_REGEN_INTERVAL_SECONDS
    elapsed = min(now - last_update, max_seconds_needed)
    elapsed = max(elapsed, 0)   # không âm

    regen_ticks = elapsed // STAMINA_REGEN_INTERVAL_SECONDS
    new_stamina = min(current_stamina + regen_ticks * STAMINA_REGEN_RATE, MAX_STAMINA)

    farm_data["stamina"] = new_stamina
    farm_data["last_stamina_update"] = now
    await save_farm_data(bot, user_id, farm_data)

    return new_stamina

async def save_farm_data(bot: commands.Bot, user_id: str, farm_data: Dict[str, Any]) -> None:
    """
    Lưu dữ liệu farm ngược lại CSDL.
    """
    try:
        json_data = json.dumps(farm_data)
        await execute_db(
            bot,
            "UPDATE event_profiles SET farm_data = $1::jsonb WHERE discord_id = $2",
            json_data, user_id
        )
    except Exception as e:
        log.error(f"Lỗi khi save_farm_data cho {user_id}: {e}")

def calculate_crop_status(crop_data: Dict[str, Any], slot_id: str = None, crops: Dict[str, Any] = None) -> Tuple[str, int]:
    """
    Tính toán trạng thái cây trồng (sync).
    Trả về (Trạng Thái, Thời Gian Còn Lại/Quá Hạn tính bằng giây).
    """
    ADJACENCY_MAP = {
        "1": ["2", "4"],
        "2": ["1", "3", "5"],
        "3": ["2", "6"],
        "4": ["1", "5", "7"],
        "5": ["2", "4", "6", "8"],
        "6": ["3", "5", "9"],
        "7": ["4", "8"],
        "8": ["5", "7", "9"],
        "9": ["6", "8"]
    }
    try:
        seed_id = crop_data.get("seed")
        planted_at = crop_data.get("planted_at", 0)
        watered = crop_data.get("watered", False)
        
        seed_config = config.SEEDS.get(seed_id)
        if not seed_config:
            return config.STATUS_EMPTY, 0
            
        current_time = int(time.time())
        elapsed_time = current_time - planted_at
        
        required_time = seed_config["grow_time_seconds"]
        if watered:
            required_time -= int(required_time * config.WATER_BONUS)
            
        # Adjacency Bonus: Nếu gần cây Ngôi Sao (star), giảm thêm 20% thời gian
        if slot_id and crops and slot_id in ADJACENCY_MAP:
            has_star_neighbor = False
            for neighbor_id in ADJACENCY_MAP[slot_id]:
                if neighbor_id in crops and crops[neighbor_id].get("seed") == "star":
                    has_star_neighbor = True
                    break
            
            if has_star_neighbor:
                required_time -= int(required_time * 0.20)
            
        if elapsed_time < required_time:
            remaining = required_time - elapsed_time
            return config.STATUS_GROWING, remaining
            
        # Nếu đã chín, kiểm tra xem có héo không (quá thời gian WITHER_TIME kể từ lúc chín)
        if elapsed_time > required_time + config.WITHER_TIME:
            return config.STATUS_WITHERED, 0
            
        return config.STATUS_READY, 0
    except (TypeError, KeyError, ValueError) as e:
        log.warning(f"Lỗi tính toán trạng thái cây: {e}")
        return config.STATUS_EMPTY, 0

async def plant_seed(bot: commands.Bot, user_id: str, slot_id: str, seed_type: str) -> Tuple[bool, str]:
    """
    Xử lý logic trồng cây vào 1 ô đất cụ thể. Hạt giống sẽ được trừ vào inventory.
    """
    if seed_type not in config.SEEDS:
        return False, "Hạt giống không tồn tại!"
        
    farm_data = await get_farm_data(bot, user_id)
    inventory = farm_data.get("inventory", {})
    crops = farm_data.get("crops", {})
    
    seed_item_id = f"seed_{seed_type}"
    if inventory.get(seed_item_id, 0) < 1:
        return False, "Bạn không có hạt giống này trong túi đồ!"

    
    # Ép slot_id về string để key json đồng nhất
    slot_id_str = str(slot_id)
    
    max_slots = farm_data.get("slots", 3)
    try:
        slot_num = int(slot_id_str)
        if slot_num > max_slots or slot_num < 1:
            return False, "Ô đất không hợp lệ hoặc chưa được mở khóa!"
    except ValueError:
        return False, "Mã ô đất bị lỗi!"
    
    if slot_id_str in crops:
        return False, "Ô đất này đã có cây trồng rồi!"
        
    crops[slot_id_str] = {
        "seed": seed_type,
        "planted_at": int(time.time()),
        "watered": False
    }
    
    # Trừ hạt giống trong kho
    inventory[seed_item_id] -= 1
    if inventory[seed_item_id] <= 0:
        del inventory[seed_item_id]
    
    await save_farm_data(bot, user_id, farm_data)
    return True, "Trồng thành công!"

async def buy_seed(bot: commands.Bot, user_id: str, seed_type: str, amount: int = 1) -> Tuple[bool, str]:
    """
    Mua hạt giống và thêm vào inventory.
    """
    if seed_type not in config.SEEDS:
        return False, "Hạt giống không tồn tại!"
        
    seed_config = config.SEEDS[seed_type]
    total_cost = seed_config["cost"] * amount
    
    user_points = await fetchval_db(bot, "SELECT points FROM event_profiles WHERE discord_id = $1", user_id)
    if user_points is None or float(user_points) < total_cost:
        return False, f"Không đủ điểm sự kiện (Cần {total_cost:,} điểm)!"
        
    # Trừ tiền
    from cogs.common.db import deduct_event_points
    success = await deduct_event_points(bot, user_id, total_cost)
    if not success:
        return False, f"Không đủ điểm sự kiện (Cần {total_cost:,} điểm)!"
        
    # Thêm vào kho đồ
    farm_data = await get_farm_data(bot, user_id)
    inventory = farm_data.setdefault("inventory", {})
    seed_item_id = f"seed_{seed_type}"
    
    inventory[seed_item_id] = inventory.get(seed_item_id, 0) + amount
    await save_farm_data(bot, user_id, farm_data)
    
    return True, f"Mua thành công {amount}x {seed_config['name']}!"

async def water_all(bot: commands.Bot, user_id: str) -> Tuple[bool, int]:
    """
    Xử lý logic tưới nước cho toàn bộ vườn.
    """
    farm_data = await get_farm_data(bot, user_id)
    crops = farm_data.get("crops", {})
    
    watered_count = 0
    changed = False
    
    for slot_id, crop in crops.items():
        if crop.get("watered"):
            continue
            
        status, _ = calculate_crop_status(crop, slot_id, crops)
        if status == config.STATUS_GROWING:
            crop["watered"] = True
            watered_count += 1
            changed = True
            
    if changed:
        await save_farm_data(bot, user_id, farm_data)
        
    return True, watered_count

async def harvest_all(bot: commands.Bot, user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Thu hoạch toàn bộ cây có trạng thái READY. Có cơ chế Cây Khổng Lồ (Giant Crops).
    """
    farm_data = await get_farm_data(bot, user_id)
    crops = farm_data.get("crops", {})
    inventory = farm_data.setdefault("inventory", {})
    
    harvest_report = {}
    withered_count = 0
    slots_to_remove = set()
    
    # 1. Quét Cây Khổng Lồ (Giant Crops) trên ma trận 3x3
    LINES = [
        ("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), # Hàng ngang
        ("1", "4", "7"), ("2", "5", "8"), ("3", "6", "9")  # Hàng dọc
    ]
    
    for line in LINES:
        s1, s2, s3 = line
        if s1 in crops and s2 in crops and s3 in crops:
            if s1 in slots_to_remove or s2 in slots_to_remove or s3 in slots_to_remove:
                continue # Đã bị thu hoạch bởi tuyến khác
                
            c1, c2, c3 = crops[s1], crops[s2], crops[s3]
            if c1.get("seed") == c2.get("seed") == c3.get("seed"):
                st1, _ = calculate_crop_status(c1, s1, crops)
                st2, _ = calculate_crop_status(c2, s2, crops)
                st3, _ = calculate_crop_status(c3, s3, crops)
                
                if st1 == config.STATUS_READY and st2 == config.STATUS_READY and st3 == config.STATUS_READY:
                    seed_id = c1.get("seed")
                    seed_config = config.SEEDS.get(seed_id)
                    if seed_config:
                        # Rơi ngẫu nhiên 5-8 vật phẩm
                        drop_count = random.randint(5, 8)
                        
                        for _ in range(drop_count):
                            # Tỉ lệ phẩm chất dựa trên cây thứ 1 (để đơn giản)
                            watered = c1.get("watered", False)
                            roll = random.random()
                            if watered:
                                if roll < 0.40: quality = "normal"
                                elif roll < 0.70: quality = "silver"
                                elif roll < 0.95: quality = "gold"
                                else: quality = "iridium"
                            else:
                                if roll < 0.70: quality = "normal"
                                else: quality = "silver"
                                
                            item_id = f"{seed_id}_{quality}"
                            inventory[item_id] = inventory.get(item_id, 0) + 1
                            harvest_report[item_id] = harvest_report.get(item_id, 0) + 1
                            
                    slots_to_remove.update([s1, s2, s3])
    
    # 2. Quét các cây đơn lẻ còn lại
    for slot_id, crop in crops.items():
        if slot_id in slots_to_remove:
            continue
            
        status, _ = calculate_crop_status(crop, slot_id, crops)
        
        if status == config.STATUS_READY:
            seed_id = crop.get("seed")
            watered = crop.get("watered", False)
            seed_config = config.SEEDS.get(seed_id)
            
            if seed_config:
                # Tính phẩm chất
                roll = random.random()
                if watered:
                    if roll < 0.40: quality = "normal"
                    elif roll < 0.70: quality = "silver"
                    elif roll < 0.95: quality = "gold"
                    else: quality = "iridium"
                else:
                    if roll < 0.70: quality = "normal"
                    else: quality = "silver"
                    
                item_id = f"{seed_id}_{quality}"
                inventory[item_id] = inventory.get(item_id, 0) + 1
                
                # Cập nhật báo cáo
                harvest_report[item_id] = harvest_report.get(item_id, 0) + 1
                
            slots_to_remove.add(slot_id)
            
        elif status == config.STATUS_WITHERED:
            withered_count += 1
            slots_to_remove.add(slot_id)
            
    # 3. Xoá các cây đã thu hoạch hoặc bị héo
    for slot in slots_to_remove:
        del crops[slot]
        
    if slots_to_remove:
        await save_farm_data(bot, user_id, farm_data)
        
    return True, {"harvested": harvest_report, "withered": withered_count}

async def sell_inventory(bot: commands.Bot, user_id: str, category: str) -> int:
    """
    Bán kho đồ theo danh mục: 'crops' (Nông sản), 'ores' (Khoáng sản), 'fish' (Cá).
    Quy ra điểm và cộng vào DB. Trả về tổng số tiền.
    """
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT
    
    farm_data = await get_farm_data(bot, user_id)
    inventory = farm_data.get("inventory", {})
    
    if not inventory:
        return 0
        
    total_profit = 0
    items_to_keep = {}
    
    for item_id, count in inventory.items():
        # Hạt giống thì không bao giờ bán qua nút này
        if item_id.startswith("seed_"):
            items_to_keep[item_id] = count
            continue
            
        is_ore = item_id in MINING_LOOT
        is_fish = item_id in FISH_LOOT
        is_crop = not (is_ore or is_fish)
        
        should_sell = False
        if category == "crops" and is_crop:
            should_sell = True
        elif category == "ores" and is_ore:
            should_sell = True
        elif category == "fish" and is_fish:
            should_sell = True
            
        if not should_sell:
            items_to_keep[item_id] = count
            continue
            
        # Tính tiền
        if is_ore:
            profit_per_item = MINING_LOOT[item_id].get("price", 0)
        elif is_fish:
            profit_per_item = FISH_LOOT[item_id].get("price", 0)
        else:
            # Là crop
            parts = item_id.split("_")
            if len(parts) >= 2:
                seed_id = "_".join(parts[:-1])
                quality = parts[-1]
            else:
                seed_id = item_id
                quality = "normal"
                
            seed_config = config.SEEDS.get(seed_id)
            if seed_config:
                base_cost = seed_config["reward_min"]
                multiplier = config.QUALITY_MULTIPLIERS.get(quality, 1.0)
                profit_per_item = int(base_cost * multiplier)
            else:
                profit_per_item = 0
                
        total_profit += profit_per_item * count
        
    if total_profit > 0:
        await add_event_points(bot, user_id, float(total_profit), is_earned=True)
        
    farm_data["inventory"] = items_to_keep
    await save_farm_data(bot, user_id, farm_data)
    
    return total_profit

async def remove_crop(bot: commands.Bot, user_id: str, slot_id: str) -> Tuple[bool, str]:
    """
    Cuốc bỏ cây trồng ở một ô đất cụ thể.
    """
    farm_data = await get_farm_data(bot, user_id)
    crops = farm_data.get("crops", {})
    
    slot_id_str = str(slot_id)
    
    if slot_id_str not in crops:
        return False, "Ô đất này đang trống hoặc không tồn tại!"
        
    del crops[slot_id_str]
    await save_farm_data(bot, user_id, farm_data)
    
    return True, "Đã dọn dẹp ô đất!"

async def expand_farm_slot(bot: commands.Bot, user_id: str) -> Tuple[bool, str]:
    """
    Mở rộng thêm 1 ô đất cho Nông trại. Tối đa đạt MAX_SLOTS.
    """
    farm_data = await get_farm_data(bot, user_id)
    current_slots = farm_data.get("slots", 3)
    
    if current_slots >= config.MAX_SLOTS:
        return False, "Nông trại của bạn đã đạt kích thước tối đa!"
        
    price = config.get_slot_price(current_slots)
    
    user_points = await fetchval_db(bot, "SELECT points FROM event_profiles WHERE discord_id = $1", user_id)
    if user_points is None or float(user_points) < price:
        return False, f"Không đủ điểm sự kiện để mở rộng (Cần {price:,} điểm)!"
        
    from cogs.common.db import deduct_event_points
    success = await deduct_event_points(bot, user_id, price)
    if not success:
        return False, f"Không đủ điểm sự kiện để mở rộng (Cần {price:,} điểm)!"
        
    farm_data["slots"] = current_slots + 1
    await save_farm_data(bot, user_id, farm_data)
    
    return True, f"Mở rộng thành công lên {current_slots + 1} ô đất!"


async def sell_items_partial(
    bot: commands.Bot,
    user_id: str,
    item_id: str,
    amount: int,
) -> Tuple[bool, int, str]:
    """
    Bán một lượng cụ thể của một loại vật phẩm trong túi đồ nông trại.

    Args:
        bot: Bot instance.
        user_id: Discord ID (string).
        item_id: Key trong farm_data.inventory (VD: "tomato_normal", "ore_iron_common").
        amount: Số lượng muốn bán (-1 = bán hết).

    Returns:
        (success, total_profit, message)
    """
    from cogs.events.mining.mining_config import MINING_LOOT
    from cogs.events.fishing.fishing_config import FISH_LOOT

    farm_data = await get_farm_data(bot, user_id)
    inventory = farm_data.get("inventory", {})

    current_qty = inventory.get(item_id, 0)
    if current_qty <= 0:
        return False, 0, "Bạn không có vật phẩm này trong túi đồ!"

    # -1 nghĩa là bán hết
    sell_qty = current_qty if amount == -1 else min(amount, current_qty)
    if sell_qty <= 0:
        return False, 0, "Số lượng không hợp lệ!"

    # Tính giá trị
    if item_id in MINING_LOOT:
        profit_per = MINING_LOOT[item_id].get("price", 0)
    elif item_id in FISH_LOOT:
        profit_per = FISH_LOOT[item_id].get("price", 0)
    elif item_id.startswith("seed_"):
        return False, 0, "Hạt giống không thể bán — hãy dùng để trồng cây!"
    else:
        # Crop — tách seed_id và quality
        parts = item_id.split("_")
        if len(parts) >= 2:
            seed_id = "_".join(parts[:-1])
            quality = parts[-1]
        else:
            seed_id, quality = item_id, "normal"

        seed_cfg = config.SEEDS.get(seed_id)
        if not seed_cfg:
            return False, 0, f"Vật phẩm `{item_id}` không xác định được giá!"
        multiplier = config.QUALITY_MULTIPLIERS.get(quality, 1.0)
        profit_per = int(seed_cfg["reward_min"] * multiplier)

    total_profit = profit_per * sell_qty

    # Cập nhật inventory
    new_qty = current_qty - sell_qty
    if new_qty <= 0:
        inventory.pop(item_id, None)
    else:
        inventory[item_id] = new_qty

    farm_data["inventory"] = inventory
    await save_farm_data(bot, user_id, farm_data)

    if total_profit > 0:
        await add_event_points(bot, user_id, float(total_profit), is_earned=True)

    return True, total_profit, f"Đã bán **{sell_qty}** vật phẩm, thu về **{total_profit:,}** điểm!"
