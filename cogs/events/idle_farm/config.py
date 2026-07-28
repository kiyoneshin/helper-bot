"""
config.py — Cấu hình hệ thống Idle Farm
=======================================
Định nghĩa hạt giống, trạng thái cây trồng và các hằng số.
"""

from typing import TypedDict, Dict

class SeedConfig(TypedDict):
    name: str
    icon: str
    grow_time_seconds: int
    cost: int
    reward_min: int
    reward_max: int
    description: str

# Hằng số trạng thái cây
STATUS_EMPTY = "EMPTY"
STATUS_GROWING = "GROWING"
STATUS_READY = "READY"
STATUS_WITHERED = "WITHERED"

# Cấu hình chung cho cây trồng
WATER_BONUS = 0.20  # Giảm 20% thời gian sinh trưởng nếu được tưới
WITHER_TIME = 12 * 60 * 60  # Cây sẽ héo sau 12 tiếng kể từ lúc chín

# Hệ thống phẩm chất
QUALITY_MULTIPLIERS = {"normal": 1.0, "silver": 1.25, "gold": 1.5, "iridium": 2.0}
QUALITY_EMOJIS = {"normal": "", "silver": "🥈", "gold": "🥇", "iridium": "🌟"}

SEEDS: Dict[str, SeedConfig] = {
    "wheat": {
        "name": "Lúa Mì",
        "icon": "🌾",
        "grow_time_seconds": 30 * 60,  # 30 phút
        "cost": 100,
        "reward_min": 150,
        "reward_max": 200,
        "description": "Cây trồng cơ bản, thu hoạch nhanh."
    },
    "sunflower": {
        "name": "Hướng Dương",
        "icon": "🌻",
        "grow_time_seconds": 12 * 60 * 60,  # 12 tiếng
        "cost": 500,
        "reward_min": 1000,
        "reward_max": 1500,
        "description": "Mang lại lợi nhuận cao nhưng mất nhiều thời gian."
    },
    "star": {
        "name": "Ngôi Sao",
        "icon": "⭐",
        "grow_time_seconds": 24 * 60 * 60,  # 24 tiếng
        "cost": 2000,
        "reward_min": 5000,
        "reward_max": 10000,
        "description": "Vật phẩm hiếm, có yếu tố ngẫu nhiên."
    }
}
