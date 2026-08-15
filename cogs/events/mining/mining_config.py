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
STAMINA_REGEN_INTERVAL_SECONDS: int = 60  # 60 giây hồi 1 <:symbol_points_p:1538282388507987989> -> 100 <:symbol_points_p:1538282388507987989> mất 1h40m

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

def get_mining_display_weights(pickaxe_level: int) -> dict[str, int]:
    weights = _WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1])
    return dict(zip(_LOOT_KEYS, weights))


def get_mining_loot(pickaxe_level: int, food_boosts: dict = None, skills_data: dict = None) -> Tuple[str, int]:
    """
    Random loot dựa theo cấp Cuốc + Skill Mining passive bonus.
    Trả về (item_id, số_lượng).
    - Lv3 (Cuốc Sắt): 15% cơ hội nhận x2 quặng.
    - Lv4 (Cuốc Vàng): 20% cơ hội nhận x2 quặng.
    - Miner profession: luôn +1 quặng.
    - Prospector profession: +20% tỉ lệ quặng hiếm.
    - Skill level: mỗi cấp Mining dịch chuyển 2% weight từ stone sang ore hiếm.
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}

    weights = list(_WEIGHTS_BY_LEVEL.get(pickaxe_level, _WEIGHTS_BY_LEVEL[1]))

    # --- Skill per-level passive: Mỗi cấp Mining shift 2% từ stone sang rare ore ---
    from cogs.events.skills.skills_db import get_skill_bonus, has_profession
    mining_level = skills_data.get("mining", {}).get("level", 0)
    rare_shift = min(mining_level * 2.0, 30.0)  # Tối đa shift 30%

    if rare_shift > 0:
        # Trừ từ stone (index 0), phân phối đều cho copper/iron/gold/diamond (index 2-5)
        max_reduce = weights[0] * (rare_shift / 100)
        per_rare = max_reduce / 4
        weights[0] = max(weights[0] - int(max_reduce), 5)
        for i in range(2, len(weights)):
            weights[i] = int(weights[i] + per_rare)

    # --- Food boosts ---
    rare_bonus = float(food_boosts.get("rare_ore", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_food_bonus = rare_bonus + all_bonus
    if total_food_bonus > 0:
        for i in range(2, len(weights)):
            weights[i] += int(weights[i] * total_food_bonus)

    # --- Prospector profession: +20% tỉ lệ quặng hiếm ---
    if has_profession(skills_data, "mining", "prospector"):
        for i in range(2, len(weights)):
            weights[i] = int(weights[i] * 1.20)

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

