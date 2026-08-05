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
    1: "Cuốc Đá 🪨",
    2: "Cuốc Đồng 🟠",
    3: "Cuốc Sắt ⚙️",
    4: "Cuốc Vàng 🌟",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT QUẶNG (MINING_LOOT)
# ---------------------------------------------------------------------------

MINING_LOOT: dict = {
    "stone":      {"name": "Đá",           "icon": "🪨", "weight": 55, "category": "ore",  "price": 50},
    "coal":       {"name": "Than Đá",      "icon": "⬛", "weight": 22, "category": "ore",  "price": 150},
    "copper_ore": {"name": "Quặng Đồng",   "icon": "🟠", "weight": 14, "category": "ore",  "price": 500},
    "iron_ore":   {"name": "Quặng Sắt",    "icon": "⚙️", "weight": 7,  "category": "ore",  "price": 1500},
    "gold_ore":   {"name": "Quặng Vàng",   "icon": "🌕", "weight": 2,  "category": "ore",  "price": 5000},
    "diamond":    {"name": "Kim Cương",    "icon": "💎", "weight": 0,  "category": "ore",  "price": 20000},
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


def get_mining_loot(pickaxe_level: int) -> Tuple[str, int]:
    """
    Random loot dựa theo cấp Cuốc.
    Trả về (item_id, số_lượng).
    - Lv3 (Cuốc Sắt): 15% cơ hội nhận x2 quặng.
    - Lv4 (Cuốc Vàng): 20% cơ hội nhận x2 quặng.
    """
    weights = _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1])
    item_id: str = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]

    quantity = 1
    if pickaxe_level >= 4 and random.random() < 0.20:
        quantity = 2  # Cuốc Vàng: 20% x2
    elif pickaxe_level >= 3 and random.random() < 0.15:
        quantity = 2  # Cuốc Sắt: 15% x2

    return item_id, quantity
