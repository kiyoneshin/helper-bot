"""
machine_config.py — Cấu hình hệ thống Máy Chế Biến (Artisan Processing)
=========================================================================
Phỏng theo Stardew Valley: Keg, Preserves Jar, Furnace.
Mỗi recipe tốn thời gian thực để hoàn thành.
"""
from typing import TypedDict, Dict, List

# ---------------------------------------------------------------------------
# KIỂU DỮ LIỆU
# ---------------------------------------------------------------------------

class RecipeConfig(TypedDict):
    name: str
    icon: str
    ingredients: Dict[str, int]   # {item_id: quantity}
    output_id: str
    output_qty: int
    duration_seconds: int
    sell_price: int
    description: str

class MachineConfig(TypedDict):
    id: int
    name: str
    icon: str
    description: str
    db_key: str
    recipes: List[str]           # danh sách recipe_id
    ingredients: Dict[str, int]  # nguyên liệu để chế tạo ra máy

# ---------------------------------------------------------------------------
# SẢN PHẨM THỦ CÔNG (ARTISAN GOODS)
# ---------------------------------------------------------------------------

ARTISAN_GOODS: Dict[str, dict] = {
    # Từ Keg
    "beer":         {"name": "Bia",           "icon": "<:machine_00_beer:1535647162590040164>", "price": 450,   "category": "artisan"},
    "wine_strawb":  {"name": "Rượu Dâu",      "icon": "<:machine_01_wine:1535647164514963487>", "price": 7000,  "category": "artisan"},
    "spirit_star":  {"name": "Linh Tửu",      "icon": "<:machine_02_spririt_star:1535647166297546823>", "price": 50000, "category": "artisan"},
    # Từ Preserves Jar
    "tomato_jam":   {"name": "Mứt Cà Chua",   "icon": "<:machine_03_tomato_jam:1535647168252088390>", "price": 2250,  "category": "artisan"},
    "pumpkin_jam":  {"name": "Mứt Bí Ngô",    "icon": "<:machine_04_pumpkin_juice:1535647170328535081>", "price": 8750,  "category": "artisan"},
    # Từ Furnace
    "copper_bar":   {"name": "Phôi Đồng",     "icon": "<:machine_05_bronze_bar:1535647172840919143>", "price": 2500,  "category": "artisan"},
    "iron_bar":     {"name": "Phôi Sắt",      "icon": "<:machine_06_iron_bar:1535647174925352980>", "price": 7500,  "category": "artisan"},
    "gold_bar":     {"name": "Phôi Vàng",     "icon": "<:machine_07_gold_bar:1535647177186086984>", "price": 25000, "category": "artisan"},
}

# ---------------------------------------------------------------------------
# RECIPES
# ---------------------------------------------------------------------------

