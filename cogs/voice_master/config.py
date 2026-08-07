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
        }
    },
    
    # Nhóm dành cho Role Custom (VIP, Donate, v.v...)
    "custom": {
        "roles": [
            # Thêm các ID Role Custom vào đây
            0,
        ],
        "perms": {
            "can_lock": True,
            "can_hide": True,
            "can_change_limit": True,
            "can_change_name": True,
            "can_transfer": True,
        }
    },
    
    # Nhóm dành cho Cấp Độ (Level Roles)
    "level": {
        "roles": [
            # Ví dụ ID của Role Level 10, Level 20...
            0,
        ],
        "perms": {
            "can_lock": True,
            "can_hide": False,
            "can_change_limit": True,
            "can_change_name": False,
            "can_transfer": False,
        }
    },
    
    # Bạn có thể tự thêm các nhóm khác ở bên dưới nếu muốn:
    # "nhom_khac": {
    #     "roles": [123456789],
    #     "perms": {
    #         "can_lock": True,
    #         "can_hide": False,
    #         "can_change_limit": False,
    #         "can_change_name": False,
    #         "can_transfer": False,
    #     }
    # }
}
