"""
fishing_config.py — Cấu hình Minigame Câu Cá
=============================================
Tỉ lệ xuất hiện cá, chi phí thể lực, nâng cấp cần câu và RNG theo level.
"""
import random
from typing import Tuple

# ---------------------------------------------------------------------------
# CẤU HÌNH
# ---------------------------------------------------------------------------

STAMINA_PER_FISH: int = 3
CATCH_WINDOW_SECONDS: float = 4.5   # Tăng lên 4.5s để bù lag mạng
PERFECT_CATCH_THRESHOLD: float = 2  # < 2s = Perfect Catch (x2 rare)
WAIT_MIN_SECONDS: float = 2.0
WAIT_MAX_SECONDS: float = 5.0

# ---------------------------------------------------------------------------
# CẤU HÌNH NÂNG CẤP CẦN CÂU
# ---------------------------------------------------------------------------

MAX_ROD_LEVEL: int = 4

ROD_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (8_000,  {"wood": 10, "copper_ore": 5}),                       # Lên Lv2: Cần Đồng
    2: (20_000, {"hardwood": 5, "iron_ore": 5}),                       # Lên Lv3: Cần Sắt
    3: (70_000, {"gold_bar": 3, "stingray": 2, "legendary_fish": 1}),  # Lên Lv4: Cần Vàng
}

ROD_NAMES: dict = {
    1: "Cần Tre 🎋",
    2: "Cần Đồng 🟠",
    3: "Cần Sắt ⚙️",
    4: "Cần Vàng 🌟",
}

# ---------------------------------------------------------------------------
# BẢNG CÁ (FISH_LOOT)
# ---------------------------------------------------------------------------

FISH_LOOT: dict = {
    "trash":          {"name": "Rác",             "icon": "🥫", "weight": 35, "category": "fish", "rare_rank": 0, "price": 10},
    "carp":           {"name": "Cá Chép",         "icon": "🐟", "weight": 28, "category": "fish", "rare_rank": 1, "price": 200},
    "lobster":        {"name": "Tôm Hùm",         "icon": "🦞", "weight": 18, "category": "fish", "rare_rank": 2, "price": 600},
    "salmon":         {"name": "Cá Hồi",          "icon": "🍣", "weight": 10, "category": "fish", "rare_rank": 2, "price": 900},
    "jellyfish":      {"name": "Sứa",             "icon": "🪼", "weight": 5,  "category": "fish", "rare_rank": 3, "price": 2000},
    "squid":          {"name": "Mực",             "icon": "🦑", "weight": 3,  "category": "fish", "rare_rank": 3, "price": 2500},
    "stingray":       {"name": "Cá Đuối",         "icon": "🦈", "weight": 1,  "category": "fish", "rare_rank": 4, "price": 6000},
    "legendary_fish": {"name": "Cá Huyền Thoại", "icon": "🐉", "weight": 0,  "category": "fish", "rare_rank": 5, "price": 15000},
    # legendary_fish weight=0, chỉ xuất hiện khi Perfect Catch ở Lv3+
}

_FISH_KEYS: list[str] = list(FISH_LOOT.keys())

def get_fishing_display_weights(rod_level: int) -> dict[str, int]:
    """Tính weights hiển thị theo cấp cần, dùng cho embed."""
    weights = _get_weights(rod_level, is_perfect=False)
    return dict(zip(_FISH_KEYS, weights))


def _get_weights(rod_level: int, is_perfect: bool) -> list[int]:
    """
    Weights động theo cấp cần câu.
    Mỗi cấp giảm Rác và tăng cá hiếm.
    legendary_fish (weight=0) chỉ xuất hiện khi Perfect + Lv3+.
    
    Layout: [trash, carp, lobster, salmon, jellyfish, squid, stingray, legendary]
    """
    base = {
        1: [42, 30, 16, 8,  3, 1,  0, 0],
        2: [32, 30, 18, 10, 5, 3,  2, 0],
        3: [22, 28, 20, 12, 8, 6,  4, 0],
        4: [15, 25, 20, 14, 10, 8, 6, 2],
    }
    w = list(base.get(rod_level, base[1]))

    # Perfect Catch: x2 tỉ lệ Mực, Cá Đuối, và kích hoạt Cá Huyền Thoại ở Lv3+
    if is_perfect:
        w[5] = w[5] * 2  # squid
        w[6] = w[6] * 2  # stingray
        if rod_level >= 3:
            w[7] = max(w[7], 1)  # legendary mức 1 khi Perfect + Lv3
        if rod_level >= 4:
            w[7] = 5  # legendary 5% khi Perfect + Lv4
    return w


def get_fishing_loot(rod_level: int, reaction_time: float, food_boosts: dict = None) -> Tuple[str, bool]:
    """
    Random cá dựa theo cấp Cần và tốc độ phản xạ.
    Trả về (fish_id, is_perfect_catch).
    """
    if food_boosts is None: food_boosts = {}
    is_perfect = reaction_time < PERFECT_CATCH_THRESHOLD
    weights = list(_get_weights(rod_level, is_perfect))
    
    # Cộng dồn tỉ lệ rare fish (legendary)
    rare_bonus = float(food_boosts.get("rare_fish", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_bonus = rare_bonus + all_bonus
    
    if total_bonus > 0:
        # legendary_fish is the last in _FISH_KEYS
        idx = len(_FISH_KEYS) - 1
        weights[idx] += int(weights[idx] * total_bonus)
        
    fish_id: str = random.choices(_FISH_KEYS, weights=weights, k=1)[0]
    return fish_id, is_perfect