RECIPES: Dict[str, RecipeConfig] = {
    # --- KEG ---
    "keg_beer": {
        "name": "Ủ Bia",
        "icon": "<:machine_00_beer:1535647162590040164>",
        "ingredients": {"wheat_normal": 5},
        "output_id": "beer",
        "output_qty": 1,
        "duration_seconds": 1 * 60 * 60,   # 1h
        "sell_price": 450,
        "description": "Lúa Mì x5 → Bia x1 (1 tiếng)",
    },
    "keg_wine_strawb": {
        "name": "Ủ Rượu Dâu",
        "icon": "<:machine_01_wine:1535647164514963487>",
        "ingredients": {"strawberry_normal": 3},
        "output_id": "wine_strawb",
        "output_qty": 1,
        "duration_seconds": 3 * 60 * 60,   # 3h — Stardew: 7 ngày * 1/x
        "sell_price": 7000,
        "description": "Dâu Tây x3 → Rượu Dâu x1 (3 tiếng)",
    },
    "keg_spirit_star": {
        "name": "Ủ Linh Tửu",
        "icon": "<:machine_02_spririt_star:1535647166297546823>",
        "ingredients": {"star_iridium": 1},
        "output_id": "spirit_star",
        "output_qty": 1,
        "duration_seconds": 12 * 60 * 60,  # 12h
        "sell_price": 50000,
        "description": "Ngôi Sao x1 → Linh Tửu x1 (12 tiếng)",
    },

    # --- PRESERVES JAR ---
    "jar_tomato_jam": {
        "name": "Làm Mứt Cà Chua",
        "icon": "<:machine_03_tomato_jam:1535647168252088390>",
        "ingredients": {"tomato_normal": 4},
        "output_id": "tomato_jam",
        "output_qty": 1,
        "duration_seconds": 2 * 60 * 60,   # 2h
        "sell_price": 2250,
        "description": "Cà Chua x4 → Mứt Cà Chua x1 (2 tiếng)",
    },
    "jar_pumpkin_jam": {
        "name": "Làm Mứt Bí Ngô",
        "icon": "<:machine_04_pumpkin_juice:1535647170328535081>",
        "ingredients": {"pumpkin_normal": 3},
        "output_id": "pumpkin_jam",
        "output_qty": 1,
        "duration_seconds": 4 * 60 * 60,   # 4h
        "sell_price": 8750,
        "description": "Bí Ngô x3 → Mứt Bí Ngô x1 (4 tiếng)",
    },

    # --- FURNACE ---
    "furnace_copper": {
        "name": "Đúc Phôi Đồng",
        "icon": "<:machine_05_bronze_bar:1535647172840919143>",
        "ingredients": {"copper_ore": 5, "coal": 2},
        "output_id": "copper_bar",
        "output_qty": 1,
        "duration_seconds": 30 * 60,        # 30 phút
        "sell_price": 2500,
        "description": "Quặng Đồng x5 + Than x2 → Phôi Đồng x1 (30 phút)",
    },
    "furnace_iron": {
        "name": "Đúc Phôi Sắt",
        "icon": "<:machine_06_iron_bar:1535647174925352980>",
        "ingredients": {"iron_ore": 5, "coal": 4},
        "output_id": "iron_bar",
        "output_qty": 1,
        "duration_seconds": 1 * 60 * 60,    # 1h
        "sell_price": 7500,
        "description": "Quặng Sắt x5 + Than x4 → Phôi Sắt x1 (1 tiếng)",
    },
    "furnace_gold": {
        "name": "Đúc Phôi Vàng",
        "icon": "<:machine_07_gold_bar:1535647177186086984>",
        "ingredients": {"gold_ore": 5, "coal": 6},
        "output_id": "gold_bar",
        "output_qty": 1,
        "duration_seconds": 2 * 60 * 60,    # 2h
        "sell_price": 25000,
        "description": "Quặng Vàng x5 + Than x6 → Phôi Vàng x1 (2 tiếng)",
    },
}

# ---------------------------------------------------------------------------
# MACHINES
# ---------------------------------------------------------------------------

MACHINES: Dict[str, MachineConfig] = {
    "keg": {
        "id": 101,
        "name": "Thùng Ủ Rượu",
        "icon": "<:machine_08_keg:1535657702020354098>",
        "description": "Biến nông sản thành đồ uống giá trị cao.",
        "db_key": "keg",
        "recipes": ["keg_beer", "keg_wine_strawb", "keg_spirit_star"],
        "ingredients": {"wood_normal": 30, "copper_bar": 1, "iron_bar": 1}
    },
    "jar": {
        "id": 102,
        "name": "Máy Làm Mứt",
        "icon": "<:machine_09_jar:1535657704021037156>",
        "description": "Chế biến rau củ thành mứt thơm ngon.",
        "db_key": "jar",
        "recipes": ["jar_tomato_jam", "jar_pumpkin_jam"],
        "ingredients": {"wood_normal": 30, "stone": 20, "coal": 2}
    },
    "furnace": {
        "id": 103,
        "name": "Lò Rèn",
        "icon": "<:machine_10_furnace:1535657705958674452>",
        "description": "Luyện quặng thành phôi kim loại cứng.",
        "db_key": "furnace",
        "recipes": ["furnace_copper", "furnace_iron", "furnace_gold"],
        "ingredients": {"stone": 20, "copper_ore": 5}
    },
}

MACHINE_BY_ID: Dict[int, str] = {
    machine["id"]: key for key, machine in MACHINES.items()
}
