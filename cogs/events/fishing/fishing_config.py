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

STAMINA_PER_FISH: int = 15
CATCH_WINDOW_SECONDS: float = 4.5   # Tăng lên 4.5s để bù lag mạng
PERFECT_CATCH_THRESHOLD: float = 2 # < 2s = Perfect Catch (x2 rare)
WAIT_MIN_SECONDS: float = 2.0
WAIT_MAX_SECONDS: float = 5.0

# ---------------------------------------------------------------------------
# CẤU HÌNH NÂNG CẤP CẦN CÂU
# ---------------------------------------------------------------------------

MAX_ROD_LEVEL: int = 3

ROD_UPGRADE_COST: dict = {
    # level_hiện_tại -> (điểm_cần, {item_id: số_lượng})
    1: (8_000,  {"stone": 5, "copper_ore": 3}),  # Lên Lv2: Cần Đồng
    2: (20_000, {"iron_ore": 5, "coal": 8}),     # Lên Lv3: Cần Sắt
}

ROD_NAMES: dict = {
    1: "Cần Tre 🎋",
    2: "Cần Đồng 🟠",
    3: "Cần Sắt ⚙️",
}

# ---------------------------------------------------------------------------
# BẢNG CÁ (FISH_LOOT)
# ---------------------------------------------------------------------------

FISH_LOOT: dict = {
    "trash":         {"name": "Rác",            "icon": "🥫", "weight": 40, "category": "fish", "rare_rank": 0},
    "carp":          {"name": "Cá Chép",        "icon": "🐟", "weight": 30, "category": "fish", "rare_rank": 1},
    "tuna":          {"name": "Cá Ngừ",         "icon": "🐡", "weight": 20, "category": "fish", "rare_rank": 2},
    "squid":         {"name": "Mực",            "icon": "🦑", "weight": 8,  "category": "fish", "rare_rank": 3},
    "legendary_fish":{"name": "Cá Huyền Thoại","icon": "🐉", "weight": 2,  "category": "fish", "rare_rank": 5},
}

# Base weights (level 1)
_BASE_WEIGHTS: list[int] = [40, 30, 20, 8, 2]
_FISH_KEYS:    list[str] = list(FISH_LOOT.keys())


def get_fishing_loot(rod_level: int, reaction_time: float) -> Tuple[str, bool]:
    """
    Random cá dựa theo cấp Cần và tốc độ phản xạ.
    Trả về (fish_id, is_perfect_catch).

    Buff theo cấp cần (mỗi level -10% Rác, phân bổ vào cá hiếm):
      Lv1: [40, 30, 20, 8, 2]
      Lv2: [30, 33, 24, 9, 4]
      Lv3: [20, 36, 28, 10, 6]

    Perfect Catch (reaction_time < 1.5s): x2 tỉ lệ Mực và Cá Huyền Thoại.
    """
    # Tính weights theo rod_level
    trash_w = max(40 - (rod_level - 1) * 10, 20)
    bonus   = (40 - trash_w)          # điểm % lấy ra từ Rác
    carp_w  = 30 + int(bonus * 0.3)   # 30% bonus vào Chép
    tuna_w  = 20 + int(bonus * 0.4)   # 40% bonus vào Ngừ
    squid_w = 8  + int(bonus * 0.15)  # 15% bonus vào Mực
    legend_w= 2  + int(bonus * 0.15)  # 15% bonus vào Huyền Thoại

    weights = [trash_w, carp_w, tuna_w, squid_w, legend_w]

    # Perfect Catch buff: x2 Mực và Huyền Thoại
    is_perfect = reaction_time < PERFECT_CATCH_THRESHOLD
    if is_perfect:
        weights[3] *= 2  # squid
        weights[4] *= 2  # legendary

    fish_id: str = random.choices(_FISH_KEYS, weights=weights, k=1)[0]
    return fish_id, is_perfect
