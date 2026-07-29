"""
fishing_config.py — Cấu hình Minigame Câu Cá
=============================================
Tỉ lệ xuất hiện cá, chi phí thể lực, và thông tin hiển thị.
"""

# ---------------------------------------------------------------------------
# CẤU HÌNH
# ---------------------------------------------------------------------------

STAMINA_PER_FISH: int = 15
"""Thể lực tiêu hao mỗi lần quăng cần."""

CATCH_WINDOW_SECONDS: float = 2.0
"""Thời gian (giây) người chơi có để bấm "Giật Cần" trước khi cá chạy mất."""

WAIT_MIN_SECONDS: float = 2.0
"""Thời gian chờ tối thiểu (giây) trước khi cá cắn câu."""

WAIT_MAX_SECONDS: float = 5.0
"""Thời gian chờ tối đa (giây) trước khi cá cắn câu."""

# ---------------------------------------------------------------------------
# BẢNG CÁ (FISH_LOOT)
# Tổng weight = 100 để dễ đọc như phần trăm.
# ---------------------------------------------------------------------------

FISH_LOOT: dict = {
    "trash": {
        "name": "Rác",
        "icon": "🥫",
        "weight": 40,
        "category": "fish",
        "rare_rank": 0,     # 0 = không phải cá, 5 = huyền thoại
    },
    "carp": {
        "name": "Cá Chép",
        "icon": "🐟",
        "weight": 30,
        "category": "fish",
        "rare_rank": 1,
    },
    "tuna": {
        "name": "Cá Ngừ",
        "icon": "🐡",
        "weight": 20,
        "category": "fish",
        "rare_rank": 2,
    },
    "squid": {
        "name": "Mực",
        "icon": "🦑",
        "weight": 8,
        "category": "fish",
        "rare_rank": 3,
    },
    "legendary_fish": {
        "name": "Cá Huyền Thoại",
        "icon": "🐉",
        "weight": 2,
        "category": "fish",
        "rare_rank": 5,
    },
}

# Trích xuất sẵn để dùng với random.choices()
_FISH_KEYS:    list[str] = list(FISH_LOOT.keys())
_FISH_WEIGHTS: list[int] = [v["weight"] for v in FISH_LOOT.values()]
