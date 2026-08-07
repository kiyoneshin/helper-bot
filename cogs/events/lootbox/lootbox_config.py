"""
lootbox_config.py — Cấu hình hệ thống Lootbox 6 tầng
=======================================================
Quản lý tỉ lệ drop, pool vật phẩm, cơ chế Luck, và logic roll.
"""

import random
from typing import NamedTuple, Optional

# ---------------------------------------------------------------------------
# ID LOOTBOX (khớp với item_config.py ID 60-65)
# ---------------------------------------------------------------------------
LB_COMMON    = 60
LB_UNCOMMON  = 61
LB_RARE      = 62
LB_EPIC      = 63
LB_LEGENDARY = 64
LB_GODLY     = 65

# Chữ viết tắt tier → ID
TIER_ALIASES: dict[str, int] = {
    "common":    LB_COMMON,    "c": LB_COMMON,
    "uncommon":  LB_UNCOMMON,  "u": LB_UNCOMMON,
    "rare":      LB_RARE,      "r": LB_RARE,
    "epic":      LB_EPIC,      "e": LB_EPIC,
    "legendary": LB_LEGENDARY, "l": LB_LEGENDARY,
    "godly":     LB_GODLY,     "g": LB_GODLY,
}

TIER_NAMES: dict[int, str] = {
    LB_COMMON:    "Common",
    LB_UNCOMMON:  "Uncommon",
    LB_RARE:      "Rare",
    LB_EPIC:      "Epic",
    LB_LEGENDARY: "Legendary",
    LB_GODLY:     "Godly",
}

TIER_EMOJIS: dict[int, str] = {
    LB_COMMON:    "📦",
    LB_UNCOMMON:  "🟢",
    LB_RARE:      "🔵",
    LB_EPIC:      "🟣",
    LB_LEGENDARY: "🟠",
    LB_GODLY:     "🌟",
}

TIER_COLORS: dict[int, int] = {
    LB_COMMON:    0xaaaaaa,
    LB_UNCOMMON:  0x55aa55,
    LB_RARE:      0x5588ff,
    LB_EPIC:      0xaa44ff,
    LB_LEGENDARY: 0xff8800,
    LB_GODLY:     0xffd700,
}

# Rank colors cho vật phẩm nhận được
RANK_COLORS: dict[int, str] = {
    0: "⬜",  # Common
    1: "🟩",  # Common+
    2: "🟦",  # Rare
    3: "🟪",  # Epic
    4: "🟧",  # Legendary
    5: "🌟",  # Godly
}

# ---------------------------------------------------------------------------
# CẤU HÌNH TIER — weights theo rare_rank [rank0, rank1, rank2, rank3, rank4, rank5]
# ---------------------------------------------------------------------------
# Mỗi rank tương ứng với rare_rank trong drop pool
TIER_RANK_WEIGHTS: dict[int, list[int]] = {
    LB_COMMON:    [60, 40,  0,  0,  0,  0],
    LB_UNCOMMON:  [25, 50, 25,  0,  0,  0],
    LB_RARE:      [ 5, 25, 45, 25,  0,  0],
    LB_EPIC:      [ 0,  5, 25, 45, 25,  0],
    LB_LEGENDARY: [ 0,  0,  5, 35, 45, 15],
    LB_GODLY:     [ 0,  0,  0, 15, 40, 45],
}

# Weights khi buff item 6 active (tăng tỉ lệ rank cao hơn)
TIER_RANK_WEIGHTS_BUFFED: dict[int, list[int]] = {
    LB_COMMON:    [40, 55,  5,  0,  0,  0],
    LB_UNCOMMON:  [10, 40, 45,  5,  0,  0],
    LB_RARE:      [ 0, 10, 40, 45,  5,  0],
    LB_EPIC:      [ 0,  0, 15, 40, 40,  5],
    LB_LEGENDARY: [ 0,  0,  0, 25, 45, 30],
    LB_GODLY:     [ 0,  0,  0,  5, 30, 65],
}

