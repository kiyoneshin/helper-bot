"""
event_help.py — Hệ Thống Trợ Giúp Sự Kiện 3 Tầng (y!ehelp)
============================================================
Kiến trúc:
  Tầng 1 - Home     : Danh sách danh mục (Dropdown → Tầng 2)
  Tầng 2 - Category : Danh sách lệnh trong danh mục (Dropdown → Tầng 3 | Button → Tầng 1)
  Tầng 3 - Detail   : Chi tiết lệnh (Button ◀ → Tầng 2 | Button 🏠 → Tầng 1)

Dữ liệu trung tâm: CMD_DATA + CATEGORY_DATA
"""

from __future__ import annotations

import discord
from discord.ext import commands
from typing import Optional

COLOR_THEME = 0xFFB6C1  # Angelic pink

# =============================================================================
# DỮ LIỆU TRUNG TÂM — Chỉ cần sửa ở đây khi thêm/xóa/cập nhật lệnh
# =============================================================================

CMD_DATA: dict[str, dict] = {
    # ── CASINO ────────────────────────────────────────────────────────────────
    "coinflip": {
        "name": "Coinflip",
        "emoji": "🪙",
        "short": "Tung đồng xu H/T. Thắng x1.9, đứng xu Jackpot x5.0.",
        "aliases": ["cf"],
        "cooldown": None,
        "usage": "y!cf <h/t> <tiền_cược | all>",
        "examples": ["y!cf h 50k", "y!cf t all"],
        "note": "Tỉ lệ: Thắng 44% / Thua 55% / Đứng xu 1%",
    },
    "cups": {
        "name": "Cups",
        "emoji": "🥤",
        "short": "Đoán ly có bảo vật trong 3 ly. Chọn đúng nhận x2.3.",
        "aliases": [],
        "cooldown": "30s timeout",
        "usage": "y!cups <tiền_cược | all>",
        "examples": ["y!cups 10k", "y!cups all"],
        "note": "Cần nhấn nút trong 30s, hết giờ sòng trả lại tiền.",
    },
    "dice": {
        "name": "Dice 7",
        "emoji": "🎲",
        "short": "Lắc xúc xắc 7 mặt. Mặt 4-6 thắng x1.25~x2.0. Mặt 7 nổ hũ x8.0 tiền cược.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!dice <tiền_cược | all>",
        "examples": ["y!dice 100k", "y!dice all"],
        "note": "Mặt 1-3 thua 25%~100%. Mặt 4-6 thắng x1.25~x2.0. Mặt 7 nổ hũ x8.0 tiền cược.",
    },
    "roulette": {
        "name": "Roulette",
        "emoji": "🔫",
        "short": "Cò quay tử thần. Sống sót lần 1-5 nhận x1.1→x5.0.",
        "aliases": ["shot"],
        "cooldown": None,
        "usage": "y!shot <tiền_cược | all>",
        "examples": ["y!shot 50k", "y!shot all"],
        "note": "Mỗi lần bóp cò tăng xác suất chết. Rút lui sớm để chốt lời an toàn.",
    },
    "adopt": {
        "name": "Nhận Nuôi Thú",
        "emoji": "🐾",
        "short": "Nhận nuôi thú cưng chung cho cặp đôi.",
        "aliases": [],
        "cooldown": 0,
        "usage": "y!adopt <loại_thú>",
        "examples": ["y!adopt dog", "y!adopt sói", "y!adopt thỏ"],
        "note": "Hai bạn cần tối thiểu 200 Điểm Thân Mật (DTM) để nhận nuôi. Có thể nuôi: dog, cat, fox, wolf, penguin, rabbit, bear, dragon.",
    },
    "namepet": {
        "name": "Đặt Tên Thú",
        "emoji": "🏷️",
        "short": "Đặt hoặc đổi tên riêng cho Thú cưng chung của hai bạn.",
        "aliases": [],
        "cooldown": 0,
        "usage": "y!namepet <tên_thú_cưng>",
        "examples": ["y!namepet Bông Tuyết", "y!namepet Bé Mực"],
        "note": "Hai bạn cần phải nhận nuôi thú cưng (y!adopt) trước khi đặt tên. Tối đa 30 ký tự.",
    },
    "crash": {
        "name": "Crash (Tàu Bay)",
        "emoji": "🚀",
        "short": "Tàu bay tăng hệ số x1.1→x99. Nhảy dù trước khi nổ để thắng.",
        "aliases": ["cr"],
        "cooldown": "Lobby 30s",
        "usage": "y!crash <tiền_cược>",
        "examples": ["y!crash 100k", "y!crash 1m"],
        "note": "Chớp đúng thời cơ rút lui để kiếm thêm tiền.",
    },
    "wheel": {
        "name": "Vòng Quay",
        "emoji": "🎡",
        "short": "Vòng quay 16 ô. Ô Tím x9.0, Xanh lá x1.8.",
        "aliases": [],
        "cooldown": None,
        "usage": "y!wheel <tiền_cược | all>",
        "examples": ["y!wheel 50k", "y!wheel all"],
        "note": "Thua ô Vàng tuy mất trắng tiền cược nhưng được tặng 1 vé xổ số!",
    },
    "slots": {
        "name": "Máy Xẻng (Slots)",
        "emoji": "🎰",
        "short": "Quay máy 5 cuộn. 5 biểu tượng giống nhau = Nổ hũ Jackpot.",
        "aliases": ["slot"],
        "cooldown": None,
        "usage": "y!slots <tiền_cược | all>",
        "examples": ["y!slots 100k", "y!slots all"],
        "note": "Nhiều cấp độ thắng tùy số biểu tượng trùng.",
    },
    "taixiu": {
        "name": "Tài Xỉu",
        "emoji": "🎲",
        "short": "Lắc 3 xúc xắc. Tài (11-17) / Xỉu (4-10). Thắng x1.95.",
        "aliases": ["tx"],
        "cooldown": None,
        "usage": "y!tx <tai/xiu> <tiền_cược | all>",
        "examples": ["y!tx tai 100k", "y!tx xiu all"],
        "note": "Bão (ra 3 con 1 hoặc 3 con 6): Mất sạch.",
    },
    "baucua": {
        "name": "Bầu Cua",
        "emoji": "🦀",
        "short": "Bàn Bầu Cua Tôm Cá chung. Sảnh cược tương tác.",
        "aliases": ["bc"],
        "cooldown": None,
        "usage": "y!bc",
        "examples": ["y!bc"],
        "note": "Gồm 6 con: Bầu, Cua, Tôm, Cá, Nai, Gà. Đặt cược bằng tin nhắn trong sảnh: `<tên_con> <số_tiền>`.",
    },
    "betvit": {
        "name": "Đua Vịt",
        "emoji": "🦆",
        "short": "Cược vào màu vịt. Vịt thắng, bạn thắng theo tỉ lệ pool.",
        "aliases": ["bv", "bevit"],
        "cooldown": None,
        "usage": "y!betvit <màu> <tiền>",
        "examples": ["y!betvit do 50k", "y!bv xanh 100k"],
        "note": "Màu: do, xanh, vang, hong, yon. Xem tỉ lệ: `y!xemvit`. Hủy cược: `y!huybet`.",
    },
    "xoso": {
        "name": "Xổ Số",
        "emoji": "🎟️",
        "short": "Vé số kiến thiết. Đổi đời sau một đêm.",
        "aliases": ["lottery", "xs"],
        "cooldown": None,
        "usage": "y!xoso [mua|ban] [số_lượng]",
        "examples": ["y!xoso", "y!xoso mua 5", "y!xoso ban 12"],
        "note": "Gõ y!xoso để xem thông tin. Kết quả xổ lúc cuối ngày.",
    },
    "multidice": {
        "name": "Multi Dice (PvP)",
        "emoji": "🎲",
        "short": "Xúc Xắc PvP nhiều người. Điểm cao nhất ăn cả nồi.",
        "aliases": ["md", "quanhung"],
        "cooldown": None,
        "usage": "y!md <tiền_cược> [@user1 @user2...]",
        "examples": ["y!md 100k @Bạn_A @Bạn_B"],
        "note": "Có thể mời tối đa nhiều người. Tự động chia thưởng khi kết thúc.",
    },
    # ── KINH TẾ ───────────────────────────────────────────────────────────────
    "daily": {
        "name": "Điểm Danh",
        "emoji": "🎁",
        "short": "Nhận thưởng 500 điểm mỗi ngày. Chuỗi càng dài, thưởng càng lớn.",
        "aliases": ["diemdanh"],
        "cooldown": "24h",
        "usage": "y!daily",
        "examples": ["y!daily"],
        "note": "Thưởng chuỗi (streak) cộng thêm tối đa 500 điểm/ngày.",
    },
    "weekly": {
        "name": "Lương Tuần",
        "emoji": "💎",
        "short": "Nhận lương 5,000 điểm mỗi tuần (7 ngày/lần).",
        "aliases": ["luongtuan"],
        "cooldown": "7 ngày",
        "usage": "y!weekly",
        "examples": ["y!weekly"],
        "note": None,
    },
    "point": {
        "name": "Xem Điểm",
        "emoji": "📊",
        "short": "Kiểm tra số dư điểm và thông tin sự kiện của bạn (hoặc người khác).",
        "aliases": ["bal", "vi"],
        "cooldown": None,
        "usage": "y!point [@user]",
        "examples": ["y!point", "y!point @BanBe"],
        "note": None,
    },
    "etop": {
        "name": "Bảng Xếp Hạng",
        "emoji": "🏆",
        "short": "Xem Top 10 người chơi có nhiều điểm tích lũy nhất server.",
        "aliases": ["evtop", "eventtop", "eventop"],
        "cooldown": None,
        "usage": "y!etop",
        "examples": ["y!etop"],
        "note": None,
    },
    "milestone": {
        "name": "Cột Mốc",
        "emoji": "🎯",
        "short": "Xem các cột mốc phần thưởng và tiến độ đạt mốc hiện tại.",
        "aliases": ["qua", "reward"],
        "cooldown": None,
        "usage": "y!milestone",
        "examples": ["y!milestone"],
        "note": "Đạt mốc rồi dùng `y!claim` hoặc `y!nhanqua` để nhận thưởng.",
    },
    "shop": {
        "name": "Cửa Hàng",
        "emoji": "🛒",
        "short": "Xem các vật phẩm có thể mua bằng điểm sự kiện.",
        "aliases": ["cuahang", "store"],
        "cooldown": None,
        "usage": "y!shop",
        "examples": ["y!shop"],
        "note": "Mua vật phẩm bằng lệnh `y!buy <ID> [số_lượng]`.",
    },
    "black_market": {
        "name": "Chợ Đen",
        "emoji": "🖤",
        "short": "Shop bí ẩn thay đổi hàng ngày. Hàng độc, hiếm và... bất thường.",
        "aliases": ["chodem", "blackmarket", "bm"],
        "cooldown": None,
        "usage": "y!choden",
        "examples": ["y!choden"],
        "note": "Hàng reset mỗi 00:00 UTC+7. Số lượng kho có hạn, ai nhanh thì được.",
    },
    "vayno": {
        "name": "Vay Nợ",
        "emoji": "🏦",
        "short": "Vay tiền từ ngân hàng dựa trên 50% điểm tích lũy của bạn.",
        "aliases": ["vay", "loan"],
        "cooldown": None,
        "usage": "y!vayno <số_tiền>",
        "examples": ["y!vayno 100k"],
        "note": "Lãi suất 1%/ngày. Trả nợ bằng `y!trano`. Vỡ nợ sẽ bị khóa tài khoản!",
    },
    # ── KHU SINH THÁI ─────────────────────────────────────────────────────────
    "farm": {
        "name": "Nông Trại",
        "emoji": "🌻",
        "short": "Mở giao diện Nông Trại. Trồng, chăm sóc và thu hoạch mùa vụ.",
        "aliases": ["nongtrai"],
        "cooldown": None,
        "usage": "y!farm",
        "examples": ["y!farm"],
        "note": "Mua hạt giống bằng `y!shop`. Upgrade ô đất: `y!upgrade`.",
    },
    "mine": {
        "name": "Đào Mỏ",
        "emoji": "⛏️",
        "short": "Tiến vào hang động đào quặng. Càng vào sâu càng nhiều quặng quý.",
        "aliases": ["dao", "khoamo", "mining"],
        "cooldown": None,
        "usage": "y!mine",
        "examples": ["y!mine"],
        "note": "Tốn 4 Thể Lực mỗi lần đào. Bán quặng bằng `y!inv ban`.",
    },
    "fish": {
        "name": "Câu Cá",
        "emoji": "🎣",
        "short": "Thả cần đợi cá cắn. Cá hiếm bán được nhiều điểm hơn.",
        "aliases": ["cauca", "fishing", "caca"],
        "cooldown": None,
        "usage": "y!fish",
        "examples": ["y!fish"],
        "note": "Tốn 3 Thể Lực mỗi lần câu. Nâng cấp cần câu để tăng tỉ lệ cá hiếm.",
    },
    "inventory": {
        "name": "Kho Đồ",
        "emoji": "🎒",
        "short": "Xem vật phẩm trong kho, bán nông sản/quặng/cá lấy điểm.",
        "aliases": ["inv", "bag", "tuido", "khodo"],
        "cooldown": None,
        "usage": "y!inv",
        "examples": ["y!inv"],
        "note": "",
    },
    # ── HỆ THỐNG TÌNH YÊU ──────────────────────────────────────────────────────
    "marry": {
        "name": "Kết Hôn",
        "emoji": "💍",
        "short": "Cầu hôn một người để chính thức thành vợ chồng.",
        "aliases": ["kethon"],
        "cooldown": None,
        "usage": "y!marry [@user] [ring_id]",
        "examples": ["y!marry @BanGai 31", "y!kethon @Crush 32"],
        "note": "Nhẫn ID 31-34 mua trong y!shop.",
    },
    "divorce": {
        "name": "Ly Hôn",
        "emoji": "💔",
        "short": "Đơn phương ly hôn người hiện tại.",
        "aliases": ["lydi", "lyhon"],
        "cooldown": None,
        "usage": "y!divorce",
        "examples": ["y!divorce", "y!lydi"],
        "note": "Hành động này sẽ xóa toàn bộ điểm thân mật và thú cưng chung.",
    },
    "promise": {
        "name": "Lời Thề",
        "emoji": "💌",
        "short": "Khắc ghi lời thề non hẹn biển lên Profile Tình Yêu.",
        "aliases": ["hua"],
        "cooldown": None,
        "usage": "y!promise <lời_hứa>",
        "examples": ["y!promise Anh hứa sẽ yêu em mãi mãi"],
        "note": "Bất cứ lúc nào cũng có thể đổi lại lời hứa.",
    },
    "gift": {
        "name": "Tặng Quà",
        "emoji": "🎁",
        "short": "Tặng quà mua từ Cửa Hàng (Quà Tặng) cho vợ/chồng. Tăng DTM.",
        "aliases": ["tangqua"],
        "cooldown": 0,
        "usage": "y!gift <@user> <id_quà>",
        "examples": ["y!gift @nguoiyeu 41", "y!gift 123456789 42"],
        "note": "Quà tặng phải mua trong Cửa Hàng (y!shop mục Quà Tặng) trước khi dùng lệnh này. Mỗi món quà có lượng DTM tăng thêm riêng.",
    },
    "upgradering": {
        "name": "Nâng Cấp Nhẫn",
        "emoji": "✨",
        "short": "Đổi sang Nhẫn cấp cao hơn để nhận thêm buff DTM và giảm Cooldown.",
        "aliases": ["nangcapnhan"],
        "cooldown": None,
        "usage": "y!upgradering <ring_id>",
        "examples": ["y!upgradering 33"],
        "note": "Bạn cần mua sẵn nhẫn mới trong túi đồ (y!inv) trước.",
    },
    "setimage": {
        "name": "Cài Ảnh",
        "emoji": "🖼️",
        "short": "Cài ảnh kỷ niệm hiển thị dưới Profile Tình Yêu.",
        "aliases": ["setanh"],
        "cooldown": None,
        "usage": "y!setimage <link_ảnh>",
        "examples": ["y!setimage https://example.com/image.png"],
        "note": "Link ảnh phải kết thúc bằng .png, .jpg hoặc .gif",
    },
    "coupletask": {
        "name": "Nhiệm Vụ Đôi",
        "emoji": "📋",
        "short": "Nhận 1 nhiệm vụ ngẫu nhiên chung cho cả 2 người. Hoàn thành để lấy +100 DTM.",
        "aliases": [],
        "cooldown": "1 lần/ngày",
        "usage": "y!coupletask",
        "examples": ["y!coupletask"],
        "note": "Ngày mới (sau 0h) sẽ nhận được task mới.",
    },
    "actions": {
        "name": "Hành Động Cặp Đôi",
        "emoji": "💞",
        "short": "Các lệnh tương tác đặc biệt dành cho vợ/chồng.",
        "aliases": ["om", "hon", "tat", "can", "seg", "..."],
        "cooldown": 0,
        "usage": "y!<hành_động> <@user>",
        "examples": ["y!hug @VoYeu", "y!kiss @ChongYeu"],
        "note": "Bao gồm các lệnh sau (có thể dùng tên tiếng Anh hoặc alias tiếng Việt):\\n"
                "- 🤜 **Bạo lực:** `y!slap` (tat), `y!punch` (dam), `y!bite` (can), `y!tickle` (choclet)\\n"
                "- 💖 **Nhẹ nhàng:** `y!poke` (choc), `y!pat` (xoadau), `y!saylove` (noiyeu, iuem, iuanh)\\n"
                "- 🤗 **Ôm ấp:** `y!hug` (om), `y!cuddle` (auyem), `y!snuggle` (nung, nũng)\\n"
                "- 💋 **Thân mật:** `y!kiss` (hon, hun), `y!lick` (liem), `y!nom` (mam), `y!fuck` (seg)\\n"
                "*(Lưu ý: Thời gian hồi chiêu và lượng DTM nhận được tùy thuộc vào độ 'thân mật' của hành động và cấp bậc Nhẫn cưới của bạn)*",
    },
    "trano": {
        "name": "Trả Nợ",
        "emoji": "💵",
        "short": "Trả nợ cho ngân hàng để tránh bị khóa tài khoản.",
        "aliases": ["tra", "payloan"],
        "cooldown": None,
        "usage": "y!trano <số_tiền | all>",
        "examples": ["y!trano 50k", "y!trano all"],
        "note": "Bạn cần trả cả gốc lẫn lãi.",
    },
    "ebuy": {
        "name": "Mua Chợ Đen",
        "emoji": "🛍️",
        "short": "Mua vật phẩm trực tiếp từ Chợ Đen.",
        "aliases": ["muadem", "bmbuy"],
        "cooldown": None,
        "usage": "y!ebuy <id_vật_phẩm> [số_lượng]",
        "examples": ["y!ebuy 1", "y!ebuy 2 5"],
        "note": "Số lượng kho có hạn, hãy nhanh tay!",
    },
    "recipe": {
        "name": "Công Thức",
        "emoji": "📜",
        "short": "Xem các công thức chế tạo (Crafting).",
        "aliases": ["recipes", "crafting"],
        "cooldown": None,
        "usage": "y!recipe",
        "examples": ["y!recipe"],
        "note": "Thu thập nguyên liệu từ Nông Trại/Đào Mỏ để chế tạo.",
    },
    "task": {
        "name": "Nhiệm Vụ Hàng Ngày",
        "emoji": "📋",
        "short": "Hoàn thành các nhiệm vụ nhỏ mỗi ngày để lấy phần thưởng.",
        "aliases": ["tasks", "nhiemvu"],
        "cooldown": None,
        "usage": "y!task",
        "examples": ["y!task"],
        "note": "Nhiệm vụ reset vào lúc 0:00 mỗi ngày.",
    },
    "quest": {
        "name": "Nhiệm Vụ Tân Thủ",
        "emoji": "🎯",
        "short": "Xem và nhận thưởng từ chuỗi nhiệm vụ tân thủ.",
        "aliases": ["quests"],
        "cooldown": None,
        "usage": "y!quest",
        "examples": ["y!quest"],
        "note": "Nhiệm vụ tân thủ chỉ làm 1 lần duy nhất.",
    },
    "work": {
        "name": "Làm Việc",
        "emoji": "💼",
        "short": "Gõ phím đi làm nhận lương. Có tỉ lệ gặp boss/trúng mánh.",
        "aliases": ["w"],
        "cooldown": "5p",
        "usage": "y!work",
        "examples": ["y!work", "y!w"],
        "note": "Đôi khi sẽ bị sếp la nếu làm việc không chăm chỉ.",
    },
    "upgrade": {
        "name": "Nâng Cấp Nông Trại",
        "emoji": "⬆️",
        "short": "Nâng cấp ô đất hoặc cần câu bằng nguyên liệu.",
        "aliases": ["nangcap", "morong"],
        "cooldown": None,
        "usage": "y!upgrade",
        "examples": ["y!upgrade"],
        "note": "Cần nguyên liệu để mở khóa tính năng cao cấp.",
    },
    "machine": {
        "name": "Chế Biến",
        "emoji": "⚙️",
        "short": "Mở giao diện Máy Chế Biến để làm ra vật phẩm cấp cao.",
        "aliases": ["chebien", "maymoc"],
        "cooldown": None,
        "usage": "y!machine",
        "examples": ["y!machine"],
        "note": "Tăng giá trị nông sản/quặng khi bán.",
    },
    "chop": {
        "name": "Chặt Cây",
        "emoji": "🪓",
        "short": "Tiến vào rừng sâu chặt gỗ. Có rủi ro bị sói cắn.",
        "aliases": ["chatcay", "woodcut"],
        "cooldown": None,
        "usage": "y!chop",
        "examples": ["y!chop"],
        "note": "Tốn 3 Thể Lực mỗi lần chặt.",
    },

}

