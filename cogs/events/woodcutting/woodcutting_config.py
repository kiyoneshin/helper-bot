"""
woodcutting_config.py — Cấu hình hệ thống Lâm Nghiệp (Chặt Gỗ)
"""
import random

# ---------------------------------------------------------------------------
# CẤU HÌNH THỂ LỰC (STAMINA)
# ---------------------------------------------------------------------------
STAMINA_PER_CHOP: int = 5

# ---------------------------------------------------------------------------
# CẤU HÌNH NÂNG CẤP RÌU
# ---------------------------------------------------------------------------
MAX_AXE_LEVEL: int = 3

AXE_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (10_000, {"wood": 10, "copper_ore": 5}),  # Lên Lv2: Rìu Đồng
    2: (30_000, {"hardwood": 10, "iron_ore": 5}),  # Lên Lv3: Rìu Sắt
}

AXE_NAMES: dict = {
    1: "Rìu Cùn 🪓",
    2: "Rìu Đồng 🟠",
    3: "Rìu Sắt ⚙️",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT GỖ (WOODCUTTING_LOOT)
# ---------------------------------------------------------------------------
WOODCUTTING_LOOT: dict = {
    "twigs":    {"name": "Que Củi",    "icon": "🪵", "weight": 60, "category": "wood", "price": 20},
    "wood":     {"name": "Gỗ Thường",  "icon": "🌲", "weight": 25, "category": "wood", "price": 100},
    "hardwood": {"name": "Gỗ Cứng",    "icon": "🌳", "weight": 12, "category": "wood", "price": 400},
    "sap":      {"name": "Nhựa Cây",   "icon": "💧", "weight": 3,  "category": "wood", "price": 1200},
}

_WEIGHTS_BY_LEVEL: dict[int, list[int]] = {
    1: [70, 20, 8, 2],   # Rìu Cùn: Rất nhiều củi, ít gỗ tốt
    2: [55, 30, 12, 3],  # Rìu Đồng: Cân bằng
    3: [40, 35, 18, 7],  # Rìu Sắt: Tỷ lệ đồ xịn tăng mạnh
}

_LOOT_KEYS: list[str] = list(WOODCUTTING_LOOT.keys())

def get_woodcutting_display_weights(axe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))

def get_woodcutting_loot(axe_level: int) -> tuple[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1])
    chosen = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]
    qty = 1
    if axe_level == 3 and chosen in ["twigs", "wood"] and random.random() < 0.2:
        qty = 2
    return chosen, qty
