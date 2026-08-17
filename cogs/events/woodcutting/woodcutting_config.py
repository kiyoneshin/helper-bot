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
    1: "Rìu Cùn <:wood_05_basic_hatchet:1535654327836868648>",
    2: "Rìu Đồng <:wood_06_copper_hatchet:1535654329669787719>",
    3: "Rìu Sắt <:wood_07_iron_hatchet:1535654331771265034>",
    4: "Rìu Vàng <:wood_08_gold_hatchet:1535654333931331654>",
}

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT GỖ (WOODCUTTING_LOOT)
# ---------------------------------------------------------------------------
WOODCUTTING_LOOT: dict = {
    "twigs":      {"name": "Que Củi",    "icon": "<:wood_00_twigs:1535654317321748570>", "weight": 55, "category": "wood", "price": 1},
    "wood":       {"name": "Gỗ Thường",  "icon": "<:wood_01_wood_scrap:1535654318856999043>", "weight": 25, "category": "wood", "price": 3},
    "hardwood":   {"name": "Gỗ Cứng",    "icon": "<:wood_02_hardwood:1535654321025196102>", "weight": 12, "category": "wood", "price": 10},
    "pine_resin": {"name": "Nhựa Thông", "icon": "<:wood_03_resin:1535654323231522857>", "weight": 5,  "category": "wood", "price": 30},
    "sap":        {"name": "Nhựa Cây",   "icon": "<:wood_04_sap:1535654325530136636>", "weight": 3,  "category": "wood", "price": 60},
}

_WEIGHTS_BY_LEVEL: dict[int, list[int]] = {
    # 5 items: twigs, wood, hardwood, pine_resin, sap
    1: [70, 20, 8,  2, 0],   # Lv1 Rìu Cùn: Không có Nhựa cây
    2: [55, 28, 12, 4, 1],   # Lv2 Rìu Đồng
    3: [40, 32, 18, 7, 3],   # Lv3 Rìu Sắt
    4: [30, 32, 22, 10, 6],  # Lv4 Rìu Vàng: Nhựa Cây 6%
}

_LOOT_KEYS: list[str] = list(WOODCUTTING_LOOT.keys())

def apply_rare_shift(weights: list[float], normal_indices: list[int], rare_indices: list[int], rare_dist: list[float], shift_pct: float, max_shift: float = 0.8):
    """
    Hút weight từ normal_indices và phân bổ cho rare_indices theo tỉ lệ rare_dist.
    max_shift: tối đa hút bao nhiêu % của normal weight (mặc định 80% để chừa lại 1 ít đồ thường).
    """
    if shift_pct <= 0: return
    shift_pct = min(shift_pct, max_shift)
    
    stolen = 0.0
    for idx in normal_indices:
        reduce_amount = weights[idx] * shift_pct
        weights[idx] -= reduce_amount
        stolen += reduce_amount
        
    for i, idx in enumerate(rare_indices):
        weights[idx] += stolen * rare_dist[i]


def _apply_woodcutting_boosts(axe_level: int, food_boosts: dict, skills_data: dict) -> list[float]:
    from cogs.events.skills.skills_db import has_profession
    weights = list(float(w) for w in _WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1]))
    
    chopping_level = skills_data.get("chopping", {}).get("level", 0)
    food_rare = float(food_boosts.get("rare_wood", {}).get("value", 0))
    food_all = float(food_boosts.get("all_boost", {}).get("value", 0))
    prof_bonus = 0.20 if has_profession(skills_data, "chopping", "lumberjack") else 0.0
    
    from cogs.events.skills.skills_config import SKILL_PER_LEVEL_BONUS
    rare_shift = SKILL_PER_LEVEL_BONUS["chopping"].get("rare_shift_pct", 2.5) / 100.0
    shift_pct = (chopping_level * rare_shift) + food_rare + food_all + prof_bonus
    
    # Normal: twigs (0), wood (1)
    # Rare: hardwood (2), pine_resin (3), sap (4)
    # Dist: 50%, 30%, 20%
    apply_rare_shift(weights, [0, 1], [2, 3, 4], [0.50, 0.30, 0.20], shift_pct, max_shift=0.8)
    
    return weights


def get_woodcutting_display_weights(axe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))


def get_woodcutting_effective_weights(axe_level: int, food_boosts: dict = None, skills_data: dict = None) -> dict[str, float]:  # type: ignore
    """
    Tính bảng tỉ lệ % thực tế sau khi áp dụng tất cả buff (skill + food + profession).
    Normalize về tổng 100%.
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}
    
    weights = _apply_woodcutting_boosts(axe_level, food_boosts, skills_data)
    total = sum(weights) or 1
    return {k: round(w / total * 100, 1) for k, w in zip(_LOOT_KEYS, weights)}


def get_woodcutting_loot(axe_level: int, food_boosts: dict = None, skills_data: dict = None) -> tuple[str, int]:  # type: ignore
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}
    from cogs.events.skills.skills_db import has_profession

    weights = _apply_woodcutting_boosts(axe_level, food_boosts, skills_data)
    
    total = sum(weights)
    if total <= 0:
        weights = list(_WEIGHTS_BY_LEVEL.get(axe_level, _WEIGHTS_BY_LEVEL[1]))

    chosen = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]
    qty = 1

    # Double chance theo cấp rìu
    if axe_level >= 4 and chosen in ["twigs", "wood"] and random.random() < 0.25:
        qty = 2
    elif axe_level == 3 and chosen in ["twigs", "wood"] and random.random() < 0.20:
        qty = 2

    # --- Forester profession: +1 gỗ ---
    if has_profession(skills_data, "chopping", "forester"):
        qty += 1

    # --- Botanist profession: +1 gỗ bổ sung (cộng thêm với Forester) ---
    if has_profession(skills_data, "chopping", "botanist"):
        qty += 1

    return chosen, qty

