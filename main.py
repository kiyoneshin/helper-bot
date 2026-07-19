import os
import logging
import asyncio
from typing import Optional

import discord
from discord.ext import commands
import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("StaffBot")

TOKEN = os.environ.get("DISCORD_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
TARGET_GUILD = int(os.environ.get("GUILD_ID", "0"))
TRAP_CHANNEL_ID = int(os.environ.get("TRAP_CHANNEL_ID", "0"))

if not TOKEN or not DATABASE_URL:
    raise ValueError("LỖI: Thiếu DISCORD_TOKEN hoặc DATABASE_URL trong .env!")

# Cấu hình đầy đủ các quyền (Intents) cần thiết cho bot
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

def get_custom_prefix(bot, message: discord.Message):
    """
    Hàm xác định prefix cho mỗi tin nhắn gửi lên.
    """
    prefixes = ["y!", "Y!"]
    prefixes.extend(commands.when_mentioned(bot, message))
    
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        if message.reference.resolved.author.id == bot.user.id:
            prefixes.append("")
            
    return prefixes

class StaffBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=get_custom_prefix,
            intents=intents, 
            help_command=None,
            case_insensitive=True
        )
        self.db_pool: Optional[asyncpg.Pool] = None
        self.trap_channel_id: int = TRAP_CHANNEL_ID

    async def setup_hook(self):
        # Khởi tạo kết nối PostgreSQL
        self.db_pool = await asyncpg.create_pool(DATABASE_URL)
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS profiles (
                        discord_id VARCHAR PRIMARY KEY,
                        role VARCHAR, 
                        display_name VARCHAR,
                        description TEXT,
                        contact VARCHAR,
                        tags JSONB DEFAULT '[]'::jsonb,
                        photos JSONB DEFAULT '[]'::jsonb,
                        votes JSONB DEFAULT '{}'::jsonb,
                        rating NUMERIC DEFAULT 0.0,
                        weekly_replies INT DEFAULT 0
                    )
                ''')
                await conn.execute('''
                    ALTER TABLE profiles
                    ADD COLUMN IF NOT EXISTS weekly_replies INT DEFAULT 0
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS staff_message_logs (
                        id SERIAL PRIMARY KEY,
                        discord_id VARCHAR NOT NULL,
                        sent_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                    )
                ''')
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_msg_logs_discord_sent
                    ON staff_message_logs (discord_id, sent_at)
                ''')
                log.info("Database PostgreSQL đã sẵn sàng.")
        else:
            log.error("Không thể khởi tạo db_pool!")

        # =====================================================================
        # NẠP TỰ ĐỘNG (RECURSIVE AUTO-LOAD) TOÀN BỘ COGS TRONG CÁC SUB-FOLDER
        # =====================================================================
        cogs_dir = "./cogs"
        if os.path.exists(cogs_dir):
            for root, dirs, files in os.walk(cogs_dir):
                if "common" in root.split(os.sep) or "utils" in root.split(os.sep):
                    continue
                
                for filename in files:
                    if filename.endswith(".py") and not filename.startswith("_"):
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, start=".")
                        cog_name = rel_path[:-3].replace(os.sep, ".").replace("/", ".").replace("\\", ".")
                        
                        try:
                            await self.load_extension(cog_name)
                            log.info(f"🌸 Đã nạp thành công Cog: {cog_name}")
                        except Exception as e:
                            log.error(f"❌ Lỗi khi nạp Cog [{cog_name}]: {e}", exc_info=True)
        else:
            log.warning("Không tìm thấy thư mục ./cogs để nạp module!")

        log.info("Đã hoàn tất tiến trình kiểm tra và nạp các Cogs.")

        if TARGET_GUILD != 0:
            guild = discord.Object(id=TARGET_GUILD)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def on_ready(self):
        log.info(f"Bot đã bảo mật thành công dưới tên: {self.user}")

bot = StaffBot()

async def main():
    await bot.start(str(TOKEN))

if __name__ == "__main__":
    asyncio.run(main())