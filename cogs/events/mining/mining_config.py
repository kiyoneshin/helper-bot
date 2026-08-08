"""
mining_config.py — Cấu hình hệ thống Khu Mỏ
==============================================
Định nghĩa thể lực, tốc độ hồi phục, và bảng tỉ lệ rớt quặng.
"""
import random
from typing import Tuple

# ---------------------------------------------------------------------------
# CẤU HÌNH THỂ LỰC (STAMINA)
# ---------------------------------------------------------------------------

MAX_STAMINA: int = 100
STAMINA_PER_HIT: int = 4
STAMINA_REGEN_RATE: int = 1
STAMINA_REGEN_INTERVAL_SECONDS: int = 18  # 18 giây hồi 1 điểm -> 100 điểm mất 30 phút

# ---------------------------------------------------------------------------
# CẤU HÌNH NÂNG CẤP CUỐC
# ---------------------------------------------------------------------------

MAX_PICKAXE_LEVEL: int = 4

PICKAXE_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (10_000,  {"wood": 20, "copper_ore": 10}),          # Lên Lv2: Cuốc Đồng
    2: (25_000,  {"hardwood": 10, "iron_ore": 10}),        # Lên Lv3: Cuốc Sắt
    3: (80_000,  {"copper_bar": 5, "iron_bar": 5, "diamond": 2}),  # Lên Lv4: Cuốc Vàng
}

PICKAXE_NAMES: dict = {
    1: "Cuốc Đá <:mine_06_stone_pickaxe:1535654573312839731>",
    2: "Cuốc Đồng <:mine_07_bronze_pickaxe:1535654575258869841>",
    3: "Cuốc Sắt <:mine_08_iron_pickaxe:1535654577733373972>",
    4: "Cuốc Vàng <:mine_09_gold_pickaxe:1535654579965009960>",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT QUẶNG (MINING_LOOT)
# ---------------------------------------------------------------------------

MINING_LOOT: dict = {
    "stone":      {"name": "Đá",           "icon": "<:mine_00_stone:1535654559412781067>", "weight": 55, "category": "ore",  "price": 50},
    "coal":       {"name": "Than Đá",      "icon": "<:mine_01_coal:1535654561480708106>", "weight": 22, "category": "ore",  "price": 150},
    "copper_ore": {"name": "Quặng Đồng",   "icon": "<:mine_02_copper_ore:1535654564504670449>", "weight": 14, "category": "ore",  "price": 500},
    "iron_ore":   {"name": "Quặng Sắt",    "icon": "<:mine_03_iron_ore:1535654566853615717>", "weight": 7,  "category": "ore",  "price": 1500},
    "gold_ore":   {"name": "Quặng Vàng",   "icon": "<:mine_04_gold_ore:1535654569143566396>", "weight": 2,  "category": "ore",  "price": 5000},
    "diamond":    {"name": "Kim Cương",    "icon": "<:mine_05_diamond:1535654571039260774>", "weight": 0,  "category": "ore",  "price": 20000},
    # diamond weight=0 trong bảng cơ bản, chỉ xuất hiện ở Lv3+
}

# Weights theo cấp cuốc (6 items: stone, coal, copper, iron, gold, diamond)
_WEIGHTS_BY_LEVEL: dict[int, list[int]] = {
    1: [60, 22, 14, 4,  0, 0],   # Lv1: Không có Vàng/Kim cương
    2: [48, 25, 17, 8,  2, 0],   # Lv2: Xuất hiện Vàng hiếm
    3: [38, 26, 18, 12, 5, 1],   # Lv3: Kim Cương mức 1%
    4: [30, 24, 18, 15, 9, 4],   # Lv4 Cuốc Vàng: Kim Cương 4%
}

_LOOT_KEYS: list[str] = list(MINING_LOOT.keys())

def get_mining_display_weights(pickaxe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))


def get_mining_loot(pickaxe_level: int, food_boosts: dict = None) -> Tuple[str, int]:
    """
    Random loot dựa theo cấp Cuốc.
    Trả về (item_id, số_lượng).
    - Lv3 (Cuốc Sắt): 15% cơ hội nhận x2 quặng.
    - Lv4 (Cuốc Vàng): 20% cơ hội nhận x2 quặng.
    """
    if food_boosts is None: food_boosts = {}
    weights = list(_WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1]))
    
    # Cộng dồn tỉ lệ rare ore (từ copper, iron, gold, diamond)
    rare_bonus = float(food_boosts.get("rare_ore", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_bonus = rare_bonus + all_bonus
    
    if total_bonus > 0:
        # _LOOT_KEYS = ["stone", "coal", "copper_ore", "iron_ore", "gold_ore", "diamond"]
        # Tăng trọng số của ore (từ index 2 trở đi)
        for i in range(2, len(weights)):
            weights[i] += int(weights[i] * total_bonus)
            
    item_id: str = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]

    quantity = 1
    if pickaxe_level >= 4 and random.random() < 0.20:
        quantity = 2  # Cuốc Vàng: 20% x2
    elif pickaxe_level >= 3 and random.random() < 0.15:
        quantity = 2  # Cuốc Sắt: 15% x2

    return item_id, quantity
