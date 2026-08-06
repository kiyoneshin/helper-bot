"""
farm_tasks.py — Background Tasks cho Hệ sinh thái Idle Farm
==============================================================
"""

import discord
from discord.ext import commands, tasks
import json
import logging

from cogs.common.db import fetchall_db
from .farm_db import get_and_update_stamina

log = logging.getLogger("FarmTasks")

class FarmTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_stamina_full.start()

    def cog_unload(self) -> None:
        self.check_stamina_full.cancel()

    @tasks.loop(minutes=1)
    async def check_stamina_full(self) -> None:
        """Kiểm tra và ping người dùng khi thể lực đầy."""
        try:
            # Lấy tất cả user chưa được ping (stamina_notified = False)
            rows = await fetchall_db(
                self.bot,
                "SELECT discord_id, farm_data FROM event_profiles WHERE farm_data->>'stamina_notified' = 'false'"
            )
            
            from cogs.events.mining.mining_config import MAX_STAMINA
            
            for row in rows:
                user_id = str(row["discord_id"])
                
                # Hàm này tự động tính toán lại stamina dựa trên thời gian
                # Không truyền channel_id để tránh ghi đè last_channel_id
                stamina = await get_and_update_stamina(self.bot, user_id)
                
                if stamina >= MAX_STAMINA:
                    # Đã đầy, gửi ping
                    raw_data = row["farm_data"]
                    farm_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    channel_id = farm_data.get("last_channel_id")
                    
                    if channel_id:
                        channel = self.bot.get_channel(int(channel_id))
                        if channel:
                            try:
                                await channel.send(
                                    f"⚡ <@{user_id}> Thể lực của bạn đã hồi đầy! Đã đến lúc trở lại làm việc!"
                                )
                            except discord.Forbidden:
                                # Bot không có quyền gửi tin nhắn
                                pass
                            except Exception as e:
                                log.error(f"Lỗi gửi ping stamina cho {user_id} ở kênh {channel_id}: {e}")
        
        except Exception as e:
            log.error(f"Lỗi trong vòng lặp check_stamina_full: {e}")

    @check_stamina_full.before_loop
    async def before_check_stamina_full(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FarmTasksCog(bot))
