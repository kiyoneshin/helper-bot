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

from cogs.common.db import fetchval_db, execute_db, get_or_create_event_profile
from . import config

log = logging.getLogger("FarmDB")

async def get_farm_data(bot: commands.Bot, user_id: str) -> Dict[str, Any]:
    """
    Lấy dữ liệu farm của user từ Database (cột farm_data kiểu JSONB).
    Nếu chưa có, trả về cấu trúc mặc định: {"slots": 3, "crops": {}}
    """
    default_data = {"slots": 3, "crops": {}}
    
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
            
        return data
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        log.warning(f"Lỗi parse farm_data cho {user_id}: {e}")
        return default_data

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

def calculate_crop_status(crop_data: Dict[str, Any]) -> Tuple[str, int]:
    """
    Tính toán trạng thái cây trồng (sync).
    Trả về (Trạng Thái, Thời Gian Còn Lại/Quá Hạn tính bằng giây).
    """
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
    Xử lý logic trồng cây vào 1 ô đất cụ thể.
    """
    if seed_type not in config.SEEDS:
        return False, "Hạt giống không tồn tại!"
        
    farm_data = await get_farm_data(bot, user_id)
    crops = farm_data.get("crops", {})
    
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
    
    await save_farm_data(bot, user_id, farm_data)
    return True, "Trồng thành công!"

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
            
        status, _ = calculate_crop_status(crop)
        if status == config.STATUS_GROWING:
            crop["watered"] = True
            watered_count += 1
            changed = True
            
    if changed:
        await save_farm_data(bot, user_id, farm_data)
        
    return True, watered_count

async def harvest_all(bot: commands.Bot, user_id: str) -> Tuple[bool, Dict[str, int]]:
    """
    Thu hoạch toàn bộ cây có trạng thái READY.
    """
    farm_data = await get_farm_data(bot, user_id)
    crops = farm_data.get("crops", {})
    
    total_profit = 0
    withered_count = 0
    slots_to_remove = []
    
    for slot_id, crop in crops.items():
        status, _ = calculate_crop_status(crop)
        
        if status == config.STATUS_READY:
            seed_id = crop.get("seed")
            seed_config = config.SEEDS.get(seed_id)
            if seed_config:
                profit = random.randint(seed_config["reward_min"], seed_config["reward_max"])
                total_profit += profit
            slots_to_remove.append(slot_id)
            
        elif status == config.STATUS_WITHERED:
            withered_count += 1
            slots_to_remove.append(slot_id)
            
    # Xoá các cây đã thu hoạch hoặc bị héo
    for slot in slots_to_remove:
        del crops[slot]
        
    if slots_to_remove:
        await save_farm_data(bot, user_id, farm_data)
        
    return True, {"profit": total_profit, "withered": withered_count}