CATEGORY_DATA: dict[str, dict] = {
    "Casino & Giải Trí": {
        "emoji": "🎰",
        "desc": "Các minigame cờ bạc và thử vận may.",
        "commands": ["coinflip", "cups", "dice", "roulette", "crash", "wheel", "slots", "taixiu", "baucua", "betvit", "xoso", "multidice"],
        "cogs": ["BasicGames", "CrashGame", "DuckRace", "Lottery", "MultiDice", "VietnamGames", "WheelSlots"],
    },
    "Kinh Tế & Cửa Hàng": {
        "emoji": "🛒",
        "desc": "Quản lý điểm, cửa hàng, cột mốc và ngân hàng.",
        "commands": ["daily", "weekly", "point", "etop", "milestone", "shop", "black_market", "ebuy", "vayno", "trano"],
        "cogs": ["EventShopCog", "Rewards", "MilestoneCog", "BlackMarketCog", "BankingCog"],
    },
    "Nhiệm Vụ & Công Việc": {
        "emoji": "📋",
        "desc": "Hệ thống nhiệm vụ, công việc để cày cuốc.",
        "commands": ["task", "quest", "work"],
        "cogs": ["TasksCog", "WorkCog"],
    },
    "Khu Sinh Thái": {
        "emoji": "🏕️",
        "desc": "Trồng trọt, đào mỏ, câu cá, chặt cây, chế tạo và quản lý kho đồ.",
        "commands": ["farm", "upgrade", "machine", "mine", "fish", "chop", "recipe", "inventory"],
        "cogs": ["IdleFarmCog", "Mining", "Fishing", "Woodcutting", "Recipes"],
    },
    "Hệ Thống Tình Yêu": {
        "emoji": "💖",
        "desc": "Kết hôn, cày điểm thân mật và tương tác cùng người thương.",
        "commands": ["marry", "divorce", "coupletask", "gift", "promise", "setimage", "adopt", "namepet", "upgradering", "actions"],
        "cogs": ["MarriageCog"],
    },
}

