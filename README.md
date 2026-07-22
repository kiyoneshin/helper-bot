# helper-bot

ssh -i "angelic-key.pem" ubuntu@<IP_EC2>

cd /home/ubuntu/angelic-bot

# Tải danh sách toàn bộ các nhánh mới nhất từ GitHub về
git fetch --all

# Chuyển sang nhánh bạn muốn dùng (ví dụ nhánh 'dev')
git checkout dev

# Kéo code mới nhất của nhánh đó về
git pull origin dev

# Cập nhật thư viện (nếu nhánh mới có thêm thư viện) và khởi động lại bot
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart angelic