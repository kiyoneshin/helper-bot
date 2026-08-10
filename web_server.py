import os
import re

# Regex quét các ký tự ngoài bảng mã cơ bản (chứa Emoji)
# Giới hạn dải này giúp bỏ qua tiếng Việt và ký tự thường
EMOJI_REGEX = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]')

def scan_emojis(directory="."):
    print("🔍 ĐANG QUÉT EMOJI MẶC ĐỊNH TRONG CODE...\n")
    found_count = 0
    
    for root, dirs, files in os.walk(directory):
        # Bỏ qua các thư mục không cần thiết
        if any(skip in root for skip in ['__pycache__', '.git', 'venv', 'env']):
            continue
            
        for file in files:
            if file.endswith(".py") and file != "find_emoji.py":
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line_num, line in enumerate(lines, 1):
                            if EMOJI_REGEX.search(line):
                                print(f"📍 File: {filepath} | Dòng {line_num}")
                                print(f"   Code: {line.strip()}")
                                print("-" * 50)
                                found_count += 1
                except Exception as e:
                    pass

    print(f"\n✅ Đã quét xong! Tìm thấy {found_count} dòng code đang chứa Emoji mặc định.")

if __name__ == "__main__":
    scan_emojis("cogs/events")