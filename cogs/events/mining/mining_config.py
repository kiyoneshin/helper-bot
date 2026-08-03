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

MAX_PICKAXE_LEVEL: int = 3

PICKAXE_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (10_000, {"wood": 20, "copper_ore": 10}),  # Lên Lv2: Cuốc Đồng
    2: (25_000, {"hardwood": 10, "iron_ore": 10}),    # Lên Lv3: Cuốc Sắt
}

PICKAXE_NAMES: dict = {
    1: "Cuốc Đá 🪨",
    2: "Cuốc Đồng 🟠",
    3: "Cuốc Sắt ⚙️",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT QUẶNG (MINING_LOOT)
# ---------------------------------------------------------------------------

MINING_LOOT: dict = {
    "stone":      {"name": "Đá",          "icon": "🪨", "weight": 60, "category": "ore", "price": 50},
    "coal":       {"name": "Than Đá",     "icon": "⬛", "weight": 20, "category": "ore", "price": 150},
    "copper_ore": {"name": "Quặng Đồng",  "icon": "🟠", "weight": 15, "category": "ore", "price": 500},
    "iron_ore":   {"name": "Quặng Sắt",   "icon": "⚙️", "weight": 5,  "category": "ore", "price": 1500},
}

# Weights theo cấp cuốc
_WEIGHTS_BY_LEVEL: dict[int, list[int]] = {
    1: [60, 20, 15, 5],  # Đá 60%, Than 20%, Đồng 15%, Sắt 5%
    2: [45, 25, 20, 10], # Cuốc Đồng: ít Đá hơn, nhiều quặng hơn
    3: [40, 25, 22, 13], # Cuốc Sắt: cao nhất (+ bonus x2 riêng)
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
    """
    weights = _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1])
    item_id: str = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]

    quantity = 1
    if pickaxe_level >= 3 and random.random() < 0.15:
        quantity = 2  # Cuốc Sắt: 15% x2

    return item_id, quantity
