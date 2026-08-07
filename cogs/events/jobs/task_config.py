# Cấu hình Nhiệm vụ (Task & Quest Configuration)

# ==========================================
# 1. DAILY TASKS (15 Nhiệm vụ)
# ==========================================
DAILY_TASKS = {
    "d1": {"name": "Con sen chăm chỉ", "desc": "Sử dụng lệnh kwork 3 lần.", "action": "work", "target": 3, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d2": {"name": "Ngứa tay đỏ đen", "desc": "Cược máy xèng (kslots) 5 lần.", "action": "slots", "target": 5, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d3": {"name": "Cao thủ lắc xí ngầu", "desc": "Đổ xúc xắc (kdice) 3 lần.", "action": "dice", "target": 3, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d4": {"name": "Đam mê xóc đĩa", "desc": "Chơi tài xỉu (ktaixiu) 5 lần.", "action": "taixiu", "target": 5, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d5": {"name": "Giao lưu văn hóa", "desc": "Gửi 20 tin nhắn ở kênh chat.", "action": "chat", "target": 20, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 100},
    "d6": {"name": "Nông dân thực thụ", "desc": "Trồng hoặc thu hoạch 5 lần.", "action": "farm", "target": 5, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d7": {"name": "Nhân phẩm đỉnh cao", "desc": "Tham gia 3 cái Giveaway.", "action": "giveaway_join", "target": 3, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d8": {"name": "Chúa tể biểu cảm", "desc": "Thả 10 cái reaction.", "action": "reaction", "target": 10, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d9": {"name": "Người chơi hệ điểm danh", "desc": "Nhận điểm danh hằng ngày (kdaily).", "action": "daily", "target": 1, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d10": {"name": "Ông hoàng hóng hớt", "desc": "Ngồi voice chat 10 chu kỳ (10 phút).", "action": "voice", "target": 10, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 100},
    "d11": {"name": "Tỷ phú tương lai", "desc": "Check số dư ví 1 lần (kpoint).", "action": "check_bal", "target": 1, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d12": {"name": "Soi rank thiên hạ", "desc": "Xem bảng xếp hạng (ketop).", "action": "check_top", "target": 1, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d13": {"name": "Thú vui tao nhã", "desc": "Chơi Bầu Cua 2 lần.", "action": "baucua", "target": 2, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d14": {"name": "Thủ thư chăm học", "desc": "Lên 1 cấp độ Arcane Level.", "action": "arcane_lvup", "target": 1, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
    "d15": {"name": "Gia nhập hội nhà giàu", "desc": "Vào cửa hàng xem đồ 1 lần (lệnh shop).", "action": "shop", "target": 1, "reward_min": 250, "reward_max": 500, "lb_reward_tier": 60, "lb_reward_chance": 50},
}

# ==========================================
# 2. WEEKLY TASKS (7 Nhiệm vụ)
# ==========================================
WEEKLY_TASKS = {
    "w1": {"name": "Lao động là vinh quang", "desc": "Sử dụng lệnh kwork 20 lần.", "action": "work", "target": 20, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 61, "lb_reward_chance": 100},
    "w2": {"name": "Con nghiện casino", "desc": "Tham gia tổng cộng 50 ván cờ bạc (Slots/Dice/Taixiu).", "action": "gamble_any", "target": 50, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 61, "lb_reward_chance": 100},
    "w3": {"name": "Chiến thần giao tiếp", "desc": "Gửi 300 tin nhắn chat.", "action": "chat", "target": 300, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 62, "lb_reward_chance": 100},
    "w4": {"name": "Bậc thầy trồng trọt", "desc": "Trồng hoặc thu hoạch 50 lần.", "action": "farm", "target": 50, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 61, "lb_reward_chance": 100},
    "w5": {"name": "Bám rễ phòng voice", "desc": "Ngồi voice chat 60 chu kỳ (1 tiếng).", "action": "voice", "target": 60, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 62, "lb_reward_chance": 100},
    "w6": {"name": "Nhà sưu tầm Giveaway", "desc": "Tham gia 15 cái Giveaway.", "action": "giveaway_join", "target": 15, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 61, "lb_reward_chance": 100},
    "w7": {"name": "Khách ruột ngân hàng", "desc": "Thực hiện vay hoặc trả nợ ngân hàng 3 lần.", "action": "bank_tx", "target": 3, "reward_min": 1500, "reward_max": 2500, "lb_reward_tier": 61, "lb_reward_chance": 100},
}

# ==========================================
# 3. LONG-TERM QUESTS (5 Nhiệm vụ)
# (Quest thì gán sẵn cho mọi user, chung 1 mốc)
# ==========================================
QUESTS = {
    "q1": {"name": "🌟 Đế Vương May Mắn", "desc": "Chiến thắng 5 lần Giveaway.", "action": "giveaway_win", "target": 5, "reward_fixed": 5000, "lb_reward_tier": 63, "lb_reward_chance": 100},
    "q2": {"name": "💰 Thần Bài Angelic", "desc": "Tham gia 500 ván cờ bạc (bất kỳ).", "action": "gamble_any", "target": 500, "reward_fixed": 10000, "lb_reward_tier": 63, "lb_reward_chance": 100},
    "q3": {"name": "👑 Tám Xuyên Lục Địa", "desc": "Đạt 20 lần Lên cấp (Arcane).", "action": "arcane_lvup", "target": 20, "reward_fixed": 8000, "lb_reward_tier": 63, "lb_reward_chance": 100},
    "q4": {"name": "🌾 Lão Nông Tỷ Phú", "desc": "Thu hoạch 200 vụ mùa.", "action": "farm", "target": 200, "reward_fixed": 7000, "lb_reward_tier": 63, "lb_reward_chance": 100},
    "q5": {"name": "🏃 Máy Cày Bền Bỉ", "desc": "Sử dụng lệnh kwork 100 lần.", "action": "work", "target": 100, "reward_fixed": 8000, "lb_reward_tier": 63, "lb_reward_chance": 100},
}