# =============================================================================
# BUILDERS — Hàm thuần túy xây dựng Embed (không có side effect)
# =============================================================================

def build_home_embed(bot: commands.Bot, author: discord.Member | discord.User) -> discord.Embed:
    embed = discord.Embed(
        title=f"🌸 Cẩm Nang Sự Kiện — {author.display_name} ໒꒱",
        description=(
            "Chào mừng bạn đến với hệ thống sự kiện Angelic!\n\n"
            "Tham gia Casino để thử vận may, Khu Sinh Thái để cày an toàn, "
            "hoặc mua sắm tại Cửa Hàng để đổi phần quà.\n\n"
            "**📋 Chọn danh mục bên dưới để xem chi tiết:**"
        ),
        color=COLOR_THEME,
    )

    total_cmds = 0
    for cat_name, cat_info in CATEGORY_DATA.items():
        count = len(cat_info["commands"])
        total_cmds += count
        embed.add_field(
            name=f"{cat_info['emoji']} {cat_name}",
            value=f"{cat_info['desc']}\n*({count} lệnh)*",
            inline=False,
        )

    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Tổng {total_cmds} lệnh sự kiện  •  Chọn danh mục từ menu bên dưới")
    return embed


def build_category_embed(cat_name: str) -> discord.Embed:
    cat = CATEGORY_DATA.get(cat_name)
    if not cat:
        return discord.Embed(title="❌ Không tìm thấy danh mục", color=discord.Color.red())

    embed = discord.Embed(
        title=f"{cat['emoji']} {cat_name}",
        description=f"{cat['desc']}\n\n**Chọn lệnh từ menu bên dưới để xem chi tiết:**",
        color=COLOR_THEME,
    )
    for key in cat["commands"]:
        cmd = CMD_DATA.get(key)
        if cmd:
            aliases = f" · `{'`, `'.join(f'y!{a}' for a in cmd['aliases'])}`" if cmd["aliases"] else ""
            embed.add_field(
                name=f"{cmd['emoji']} `y!{key}`{aliases}",
                value=cmd["short"],
                inline=False,
            )
    embed.set_footer(text="Nhấn ◀ Quay Lại để về trang chủ")
    return embed


