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
    1: "Cần Tre <:fish_08_wooden_fishing_pole:1535649348577140736>",
    2: "Cần Đồng <:fish_09_copper_fishing_rod:1535649350745718784>",
    3: "Cần Sắt <:fish_10_iron_fishing_rod:1535649352654266418>",
    4: "Cần Vàng <:fish_11_gold_fishing_rod:1535649354851811478>",
}

# ---------------------------------------------------------------------------
# BẢNG CÁ (FISH_LOOT)
# ---------------------------------------------------------------------------

FISH_LOOT: dict = {
    "trash":          {"name": "Rác",             "icon": "<:fish_00_trash:1535649328562053230>", "weight": 35, "category": "fish", "rare_rank": 0, "price": 1},
    "carp":           {"name": "Cá Chép",         "icon": "<:fish_01_carp:1535649330881634354>", "weight": 28, "category": "fish", "rare_rank": 1, "price": 3},
    "lobster":        {"name": "Tôm Hùm",         "icon": "<:fish_02_lobster:1535649333762985994>", "weight": 18, "category": "fish", "rare_rank": 2, "price": 8},
    "salmon":         {"name": "Cá Hồi",          "icon": "<:fish_03_salmon:1535649337458163763>", "weight": 10, "category": "fish", "rare_rank": 2, "price": 12},
    "jellyfish":      {"name": "Sứa",             "icon": "<:fish_04_jelly_fish:1535649339454652426>", "weight": 5,  "category": "fish", "rare_rank": 3, "price": 20},
    "squid":          {"name": "Mực",             "icon": "<:fish_05_squid:1535649341254017024>", "weight": 3,  "category": "fish", "rare_rank": 3, "price": 30},
    "stingray":       {"name": "Cá Đuối",         "icon": "<:fish_06_stingray:1535649344156467260>", "weight": 1,  "category": "fish", "rare_rank": 4, "price": 50},
    "legendary_fish": {"name": "Cá Huyền Thoại", "icon": "<:fish_07_legendary:1535649346421395526>", "weight": 0,  "category": "fish", "rare_rank": 5, "price": 120},
    # legendary_fish weight=0, chỉ xuất hiện khi Perfect Catch ở Lv3+
}

_FISH_KEYS: list[str] = list(FISH_LOOT.keys())

def get_fishing_display_weights(rod_level: int) -> dict[str, int]:
    """Tính weights hiển thị theo cấp cần, dùng cho embed."""
    weights = _get_weights(rod_level, is_perfect=False)
    return dict(zip(_FISH_KEYS, weights))


