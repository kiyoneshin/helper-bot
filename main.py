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

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class StaffBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="y!", intents=intents, help_command=None)
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
                        rating NUMERIC DEFAULT 0.0
                    )
                ''')
                log.info("Database PostgreSQL đã sẵn sàng.")
        else:
            log.error("Không thể khởi tạo db_pool!")

        # Nạp các module tính năng rút gọn
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.staff_ui")
        await self.load_extension("cogs.trap_channel")
        await self.load_extension("cogs.welcome")
        log.info("Đã nạp thành công các Cogs.")

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