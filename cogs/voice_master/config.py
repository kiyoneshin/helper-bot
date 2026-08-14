# ==========================================
# CẤU HÌNH KÊNH VOICE MASTER
# ==========================================
# ID của Danh mục (Category) chứa các phòng thoại tạm thời
VOICE_CATEGORY_ID = 1498711783752601705

# ID của Kênh Join-to-Create (Kênh mà user bấm vào để tạo phòng)
# Hãy điền ID kênh "V O I C E" của bạn vào đây:
JOIN_TO_CREATE_CHANNEL_ID = 1535224214083338291

"""
config.py - Cấu hình tĩnh cho Voice Master
Bạn có thể thiết lập quyền thủ công thông qua ID của Role tại đây thay vì dùng Database.
"""

# Bạn hãy điền các Role ID vào trong các list [] tương ứng bên dưới.
# ==========================================
# CẤU HÌNH KÊNH VOICE MASTER
# ==========================================
# ID của Danh mục (Category) chứa các phòng thoại tạm thời
VOICE_CATEGORY_ID = 1498711783752601705

# ID của Kênh Join-to-Create (Kênh mà user bấm vào để tạo phòng)
# Hãy điền ID kênh "V O I C E" của bạn vào đây:
JOIN_TO_CREATE_CHANNEL_ID = 1535224214083338291

"""
config.py - Cấu hình tĩnh cho Voice Master
Bạn có thể thiết lập quyền thủ công thông qua ID của Role tại đây thay vì dùng Database.
"""

# Bạn hãy điền các Role ID vào trong các list [] tương ứng bên dưới.
# Cấu trúc: 
# "tên_nhóm_role": {
#     "roles": [ID_1, ID_2, ...],
#     "perms": { "can_lock": True/False, ... }
# }

STATIC_VOICE_PERMS = {
    # Nhóm dành cho Server Booster
    "booster": {
        "roles": [
            1510276257181339708, 
        ],
        "perms": {
            "can_lock": True,
            "can_hide": True,
            "can_change_limit": True,
            "can_change_name": True,
            "can_transfer": True,
            "is_persistent": True
        }
    },
    
    # Nhóm dành cho Level 15 (Set Status - Đổi tên)
    "level_15": {
        "roles": [
            1533405894933610497,
        ],
        "perms": {
            "set_status": True,
            "can_change_name": True,
        }
    },
    
    # Nhóm dành cho Level 30 (Priority Speaker + Đổi limit)
    "level_30": {
        "roles": [
            1533406979014398043,
        ],
        "perms": {
            "priority_speaker": True,
            "can_change_limit": True,
        }
    },

    # Nhóm dành cho Level 50 (Kênh cá nhân không bị xóa + Khóa kênh + Không thể claim)
    "level_50": {
        "roles": [
            1533408225439912020,
        ],
        "perms": {
            "is_persistent": True,
            "can_lock": True,
            "can_hide": True,
        }
    },

    # Nhóm dành cho Level 75 (Di chuyển thành viên)
    "level_75": {
        "roles": [
            1533409372779319326,
        ],
        "perms": {
            "move_members": True,
        }
    },
}

async def setup(bot):
    pass
