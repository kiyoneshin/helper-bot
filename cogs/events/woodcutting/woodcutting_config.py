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
MAX_AXE_LEVEL: int = 4

AXE_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (10_000, {"wood": 10, "copper_ore": 5}),                  # Lên Lv2: Rìu Đồng
    2: (30_000, {"hardwood": 10, "iron_ore": 5}),                 # Lên Lv3: Rìu Sắt
    3: (90_000, {"iron_bar": 5, "gold_bar": 3, "pine_resin": 5}), # Lên Lv4: Rìu Vàng
}

AXE_NAMES: dict = {
    1: "Rìu Cùn 🪓",
    2: "Rìu Đồng 🟠",
    3: "Rìu Sắt ⚙️",
    4: "Rìu Vàng 🌟",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT GỖ (WOODCUTTING_LOOT)
# ---------------------------------------------------------------------------
WOODCUTTING_LOOT: dict = {
    "twigs":      {"name": "Que Củi",    "icon": "🪵", "weight": 55, "category": "wood", "price": 20},
    "wood":       {"name": "Gỗ Thường",  "icon": "🌲", "weight": 25, "category": "wood", "price": 100},
    "hardwood":   {"name": "Gỗ Cứng",    "icon": "🌳", "weight": 12, "category": "wood", "price": 400},
    "pine_resin": {"name": "Nhựa Thông", "icon": "🫙", "weight": 5,  "category": "wood", "price": 1500},
    "sap":        {"name": "Nhựa Cây",   "icon": "💧", "weight": 3,  "category": "wood", "price": 3000},
}

_WEIGHTS_BY_LEVEL: dict[int, list[int]] = {
    # 5 items: twigs, wood, hardwood, pine_resin, sap
    1: [70, 20, 8,  2, 0],   # Lv1 Rìu Cùn: Không có Nhựa cây
    2: [55, 28, 12, 4, 1],   # Lv2 Rìu Đồng
    3: [40, 32, 18, 7, 3],   # Lv3 Rìu Sắt
    4: [30, 32, 22, 10, 6],  # Lv4 Rìu Vàng: Nhựa Cây 6%
}

_LOOT_KEYS: list[str] = list(WOODCUTTING_LOOT.keys())

def get_woodcutting_display_weights(axe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))

def get_woodcutting_loot(axe_level: int, food_boosts: dict = None) -> tuple[str, int]:
    if food_boosts is None: food_boosts = {}
    
    weights = list(_WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1]))
    
    # Cộng dồn tỉ lệ rare wood
    rare_bonus = float(food_boosts.get("rare_wood", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_bonus = rare_bonus + all_bonus
    
    if total_bonus > 0:
        # Giả sử _LOOT_KEYS = ["twigs", "wood", "hardwood", "pine_resin", "sap"]
        # hardwood là rare wood, ta tăng trọng số của nó lên (weights[2])
        if len(weights) > 2:
            weights[2] += int(weights[2] * total_bonus)
            
    chosen = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]
    qty = 1
    # Rìu Sắt Lv3: 20% nhân đôi Twigs/Wood; Rìu Vàng Lv4: 25%
    if axe_level >= 4 and chosen in ["twigs", "wood"] and random.random() < 0.25:
        qty = 2
    elif axe_level == 3 and chosen in ["twigs", "wood"] and random.random() < 0.20:
        qty = 2
    return chosen, qty