def build_detail_embed(cmd_key: str) -> discord.Embed:
    cmd = CMD_DATA.get(cmd_key)
    if not cmd:
        return discord.Embed(title="❌ Không tìm thấy lệnh", color=discord.Color.red())

    embed = discord.Embed(
        title=f"{cmd['emoji']} {cmd['name']}",
        description=cmd["short"],
        color=COLOR_THEME,
    )

    if cmd.get("aliases"):
        embed.add_field(
            name="📛 Lệnh rút gọn",
            value=" · ".join(f"`y!{a}`" for a in cmd["aliases"]),
            inline=True,
        )
    if cmd.get("cooldown"):
        embed.add_field(name="⏱️ Cooldown", value=cmd["cooldown"], inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="📝 Cú pháp", value=f"`{cmd['usage']}`", inline=False)

    if cmd.get("examples"):
        embed.add_field(
            name="💡 Ví dụ",
            value="\n".join(f"`{e}`" for e in cmd["examples"]),
            inline=False,
        )
    if cmd.get("note"):
        embed.add_field(name="ℹ️ Ghi chú", value=cmd["note"], inline=False)

    embed.set_footer(text="Nhấn ◀ Quay Lại để về danh sách lệnh")
    return embed


# =============================================================================
# VIEWS — 3 Tầng UI tương tác
# =============================================================================

