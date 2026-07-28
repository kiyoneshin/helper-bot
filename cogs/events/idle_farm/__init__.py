# KHÔNG ĐỂ HÀM setup() Ở ĐÂY!
# Vì file main.py sử dụng tính năng nạp đệ quy (recursive auto-load) toàn bộ file `.py`, 
# nếu đặt hàm setup ở file này, bot sẽ nạp cog 2 lần (1 lần qua __init__.py, 1 lần qua farm_cmd.py).
# Điều này sẽ gây lỗi trùng lệnh (CommandRegistrationError) và làm crash toàn bộ Nông Trại!
