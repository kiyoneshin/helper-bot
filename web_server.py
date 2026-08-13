import os
import re

# Regex quét các ký tự ngoài bảng mã cơ bản (chứa Emoji)
# Giới hạn dải này giúp bỏ qua tiếng Việt và ký tự thường
EMOJI_REGEX = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]')

def scan_emojis(directory="."):
    print("🔍 ĐANG QUÉT EMOJI MẶC ĐỊNH TRONG CODE...\n")
    found_count = 0
    
    with open('d:/Code/Projects/helper-bot/scratch/native_emoji_usage.md', 'w', encoding='utf-8') as f_out:
        f_out.write('# Báo Cáo Sử Dụng Emoji Mặc Định / Emoji Khác\n\n')
        for root, dirs, files in os.walk(directory):
            # Bỏ qua các thư mục không cần thiết
            if any(skip in root for skip in ['__pycache__', '.git', 'venv', 'env', 'scratch']):
                continue
                
            for file in files:
                if file.endswith(".py") and file != "find_emoji.py":
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            for line_num, line in enumerate(lines, 1):
                                if EMOJI_REGEX.search(line):
                                    abs_path = os.path.abspath(filepath).replace(chr(92), '/')
                                    f_out.write(f"- [{file}:{line_num}](file:///{abs_path}#L{line_num}): `{line.strip()}`\n")
                                    found_count += 1
                    except Exception as e:
                        pass

    print(f"\n✅ Đã quét xong! Tìm thấy {found_count} dòng code đang chứa Emoji mặc định.")
    print("👉 Xem chi tiết tại: scratch/native_emoji_usage.md")

if __name__ == "__main__":
    scan_emojis("cogs/events")