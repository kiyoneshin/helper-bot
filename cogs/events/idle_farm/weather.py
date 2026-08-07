import time
import random

# =====================================================================
# HỆ THỐNG THỜI TIẾT (NGẪU NHIÊN & ĐỒNG BỘ)
# =====================================================================
# Thời tiết xoay vòng mỗi 8 giờ, sử dụng epoch time để làm seed ngẫu nhiên.
# Đảm bảo toàn bộ server có chung một thời tiết tại cùng một thời điểm.

WEATHER_CYCLE_HOURS = 8

WEATHER_TYPES = {
    "sunny": {
        "name": "Nắng",
        "emoji": "☀️",
        "desc": "Cây trồng phát triển nhanh hơn 20%.",
        "growth_time_modifier": 0.8,
        "yield_modifier": 0,
        "rare_drop_modifier": 1.0,
    },
    "rainy": {
        "name": "Mưa",
        "emoji": "🌧️",
        "desc": "Sản lượng thu hoạch +1, nhưng phát triển chậm hơn 10%.",
        "growth_time_modifier": 1.1,
        "yield_modifier": 1,
        "rare_drop_modifier": 1.0,
    },
    "stormy": {
        "name": "Bão",
        "emoji": "🌪️",
        "desc": "Sản lượng -1, nhưng có tỉ lệ rớt vật phẩm hiếm x1.5.",
        "growth_time_modifier": 1.0,
        "yield_modifier": -1,
        "rare_drop_modifier": 1.5,
    },
    "cloudy": {
        "name": "Âm u",
        "emoji": "☁️",
        "desc": "Không có hiệu ứng đặc biệt.",
        "growth_time_modifier": 1.0,
        "yield_modifier": 0,
        "rare_drop_modifier": 1.0,
    },
    "snowy": {
        "name": "Băng giá",
        "emoji": "❄️",
        "desc": "Phát triển chậm 50%, nhưng nhận x2 EXP nông trại.",
        "growth_time_modifier": 1.5,
        "yield_modifier": 0,
        "rare_drop_modifier": 1.0,
    },
    "heatwave": {
        "name": "Nắng gắt",
        "emoji": "🔥",
        "desc": "Phát triển cực nhanh (giảm 30% tgian) nhưng sản lượng -1.",
        "growth_time_modifier": 0.7,
        "yield_modifier": -1,
        "rare_drop_modifier": 1.0,
    }
}

# Tỉ lệ xuất hiện các loại thời tiết (tổng không cần bằng 100)
WEATHER_WEIGHTS = {
    "sunny": 35,
    "cloudy": 25,
    "rainy": 20,
    "stormy": 5,
    "snowy": 5,
    "heatwave": 10,
}

def get_current_weather() -> dict:
    """Trả về cấu hình thời tiết hiện tại dựa trên seed thời gian (block 8 giờ)."""
    current_time = int(time.time())
    cycle_length = WEATHER_CYCLE_HOURS * 3600
    current_cycle = current_time // cycle_length
    
    # Tính thời gian còn lại của chu kỳ hiện tại
    next_cycle_time = (current_cycle + 1) * cycle_length
    time_left = next_cycle_time - current_time
    
    # Seed random bằng số thứ tự chu kỳ để đồng bộ
    random.seed(current_cycle)
    
    choices = list(WEATHER_WEIGHTS.keys())
    weights = list(WEATHER_WEIGHTS.values())
    
    chosen_weather_key = random.choices(choices, weights=weights, k=1)[0]
    weather_data = dict(WEATHER_TYPES[chosen_weather_key]) # copy
    
    # Reset seed để không ảnh hưởng các hàm random khác trong bot
    random.seed()
    
    weather_data["key"] = chosen_weather_key
    weather_data["time_left"] = time_left
    return weather_data
