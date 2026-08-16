"""
skills_config.py — Cấu hình trung tâm Hệ Thống Kỹ Năng (Skills)
=================================================================

4 Skills: farming, mining, chopping, fishing
Mỗi skill có 10 cấp. Cấp 5 và 10 mở Profession (nhánh nghề nghiệp).
"""

# ---------------------------------------------------------------------------
# BẢNG KINH NGHIỆM (XP TABLE) — Cân bằng dựa theo Stardew Valley
# ---------------------------------------------------------------------------

# XP cần thiết để đạt từng cấp (1-10)
# level_xp_table[N] = tổng XP cần có để đạt cấp N
LEVEL_XP_TOTAL: dict[int, int] = {
    0: 0,
    1: 100,
    2: 380,
    3: 770,
    4: 1_300,
    5: 2_150,
    6: 3_300,
    7: 4_800,
    8: 6_900,
    9: 10_000,
    10: 15_000,
}

# XP cần thêm để đạt mỗi cấp (tính từ cấp hiện tại)
LEVEL_XP_DELTA: dict[int, int] = {
    1: 100,
    2: 280,
    3: 390,
    4: 530,
    5: 850,
    6: 1_150,
    7: 1_500,
    8: 2_100,
    9: 3_100,
    10: 5_000,
}

MAX_LEVEL = 10
RESET_COST = 25_000  # Điểm Sự Kiện cần để reset profession


def get_level_from_xp(xp: int) -> tuple[int, int, int]:
    """
    Từ tổng XP tích lũy, trả về (level, xp_in_level, xp_to_next).
    Nếu đã max level, xp_in_level = xp kể từ Lv9, xp_to_next = LEVEL_XP_DELTA[10].
    """
    level = 0
    for lv in range(1, MAX_LEVEL + 1):
        if xp >= LEVEL_XP_TOTAL[lv]:
            level = lv
        else:
            break

    if level >= MAX_LEVEL:
        xp_start = LEVEL_XP_TOTAL[MAX_LEVEL - 1]
        xp_in = xp - xp_start
        xp_need = LEVEL_XP_DELTA[MAX_LEVEL]
        return MAX_LEVEL, min(xp_in, xp_need), xp_need

    xp_start = LEVEL_XP_TOTAL[level]
    xp_in = xp - xp_start
    xp_need = LEVEL_XP_DELTA[level + 1]
    return level, xp_in, xp_need


# ---------------------------------------------------------------------------
# XP THEO ĐỘ HIẾM CỦA LỘT ĐỒ
# ---------------------------------------------------------------------------

# Mining XP by ore rarity
MINING_XP: dict[str, int] = {
    "stone":      1,
    "coal":       2,
    "copper_ore": 5,
    "iron_ore":   10,
    "gold_ore":   20,
    "diamond":    40,
}

# Woodcutting XP by wood rarity
CHOPPING_XP: dict[str, int] = {
    "twigs":      1,
    "wood":       3,
    "hardwood":   8,
    "pine_resin": 18,
    "sap":        30,
}

# Fishing XP by fish rare_rank
FISHING_XP_BY_RANK: dict[int, int] = {
    0: 1,   # trash
    1: 3,   # common (carp)
    2: 8,   # uncommon (lobster, salmon)
    3: 18,  # rare (jellyfish, squid)
    4: 35,  # epic (stingray)
    5: 60,  # legendary
}

# Farming XP by seed type
FARMING_XP: dict[str, int] = {
    "wheat":      4,
    "potato":     8,
    "tomato":     15,
    "strawberry": 22,
    "pumpkin":    30,
    "sunflower":  20,
    "star":       50,
}


# ---------------------------------------------------------------------------
# PROFESSIONS — 12 profession tổng cộng
# ---------------------------------------------------------------------------
# profession_id phải khớp với profession_5/profession_10 lưu trong DB
# parent_profession: None (Lv5) hoặc ID profession Lv5 (Lv10)

