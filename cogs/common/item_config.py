"""
item_config.py — Bảng cấu hình trung tâm cho toàn bộ vật phẩm của bot.
======================================================================
Là nguồn sự thật duy nhất (single source of truth) cho tất cả items.

Quy ước ID:
  0  –  9 : Sự kiện / Event   (lottery, event items)
  10 – 19 : Nông trại / Farm  (hạt giống)
  20 – 29 : Chợ đen / Black Market

Cấu trúc mỗi item:
  id          (int)          : ID số duy nhất.
  name        (str)          : Tên hiển thị.
  icon        (str)          : Emoji đại diện.
  price       (int | None)   : Giá mua (None = không thể mua).
  description (str)          : Mô tả vật phẩm.
  db_key      (str)          : Key lưu trong Database.
  category    (str)          : "event" | "farm" | "blackmarket"
  usable      (bool)         : Có dùng bằng y!use không.
"""

from typing import TypedDict

class ItemEntry(TypedDict):
    id: int
    name: str
    icon: str
    price: int | None
    description: str
    db_key: str
    category: str
    usable: bool

# ============================================================
# REGISTRY CHÍNH — Dict[int, ItemEntry]
# ============================================================
ITEM_REGISTRY: dict[int, ItemEntry] = {

    # ──────────────────────────────────────────────────────────
    # ID 0–9 : SỰ KIỆN (EVENT)
    # ──────────────────────────────────────────────────────────
    0: {
        "id":          0,
        "name":        "Vé Xổ Số",
        "icon":        "🎟️",
        "price":       50,
        "description": "Vé tham gia xổ số hàng ngày. Tối đa 200 vé/người.",
        "db_key":      "lottery_ticket",   # xử lý đặc biệt qua bảng lottery_tickets
        "category":    "event",
        "usable":      False,
    },
    1: {
        "id":          1,
        "name":        "Hộp Quà Bí Ẩn (Gacha)",
        "icon":        "🎁",
        "price":       2500,
        "description": "Mở ra phần thưởng ngẫu nhiên.",
        "db_key":      "item_1",
        "category":    "event",
        "usable":      True,
    },
    2: {
        "id":          2,
        "name":        "Role Màu Sự Kiện",
        "icon":        "🎭",
        "price":       10000,
        "description": "Nhận role màu trong 7 ngày.",
        "db_key":      "item_2",
        "category":    "event",
        "usable":      False,
    },
    3: {
        "id":          3,
        "name":        "Role Màu Thiết Kế Riêng",
        "icon":        "🎨",
        "price":       30000,
        "description": "Nhận role màu thiết kế riêng trong 30 ngày.",
        "db_key":      "item_3",
        "category":    "event",
        "usable":      False,
    },
    4: {
        "id":          4,
        "name":        "Role Biểu Tượng Vĩnh Viễn",
        "icon":        "👑",
        "price":       70000,
        "description": "Nhận role biểu tượng vĩnh viễn (Giới hạn: 5 slot).",
        "db_key":      "item_4",
        "category":    "event",
        "usable":      False,
    },
    5: {
        "id":          5,
        "name":        "Vật Phẩm Tối Cao",
        "icon":        "🏆",
        "price":       110000,
        "description": "Nitro / Custom Đặc Quyền.",
        "db_key":      "item_5",
        "category":    "event",
        "usable":      False,
    },
    6: {
        "id":          6,
        "name":        "Thẻ Tăng Tốc",
        "icon":        "⚡",
        "price":       None,              # Không bán trong shop — chỉ nhận qua sự kiện
        "description": "Giảm 50% thời gian hồi thể lực trong 30 phút.",
        "db_key":      "boost_card",
        "category":    "event",
        "usable":      True,
    },

    # ──────────────────────────────────────────────────────────
    # ID 10–19 : NÔNG TRẠI (FARM — Hạt giống)
    # ──────────────────────────────────────────────────────────
    10: {
        "id":          10,
        "name":        "Hạt Giống Lúa Mì",
        "icon":        "🌾",
        "price":       100,
        "description": "Cây cơ bản, thu hoạch sau 30 phút.",
        "db_key":      "seed_wheat",       # key trong farm_data.inventory
        "category":    "farm",
        "usable":      False,              # Dùng qua y!farm, không y!use
    },
    11: {
        "id":          11,
        "name":        "Hạt Giống Hướng Dương",
        "icon":        "🌻",
        "price":       500,
        "description": "Lợi nhuận cao, thu hoạch sau 12 tiếng.",
        "db_key":      "seed_sunflower",
        "category":    "farm",
        "usable":      False,
    },
    12: {
        "id":          12,
        "name":        "Hạt Giống Ngôi Sao",
        "icon":        "⭐",
        "price":       2000,
        "description": "Cây hiếm với phần thưởng ngẫu nhiên, thu hoạch sau 24 tiếng.",
        "db_key":      "seed_star",
        "category":    "farm",
        "usable":      False,
    },

    # ──────────────────────────────────────────────────────────
    # ID 20–29 : CHỢ ĐEN (BLACK MARKET)
    # ──────────────────────────────────────────────────────────
    20: {
        "id":          20,
        "name":        "Bom Ảo Giác",
        "icon":        "💣",
        "price":       1500,               # Tier 1 — Gây khó chịu nhẹ, không mất gì thực sự
        "description": "Bot tag mục tiêu 3 lần liên tiếp rồi xóa ngay lập tức (Ghost Ping).",
        "db_key":      "ghost_ping_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    21: {
        "id":          21,
        "name":        "Búa Gõ 1 Phút",
        "icon":        "🔨",
        "price":       3000,               # Tier 2 — Phiền toái ngắn hạn
        "description": "Timeout mục tiêu 1 phút (cấm chat/voice).",
        "db_key":      "timeout_1m",
        "category":    "blackmarket",
        "usable":      True,
    },
    22: {
        "id":          22,
        "name":        "Thẻ Đổi Tên",
        "icon":        "🤡",
        "price":       5000,               # Tier 2 — Xấu hổ nhẹ, đổi nick tấu hài
        "description": "Buộc mục tiêu đổi biệt danh thành tên tấu hài tùy ý người dùng.",
        "db_key":      "nickname_change",
        "category":    "blackmarket",
        "usable":      True,
    },
    23: {
        "id":          23,
        "name":        "Bao Tay Đạo Chích",
        "icon":        "🧤",
        "price":       7000,               # Tier 3 — Mất điểm thực, ảnh hưởng kinh tế
        "description": "Trộm ngẫu nhiên 50–500 điểm sự kiện của mục tiêu.",
        "db_key":      "thief_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    24: {
        "id":          24,
        "name":        "Thẻ Rút Phích Cắm",
        "icon":        "🔌",
        "price":       8000,               # Tier 3 — Cướp trải nghiệm voice ngay lập tức
        "description": "Đá văng mục tiêu khỏi Voice Channel ngay lập tức.",
        "db_key":      "disconnect_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    25: {
        "id":          25,
        "name":        "Búa Gõ 5 Phút",
        "icon":        "🔨",
        "price":       10000,              # Tier 4 — Phiền toái dài hơn, ngăn chat/voice 5p
        "description": "Timeout mục tiêu 5 phút (cấm chat/voice).",
        "db_key":      "timeout_5m",
        "category":    "blackmarket",
        "usable":      True,
    },
    26: {
        "id":          26,
        "name":        "Thẻ Miễn Nhiễm",
        "icon":        "🛡️",
        "price":       12000,              # Tier 4 — Phòng thủ cao cấp
        "description": "Tự động chặn 1 lần bị người khác dùng thẻ xấu lên mình.",
        "db_key":      "shield_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    27: {
        "id":          27,
        "name":        "Thẻ Đặc Xá",
        "icon":        "🕊️",
        "price":       15000,              # Tier 5 — Phá vỡ hình phạt tống giam của người khác
        "description": "Cứu người khác khỏi tù hoặc tự cứu mình.",
        "db_key":      "free_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    28: {
        "id":          28,
        "name":        "Thẻ Tống Giam",
        "icon":        "🚔",
        "price":       25000,              # Tier 5 — Mạnh nhất, cướp toàn bộ quyền hạn người khác
        "description": "Gửi 1 người vào chuồng chó (50 lần lau dọn).",
        "db_key":      "jail_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    29: {
        "id":          29,
        "name":        "Trát Hầu Tòa",
        "icon":        "📜",
        "price":       20000,              # Tier 5 — Gây hoảng loạn tâm lý tạm thời
        "description": "Gửi một Embed dọa ban vĩnh viễn cực kỳ nghiêm trọng rồi chốt là đùa.",
        "db_key":      "fake_ban_card",
        "category":    "blackmarket",
        "usable":      True,
    },
    
    # ──────────────────────────────────────────────────────────
    # ID 30–39 : NHẪN CƯỚI & TRANG SỨC (MARRIAGE)
    # ──────────────────────────────────────────────────────────
    31: {
        "id":          31,
        "name":        "Nhẫn Cỏ",
        "icon":        "🌿",
        "price":       1000,
        "description": "Biểu tượng tình yêu giản dị. (Không có buff). Dùng: y!marry @user 31",
        "db_key":      "ring_31",
        "category":    "ring",
        "usable":      False,
    },
    32: {
        "id":          32,
        "name":        "Nhẫn Bạc",
        "icon":        "💍",
        "price":       10000,
        "description": "Tăng 10% Điểm Thân Mật (DTM) khi tương tác. Mở khóa y!adopt.",
        "db_key":      "ring_32",
        "category":    "ring",
        "usable":      False,
    },
    33: {
        "id":          33,
        "name":        "Nhẫn Vàng",
        "icon":        "🌟",
        "price":       50000,
        "description": "Tăng 20% DTM. Giảm 10% Cooldown lệnh hành động.",
        "db_key":      "ring_33",
        "category":    "ring",
        "usable":      False,
    },
    34: {
        "id":          34,
        "name":        "Nhẫn Kim Cương",
        "icon":        "💎",
        "price":       200000,
        "description": "Tăng 50% DTM. Giảm 25% Cooldown. Nhân 1.5 phần thưởng khi y!work chung.",
        "db_key":      "ring_34",
        "category":    "ring",
        "usable":      False,
    },
}

# ============================================================
# LOOKUP HELPERS — Tiện ích tra cứu ngược
# ============================================================

def get_item_by_id(item_id: int) -> ItemEntry | None:
    """Tra cứu item theo ID số."""
    return ITEM_REGISTRY.get(item_id)

def get_item_by_db_key(db_key: str) -> ItemEntry | None:
    """Tra cứu item theo db_key (tên cột/key trong DB)."""
    for item in ITEM_REGISTRY.values():
        if item["db_key"] == db_key:
            return item
    return None

def get_items_by_category(category: str) -> list[ItemEntry]:
    """Lấy danh sách items theo category, sắp xếp theo ID."""
    return sorted(
        [item for item in ITEM_REGISTRY.values() if item["category"] == category],
        key=lambda x: x["id"],
    )

def get_buyable_items(category: str) -> list[ItemEntry]:
    """Lấy danh sách items CÓ THỂ MUA (price != None) theo category."""
    return [
        item for item in get_items_by_category(category)
        if item["price"] is not None
    ]
