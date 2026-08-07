# ==========================================
# CẤU HÌNH KÊNH VOICE MASTER
# ==========================================
# ID của Danh mục (Category) chứa các phòng thoại tạm thời
VOICE_CATEGORY_ID = 1498711783752601705

# ID của Kênh Join-to-Create (Kênh mà user bấm vào để tạo phòng)
# Hãy điền ID kênh "V O I C E" của bạn vào đây:
JOIN_TO_CREATE_CHANNEL_ID = 1535224214083338291

"""
config.py - Cáº¥u hÃ¬nh tÄ©nh cho Voice Master
Báº¡n cÃ³ thá»ƒ thiáº¿t láº­p quyá»n thá»§ cÃ´ng thÃ´ng qua ID cá»§a Role táº¡i Ä‘Ã¢y thay vÃ¬ dÃ¹ng Database.
"""

# Báº¡n hÃ£y Ä‘iá»n cÃ¡c Role ID vÃ o trong cÃ¡c list [] tÆ°Æ¡ng á»©ng bÃªn dÆ°á»›i.
# Cáº¥u trÃºc: 
# "tÃªn_nhÃ³m_role": {
#     "roles": [ID_1, ID_2, ...],
#     "perms": { "can_lock": True/False, ... }
# }

STATIC_VOICE_PERMS = {
    # NhÃ³m dÃ nh cho Server Booster
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
    
    # NhÃ³m dÃ nh cho Role Custom (VIP, Donate, v.v...)
    "custom": {
        "roles": [
            # ThÃªm cÃ¡c ID Role Custom vÃ o Ä‘Ã¢y
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
    
    # NhÃ³m dÃ nh cho Cáº¥p Äá»™ (Level Roles)
    "level": {
        "roles": [
            # VÃ­ dá»¥ ID cá»§a Role Level 10, Level 20...
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
    
    # Báº¡n cÃ³ thá»ƒ tá»± thÃªm cÃ¡c nhÃ³m khÃ¡c á»Ÿ bÃªn dÆ°á»›i náº¿u muá»‘n:
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

