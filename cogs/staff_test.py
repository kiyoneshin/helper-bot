import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any, List

log = logging.getLogger("StaffTest")

# =====================================================================
# 1. DANH SÁCH ID NGƯỜI KIỂM THỬ & DECORATOR BẢO MẬT
# =====================================================================

# Điền Discord ID của bạn (và những người được quyền test) vào danh sách này
TESTER_IDS: List[int] = [
    468428368828956692, # ID của bạn
]

def is_tester():
    """Decorator kiểm tra: Chỉ có ID nằm trong TESTER_IDS mới được chạy lệnh"""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id not in TESTER_IDS:
            await ctx.send(
                "⚠️ **Quyền truy cập bị từ chối!**\n"
                "➡️ Các lệnh `y!test_...` chỉ dành riêng cho người kiểm thử hệ thống (Developer/Tester)."
            )
            return False
        return True
    return commands.check(predicate)


async def query_db(bot: Any, sql: str, *args) -> list:
    """Hàm tự động dò tìm và truy vấn Database trên bot"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []


# =====================================================================
# 2. COG CHỨA CÁC LỆNH KIỂM THỬ (TEST SUITE)
# =====================================================================

class StaffTestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="test_reply")
    @is_tester()
    async def test_reply_trigger(self, ctx: commands.Context, target: Optional[str] = None):
        """[TEST] Giả lập kích hoạt ngay lập tức câu nhắc nhở vote (không cần đợi 10 reply)
        ➡️ Cú pháp: y!test_reply @user hoặc y!test_reply <ID>
        """
        if not target:
            await ctx.send("⚠️ **Thiếu thông tin!**\n➡️ Vui lòng ping hoặc nhập ID nhân sự muốn test: `y!test_reply @Yon Yon Lon Ton`")
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()
        
        try:
            records = await query_db(self.bot, "SELECT display_name, role FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send("📭 **Không tìm thấy nhân sự này trong Database!**")
                return

            db_role = str(records[0]['role']).lower().strip()
            display_name = records[0]['display_name']
            
            # Giả lập gửi ngay tin nhắn nhắc nhở mà tính năng lắng nghe 10 reply hay làm
            reminder_text = (
                f"➡️ **[TEST TRIGGER]** Nếu bạn thấy {db_role} <@{target_id}> ({display_name}) nhiệt tình, "
                f"hãy đừng ngần ngại bỏ ra 1 phút sử dụng lệnh `y!menu` chọn đến "
                f"{db_role} để vote cho họ nhé!"
            )
            await ctx.send(reminder_text)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(f"Lỗi truy vấn khi test: {e}")

    @commands.command(name="test_vote")
    @is_tester()
    async def test_inject_vote(self, ctx: commands.Context, target: Optional[str] = None, score: Optional[float] = None):
        """[TEST] Bơm trực tiếp 1 điểm số ảo vào hồ sơ Staff để test tính toán điểm trung bình
        ➡️ Cú pháp: y!test_vote @user <điểm> (Ví dụ: y!test_vote @user 4.5)
        """
        if not target or score is None:
            await ctx.send(
                "⚠️ **Sai cú pháp!**\n"
                "➡️ Cú pháp chuẩn: `y!test_vote @user <điểm>` (Ví dụ: `y!test_vote @Yon 4.8`)"
            )
            return

        if not (0.0 <= score <= 5.0):
            await ctx.send("⚠️ Điểm test phải nằm trong khoảng từ `0.0` đến `5.0`!")
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()
        score = round(score, 1)

        try:
            records = await query_db(self.bot, "SELECT display_name, votes FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send("📭 **Không tìm thấy nhân sự này trong Database!**")
                return

            row = records[0]
            v_data = row.get('votes', {})
            votes_dict = {}
            if isinstance(v_data, str):
                try: votes_dict = json.loads(v_data)
                except Exception: votes_dict = {}
            elif isinstance(v_data, dict):
                votes_dict = v_data
            elif isinstance(v_data, list):
                for idx, s in enumerate(v_data):
                    if isinstance(s, (int, float)):
                        votes_dict[f"old_{idx}"] = float(s)

            # ĐÃ CHUẨN HÓA: Bơm điểm ảo với cấu trúc test_injection_number
            fake_tester_id = f"test_injection_{len(votes_dict) + 1}"
            votes_dict[fake_tester_id] = score
            
            scores = [float(v) for v in votes_dict.values()]
            new_avg = round(sum(scores) / len(scores), 1)

            await query_db(
                self.bot, 
                "UPDATE profiles SET votes = $1::text::jsonb, rating = $2 WHERE discord_id = $3",
                json.dumps(votes_dict), new_avg, target_id
            )

            await ctx.send(
                f"💖 **[TEST SUCCESS]** Đã bơm điểm ảo **{score} ⭐** cho **{row['display_name']}** với ID `{fake_tester_id}`!\n"
                f"➡️ Điểm trung bình mới cập nhật: **⭐ {new_avg}/5.0** ({len(scores)} lượt)"
            )
        except Exception as e:
            await ctx.send(f"Lỗi khi bơm điểm test: {e}")

    @commands.command(name="test_reset")
    @is_tester()
    async def test_reset_data(self, ctx: commands.Context, target: Optional[str] = None):
        """[TEST] Chỉ dọn dẹp các điểm vote ảo (test_injection_...) và giữ nguyên vote thực
        ➡️ Cú pháp: y!test_reset @user
        """
        if not target:
            await ctx.send("⚠️ **Thiếu thông tin!**\n➡️ Vui lòng nhập ID hoặc ping Staff cần dọn điểm test: `y!test_reset @user`")
            return

        target_id = target.replace("<@", "").replace("!", "").replace(">", "").strip()

        try:
            records = await query_db(self.bot, "SELECT display_name, votes FROM profiles WHERE discord_id = $1", target_id)
            if not records:
                await ctx.send("📭 **Không tìm thấy nhân sự này trong Database!**")
                return

            row = records[0]
            v_data = row.get('votes', {})
            votes_dict = {}
            if isinstance(v_data, str):
                try: votes_dict = json.loads(v_data)
                except Exception: votes_dict = {}
            elif isinstance(v_data, dict):
                votes_dict = v_data
            elif isinstance(v_data, list):
                for idx, s in enumerate(v_data):
                    if isinstance(s, (int, float)):
                        votes_dict[f"old_{idx}"] = float(s)

            # Lọc bỏ tất cả các key bắt đầu bằng test_inject hoặc test_injection
            cleaned_dict = {k: v for k, v in votes_dict.items() if not str(k).startswith("test_inject")}
            removed_count = len(votes_dict) - len(cleaned_dict)

            # Tính lại điểm trung bình trên số vote thực tế còn lại
            scores = [float(v) for v in cleaned_dict.values()]
            new_avg = round(sum(scores) / len(scores), 1) if scores else 0.0

            await query_db(
                self.bot,
                "UPDATE profiles SET votes = $1::text::jsonb, rating = $2 WHERE discord_id = $3",
                json.dumps(cleaned_dict), new_avg, target_id
            )

            # Reset luôn bộ đếm reply trong bộ nhớ tạm của StaffListenerCog (nếu đang chạy)
            listener_cog = self.bot.get_cog("StaffListenerCog")
            if listener_cog and hasattr(listener_cog, "reply_counters"):
                if int(target_id) in listener_cog.reply_counters:
                    listener_cog.reply_counters[int(target_id)] = 0

            await ctx.send(
                f"🧹 **[TEST CLEANUP]** Đã lọc và xóa **{removed_count} lượt vote ảo** khỏi hồ sơ của **{row['display_name']}**!\n"
                f"➡️ Điểm trung bình thực tế còn lại: **⭐ {new_avg}/5.0** ({len(scores)} lượt thực)"
            )
        except Exception as e:
            await ctx.send(f"Lỗi khi dọn điểm test: {e}")

async def setup(bot):
    await bot.add_cog(StaffTestCog(bot))