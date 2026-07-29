"""
mining_config.py — Cấu hình hệ thống Khu Mỏ
==============================================
Định nghĩa thể lực, tốc độ hồi phục, và bảng tỉ lệ rớt quặng.
"""

# ---------------------------------------------------------------------------
# CẤU HÌNH THỂ LỰC (STAMINA)
# ---------------------------------------------------------------------------

MAX_STAMINA: int = 100
"""Thể lực tối đa."""

STAMINA_PER_HIT: int = 10
"""Số thể lực tiêu hao mỗi lần đập đá."""

STAMINA_REGEN_RATE: int = 1
"""Số thể lực hồi phục mỗi khoảng thời gian."""

STAMINA_REGEN_INTERVAL_SECONDS: int = 3 * 60
"""Khoảng thời gian (giây) để hồi 1 điểm thể lực (3 phút/1 điểm)."""

# ---------------------------------------------------------------------------
# BẢNG TỶ LỆ RỚT QUẶNG (MINING_LOOT)
# Tổng weight = 100 để dễ đọc như phần trăm.
# ---------------------------------------------------------------------------

MINING_LOOT: dict = {
    "stone": {
        "name": "Đá",
        "icon": "🪨",
        "weight": 60,   # 60% cơ hội
        "category": "ore",
    },
    "coal": {
        "name": "Than Đá",
        "icon": "⬛",
        "weight": 20,   # 20% cơ hội
        "category": "ore",
    },
    "copper_ore": {
        "name": "Quặng Đồng",
        "icon": "🟠",
        "weight": 15,   # 15% cơ hội
        "category": "ore",
    },
    "iron_ore": {
        "name": "Quặng Sắt",
        "icon": "⚙️",
        "weight": 5,    # 5% cơ hội
        "category": "ore",
    },
}

# Danh sách tuần tự để dùng với random.choices() (trích trọng số)
_LOOT_KEYS:   list[str] = list(MINING_LOOT.keys())
_LOOT_WEIGHTS: list[int] = [v["weight"] for v in MINING_LOOT.values()]
