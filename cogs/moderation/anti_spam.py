import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands, tasks
from cogs.common.db import fetchval_db, execute_db

log = logging.getLogger("AntiSpam")

MAIN_CHANNEL_ID = 1498711783223853101
MUTE_ROLE_ID = 1535250762756530177

# Các Role
ROLE_LV5 = 1533400375443324959
ROLE_LV15_PLUS = [
    1533405894933610497, # lv15
    1533406979014398043, # lv30
    1533408225439912020, # lv50
    1533409372779319326, # lv75
    1533412010795073636  # lv100
]

SPAM_LIMIT = 5
SPAM_WINDOW = 300  # 5 phút (seconds)
MUTE_DURATION_MINS = 30 # 30 phút

class AntiSpamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {user_id: [timestamp1, timestamp2, ...]}
        self.media_tracker: dict[int, list[float]] = {}
        # URL Regex cơ bản
        self.url_regex = re.compile(r'https?://[^\s]+', re.IGNORECASE)

    async def cog_load(self):
        self.check_mutes_loop.start()

    async def cog_unload(self):
        self.check_mutes_loop.cancel()

    def _clean_old_timestamps(self, user_id: int, now: float):
        """Xóa các mốc thời gian đã quá 5 phút."""
        if user_id in self.media_tracker:
            self.media_tracker[user_id] = [t for t in self.media_tracker[user_id] if now - t <= SPAM_WINDOW]
            if not self.media_tracker[user_id]:
                del self.media_tracker[user_id]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.id != MAIN_CHANNEL_ID:
            return

        if not isinstance(message.author, discord.Member):
            return
            
        if not message.guild:
            return

        # Chỉ tính nếu có ảnh/file hoặc có đường link
        has_media = bool(message.attachments) or bool(self.url_regex.search(message.content))
        if not has_media:
            return

        # Kiểm tra điều kiện Role
        role_ids = {r.id for r in message.author.roles}
        if ROLE_LV5 not in role_ids:
            return
        if any(r in role_ids for r in ROLE_LV15_PLUS):
            return

        # Kiểm tra xem có đang bị cấm không (phòng hờ spam tiếp)
        if MUTE_ROLE_ID in role_ids:
            return

        now = discord.utils.utcnow().timestamp()
        
        # Dọn dẹp timestamps cũ
        self._clean_old_timestamps(message.author.id, now)

        # Cập nhật danh sách
        if message.author.id not in self.media_tracker:
            self.media_tracker[message.author.id] = []
        self.media_tracker[message.author.id].append(now)

        # Kiểm tra số lượng
        if len(self.media_tracker[message.author.id]) >= SPAM_LIMIT:
            # Vượt quá giới hạn -> Phạt
            try:
                mute_role = message.guild.get_role(MUTE_ROLE_ID)
                if mute_role:
                    await message.author.add_roles(mute_role, reason="Spam ảnh/embed ở kênh main")
                    
                    # Tính toán thời gian hết hạn (UTC+7 HCMC)
                    hcmc_tz = timezone(timedelta(hours=7))
                    expire_time = datetime.now(hcmc_tz) + timedelta(minutes=MUTE_DURATION_MINS)
                    
                    pool = getattr(self.bot, "db_pool", None)
                    if pool:
                        await pool.execute(
                            """
                            INSERT INTO media_mutes (discord_id, expire_at)
                            VALUES ($1, $2)
                            ON CONFLICT (discord_id) DO UPDATE SET expire_at = EXCLUDED.expire_at
                            """,
                            message.author.id, expire_time
                        )

                    # Gửi tin nhắn cảnh báo tự xóa
                    await message.channel.send(
                        f"🚫 {message.author.mention} Bạn đã gửi quá nhiều ảnh/link trong thời gian ngắn!\n"
                        f"Bạn bị khóa tính năng gửi ảnh/embed trong **30 phút** để chống spam.",
                        delete_after=10.0
                    )
                    log.info(f"Đã khóa media của {message.author} (ID: {message.author.id}) vì spam.")
                    
                    # Xóa khỏi tracker để tránh lặp lại logic nếu cố tình spam tiếp
                    del self.media_tracker[message.author.id]
                    
            except discord.Forbidden:
                log.error(f"Thiếu quyền gán role khóa media cho {message.author}.")
            except Exception as e:
                log.error(f"Lỗi khi xử lý spam media: {e}", exc_info=True)


    @tasks.loop(minutes=1)
    async def check_mutes_loop(self):
        """Quét DB để gỡ role cho những ai hết hạn khóa."""
        pool = getattr(self.bot, "db_pool", None)
        if not pool:
            return
            
        hcmc_tz = timezone(timedelta(hours=7))
        now = datetime.now(hcmc_tz)
        try:
            # Lấy danh sách hết hạn
            expired = await pool.fetch("SELECT discord_id FROM media_mutes WHERE expire_at <= $1", now)
            if not expired:
                return

            guild = self.bot.get_guild(1498711782221418588) # Cần ID server, hoặc tự lấy từ cache
            if not guild:
                # Tìm guild chứa main channel
                channel = self.bot.get_channel(MAIN_CHANNEL_ID)
                if isinstance(channel, discord.TextChannel):
                    guild = channel.guild
                    
            if not guild:
                return
                
            mute_role = guild.get_role(MUTE_ROLE_ID)
            if not mute_role:
                return
                
            for row in expired:
                user_id = row["discord_id"]
                member = guild.get_member(user_id)
                if member and mute_role in member.roles:
                    try:
                        await member.remove_roles(mute_role, reason="Hết hạn khóa media")
                        log.info(f"Đã gỡ role khóa media cho {member} (ID: {user_id})")
                    except discord.Forbidden:
                        log.error(f"Thiếu quyền gỡ role khóa media cho {member}.")
                        
                # Xóa khỏi DB kể cả khi member rời server
                await pool.execute("DELETE FROM media_mutes WHERE discord_id = $1", user_id)
                
        except Exception as e:
            log.error(f"Lỗi khi quét gỡ role khóa media: {e}", exc_info=True)

    @check_mutes_loop.before_loop
    async def before_check_mutes_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiSpamCog(bot))
