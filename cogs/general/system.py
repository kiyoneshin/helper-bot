"""
system.py — Lệnh Hệ Thống
=========================
Chứa lệnh kiểm tra độ trễ (ping) và nạp lại code (reload).
"""
import time
import discord
from discord.ext import commands

class SystemCog(commands.Cog, name="System"):
    """⚙ Lệnh Hệ Thống (Ping, Reload)"""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping")
    async def ping_cmd(self, ctx: commands.Context) -> None:
        """Kiểm tra độ trễ của Bot."""
        start_time = time.perf_counter()
        message = await ctx.send("🏓 Đang kiểm tra Ping...")
        end_time = time.perf_counter()

        api_latency = round(self.bot.latency * 1000)
        bot_latency = round((end_time - start_time) * 1000)

        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(name="API Latency (Đường truyền tới Discord)", value=f"`{api_latency}ms`", inline=False)
        embed.add_field(name="Bot Latency (Độ trễ xử lý code)", value=f"`{bot_latency}ms`", inline=False)
        
        await message.edit(content=None, embed=embed)

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cmd(self, ctx: commands.Context, extension: str) -> None:
        """[Admin] Nạp lại một file code (cog) mà không cần tắt bot."""
        try:
            if not extension.startswith("cogs."):
                extension = f"cogs.{extension}"
            await self.bot.reload_extension(extension)
            await ctx.send(f"<:symbol_right:1536289313959186472> Đã tải lại thành công: `{extension}`")
        except Exception as e:
            await ctx.send(f"<:symbol_wrong:1536289315867598849> Lỗi khi tải lại `{extension}`:\n```py\n{e}\n```")

    @commands.command(name="load")
    @commands.is_owner()
    async def load_cmd(self, ctx: commands.Context, extension: str) -> None:
        """[Admin] Nạp một file code (cog) mới."""
        try:
            if not extension.startswith("cogs."):
                extension = f"cogs.{extension}"
            await self.bot.load_extension(extension)
            await ctx.send(f"<:symbol_right:1536289313959186472> Đã tải thành công: `{extension}`")
        except Exception as e:
            await ctx.send(f"<:symbol_wrong:1536289315867598849> Lỗi khi tải `{extension}`:\n```py\n{e}\n```")

    @commands.hybrid_command(name="prefix")
    @commands.has_permissions(administrator=True)
    async def prefix_cmd(self, ctx: commands.Context, new_prefix: str) -> None:
        """[Admin] Đổi tiền tố (prefix) của bot trên toàn server."""
        if len(new_prefix) > 10:
            await ctx.send("<:symbol_wrong:1536289315867598849> Prefix không được dài quá 10 ký tự!")
            return
            
        try:
            sql = '''
                INSERT INTO bot_configs (config_key, config_value) 
                VALUES ('prefix', $1)
                ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value
            '''
            db_pool = getattr(self.bot, 'db_pool', None)
            if db_pool:
                await db_pool.execute(sql, new_prefix)
            self.bot.custom_prefix = new_prefix  # type: ignore
            await ctx.send(f"<:symbol_right:1536289313959186472> Đã đổi tiền tố của bot thành: `{new_prefix}`\n(Từ giờ hãy dùng `{new_prefix}help`)")
        except Exception as e:
            await ctx.send(f"<:symbol_wrong:1536289315867598849> Lỗi khi đổi prefix: `{e}`")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SystemCog(bot))
