"""
farm_tasks.py — Background Tasks cho Hệ sinh thái Idle Farm
==============================================================
"""

import discord
from discord.ext import commands, tasks
import json
import logging

from cogs.common.db import query_db, execute_db
from .farm_db import get_and_update_stamina

log = logging.getLogger("FarmTasks")

class FarmTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_stamina_full.start()

    async def cog_unload(self) -> None:
        self.check_stamina_full.cancel()

    @tasks.loop(minutes=1)
    async def check_stamina_full(self) -> None:
        """Kiểm tra và ping người dùng khi thể lực đầy."""
        try:
            # Lấy tất cả user chưa được ping (stamina_notified = False hoặc chưa có trường)
            rows = await query_db(
                self.bot,
                """SELECT discord_id, farm_data FROM event_profiles 
                   WHERE (farm_data->>'stamina_notified')::boolean IS NOT TRUE
          AND farm_data->>'last_channel_id' IS NOT NULL"""
            )
            
            from cogs.events.mining.mining_config import MAX_STAMINA
            
            for row in rows:
                user_id = str(row["discord_id"])
                
                # Tính lại stamina không truyền channel_id để tránh ghi đè
                stamina = await get_and_update_stamina(self.bot, user_id)
                
                if stamina >= MAX_STAMINA:
                    # Đã đầy, gửi ping
                    raw_data = row["farm_data"]
                    farm_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    channel_id = farm_data.get("last_channel_id")
                    
                    if channel_id:
                        channel = self.bot.get_channel(int(channel_id))
                        if isinstance(channel, discord.TextChannel | discord.Thread | discord.VoiceChannel):
                            try:
                                await channel.send(
                                    f"⚡ <@{user_id}> Thể lực của bạn đã hồi đầy **{MAX_STAMINA}/{MAX_STAMINA}**! Đã đến lúc trở lại làm việc rồi đó~ 🌟"
                                )
                                # Đánh dấu đã ping, tránh ping liên tục
                                await execute_db(
                                    self.bot,
                                    """UPDATE event_profiles 
                                       SET farm_data = farm_data || '{"stamina_notified": true}'::jsonb 
                    WHERE discord_id = $1""",
                                    user_id
                                )
                            except discord.Forbidden:
                                pass
                            except Exception as e:
                                log.error(f"Lỗi gửi ping stamina cho {user_id} ở kênh {channel_id}: {e}")
        
        except Exception as e:
            log.error(f"Lỗi trong vòng lặp check_stamina_full: {e}", exc_info=True)

    @check_stamina_full.before_loop
    async def before_check_stamina_full(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FarmTasksCog(bot))