# Giá mua trong shop (None = không bán)
TIER_PRICES: dict[int, Optional[int]] = {
    LB_COMMON:    500,
    LB_UNCOMMON:  1_500,
    LB_RARE:      4_000,
    LB_EPIC:      12_000,
    LB_LEGENDARY: None,
    LB_GODLY:     None,
}

# ---------------------------------------------------------------------------
# DROP POOL — gộp từ fish/mine/wood theo rare_rank
# ---------------------------------------------------------------------------

class DropItem(NamedTuple):
    item_id: str    # key trong farm_data.inventory
    name:    str
    icon:    str
    qty:     int    # số lượng nhận được
    rank:    int    # 0-5

# Pool theo rank — gộp từ các hệ thống hiện có
RANK_POOL: dict[int, list[tuple[str, str, str]]] = {
    # (item_id, name, icon) — qty sẽ random 1-2
    0: [
        ("trash",  "Rác",       "🥫"),
        ("stone",  "Đá",        "🪨"),
        ("twigs",  "Que Củi",   "🪵"),
    ],
    1: [
        ("carp",    "Cá Chép",   "🐟"),
        ("coal",    "Than Đá",   "⬛"),
        ("wood",    "Gỗ Thường", "🌲"),
    ],
    2: [
        ("tuna",       "Cá Ngừ",     "🐡"),
        ("salmon",     "Cá Hồi",     "🍣"),
        ("copper_ore", "Quặng Đồng", "🟠"),
        ("iron_ore",   "Quặng Sắt",  "⚙️"),
        ("hardwood",   "Gỗ Cứng",   "🌳"),
    ],
    3: [
        ("pufferfish", "Cá Nóc",     "🐠"),
        ("squid",      "Mực",        "🦑"),
        ("gold_ore",   "Quặng Vàng", "🌕"),
        ("pine_resin", "Nhựa Thông", "🫙"),
        ("sap",        "Nhựa Cây",   "💧"),
    ],
    4: [
        ("octopus",  "Bạch Tuộc",  "🐙"),
        ("diamond",  "Kim Cương",  "💎"),
    ],
    5: [
        ("legendary_fish", "Cá Huyền Thoại", "🐉"),
        ("diamond",        "Kim Cương x2",   "💎"),
        ("sap",            "Nhựa Cây x2",    "💧"),
    ],
}

# ---------------------------------------------------------------------------
# DROP CHANCE — lootbox rơi ra từ fish/mine/chop
# ---------------------------------------------------------------------------
# Format: activity -> {tier_id: base_chance_percent}
ACTIVITY_DROP_CHANCES: dict[str, dict[int, float]] = {
    "fish": {
        LB_COMMON:    5.0,
        LB_UNCOMMON:  2.0,
        LB_RARE:      0.5,
        LB_EPIC:      0.1,
        LB_LEGENDARY: 0.01,
    },
    "mine": {
        LB_COMMON:    4.0,
        LB_UNCOMMON:  1.5,
        LB_RARE:      0.4,
        LB_EPIC:      0.08,
        LB_LEGENDARY: 0.008,
    },
    "chop": {
        LB_COMMON:    3.0,
        LB_UNCOMMON:  1.0,
        LB_RARE:      0.3,
        LB_EPIC:      0.05,
        LB_LEGENDARY: 0.005,
    },
}

# Luck bonus: mỗi lần action, roll thêm x% trong [a, b] per luck_point
LUCK_BONUS_RANGE_PER_POINT: tuple[float, float] = (0.003, 0.015)  # giảm buff trên mỗi điểm luck
LUCK_MAX_CAP: int = 1500  # tối đa 1500 luck

# Cooldown cầu nguyện: 10 phút
PRAY_COOLDOWN_MINUTES: int = 10

# Cooldown mua lootbox từ shop: 6 giờ / lần
LB_BUY_COOLDOWN_HOURS: int = 6


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def parse_tier(raw: str) -> Optional[int]:
    """Phân giải tier từ tên hoặc chữ tắt. VD: 'c' → 60, 'epic' → 63."""
    return TIER_ALIASES.get(raw.lower().strip())


