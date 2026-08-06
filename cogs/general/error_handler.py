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
            error = getattr(error, "original", error)

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
            if ctx.command and ctx.command.has_error_handler():
                return
            cmd_name = ctx.invoked_with if ctx.invoked_with else (ctx.command.name if ctx.command else "unknown")
            
            usage_str = None
            example_str = None
            help_cmd = "y!help"

            # Tìm trong event_help
            try:
                from cogs.events.generals.event_help import CMD_DATA as E_CMD_DATA
                for k, v in E_CMD_DATA.items():
                    if cmd_name == k or cmd_name in v.get("aliases", []):
                        usage_str = v.get('usage', '')
                        examples = v.get('examples', [])
                        if examples:
                            example_str = examples[0]
                        help_cmd = "y!ehelp"
                        break
            except Exception:
                pass

            # Tìm trong help_cog nếu không có
            if not usage_str:
                try:
                    from cogs.general.help_cog import CMD_DATA as G_CMD_DATA
                    for k, v in G_CMD_DATA.items():
                        if cmd_name == k or cmd_name in v.get("aliases", []):
                            usage_str = v.get('usage', '')
                            examples = v.get('examples', [])
                            if examples:
                                example_str = examples[0]
                            help_cmd = "y!help"
                            break
                except Exception:
                    pass

            if usage_str:
                if example_str:
                    import re
                    example_str = re.sub(r'@[A-Za-z_]+', '<@468428368828956692>', example_str)
                    msg = f"{ctx.author.mention}, lệnh đúng là `{usage_str}`, ví dụ `{example_str}`. Để biết thêm chi tiết hãy xài lệnh `{help_cmd} {cmd_name}`"
                else:
                    msg = f"{ctx.author.mention}, lệnh đúng là `{usage_str}`. Để biết thêm chi tiết hãy xài lệnh `{help_cmd} {cmd_name}`"
                await ctx.send(msg, delete_after=30.0)
            else:
                await ctx.send(f"{ctx.author.mention}, lệnh đúng là `{ctx.prefix}{cmd_name} <các_tham_số>`. Để biết thêm chi tiết hãy xài lệnh `{ctx.prefix}help {cmd_name}`", delete_after=30.0)
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
