import discord
from discord.ext import commands
import logging
import time
from typing import Any, Dict

log = logging.getLogger("StaffMsgTracker")


async def _query_db(bot: Any, sql: str, *args) -> list:
    """Tự động tìm biến kết nối DB trên bot (chỉ dùng nội bộ trong file này)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []


async def _execute_db(bot: Any, sql: str, *args) -> None:
    """Thực thi câu lệnh SQL không trả về kết quả (INSERT/UPDATE)"""
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'execute'):
                await db_obj.execute(sql, *args)
                return


class StaffMsgTrackerCog(commands.Cog):
    """
    Cog theo dõi tin nhắn của Staff với bộ lọc chống spam (5s cooldown).
    Mỗi tin nhắn hợp lệ sẽ được ghi vào bảng staff_message_logs với timestamp UTC.
    """

    def __init__(self, bot):
        self.bot = bot
        # Bộ nhớ tạm lưu timestamp tin nhắn gần nhất của từng Staff: {staff_id: timestamp}
        self.cooldowns: Dict[int, float] = {}
        # Khoảng cách tối thiểu giữa 2 tin nhắn hợp lệ (giây)
        self.cooldown_seconds: float = 5.0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Bỏ qua bot và tin nhắn ngoài server
        if message.author.bot or not message.guild:
            return

        staff_id = message.author.id
        staff_id_str = str(staff_id)

        # Kiểm tra nhanh: người này có phải Staff trong DB không?
        try:
            records = await _query_db(
                self.bot,
                "SELECT discord_id FROM profiles WHERE discord_id = $1",
                staff_id_str
            )
        except Exception as e:
            log.error(f"[MsgTracker] Lỗi kiểm tra Staff: {e}")
            return

        if not records:
            return  # Không phải Staff, bỏ qua hoàn toàn

        # --- Bộ lọc chống Spam (5s Cooldown) ---
        current_time = time.time()
        last_time = self.cooldowns.get(staff_id, 0.0)

        if (current_time - last_time) < self.cooldown_seconds:
            # Khoảng cách < 5 giây → bỏ qua, không ghi nhận
            return

        # Cập nhật timestamp mới nhất vào bộ nhớ tạm
        self.cooldowns[staff_id] = current_time

        # --- Ghi nhận tin nhắn hợp lệ vào DB ---
        try:
            await _execute_db(
                self.bot,
                "INSERT INTO staff_message_logs (discord_id) VALUES ($1)",
                staff_id_str
            )
        except Exception as e:
            log.error(f"[MsgTracker] Lỗi ghi nhận tin nhắn cho {staff_id}: {e}")


async def setup(bot):
    await bot.add_cog(StaffMsgTrackerCog(bot))
