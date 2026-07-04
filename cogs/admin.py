import discord
from discord.ext import commands
from typing import Any

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="addstaff")
    @commands.has_permissions(administrator=True)
    async def add_staff(self, ctx: commands.Context, thanh_vien: discord.Member, role: str, *, info: str = ""):
        if role not in ["owner", "admin", "recep"]:
            await ctx.send("Role hợp lệ phải là: `owner`, `admin`, hoặc `recep`.")
            return
            
        bot: Any = self.bot
        assert bot.db_pool is not None
        async with bot.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO profiles (discord_id, role, display_name, description) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (discord_id) DO UPDATE 
                SET role = $2, display_name = $3, description = $4
            ''', str(thanh_vien.id), role, thanh_vien.display_name, info)
        
        await ctx.send(f"Đã lưu thông tin **{thanh_vien.display_name}** vào danh mục {role}.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))