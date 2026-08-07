"""
event_help.py — Hệ Thống Trợ Giúp Sự Kiện 3 Tầng (kehelp)
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
    "inv": {
        "name": "Kho Đồ",
        "emoji": "🎒",
        "short": "Xem túi đồ của bạn.",
        "aliases": ["bag", "tuido", "khodo", "inventory"],
        "cooldown": None,
        "usage": "{prefix}inv",
        "examples": ["{prefix}inv"],
        "note": None,
    },
    "use": {
        "name": "Sử Dụng Vật Phẩm",
        "emoji": "🎁",
        "short": "Sử dụng một vật phẩm trong túi đồ.",
        "aliases": ["dung", "xai"],
        "cooldown": None,
        "usage": "{prefix}use <id_vật_phẩm> [@mục_tiêu]",
        "examples": ["{prefix}use 12", "{prefix}use 41 @user"],
        "note": "Bạn cần biết ID của vật phẩm (xem trong {prefix}inv).",
    },
    "shop": {
        "name": "Cửa Hàng",
        "emoji": "🛒",
        "short": "Xem danh sách vật phẩm trong cửa hàng.",
        "aliases": ["cuahang", "store"],
        "cooldown": None,
        "usage": "{prefix}shop",
        "examples": ["{prefix}shop"],
        "note": None,
    },
    "buy": {
        "name": "Mua Hàng",
        "emoji": "🛍️",
        "short": "Mua vật phẩm từ cửa hàng.",
        "aliases": ["mua"],
        "cooldown": None,
        "usage": "{prefix}buy <id_vật_phẩm> [số_lượng]",
        "examples": ["{prefix}buy 1", "{prefix}buy 2 10"],
        "note": "Bạn cần biết ID của vật phẩm (xem trong {prefix}shop).",
    },
    # ── CASINO ────────────────────────────────────────────────────────────────
    "coinflip": {
        "name": "Coinflip",
        "emoji": "🪙",
        "short": "Tung đồng xu H/T. Thắng x1.9, đứng xu Jackpot x5.0.",
        "aliases": ["cf"],
        "cooldown": None,
        "usage": "{prefix}cf <h/t> <tiền_cược | all>",
        "examples": ["{prefix}cf h 50k", "{prefix}cf t all"],
        "note": "Tỉ lệ: Thắng 44% / Thua 55% / Đứng xu 1%",
    },
    "cups": {
        "name": "Cups",
        "emoji": "🥤",
        "short": "Đoán ly có bảo vật trong 3 ly. Chọn đúng nhận x2.3.",
        "aliases": [],
        "cooldown": "30s timeout",
        "usage": "{prefix}cups <tiền_cược | all>",
        "examples": ["{prefix}cups 10k", "{prefix}cups all"],
        "note": "Cần nhấn nút trong 30s, hết giờ sòng trả lại tiền.",
    },
    "dice": {
        "name": "Dice 7",
        "emoji": "🎲",
        "short": "Lắc xúc xắc 7 mặt. Mặt 4-6 thắng x1.25~x2.0. Mặt 7 nổ hũ x8.0 tiền cược.",
        "aliases": [],
        "cooldown": None,
        "usage": "{prefix}dice <tiền_cược | all>",
        "examples": ["{prefix}dice 100k", "{prefix}dice all"],
        "note": "Mặt 1-3 thua 25%~100%. Mặt 4-6 thắng x1.25~x2.0. Mặt 7 nổ hũ x8.0 tiền cược.",
    },
    "roulette": {
        "name": "Roulette",
        "emoji": "🔫",
        "short": "Cò quay tử thần. Sống sót lần 1-5 nhận x1.1→x5.0.",
        "aliases": ["shot"],
        "cooldown": None,
        "usage": "{prefix}shot <tiền_cược | all>",
        "examples": ["{prefix}shot 50k", "{prefix}shot all"],
        "note": "Mỗi lần bóp cò tăng xác suất chết. Rút lui sớm để chốt lời an toàn.",
    },
    "adopt": {
        "name": "Nhận Nuôi",
        "emoji": "🐾",
        "short": "Nhận nuôi thú cưng để tăng hiệu ứng tương tác.",
        "aliases": [],
        "cooldown": 0,
        "usage": "{prefix}adopt <tên_thú_cưng>",
        "examples": ["{prefix}adopt dog", "{prefix}adopt cat"],
        "note": "Yêu cầu 200 DTM để nhận nuôi. Nếu đã có thú cưng, bạn có thể nhận bé mới nhưng EXP thú cưng sẽ quay về 0.",
    },
    "namepet": {
        "name": "Đặt Tên Thú",
        "emoji": "🏷️",
        "short": "Đặt hoặc đổi tên riêng cho Thú cưng chung của hai bạn.",
        "aliases": [],
        "cooldown": 0,
        "usage": "{prefix}namepet <tên_thú_cưng>",
        "examples": ["{prefix}namepet Bông Tuyết", "{prefix}namepet Bé Mực"],
        "note": "Hai bạn cần phải nhận nuôi thú cưng ({prefix}adopt) trước khi đặt tên. Tối đa 30 ký tự.",
    },
    "pet": {
        "name": "Hồ Sơ Thú Cưng",
        "emoji": "🐶",
        "short": "Xem thông tin chi tiết thú cưng, cấp độ và buff kỹ năng đặc thù.",
        "aliases": ["thucung"],
        "cooldown": 0,
        "usage": "{prefix}pet",
        "examples": ["{prefix}pet"],
        "note": "Mỗi loại thú cưng có kỹ năng ĐỘC QUYỀN khác nhau. Nhận EXP thú cưng bằng cách đi làm ({prefix}work), làm nhiệm vụ ({prefix}task) hoặc dùng lệnh hành động.",
    },
    "crash": {
        "name": "Crash (Tàu Bay)",
        "emoji": "🚀",
        "short": "Tàu bay tăng hệ số x1.1→x99. Nhảy dù trước khi nổ để thắng.",
        "aliases": ["cr"],
        "cooldown": "Lobby 30s",
        "usage": "{prefix}crash",
        "examples": ["{prefix}crash", "{prefix}cr"],
        "note": "Gõ lệnh để mở sòng, sau đó nhấn nút Đặt Cược để chơi.",
    },
    "wheel": {
        "name": "Vòng Quay",
        "emoji": "🎡",
        "short": "Vòng quay 16 ô. Ô Tím x9.0, Xanh lá x1.8.",
        "aliases": [],
        "cooldown": None,
        "usage": "{prefix}wheel <tiền_cược | all>",
        "examples": ["{prefix}wheel 50k", "{prefix}wheel all"],
        "note": "Thua ô Vàng tuy mất trắng tiền cược nhưng được tặng 1 vé xổ số!",
    },
    "slots": {
        "name": "Máy Xẻng (Slots)",
        "emoji": "🎰",
        "short": "Quay máy 5 cuộn. 5 biểu tượng giống nhau = Nổ hũ Jackpot.",
        "aliases": ["slot"],
        "cooldown": None,
        "usage": "{prefix}slots <tiền_cược | all>",
        "examples": ["{prefix}slots 100k", "{prefix}slots all"],
        "note": "Nhiều cấp độ thắng tùy số biểu tượng trùng.",
    },
    "taixiu": {
        "name": "Tài Xỉu",
        "emoji": "🎲",
        "short": "Lắc 3 xúc xắc. Tài (11-17) / Xỉu (4-10). Thắng x1.95.",
        "aliases": ["tx"],
        "cooldown": None,
        "usage": "{prefix}tx <tai/xiu> <tiền_cược | all>",
        "examples": ["{prefix}tx tai 100k", "{prefix}tx xiu all"],
        "note": "Bão (ra 3 con 1 hoặc 3 con 6): Mất sạch.",
    },
    "baucua": {
        "name": "Bầu Cua",
        "emoji": "🦀",
        "short": "Bàn Bầu Cua Tôm Cá chung. Sảnh cược tương tác.",
        "aliases": ["bc"],
        "cooldown": None,
        "usage": "{prefix}bc",
        "examples": ["{prefix}bc"],
        "note": "Gồm 6 con: Bầu, Cua, Tôm, Cá, Nai, Gà. Đặt cược bằng tin nhắn trong sảnh: `<tên_con> <số_tiền>`.",
    },
    "betvit": {
        "name": "Đua Vịt",
        "emoji": "🦆",
        "short": "Cược vào màu vịt. Vịt thắng, bạn thắng theo tỉ lệ pool.",
        "aliases": ["bv", "bevit"],
        "cooldown": None,
        "usage": "{prefix}betvit <màu> <tiền>",
        "examples": ["{prefix}betvit do 50k", "{prefix}bv xanh 100k"],
        "note": "Màu: do, xanh, vang, hong, yon. Xem tỉ lệ: `{prefix}xemvit`. Hủy cược: `{prefix}huybet`.",
    },
    "xoso": {
        "name": "Xổ Số",
        "emoji": "🎟️",
        "short": "Vé số kiến thiết. Đổi đời sau một đêm.",
        "aliases": ["lottery", "xs"],
        "cooldown": None,
        "usage": "{prefix}xoso [mua|ban] [số_lượng]",
        "examples": ["{prefix}xoso", "{prefix}xoso mua 5", "{prefix}xoso ban 12"],
        "note": "Gõ {prefix}xoso để xem thông tin. Kết quả xổ lúc cuối ngày.",
    },
    "multidice": {
        "name": "Multi Dice (PvP)",
        "emoji": "🎲",
        "short": "Xúc Xắc PvP nhiều người. Điểm cao nhất ăn cả nồi.",
        "aliases": ["md", "quanhung"],
        "cooldown": None,
        "usage": "{prefix}md <tiền_cược> [@user1 @user2...]",
        "examples": ["{prefix}md 100k @Bạn_A @Bạn_B"],
        "note": "Có thể mời tối đa nhiều người. Tự động chia thưởng khi kết thúc.",
    },
    # ── KINH TẾ ───────────────────────────────────────────────────────────────
    "daily": {
        "name": "Điểm Danh",
        "emoji": "🎁",
        "short": "Nhận thưởng 500 điểm mỗi ngày. Chuỗi càng dài, thưởng càng lớn.",
        "aliases": ["diemdanh"],
        "cooldown": "24h",
        "usage": "{prefix}daily",
        "examples": ["{prefix}daily"],
        "note": "Thưởng chuỗi (streak) cộng thêm tối đa 500 điểm/ngày.",
    },
    "weekly": {
        "name": "Lương Tuần",
        "emoji": "💎",
        "short": "Nhận lương 5,000 điểm mỗi tuần (7 ngày/lần).",
        "aliases": ["luongtuan"],
        "cooldown": "7 ngày",
        "usage": "{prefix}weekly",
        "examples": ["{prefix}weekly"],
        "note": None,
    },
    "point": {
        "name": "Xem Điểm",
        "emoji": "📊",
        "short": "Kiểm tra số dư điểm và thông tin sự kiện của bạn (hoặc người khác).",
        "aliases": ["bal", "vi"],
        "cooldown": None,
        "usage": "{prefix}point [@user]",
        "examples": ["{prefix}point", "{prefix}point @BanBe"],
        "note": None,
    },
    "etop": {
        "name": "Bảng Xếp Hạng",
        "emoji": "🏆",
        "short": "Xem Top 10 người chơi có nhiều điểm tích lũy nhất server.",
        "aliases": ["evtop", "eventtop", "eventop"],
        "cooldown": None,
        "usage": "{prefix}etop",
        "examples": ["{prefix}etop"],
        "note": None,
    },
    "milestone": {
        "name": "Cột Mốc",
        "emoji": "🎯",
        "short": "Xem các cột mốc phần thưởng và tiến độ đạt mốc hiện tại.",
        "aliases": ["qua", "reward"],
        "cooldown": None,
        "usage": "{prefix}milestone",
        "examples": ["{prefix}milestone"],
        "note": "Đạt mốc rồi dùng `{prefix}claim` hoặc `{prefix}nhanqua` để nhận thưởng.",
    },
    "shop": {
        "name": "Cửa Hàng",
        "emoji": "🛒",
        "short": "Xem các vật phẩm có thể mua bằng điểm sự kiện.",
        "aliases": ["cuahang", "store"],
        "cooldown": None,
        "usage": "{prefix}shop",
        "examples": ["{prefix}shop"],
        "note": "Mua vật phẩm bằng lệnh `{prefix}buy <ID> [số_lượng]`.",
    },
    "black_market": {
        "name": "Chợ Đen",
        "emoji": "🖤",
        "short": "Shop bí ẩn thay đổi hàng ngày. Hàng độc, hiếm và... bất thường.",
        "aliases": ["chodem", "blackmarket", "bm"],
        "cooldown": None,
        "usage": "{prefix}choden",
        "examples": ["{prefix}choden"],
        "note": "Hàng reset mỗi 00:00 UTC+7. Số lượng kho có hạn, ai nhanh thì được.",
    },
    "vayno": {
        "name": "Vay Nợ",
        "emoji": "🏦",
        "short": "Vay tiền từ ngân hàng dựa trên 50% điểm tích lũy của bạn.",
        "aliases": ["vay", "loan"],
        "cooldown": None,
        "usage": "{prefix}vayno <số_tiền>",
        "examples": ["{prefix}vayno 100k"],
        "note": "Lãi suất 1%/ngày. Trả nợ bằng `{prefix}trano`. Vỡ nợ sẽ bị khóa tài khoản!",
    },
    # ── KHU SINH THÁI ─────────────────────────────────────────────────────────
    "farm": {
        "name": "Nông Trại",
        "emoji": "🌻",
        "short": "Mở giao diện Nông Trại. Xem cây trồng, thu hoạch và chăm sóc mùa vụ.",
        "aliases": ["nongtrai"],
        "cooldown": None,
        "usage": "{prefix}farm",
        "examples": ["{prefix}farm"],
        "note": "Mua hạt giống bằng `{prefix}shop farm`. Gieo trồng bằng `{prefix}plant <loại> <ô>`. Nâng cấp: `{prefix}upgrade`.",
    },
    "plant": {
        "name": "Gieo Hạt Giống",
        "emoji": "🌱",
        "short": "Gieo hạt giống vào các ô đất chỉ định, hỗ trợ nhiều ô cùng lúc.",
        "aliases": ["gieo", "trong"],
        "cooldown": None,
        "usage": "{prefix}plant <loại_hạt> <ô1> [ô2] ...",
        "examples": ["{prefix}plant wheat 1 2 3", "{prefix}plant tomato 1, 2, 3", "{prefix}gieo potato 4"],
        "note": (
            "Các loại hạt giống hợp lệ: `wheat`, `potato`, `tomato`, `strawberry`, `pumpkin`, `sunflower`, `star`.\n"
            "Nhập nhiều ô cách nhau bằng dấu cách hoặc dấu phẩy. Bot sẽ kiểm tra số hạt giống và trạng thái ô đất trước khi trồng.\n"
            "Bạn có thể xem số hạt đang có trong `{prefix}farm`."
        ),
    },
    "mine": {
        "name": "Đào Mỏ",
        "emoji": "⛏️",
        "short": "Tiến vào hang động đào quặng. Càng vào sâu càng nhiều quặng quý.",
        "aliases": ["dao", "khoamo", "mining"],
        "cooldown": None,
        "usage": "{prefix}mine",
        "examples": ["{prefix}mine"],
        "note": "Tốn 4 Thể Lực mỗi lần đào. Bán quặng bằng `{prefix}inv ban`.",
    },
    "fish": {
        "name": "Câu Cá",
        "emoji": "🎣",
        "short": "Thả cần đợi cá cắn. Cá hiếm bán được nhiều điểm hơn.",
        "aliases": ["cauca", "fishing", "caca"],
        "cooldown": None,
        "usage": "{prefix}fish",
        "examples": ["{prefix}fish"],
        "note": "Tốn 3 Thể Lực mỗi lần câu. Nâng cấp cần câu để tăng tỉ lệ cá hiếm.",
    },
    # ── HỆ THỐNG TÌNH YÊU ──────────────────────────────────────────────────────
    "marry": {
        "name": "Kết Hôn",
        "emoji": "💍",
        "short": "Cầu hôn một người để chính thức thành vợ chồng.",
        "aliases": ["kethon"],
        "cooldown": None,
        "usage": "{prefix}marry [@user] [ring_id]",
        "examples": ["{prefix}marry @BanGai 31", "{prefix}kethon @Crush 32"],
        "note": "Nhẫn ID 31-34 mua trong {prefix}shop.",
    },
    "divorce": {
        "name": "Ly Hôn",
        "emoji": "💔",
        "short": "Đơn phương ly hôn người hiện tại.",
        "aliases": ["lydi", "lyhon"],
        "cooldown": None,
        "usage": "{prefix}divorce",
        "examples": ["{prefix}divorce", "{prefix}lydi"],
        "note": "Hành động này sẽ xóa toàn bộ điểm thân mật và thú cưng chung.",
    },
    "cooldowns": {
        "name": "Bảng Hồi Chiêu",
        "emoji": "⏱️",
        "short": "Xem thời gian hồi chiêu của tất cả các lệnh.",
        "aliases": ["cd", "rd"],
        "cooldown": None,
        "usage": "{prefix}cooldowns",
        "examples": ["{prefix}cd"],
        "note": "Giúp bạn kiểm soát tiến độ cày cuốc. Bot tự động ping khi Thể Lực đầy 100/100.",
    },
    "promise": {
        "name": "Lời Thề",
        "emoji": "💌",
        "short": "Khắc ghi lời thề non hẹn biển lên Profile Tình Yêu.",
        "aliases": ["hua"],
        "cooldown": None,
        "usage": "{prefix}promise <lời_hứa>",
        "examples": ["{prefix}promise Anh hứa sẽ yêu em mãi mãi"],
        "note": "Bất cứ lúc nào cũng có thể đổi lại lời hứa.",
    },
    "gift": {
        "name": "Tặng Quà",
        "emoji": "🎁",
        "short": "Tặng quà mua từ Cửa Hàng (Quà Tặng) cho vợ/chồng. Tăng DTM.",
        "aliases": ["tangqua"],
        "cooldown": 0,
        "usage": "{prefix}gift <@user> <id_quà>",
        "examples": ["{prefix}gift @nguoiyeu 41", "{prefix}gift 123456789 42"],
        "note": "Quà tặng phải mua trong Cửa Hàng ({prefix}shop mục Quà Tặng) trước khi dùng lệnh này. Mỗi món quà có lượng DTM tăng thêm riêng.",
    },
    "upgradering": {
        "name": "Nâng Cấp Nhẫn",
        "emoji": "✨",
        "short": "Đổi sang Nhẫn cấp cao hơn để nhận thêm buff DTM và giảm Cooldown.",
        "aliases": ["nangcapnhan"],
        "cooldown": None,
        "usage": "{prefix}upgradering <ring_id>",
        "examples": ["{prefix}upgradering 33"],
        "note": "Bạn cần mua sẵn nhẫn mới trong túi đồ ({prefix}inv) trước.",
    },
    "setimage": {
        "name": "Cài Ảnh",
        "emoji": "🖼️",
        "short": "Cài ảnh kỷ niệm hiển thị dưới Profile Tình Yêu.",
        "aliases": ["setanh"],
        "cooldown": None,
        "usage": "{prefix}setimage <link_ảnh>",
        "examples": ["{prefix}setimage https://example.com/image.png"],
        "note": "Link ảnh phải kết thúc bằng .png, .jpg hoặc .gif",
    },
    "coupletask": {
        "name": "Nhiệm Vụ Đôi",
        "emoji": "📋",
        "short": "Nhận 1 nhiệm vụ ngẫu nhiên chung cho cả 2 người. Hoàn thành để lấy +100 DTM.",
        "aliases": [],
        "cooldown": "1 lần/ngày",
        "usage": "{prefix}coupletask",
        "examples": ["{prefix}coupletask"],
        "note": "Ngày mới (sau 0h) sẽ nhận được task mới.",
    },
    "actions": {
        "name": "Hành Động Cặp Đôi",
        "emoji": "💞",
        "short": "Các lệnh tương tác đặc biệt dành cho vợ/chồng.",
        "aliases": ["om", "hon", "tat", "can", "dutdit", "seg", "hug", "kiss", "slap", "punch", "bite", "tickle", "poke", "pat", "saylove", "cuddle", "snuggle", "lick", "nom", "fuck", "hun", "dam", "choclet", "choc", "xoadau", "noiyeu", "iuem", "iuanh", "auyem", "nung", "nũng", "liem", "mam", "hanhdong", "hd"],
        "cooldown": 0,
        "usage": "{prefix}<hành_động> <@user>",
        "examples": ["{prefix}hug @VoYeu", "{prefix}kiss @ChongYeu"],
        "note": (
            "Bao gồm các lệnh sau (có thể dùng tên tiếng Anh hoặc alias tiếng Việt):\n"
            "- 🤜 **Bạo lực:** `{prefix}slap` (tat), `{prefix}punch` (dam), `{prefix}bite` (can), `{prefix}tickle` (choclet)\n"
            "- 💖 **Nhẹ nhàng:** `{prefix}poke` (choc), `{prefix}pat` (xoadau), `{prefix}saylove` (noiyeu, iuem, iuanh)\n"
            "- 🤗 **Ôm ấp:** `{prefix}hug` (om), `{prefix}cuddle` (auyem), `{prefix}snuggle` (nung, nũng)\n"
            "- 💋 **Thân mật:** `{prefix}kiss` (hon, hun), `{prefix}lick` (liem), `{prefix}nom` (mam, cắn yêu), `{prefix}fuck`, `{prefix}dutdit` (seg)\n"
            "*(Lưu ý: Thời gian hồi chiêu và lượng DTM nhận được tùy thuộc vào độ 'thân mật' của hành động và cấp bậc Nhẫn cưới của bạn)*"
        ),
    },
    "trano": {
        "name": "Trả Nợ",
        "emoji": "💵",
        "short": "Trả nợ cho ngân hàng để tránh bị khóa tài khoản.",
        "aliases": ["tra", "payloan"],
        "cooldown": None,
        "usage": "{prefix}trano <số_tiền | all>",
        "examples": ["{prefix}trano 50k", "{prefix}trano all"],
        "note": "Bạn cần trả cả gốc lẫn lãi.",
    },
    "ebuy": {
        "name": "Mua Chợ Đen",
        "emoji": "🛍️",
        "short": "Mua vật phẩm trực tiếp từ Chợ Đen.",
        "aliases": ["muadem", "bmbuy"],
        "cooldown": None,
        "usage": "{prefix}ebuy <id_vật_phẩm> [số_lượng]",
        "examples": ["{prefix}ebuy 1", "{prefix}ebuy 2 5"],
        "note": "Số lượng kho có hạn, hãy nhanh ta{prefix}",
    },
    "recipe": {
        "name": "Công Thức",
        "emoji": "📜",
        "short": "Xem bách khoa toàn thư công thức nông cụ & máy móc.",
        "aliases": ["recipes"],
        "cooldown": None,
        "usage": "{prefix}recipe",
        "examples": ["{prefix}recipe"],
        "note": "Thu thập nguyên liệu từ Nông Trại/Đào Mỏ để chế tạo.",
    },
    "task": {
        "name": "Nhiệm Vụ Hàng Ngày",
        "emoji": "📋",
        "short": "Hoàn thành các nhiệm vụ nhỏ mỗi ngày để lấy phần thưởng.",
        "aliases": ["tasks", "nhiemvu"],
        "cooldown": None,
        "usage": "{prefix}task",
        "examples": ["{prefix}task"],
        "note": "Nhiệm vụ reset vào lúc 0:00 mỗi ngày.",
    },
    "quest": {
        "name": "Nhiệm Vụ Tân Thủ",
        "emoji": "🎯",
        "short": "Xem và nhận thưởng từ chuỗi nhiệm vụ tân thủ.",
        "aliases": ["quests"],
        "cooldown": None,
        "usage": "{prefix}quest",
        "examples": ["{prefix}quest"],
        "note": "Nhiệm vụ tân thủ chỉ làm 1 lần duy nhất.",
    },
    "work": {
        "name": "Làm Việc",
        "emoji": "💼",
        "short": "Gõ phím đi làm nhận lương. Có tỉ lệ gặp boss/trúng mánh.",
        "aliases": ["w"],
        "cooldown": "5p",
        "usage": "{prefix}work",
        "examples": ["{prefix}work", "{prefix}w"],
        "note": "Đôi khi sẽ bị sếp la nếu làm việc không chăm chỉ.",
    },
    "upgrade": {
        "name": "Nâng Cấp Nông Trại",
        "emoji": "⬆️",
        "short": "Nâng cấp ô đất hoặc cần câu bằng nguyên liệu.",
        "aliases": ["nangcap", "morong"],
        "cooldown": None,
        "usage": "{prefix}upgrade",
        "examples": ["{prefix}upgrade"],
        "note": "Cần nguyên liệu để mở khóa tính năng cao cấp.",
    },
    "machine": {
        "name": "Khu Chế Biến",
        "emoji": "🏭",
        "short": "Mở giao diện Máy Chế Biến để làm ra vật phẩm cấp cao.",
        "aliases": ["chebien", "maymoc"],
        "cooldown": None,
        "usage": "{prefix}machine",
        "examples": ["{prefix}machine"],
        "note": "Tăng giá trị nông sản/quặng khi bán (x2 - x5).",
    },
    "craft": {
        "name": "Xây Máy Chế Biến",
        "emoji": "🏗️",
        "short": "Dùng nguyên liệu gỗ/đá/phôi để chế tạo máy (Keg, Jar, Furnace).",
        "aliases": ["chebien2", "bophuong"],
        "cooldown": None,
        "usage": "{prefix}craft <id_máy> [số_lượng]",
        "examples": ["{prefix}craft 61 2", "{prefix}craft 63 1"],
        "note": "Sau khi xây xong, máy sẽ nằm trong 10 slot của {prefix}machine.",
    },
    "chop": {
        "name": "Chặt Cây",
        "emoji": "🪓",
        "short": "Tiến vào rừng sâu chặt gỗ. Có rủi ro bị sói cắn.",
        "aliases": ["chatcay", "woodcut"],
        "cooldown": None,
        "usage": "{prefix}chop",
        "examples": ["{prefix}chop"],
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
    "Kinh Tế & Kho Đồ": {
        "emoji": "🛒",
        "desc": "Quản lý điểm, túi đồ, cửa hàng, cột mốc và ngân hàng.",
        "commands": ["inv", "use", "buy", "daily", "weekly", "point", "etop", "milestone", "shop", "black_market", "ebuy", "vayno", "trano"],
        "cogs": ["InventoryCog", "ShopCog", "EventShopCog", "Rewards", "MilestoneCog", "BlackMarketCog", "BankingCog"],
    },
    "Nhiệm Vụ & Công Việc": {
        "emoji": "📋",
        "desc": "Hệ thống nhiệm vụ, công việc để cày cuốc.",
        "commands": ["task", "quest", "work"],
        "cogs": ["TasksCog", "WorkCog"],
    },
    "Ecosystem": {
        "emoji": "🌱",
        "title": "Hệ Sinh Thái (Ecosystem)",
        "desc": "Khu vực sinh thái tự nhiên. Bạn có thể trồng trọt, khai thác tài nguyên và chế biến chúng.",
        "commands": ["farm", "plant", "upgrade", "machine", "craft", "mine", "fish", "chop", "recipe"],
        "cogs": ["IdleFarmCog", "Mining", "Fishing", "Woodcutting", "Recipes"],
    },
    "Hệ Thống Tình Yêu": {
        "emoji": "💖",
        "desc": "Kết hôn, cày điểm thân mật và tương tác cùng người thương.",
        "commands": ["marry", "divorce", "coupletask", "gift", "promise", "setimage", "adopt", "pet", "namepet", "upgradering", "actions"],
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
            inline=True,
        )

    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Tổng {total_cmds} lệnh sự kiện  •  Chọn danh mục từ menu bên dưới")
    return embed


def build_category_embed(cat_name: str, prefix: str = "{prefix}") -> discord.Embed:
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
            aliases_list = cmd.get("aliases", [])
            if len(aliases_list) > 3:
                aliases_str = f" · `{'`, `'.join(f'{prefix}{a}' for a in aliases_list[:3])}` (+{len(aliases_list)-3})"
            elif aliases_list:
                aliases_str = f" · `{'`, `'.join(f'{prefix}{a}' for a in aliases_list)}`"
            else:
                aliases_str = ""
            embed.add_field(
                name=f"{cmd['emoji']} `{prefix}{key}`{aliases_str}",
                value=cmd["short"],
                inline=True,
            )
    embed.set_footer(text="Nhấn ◀ Quay Lại để về trang chủ")
    return embed


def build_detail_embed(cmd_key: str, prefix: str = "{prefix}") -> discord.Embed:
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
            name="📛 Lệnh rút gọn/Lệnh thay thế",
            value=" · ".join(f"`{prefix}{a}`" for a in cmd["aliases"]),
            inline=True,
        )
    if cmd.get("cooldown"):
        embed.add_field(name="⏱️ Cooldown", value=cmd["cooldown"], inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="📝 Cú pháp", value=f"`{cmd['usage'].replace('{prefix}', prefix)}`", inline=False)

    if cmd.get("examples"):
        embed.add_field(
            name="💡 Ví dụ",
            value="\n".join(f"`{e.replace('{prefix}', prefix)}`" for e in cmd["examples"]),
            inline=False,
        )
    if cmd.get("note"):
        embed.add_field(name="ℹ️ Ghi chú", value=cmd["note"].replace('{prefix}', prefix), inline=False)

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
        embed = build_category_embed(cat_name, prefix=self.bot.custom_prefix)
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
        embed = build_detail_embed(cmd_key, prefix=str(self.bot.custom_prefix))
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
        embed = build_category_embed(view.cat_name, prefix=view.bot.custom_prefix)
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
# COG — Lệnh kehelp
# =============================================================================

class EventHelpCog(commands.Cog):
    """🌸 Cẩm nang hướng dẫn sự kiện với UI 3 tầng."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ehelp",
        description="Xem danh sách toàn bộ các lệnh sự kiện (UI 3 tầng).",
    )
    async def ehelp_cmd(self, ctx: commands.Context, *, cmd_name: Optional[str] = None):
        """🌸 Cẩm nang sự kiện với UI tương tác 3 tầng."""
        if cmd_name:
            cmd_key = None
            for k, v in CMD_DATA.items():
                if cmd_name.lower() == k or cmd_name.lower() in v.get("aliases", []):
                    cmd_key = k
                    break
            
            if cmd_key:
                target_cat = None
                for cat, data in CATEGORY_DATA.items():
                    if cmd_key in data.get("commands", []):
                        target_cat = cat
                        break
                
                if target_cat:
                    embed = build_detail_embed(cmd_key, prefix=ctx.prefix or ctx.bot.custom_prefix)
                    view = DetailView(self.bot, ctx.author, target_cat)
                    view.message = await ctx.send(embed=embed, view=view)
                    return
                    
        embed = build_home_embed(self.bot, ctx.author)
        view = HomeView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHelpCog(bot))