PROFESSIONS: dict[str, dict] = {
    # ── FARMING LV5 ─────────────────────────────────────
    "tiller": {
        "id": "tiller",
        "skill": "farming",
        "tier": 5,
        "parent": None,
        "name": "Nông Phu",
        "icon": "🌱",
        "description": "+10% giá trị bán tất cả vật phẩm Nông Trại.",
        "bonus_key": "sell_price_farm",
        "bonus_value": 0.10,
    },
    "rancher": {
        "id": "rancher",
        "skill": "farming",
        "tier": 5,
        "parent": None,
        "name": "Nông Hộ",
        "icon": "🏡",
        "description": "+20% hiệu quả của tất cả Đồ Ăn chế biến được.",
        "bonus_key": "food_effect_boost",
        "bonus_value": 0.20,
    },
    # ── FARMING LV10 (từ Tiller) ────────────────────────
    "artisan": {
        "id": "artisan",
        "skill": "farming",
        "tier": 10,
        "parent": "tiller",
        "name": "Thợ Thủ Công",
        "icon": "🏺",
        "description": "+40% giá bán vật phẩm chế biến từ máy móc (Wine, Jam...).",
        "bonus_key": "sell_price_artisan",
        "bonus_value": 0.40,
    },
    "agriculturist": {
        "id": "agriculturist",
        "skill": "farming",
        "tier": 10,
        "parent": "tiller",
        "name": "Nông Gia",
        "icon": "🚜",
        "description": "Giảm 10% thời gian chín của mọi loại cây trồng.",
        "bonus_key": "grow_time_reduction",
        "bonus_value": 0.10,
    },
    # ── FARMING LV10 (từ Rancher) ───────────────────────
    "shepherd": {
        "id": "shepherd",
        "skill": "farming",
        "tier": 10,
        "parent": "rancher",
        "name": "Chăn Nuôi",
        "icon": "🐑",
        "description": "50% tỉ lệ Đồ Ăn kích hoạt với thời gian x2.",
        "bonus_key": "food_double_duration",
        "bonus_value": 0.50,
    },
    "coopmaster": {
        "id": "coopmaster",
        "skill": "farming",
        "tier": 10,
        "parent": "rancher",
        "name": "Người Thợ Máy",
        "icon": "⚙️",
        "description": "Giảm 20% thời gian xử lý của Máy Móc (Lò, Thùng Rượu...).",
        "bonus_key": "machine_time_reduction",
        "bonus_value": 0.20,
    },

    # ── MINING LV5 ──────────────────────────────────────
    "miner": {
        "id": "miner",
        "skill": "mining",
        "tier": 5,
        "parent": None,
        "name": "Thợ Mỏ",
        "icon": "⛏️",
        "description": "Mỗi lần đào luôn nhận thêm +1 quặng bất kể loại nào.",
        "bonus_key": "mining_bonus_ore",
        "bonus_value": 1,
    },
    "geologist": {
        "id": "geologist",
        "skill": "mining",
        "tier": 5,
        "parent": None,
        "name": "Địa Chất Gia",
        "icon": "🔬",
        "description": "+50% tỉ lệ rơi Lootbox khi đào mỏ.",
        "bonus_key": "mining_lootbox_bonus",
        "bonus_value": 0.50,
    },
    # ── MINING LV10 (từ Miner) ──────────────────────────
    "blacksmith": {
        "id": "blacksmith",
        "skill": "mining",
        "tier": 10,
        "parent": "miner",
        "name": "Thợ Rèn",
        "icon": "🔨",
        "description": "+50% giá bán các Metal Bar.",
        "bonus_key": "sell_price_metal_bar",
        "bonus_value": 0.50,
    },
    "prospector": {
        "id": "prospector",
        "skill": "mining",
        "tier": 10,
        "parent": "miner",
        "name": "Thợ Thăm Dò",
        "icon": "🗺️",
        "description": "+20% tỉ lệ rơi Quặng Hiếm.",
        "bonus_key": "mining_rare_ore_bonus",
        "bonus_value": 0.20,
    },
    # ── MINING LV10 (từ Geologist) ──────────────────────
    "gemologist": {
        "id": "gemologist",
        "skill": "mining",
        "tier": 10,
        "parent": "geologist",
        "name": "Nhà Kim Hoàn",
        "icon": "💎",
        "description": "+100% giá bán Quặng Hiếm (Kim Cương, Vàng).",
        "bonus_key": "sell_price_rare_ore",
        "bonus_value": 1.00,
    },
    "excavator": {
        "id": "excavator",
        "skill": "mining",
        "tier": 10,
        "parent": "geologist",
        "name": "Nhà Khảo Cổ",
        "icon": "🏺",
        "description": "Lootbox khi đào mỏ có 40% cơ hội tự động nâng 1 tier, 10% nâng 2 tier.",
        "bonus_key": "mining_lootbox_tier_up",
        "bonus_value": 1,
    },

    # ── CHOPPING LV5 ────────────────────────────────────
    "forester": {
        "id": "forester",
        "skill": "chopping",
        "tier": 5,
        "parent": None,
        "name": "Lâm Nghiệp",
        "icon": "🌲",
        "description": "Mỗi lần chặt cây luôn nhận thêm +1 gỗ bất kể loại nào.",
        "bonus_key": "chopping_bonus_wood",
        "bonus_value": 1,
    },
    "gatherer": {
        "id": "gatherer",
        "skill": "chopping",
        "tier": 5,
        "parent": None,
        "name": "Tiều Phu Lành Nghề",
        "icon": "🎒",
        "description": "Giảm 1 Thể Lực tiêu hao khi chặt cây (tối thiểu 1).",
        "bonus_key": "chopping_stamina_discount",
        "bonus_value": 1,
    },
    # ── CHOPPING LV10 (từ Forester) ─────────────────────
    "lumberjack": {
        "id": "lumberjack",
        "skill": "chopping",
        "tier": 10,
        "parent": "forester",
        "name": "Vua Phá Rừng",
        "icon": "🪓",
        "description": "+20% tỉ lệ rơi Gỗ Hiếm (Gỗ Cứng, Nhựa Thông, Nhựa Cây).",
        "bonus_key": "chopping_rare_wood_bonus",
        "bonus_value": 0.20,
    },
    "tapper": {
        "id": "tapper",
        "skill": "chopping",
        "tier": 10,
        "parent": "forester",
        "name": "Thợ Nhựa",
        "icon": "🧴",
        "description": "+50% giá bán tất cả vật phẩm gỗ.",
        "bonus_key": "sell_price_wood",
        "bonus_value": 0.50,
    },
    # ── CHOPPING LV10 (từ Gatherer) ─────────────────────
    "botanist": {
        "id": "botanist",
        "skill": "chopping",
        "tier": 10,
        "parent": "gatherer",
        "name": "Nhà Thực Vật",
        "icon": "🌿",
        "description": "Mỗi lần chặt, nhận thêm +1 unit gỗ bổ sung (cộng thêm với bonus Forester nếu có).",
        "bonus_key": "chopping_extra_bonus",
        "bonus_value": 1,
    },
    "tracker": {
        "id": "tracker",
        "skill": "chopping",
        "tier": 10,
        "parent": "gatherer",
        "name": "Thợ Sưu Tầm",
        "icon": "🔍",
        "description": "Khi chặt cây, có 25% tỉ lệ nhận thêm 1 drops ngẫu nhiên từ Mine hoặc Fishing.",
        "bonus_key": "chopping_cross_drop",
        "bonus_value": 0.25,
    },

    # ── FISHING LV5 ─────────────────────────────────────
    "fisher": {
        "id": "fisher",
        "skill": "fishing",
        "tier": 5,
        "parent": None,
        "name": "Cần Thủ",
        "icon": "🎣",
        "description": "+25% tỉ lệ rơi Cá Hiếm.",
        "bonus_key": "fishing_rare_bonus",
        "bonus_value": 0.25,
    },
    "trapper": {
        "id": "trapper",
        "skill": "fishing",
        "tier": 5,
        "parent": None,
        "name": "Bẫy Thủ",
        "icon": "🕸️",
        "description": "Tăng giới hạn Perfect Catch lên 3.5s.",
        "bonus_key": "fishing_perfect_window",
        "bonus_value": 1.5,
    },
    # ── FISHING LV10 (từ Fisher) ────────────────────────
    "angler": {
        "id": "angler",
        "skill": "fishing",
        "tier": 10,
        "parent": "fisher",
        "name": "Đại Cần Thủ",
        "icon": "🏆",
        "description": "+50% giá bán tất cả các loại cá.",
        "bonus_key": "sell_price_fish",
        "bonus_value": 0.50,
    },
    "pirate": {
        "id": "pirate",
        "skill": "fishing",
        "tier": 10,
        "parent": "fisher",
        "name": "Cướp Biển",
        "icon": "🏴‍☠️",
        "description": "Nhân đôi tỉ lệ rơi Cá Hiếm.",
        "bonus_key": "fishing_double_rare",
        "bonus_value": 2,
    },
    # ── FISHING LV10 (từ Trapper) ───────────────────────
    "mariner": {
        "id": "mariner",
        "skill": "fishing",
        "tier": 10,
        "parent": "trapper",
        "name": "Thủy Thủ",
        "icon": "⚓",
        "description": "Không bao giờ câu được Rác. Tỉ lệ Rác sẽ được chia cho các loại cá khác.",
        "bonus_key": "fishing_no_trash",
        "bonus_value": 1,
    },
    "luremaster": {
        "id": "luremaster",
        "skill": "fishing",
        "tier": 10,
        "parent": "trapper",
        "name": "Bậc Thầy Mồi Câu",
        "icon": "🎭",
        "description": "Khi đạt Perfect Catch, có 30% cơ hội câu được x2 số lượng cá.",
        "bonus_key": "fishing_double_catch",
        "bonus_value": 0.3,
    },
}


