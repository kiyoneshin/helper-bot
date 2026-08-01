"""
jail/__init__.py
=================
Entry point cho toàn bộ hệ thống Jail.
Hàm setup() sẽ load tất cả 5 Cog khi bot gọi load_extension("cogs.moderation.jail").
"""
from __future__ import annotations

from discord.ext import commands

from .core        import JailCore
from .tasks       import JailTasks
from .minigames   import JailGames
from .interaction import JailInteraction
from .events      import JailEvents


async def setup(bot: commands.Bot) -> None:
    """Load toàn bộ hệ thống Chuồng Chó."""
    await bot.add_cog(JailCore(bot))
    await bot.add_cog(JailTasks(bot))
    await bot.add_cog(JailGames(bot))
    await bot.add_cog(JailInteraction(bot))
    await bot.add_cog(JailEvents(bot))
