import discord
from discord.ext import commands
import math

class GlobalErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Lấy bản ghi gốc của lỗi (nếu có bị bọc bởi các lỗi khác)
        if hasattr(error, 'original'):
            error = error.original

        # Bỏ qua các lệnh không tìm thấy
        if isinstance(error, commands.CommandNotFound):
            return

        # Lỗi thiếu quyền của User
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join([f"`{p}`" for p in error.missing_permissions])
            return await ctx.send(f"🚫 **Lỗi Quyền Hạn:** Bạn cần có quyền {perms} để thực hiện lệnh này!")

        # Lỗi thiếu quyền của Bot
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join([f"`{p}`" for p in error.missing_permissions])
            return await ctx.send(f"🤖 **Bot Thiếu Quyền:** Bot cần được cấp quyền {perms} trong server này để thực hiện lệnh!")

        # Lỗi yêu cầu Owner
        if isinstance(error, commands.NotOwner):
            return await ctx.send("👑 **Giới Hạn:** Lệnh này chỉ dành cho chủ sở hữu Bot (Owner)!")

        # Lỗi yêu cầu chạy trong server (không dùng được trong DM)
        if isinstance(error, commands.NoPrivateMessage):
            return await ctx.send("🏢 **Giới Hạn:** Lệnh này chỉ có thể sử dụng trong Server, không dùng được trong tin nhắn riêng (DM)!")

        # Nếu lỗi thuộc về CheckFailure (thiếu quyền tuỳ chỉnh, không đủ điều kiện...)
        if isinstance(error, commands.CheckFailure):
            # Nếu lỗi có lời nhắn tuỳ chỉnh thì in ra
            if str(error) and "The check functions for command" not in str(error):
                await ctx.send(f"❌ **Không đủ điều kiện:** {str(error)}")
            else:
                await ctx.send("❌ **Bạn không có quyền hoặc không đủ điều kiện để sử dụng lệnh này!**")
            return

        # Lỗi Cooldown
        if isinstance(error, commands.CommandOnCooldown):
            cooldown_time = math.ceil(error.retry_after)
            minutes, seconds = divmod(cooldown_time, 60)
            hours, minutes = divmod(minutes, 60)
            time_str = ""
            if hours > 0: time_str += f"{hours} giờ "
            if minutes > 0: time_str += f"{minutes} phút "
            time_str += f"{seconds} giây"
            await ctx.send(f"⏳ Lệnh đang trong thời gian chờ! Vui lòng thử lại sau **{time_str.strip()}**.")
            return

        # Các lỗi liên quan đến sai tham số hoặc thiếu tham số
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
            cmd_name = ctx.command.name
            
            # Cố gắng lấy hướng dẫn từ event_help.py
            try:
                from cogs.events.generals.event_help import CMD_DATA
                cmd_data = CMD_DATA.get(cmd_name)
                
                # Check alias if not found
                if not cmd_data:
                    for k, v in CMD_DATA.items():
                        if cmd_name in v.get("aliases", []):
                            cmd_data = v
                            cmd_name = k
                            break

                if cmd_data:
                    emb = discord.Embed(
                        title=f"❌ Sai Cú Pháp Lệnh: {cmd_data.get('name', cmd_name)}",
                        description=cmd_data.get('short', 'Bạn đã nhập thiếu hoặc sai tham số.'),
                        color=discord.Color.red()
                    )
                    emb.add_field(name="📝 Cú Pháp Đúng", value=f"`{cmd_data.get('usage', '')}`", inline=False)
                    examples = cmd_data.get('examples', [])
                    if examples:
                        example_str = "\n".join([f"`{ex}`" for ex in examples])
                        emb.add_field(name="💡 Ví Dụ", value=example_str, inline=False)
                    if 'note' in cmd_data:
                        emb.add_field(name="ℹ️ Ghi Chú", value=cmd_data['note'], inline=False)
                    return await ctx.send(embed=emb)
            except Exception as e:
                pass # Lỡ lỗi import hoặc không có data thì fallback xuống dưới
            
            # Fallback nếu không có trong event_help
            await ctx.send(f"❌ **Lỗi Cú Pháp:** Bạn nhập sai hoặc thiếu tham số cho lệnh `{ctx.prefix}{cmd_name}`!\nVui lòng gõ `{ctx.prefix}help {cmd_name}` để xem hướng dẫn.")
            return
        
        # Bỏ qua lỗi UserNotFound hoặc MemberNotFound và in ra lỗi đẹp
        if isinstance(error, (commands.UserNotFound, commands.MemberNotFound)):
            await ctx.send(f"❌ Không tìm thấy người dùng: `{error.argument}`")
            return
            
        # Log các lỗi chưa xử lý ra console
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)

async def setup(bot):
    await bot.add_cog(GlobalErrorHandler(bot))