# ---------------------------------------------------------------------------
# ĐỊNH NGHĨA 4 SKILLS
# ---------------------------------------------------------------------------

SKILLS: dict[str, dict] = {
    "farming": {
        "id":          "farming",
        "name":        "Nông Trại",
        "icon":        "🌾",
        "color":       0x2ecc71,
        "description": "Kỹ năng trồng trọt. Thu hoạch nhiều loại cây để tích lũy kinh nghiệm.",
        "xp_source":   "Thu hoạch cây trồng tại Nông Trại. Cây quý hiếm cho nhiều XP hơn.",
        "per_level_bonus": "+3% tỉ lệ thu hoạch kép và giảm -1% thời gian cây chín mỗi cấp.",
        "professions_5":  ["tiller", "rancher"],
        "professions_10": {
            "tiller":  ["artisan", "agriculturist"],
            "rancher": ["shepherd", "coopmaster"],
        },
    },
    "mining": {
        "id":          "mining",
        "name":        "Khai Thác Mỏ",
        "icon":        "⛏️",
        "color":       0x7f8c8d,
        "description": "Kỹ năng khai thác quặng. Đào sâu hơn để tìm khoáng sản quý giá.",
        "xp_source":   "Đập đá trong Khu Mỏ. Quặng quý hiếm cho nhiều XP hơn.",
        "per_level_bonus": "Mỗi cấp tăng tỉ lệ rơi quặng hiếm và giảm tỉ lệ đá thường.",
        "professions_5":  ["miner", "geologist"],
        "professions_10": {
            "miner":     ["blacksmith", "prospector"],
            "geologist": ["gemologist", "excavator"],
        },
    },
    "chopping": {
        "id":          "chopping",
        "name":        "Chặt Gỗ",
        "icon":        "🪓",
        "color":       0x27ae60,
        "description": "Kỹ năng chặt cây. Phát triển kỹ năng để tìm được vật liệu gỗ quý hơn.",
        "xp_source":   "Chặt cây trong Khu Rừng. Gỗ hiếm và nhựa cây cho nhiều XP hơn.",
        "per_level_bonus": "Mỗi cấp tăng tỉ lệ rơi Gỗ Hiếm và giảm tỉ lệ rơi Que Củi.",
        "professions_5":  ["forester", "gatherer"],
        "professions_10": {
            "forester": ["lumberjack", "tapper"],
            "gatherer": ["botanist", "tracker"],
        },
    },
    "fishing": {
        "id":          "fishing",
        "name":        "Câu Cá",
        "icon":        "🎣",
        "color":       0x1abc9c,
        "description": "Kỹ năng câu cá. Luyện tập phản xạ để câu được những loài cá quý hiếm.",
        "xp_source":   "Câu cá tại Hồ Câu Cá. Cá càng hiếm, càng nhiều XP.",
        "per_level_bonus": "Mỗi cấp tăng tỉ lệ rơi Cá Hiếm và giảm tỉ lệ Rác.",
        "professions_5":  ["fisher", "trapper"],
        "professions_10": {
            "fisher":  ["angler", "pirate"],
            "trapper": ["mariner", "luremaster"],
        },
    },
}