def get_fishing_effective_weights(rod_level: int, food_boosts: dict = None, skills_data: dict = None) -> dict[str, float]:
    """
    Tính bảng tỉ lệ % thực tế của cá sau khi áp dụng tất cả buff (skill + food + profession).
    Dùng bảng non-perfect để hiển thị cơ bản, normalize về 100%.
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}

    from cogs.events.skills.skills_db import has_profession
    weights = list(_get_weights(rod_level, is_perfect=False))

    # Skill per-level shift
    fishing_level = skills_data.get("fishing", {}).get("level", 0)
    rare_shift = min(fishing_level * 2.0, 30.0)
    if rare_shift > 0:
        max_reduce = weights[0] * (rare_shift / 100)
        per_rare = max_reduce / 5
        weights[0] = max(weights[0] - int(max_reduce), 2)
        for i in range(1, len(weights)):
            weights[i] = int(weights[i] + per_rare)

    # Mariner profession: không rác, phân bổ theo tỉ lệ giảm dần cho các cá khác
    if has_profession(skills_data, "fishing", "mariner") and weights[0] > 0:
        trash_w = weights[0]
        weights[0] = 0
        dist = [0.40, 0.15, 0.15, 0.10, 0.10, 0.08, 0.02]
        for i in range(1, len(weights)):
            weights[i] += trash_w * dist[i-1]

    # Food boosts
    rare_bonus = float(food_boosts.get("rare_fish", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_bonus = rare_bonus + all_bonus
    if total_bonus > 0:
        idx = len(_FISH_KEYS) - 1
        weights[idx] += int(weights[idx] * total_bonus)

    # Fisher profession
    if has_profession(skills_data, "fishing", "fisher"):
        for i in range(4, len(weights)):
            weights[i] = int(weights[i] * 1.25)

    # Pirate profession
    if has_profession(skills_data, "fishing", "pirate"):
        for i in range(4, len(weights)):
            weights[i] = weights[i] * 2

    # Normalize về 100%
    total = sum(weights) or 1
    return {k: round(w / total * 100, 1) for k, w in zip(_FISH_KEYS, weights)}


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


def get_fishing_loot(rod_level: int, reaction_time: float, food_boosts: dict = None, skills_data: dict = None) -> Tuple[str, bool, int]:
    """
    Random cá dựa theo cấp Cần, phản xạ và Skill Fishing bonuses.
    Trả về (fish_id, is_perfect_catch, quantity).
    """
    if food_boosts is None: food_boosts = {}
    if skills_data is None: skills_data = {}

    from cogs.events.skills.skills_db import has_profession

    # --- Tính Perfect Catch threshold ---
    effective_threshold = PERFECT_CATCH_THRESHOLD
    if has_profession(skills_data, "fishing", "trapper"):
        effective_threshold += 1.5

    is_perfect = reaction_time < effective_threshold
    weights = list(_get_weights(rod_level, is_perfect))

    # --- Skill per-level: Mỗi cấp Fishing shift 2% từ trash sang rare fish ---
    fishing_level = skills_data.get("fishing", {}).get("level", 0)
    rare_shift = min(fishing_level * 2.0, 30.0)
    if rare_shift > 0:
        max_reduce = weights[0] * (rare_shift / 100)
        per_rare = max_reduce / 5  # phân phối cho 5 loại cá có rank > 0
        weights[0] = max(weights[0] - int(max_reduce), 2)
        for i in range(1, len(weights)):
            weights[i] = int(weights[i] + per_rare)

    # --- Mariner profession: không rác, chuyển weight sang các loại cá khác ---
    if has_profession(skills_data, "fishing", "mariner") and weights[0] > 0:
        trash_w = weights[0]
        weights[0] = 0
        dist = [0.40, 0.15, 0.15, 0.10, 0.10, 0.08, 0.02]
        for i in range(1, len(weights)):
            weights[i] += int(trash_w * dist[i-1])

    # --- Food boosts: tăng rare fish ---
    rare_bonus = float(food_boosts.get("rare_fish", {}).get("value", 0))
    all_bonus = float(food_boosts.get("all_boost", {}).get("value", 0))
    total_bonus = rare_bonus + all_bonus
    if total_bonus > 0:
        idx = len(_FISH_KEYS) - 1
        weights[idx] += int(weights[idx] * total_bonus)

    # --- Fisher profession: +25% tỉ lệ cá Rare (rank 3+) ---
    if has_profession(skills_data, "fishing", "fisher"):
        # Rare fish: jellyfish(4), squid(5), stingray(6), legendary(7)
        for i in range(4, len(weights)):
            weights[i] = int(weights[i] * 1.25)

    # --- Pirate profession: x2 tỉ lệ cá Rare (rank 3+) ---
    if has_profession(skills_data, "fishing", "pirate"):
        for i in range(4, len(weights)):
            weights[i] = weights[i] * 2

    # --- Normalize trước random để tổng luôn đồng đều ---
    total = sum(weights)
    if total <= 0:
        weights = list(_get_weights(rod_level, is_perfect))

    fish_id: str = random.choices(_FISH_KEYS, weights=weights, k=1)[0]
    
    qty = 1
    # --- Luremaster profession: 30% x2 qty khi Perfect Catch ---
    if is_perfect and has_profession(skills_data, "fishing", "luremaster"):
        if random.random() < 0.30:
            qty = 2

    return fish_id, is_perfect, qty

