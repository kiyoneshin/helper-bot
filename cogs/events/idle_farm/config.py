"""
config.py — Cấu hình hệ thống Idle Farm
=======================================
Định nghĩa hạt giống, trạng thái cây trồng và các hằng số.
"""
from typing import Dict, TypedDict
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

class SeedConfig(TypedDict):
    name: str
    icon: str
    grow_time_seconds: int
    cost: int
    reward_min: int
    reward_max: int
    description: str
    double_chance: NotRequired[float | int]

# Hằng số trạng thái cây
STATUS_EMPTY = "EMPTY"
STATUS_GROWING = "GROWING"
STATUS_READY = "READY"
STATUS_WITHERED = "WITHERED"

# Cấu hình chung cho cây trồng
WATER_BONUS = 0.20  # Giảm 20% thời gian sinh trưởng nếu được tưới
WITHER_TIME = 12 * 60 * 60  # Cây sẽ héo sau 12 tiếng kể từ lúc chín

MAX_SLOTS = 9

def get_slot_price(current_slots: int) -> int:
    """Tính giá tiền mở rộng dựa trên số ô đất hiện tại."""
    return (current_slots - 2) * 5000

# Hệ thống phẩm chất
QUALITY_MULTIPLIERS = {"normal": 1.0, "silver": 1.25, "gold": 1.5, "iridium": 2.0}
QUALITY_EMOJIS = {"normal": "", "silver": "<:symbol_medal_silver:1537552840514347048>", "gold": "<:symbol_medal_gold:1537550996664885328>", "iridium": "<a:symbol_star_yellow:1537739289834553385>"}

SEEDS: Dict[str, SeedConfig] = {
    "wheat": {
        "name": "Lúa Mì",
        "icon": "<:farm_00_wheat:1535940025080881152>",
        "grow_time_seconds": 30 * 60,  # 30 phút
        "cost": 100,
        "reward_min": 102,
        "reward_max": 102,
        "description": "Cây trồng cơ bản, thu hoạch nhanh."
    },
    "potato": {
        "name": "Khoai Tây",
        "icon": "<:farm_01_potato:1535940026935017492>",
        "grow_time_seconds": 1 * 60 * 60,  # 1 tiếng
        "cost": 200,
        "reward_min": 205,
        "reward_max": 205,
        "description": "20% cơ hội nhân đôi thu hoạch.",
        "double_chance": 0.20,  # 20% ra x2 sản lượng
    },
    "tomato": {
        "name": "Cà Chua",
        "icon": "<:farm_02_tomato:1535940028943966238>",
        "grow_time_seconds": 3 * 60 * 60,  # 3 tiếng
        "cost": 400,
        "reward_min": 412,
        "reward_max": 412,
        "description": "Nguyên liệu chế biến Mứt Cà Chua."
    },
    "strawberry": {
        "name": "Dâu Tây",
        "icon": "<:farm_03_strawberry:1535940030722351204>",
        "grow_time_seconds": 6 * 60 * 60,  # 6 tiếng
        "cost": 800,
        "reward_min": 820,
        "reward_max": 820,
        "description": "Nguyên liệu chế biến Rượu Dâu cao cấp."
    },
    "pumpkin": {
        "name": "Bí Ngô",
        "icon": "<:farm_04_pumpkin:1535940032731287552>",
        "grow_time_seconds": 8 * 60 * 60,  # 8 tiếng
        "cost": 1200,
        "reward_min": 1235,
        "reward_max": 1235,
        "description": "Nguyên liệu chế biến Mứt Bí Ngô thơm ngon."
    },
    "sunflower": {
        "name": "Hướng Dương",
        "icon": "<:farm_05_sunflower:1535940035927474217>",
        "grow_time_seconds": 12 * 60 * 60,  # 12 tiếng
        "cost": 500,
        "reward_min": 550,
        "reward_max": 550,
        "description": "Mang lại lợi nhuận cao nhưng mất nhiều thời gian."
    },
    "star": {
        "name": "Ngôi Sao",
        "icon": "<:farm_06_star:1535940037487894559>",
        "grow_time_seconds": 24 * 60 * 60,  # 24 tiếng
        "cost": 2000,
        "reward_min": 500,
        "reward_max": 3000,
        "description": "Vật phẩm hiếm, nguyên liệu chế Linh Tửu."
    }
}