def calc_luck_bonus(luck: int) -> float:
    """
    Tính bonus % từ luck (random trong khoảng [a, b] per point).
    VD: luck=100, a=0.01, b=0.05 → random giữa 1% và 5%.
    """
    if luck <= 0:
        return 0.0
    capped = min(luck, LUCK_MAX_CAP)
    per_point = random.uniform(*LUCK_BONUS_RANGE_PER_POINT)
    return capped * per_point  # % bonus


def get_activity_lootbox_drop(
    activity: str,
    luck: int = 0,
    item6_active: bool = False,
) -> Optional[int]:
    """
    Roll xem có drop lootbox từ activity (fish/mine/chop) không.
    Trả về tier_id nếu drop, None nếu không.
    """
    chances = ACTIVITY_DROP_CHANCES.get(activity, {})
    if not chances:
        return None

    luck_bonus = calc_luck_bonus(luck)  # % thêm vào
    multiplier = 1.5 if item6_active else 1.0

    # Roll từng tier từ hiếm nhất xuống thường nhất
    for tier_id in [LB_LEGENDARY, LB_EPIC, LB_RARE, LB_UNCOMMON, LB_COMMON]:
        base = chances.get(tier_id, 0)
        if base <= 0:
            continue
        effective = (base + luck_bonus) * multiplier
        if random.random() * 100 < effective:
            return tier_id
    return None


def roll_lootbox(tier_id: int, luck: int = 0, item6_active: bool = False) -> DropItem:
    """
    Mở 1 lootbox. Trả về DropItem.
    - Chọn rank bằng weighted random (có bonus luck)
    - Chọn item trong rank đó
    - Godly tier có bonus đặc biệt (điểm / thẻ BM) được xử lý riêng
    """
    weights = TIER_RANK_WEIGHTS_BUFFED[tier_id] if item6_active else TIER_RANK_WEIGHTS[tier_id]
    ranks = list(range(len(weights)))

    # Luck tăng nhẹ weight của các rank cao
    luck_bonus = calc_luck_bonus(luck)
    adjusted = list(weights)
    for i in range(len(adjusted) - 1, 0, -1):
        bump = luck_bonus * 0.2 * (i / (len(adjusted) - 1))
        adjusted[i] = max(0, adjusted[i] + bump)
        adjusted[i - 1] = max(0, adjusted[i - 1] - bump * 0.5)

    chosen_rank = random.choices(ranks, weights=adjusted, k=1)[0]

    # Lấy pool của rank đó
    pool = RANK_POOL.get(chosen_rank, RANK_POOL[0])
    item_id, name, icon = random.choice(pool)

    # Qty: rank cao hơn có thể cho x2
    if chosen_rank >= 5:
        qty = 2
    elif chosen_rank >= 3:
        qty = random.choices([1, 2], weights=[70, 30], k=1)[0]
    else:
        qty = 1

    return DropItem(item_id=item_id, name=name, icon=icon, qty=qty, rank=chosen_rank)


def roll_godly_bonus() -> Optional[dict]:
    """
    30% cơ hội nhận thêm điểm event (1k-5k)
    10% cơ hội nhận thẻ BM (item 26 hoặc 27)
    5% cơ hội nhận Hạt Giống Ngôi Sao (item 12)
    Trả về {"type": "points"/"bm_item"/"seed", "value": ...} hoặc None
    """
    roll = random.random()
    if roll < 0.05:
        return {"type": "seed", "item_id": 12, "name": "Hạt Giống Ngôi Sao", "icon": "⭐"}
    elif roll < 0.15:
        chosen_id = random.choice([26, 27])
        names = {26: "Thẻ Miễn Nhiễm", 27: "Thẻ Đặc Xá"}
        return {"type": "bm_item", "item_id": chosen_id, "name": names[chosen_id], "icon": "🛡️" if chosen_id == 26 else "🕊️"}
    elif roll < 0.45:
        pts = random.randint(1_000, 5_000)
        return {"type": "points", "value": pts}
    return None