class HomeView(discord.ui.View):
    """Tầng 1: Trang chủ với Dropdown chọn danh mục."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.message: Optional[discord.Message] = None
        self.add_item(_CategorySelect(bot, author))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _CategorySelect(discord.ui.Select):
    """Dropdown chọn danh mục trong tầng 1."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User):
        self.bot = bot
        self.author = author
        options = [
            discord.SelectOption(
                label=cat_name,
                value=cat_name,
                emoji=cat_info["emoji"],
                description=cat_info["desc"][:50],
            )
            for cat_name, cat_info in CATEGORY_DATA.items()
        ]
        super().__init__(placeholder="🔍 Chọn danh mục lệnh...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        cat_name = self.values[0]
        embed = build_category_embed(cat_name)
        view = CategoryView(self.bot, self.author, cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class CategoryView(discord.ui.View):
    """Tầng 2: Danh sách lệnh trong danh mục."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.cat_name = cat_name
        self.message: Optional[discord.Message] = None

        self.add_item(_CommandSelect(bot, author, cat_name))
        self.add_item(_HomeButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _CommandSelect(discord.ui.Select):
    """Dropdown chọn lệnh cụ thể trong tầng 2."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        self.bot = bot
        self.author = author
        self.cat_name = cat_name

        cat = CATEGORY_DATA.get(cat_name, {})
        options = []
        for key in cat.get("commands", []):
            cmd = CMD_DATA.get(key)
            if cmd:
                label = f"{cmd['emoji']} {cmd['name']}"
                options.append(discord.SelectOption(
                    label=label[:25],
                    value=key,
                    description=cmd["short"][:50],
                ))

        super().__init__(
            placeholder="📖 Chọn lệnh để xem chi tiết...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cmd_key = self.values[0]
        embed = build_detail_embed(cmd_key)
        view = DetailView(self.bot, self.author, self.cat_name)
        view.message = self.view.message  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)


class _HomeButton(discord.ui.Button):
    """Nút quay về trang chủ."""

    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: CategoryView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class DetailView(discord.ui.View):
    """Tầng 3: Chi tiết lệnh."""

    def __init__(self, bot: commands.Bot, author: discord.Member | discord.User, cat_name: str):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.author = author
        self.cat_name = cat_name
        self.message: Optional[discord.Message] = None

        self.add_item(_BackButton())
        self.add_item(_HomeButton2())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải cẩm nang của bạn!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _BackButton(discord.ui.Button):
    """Nút quay lại danh mục."""

    def __init__(self):
        super().__init__(label="◀ Quay Lại", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_category_embed(view.cat_name)
        new_view = CategoryView(view.bot, view.author, view.cat_name)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class _HomeButton2(discord.ui.Button):
    """Nút về trang chủ từ tầng 3."""

    def __init__(self):
        super().__init__(label="🏠 Trang Chủ", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DetailView = self.view  # type: ignore
        embed = build_home_embed(view.bot, view.author)
        new_view = HomeView(view.bot, view.author)
        new_view.message = view.message
        await interaction.response.edit_message(embed=embed, view=new_view)


# =============================================================================
# COG — Lệnh y!ehelp
# =============================================================================

class EventHelpCog(commands.Cog):
    """🌸 Cẩm nang hướng dẫn sự kiện với UI 3 tầng."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ehelp",
        description="Xem danh sách toàn bộ các lệnh sự kiện (UI 3 tầng).",
    )
    async def ehelp_cmd(self, ctx: commands.Context):
        """🌸 Cẩm nang sự kiện với UI tương tác 3 tầng."""
        embed = build_home_embed(self.bot, ctx.author)
        view = HomeView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHelpCog(bot))
