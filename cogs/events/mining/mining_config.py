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
STAMINA_REGEN_INTERVAL_SECONDS: int = 60  # 60 giây hồi 1 điểm -> 100 điểm mất 1h40m

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
    "stone":      {"name": "Đá",           "icon": "<:mine_00_stone:1535654559412781067>", "weight": 55, "category": "ore",  "price": 1},
    "coal":       {"name": "Than Đá",      "icon": "<:mine_01_coal:1535654561480708106>", "weight": 22, "category": "ore",  "price": 2},
    "copper_ore": {"name": "Quặng Đồng",   "icon": "<:mine_02_copper_ore:1535654564504670449>", "weight": 14, "category": "ore",  "price": 5},
    "iron_ore":   {"name": "Quặng Sắt",    "icon": "<:mine_03_iron_ore:1535654566853615717>", "weight": 7,  "category": "ore",  "price": 10},
    "gold_ore":   {"name": "Quặng Vàng",   "icon": "<:mine_04_gold_ore:1535654569143566396>", "weight": 2,  "category": "ore",  "price": 20},
    "diamond":    {"name": "Kim Cương",    "icon": "<:mine_05_diamond:1535654571039260774>", "weight": 0,  "category": "ore",  "price": 50},
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

def apply_rare_shift(weights: list[float], normal_indices: list[int], rare_indices: list[int], rare_dist: list[float], shift_pct: float, max_shift: float = 0.8):
    if shift_pct <= 0: return
    shift_pct = min(shift_pct, max_shift)
    
    stolen = 0.0
    for idx in normal_indices:
        reduce_amount = weights[idx] * shift_pct
        weights[idx] -= reduce_amount
        stolen += reduce_amount
        
    for i, idx in enumerate(rare_indices):
        weights[idx] += stolen * rare_dist[i]


def _apply_mining_boosts(pickaxe_level: int, food_boosts: dict, skills_data: dict) -> list[float]:
    from cogs.events.skills.skills_db import has_profession
    weights = list(float(w) for w in _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1]))
    
    mining_level = skills_data.get("mining", {}).get("level", 0)
    food_rare = float(food_boosts.get("rare_ore", {}).get("value", 0))
    food_all = float(food_boosts.get("all_boost", {}).get("value", 0))
    prof_bonus = 0.20 if has_profession(skills_data, "mining", "prospector") else 0.0
    
    from cogs.events.skills.skills_config import SKILL_PER_LEVEL_BONUS
    rare_shift = SKILL_PER_LEVEL_BONUS["mining"].get("rare_shift_pct", 2.0) / 100.0
    shift_pct = (mining_level * rare_shift) + food_rare + food_all + prof_bonus
    
    # Normal: stone (0), coal (1)
    # Rare: copper (2), iron (3), gold (4), diamond (5)
    # Dist: 45%, 30%, 15%, 10%
    apply_rare_shift(weights, [0, 1], [2, 3, 4, 5], [0.45, 0.30, 0.15, 0.10], shift_pct, max_shift=0.8)
    
    return weights


def get_mining_display_weights(pickaxe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))


def get_mining_effective_weights(pickaxe_level: int, food_boosts: dict = None, skills_data: dict = None) -> dict[str, float]:
    """
    Tính bảng tỉ lệ % thực tế sau khi áp dụng tất cả buff (skill + food + profession).
    Normalize về tổng 100% để hiển thị chính xác trên UI.
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}
    
    weights = _apply_mining_boosts(pickaxe_level, food_boosts, skills_data)
    total = sum(weights) or 1
    return {k: round(w / total * 100, 1) for k, w in zip(_LOOT_KEYS, weights)}


def get_mining_loot(pickaxe_level: int, food_boosts: dict = None, skills_data: dict = None) -> Tuple[str, int]:
    """
    Random loot dựa theo cấp Cuốc + Skill Mining passive bonus.
    Trả về (item_id, số_lượng).
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}
    from cogs.events.skills.skills_db import has_profession

    weights = _apply_mining_boosts(pickaxe_level, food_boosts, skills_data)
    
    total = sum(weights)
    if total <= 0:
        weights = list(_WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1]))

    item_id: str = random.choices(_LOOT_KEYS, weights=weights, k=1)[0]

    # --- Tính số lượng ---
    quantity = 1
    if pickaxe_level >= 4 and random.random() < 0.20:
        quantity = 2
    elif pickaxe_level >= 3 and random.random() < 0.15:
        quantity = 2

    # --- Miner profession: luôn +1 ore ---
    if has_profession(skills_data, "mining", "miner"):
        quantity += 1

    return item_id, quantity

