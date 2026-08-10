# =====================================================================
# CẤU HÌNH THÀNH TỰU & DANH HIỆU (ACHIEVEMENTS & TITLES)
# =====================================================================
# Mỗi thành tựu sẽ có một ID duy nhất. Người dùng hoàn thành mốc (target)
# sẽ nhận được Danh Hiệu (title) và Hộp quà (Lootbox) hoặc Điểm.

# Danh sách danh mục để hiển thị trên UI
ACH_CATEGORIES = {
    "eco": "<:ach_ecosystem:1535664845309878363> Hệ Sinh Thái",
    "casino": "<:ach_gambling:1535664851223978024> Casino & Cờ Bạc",
    "love": "<:ach_marriage:1535664860485128253> Tình Yêu",
    "general": "<:ach_general:1535664853308670042> Chung"
}

ACHIEVEMENTS = {
    # ── HỆ SINH THÁI (ECO) ───────────────────────────────────────────
    "eco_wood_1": {
        "id": "eco_wood_1",
        "category": "eco",
        "name": "Lâm Tặc Tập Sự",
        "desc": "Chặt được 100 Khúc Gỗ các loại.",
        "stat_key": "wood_chopped",
        "target": 100,
        "reward_title": "🌲 Lâm Tặc Tập Sự",
        "reward_lootbox": (61, 2) # (Lootbox ID, Số lượng) -> 60 là Common
    },
    "eco_wood_2": {
        "id": "eco_wood_2",
        "category": "eco",
        "name": "Vua Phá Rừng",
        "desc": "Chặt được 1,000 Khúc Gỗ các loại.",
        "stat_key": "wood_chopped",
        "target": 1000,
        "reward_title": "<:symbol_00_woodcutting:1536007697491558491> Vua Phá Rừng",
        "reward_lootbox": (63, 2) # 62 là Rare
    },
    "eco_rare_wood": {
        "id": "eco_rare_wood",
        "category": "eco",
        "name": "Bàn Tay Vàng Làng Chặt Gỗ",
        "desc": "Chặt được 50 Gỗ Hiếm (Rare Wood trở lên).",
        "stat_key": "rare_wood_chopped",
        "target": 50,
        "reward_title": "✨ Bàn Tay Vàng",
        "reward_lootbox": (64, 1) # 63 là Epic
    },
    "eco_mine_1": {
        "id": "eco_mine_1",
        "category": "eco",
        "name": "Thợ Mỏ Chăm Chỉ",
        "desc": "Đào được 200 Quặng các loại.",
        "stat_key": "ore_mined",
        "target": 200,
        "reward_title": "<:symbol_00_mining:1536007694920585356> Thợ Mỏ Chăm Chỉ",
        "reward_lootbox": (61, 3)
    },
    "eco_mine_2": {
        "id": "eco_mine_2",
        "category": "eco",
        "name": "Chúa Tể Lòng Đất",
        "desc": "Đào được 2,000 Quặng các loại.",
        "stat_key": "ore_mined",
        "target": 2000,
        "reward_title": "💎 Chúa Tể Lòng Đất",
        "reward_lootbox": (65, 1) # 64 là Legendary
    },
    "eco_fish_1": {
        "id": "eco_fish_1",
        "category": "eco",
        "name": "Cần Thủ Ao Làng",
        "desc": "Câu được 150 con cá.",
        "stat_key": "fish_caught",
        "target": 150,
        "reward_title": "🎣 Cần Thủ Ao Làng",
        "reward_lootbox": (62, 2) # 61 là Uncommon
    },
    "eco_fish_legend": {
        "id": "eco_fish_legend",
        "category": "eco",
        "name": "Huyền Thoại Biển Sâu",
        "desc": "Câu được 10 Cá Huyền Thoại.",
        "stat_key": "legendary_fish",
        "target": 10,
        "reward_title": "🦈 Huyền Thoại Biển Sâu",
        "reward_lootbox": (65, 1)
    },
    "eco_farm_1": {
        "id": "eco_farm_1",
        "category": "eco",
        "name": "Nông Dân Chăm Chỉ",
        "desc": "Thu hoạch 500 nông sản.",
        "stat_key": "crops",
        "target": 500,
        "reward_title": "🌻 Nông Dân Chăm Chỉ",
        "reward_lootbox": (62, 3)
    },
    "eco_farm_giant": {
        "id": "eco_farm_giant",
        "category": "eco",
        "name": "Chuyên Gia Đột Biến",
        "desc": "Thu hoạch 10 Cây Khổng Lồ.",
        "stat_key": "giant_crops",
        "target": 10,
        "reward_title": "🧬 Chuyên Gia Đột Biến",
        "reward_lootbox": (64, 2)
    },

    # ── CASINO (CASINO) ──────────────────────────────────────────────
    "casino_play_1": {
        "id": "casino_play_1",
        "category": "casino",
        "name": "Con Bạc Tân Binh",
        "desc": "Chơi Casino 100 lần (Bất kỳ trò nào).",
        "stat_key": "casino_played",
        "target": 100,
        "reward_title": "<a:gambling_slot_machine_pixel:1536322200838340628> Con Bạc Tân Binh",
        "reward_lootbox": (61, 2)
    },
    "casino_play_2": {
        "id": "casino_play_2",
        "category": "casino",
        "name": "Ma Cờ Bạc",
        "desc": "Chơi Casino 1,000 lần.",
        "stat_key": "casino_played",
        "target": 1000,
        "reward_title": "🃏 Ma Cờ Bạc",
        "reward_lootbox": (63, 2)
    },
    "casino_win_1": {
        "id": "casino_win_1",
        "category": "casino",
        "name": "Thần Bài Xuất Thế",
        "desc": "Thắng Casino 500 lần.",
        "stat_key": "casino_wins",
        "target": 500,
        "reward_title": "🃏 Thần Bài Xuất Thế",
        "reward_lootbox": (64, 1)
    },
    "casino_crash": {
        "id": "casino_crash",
        "category": "casino",
        "name": "Phi Hành Gia Liều Lĩnh",
        "desc": "Ăn Crash với hệ số x10 trở lên 5 lần.",
        "stat_key": "crash_x10",
        "target": 5,
        "reward_title": "🚀 Phi Hành Gia Liều Lĩnh",
        "reward_lootbox": (64, 1)
    },
    "casino_baucua": {
        "id": "casino_baucua",
        "category": "casino",
        "name": "Trùm Sòng Bầu Cua",
        "desc": "Thắng Bầu Cua 50 lần.",
        "stat_key": "baucua_wins",
        "target": 50,
        "reward_title": "🦀 Trùm Sòng Bầu Cua",
        "reward_lootbox": (62, 3)
    },

    # ── TÌNH YÊU (LOVE) ──────────────────────────────────────────────
    "love_marry_1": {
        "id": "love_marry_1",
        "category": "love",
        "name": "Kẻ Đang Yêu",
        "desc": "Đạt 1,000 Điểm Thân Mật (Intimacy).",
        "stat_key": "intimacy",
        "target": 1000,
        "reward_title": "💕 Kẻ Đang Yêu",
        "reward_lootbox": (62, 2)
    },
    "love_marry_2": {
        "id": "love_marry_2",
        "category": "love",
        "name": "Uyên Ương Liền Cánh",
        "desc": "Đạt 10,000 Điểm Thân Mật.",
        "stat_key": "intimacy",
        "target": 10000,
        "reward_title": "💞 Uyên Ương Liền Cánh",
        "reward_lootbox": (64, 2)
    },
    "love_pet": {
        "id": "love_pet",
        "category": "love",
        "name": "Con Sen Chính Hiệu",
        "desc": "Nâng cấp Thú cưng tình yêu lên Level 20.",
        "stat_key": "pet_level",
        "target": 20,
        "reward_title": "🐾 Con Sen Chính Hiệu",
        "reward_lootbox": (63, 2)
    },
    "love_ring": {
        "id": "love_ring",
        "category": "love",
        "name": "Đại Gia Si Tình",
        "desc": "Sở hữu Nhẫn Cưới Tối Thượng (Cấp Max).",
        "stat_key": "ring_level",
        "target": 10, # Cấp 10
        "reward_title": "💍 Đại Gia Si Tình",
        "reward_lootbox": (65, 1)
    },

    # ── CHUNG (GENERAL) ──────────────────────────────────────────────
    "gen_quests": {
        "id": "gen_quests",
        "category": "general",
        "name": "Kẻ Đánh Thuê",
        "desc": "Hoàn thành 100 Nhiệm vụ (Quests).",
        "stat_key": "quests",
        "target": 100,
        "reward_title": "📜 Kẻ Đánh Thuê",
        "reward_lootbox": (63, 2)
    },
    "gen_jail": {
        "id": "gen_jail",
        "category": "general",
        "name": "Tù Nhân Lương Tâm",
        "desc": "Bị tống vào chuồng chó 50 lần.",
        "stat_key": "jails",
        "target": 50,
        "reward_title": "⛓️ Tù Nhân Lương Tâm",
        "reward_lootbox": (61, 5)
    },
    "gen_work": {
        "id": "gen_work",
        "category": "general",
        "name": "Công Nhân Gương Mẫu",
        "desc": "Làm việc (Work) 500 lần.",
        "stat_key": "works",
        "target": 500,
        "reward_title": "👷 Công Nhân Gương Mẫu",
        "reward_lootbox": (62, 3)
    },
    "gen_rich": {
        "id": "gen_rich",
        "category": "general",
        "name": "Phú Hào",
        "desc": "Tích lũy được 10 Triệu Điểm Sự Kiện.",
        "stat_key": "total_earned",
        "target": 10000000,
        "reward_title": "💰 Phú Hào",
        "reward_lootbox": (65, 2)
    }
}