# Per-level passive bonuses (applied incrementally)
# Mỗi cấp kỹ năng sẽ dịch chuyển weight table theo hướng hiếm hơn
# Giá trị này là số % shift mỗi cấp
SKILL_PER_LEVEL_BONUS = {
    "farming":  {"double_harvest_pct": 3.0, "grow_time_reduction_pct": 1.0},
    "mining":   {"rare_shift_pct": 2.0},   # shift 2% từ stone sang các ore hiếm
    "chopping": {"rare_shift_pct": 2.5},   # shift 2.5% từ twigs sang gỗ hiếm
    "fishing":  {"rare_shift_pct": 2.0, "perfect_window_bonus": 0.1},  # +0.1s/cấp
}


def get_skill_level_info(skills_data: dict, skill_id: str) -> tuple[int, int, int, int]:
    """Lấy (level, xp_total, xp_in_level, xp_to_next) của 1 skill."""
    skill = skills_data.get(skill_id, {})
    xp = skill.get("xp", 0)
    level, xp_in, xp_need = get_level_from_xp(xp)
    return level, xp, xp_in, xp_need


def get_professions_for_skill(skill_id: str, tier: int, parent_profession_id: str | None = None) -> list[dict]:
    """Lấy danh sách profession khả dụng theo tier và parent."""
    result = []
    for prof_id, prof in PROFESSIONS.items():
        if prof["skill"] == skill_id and prof["tier"] == tier:
            if tier == 5 and prof["parent"] is None:
                result.append(prof)
            elif tier == 10 and prof["parent"] == parent_profession_id:
                result.append(prof)
    return result
