import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from cogs.common.db import (
    get_or_create_event_profile,
    add_event_points,
    execute_db
)

log = logging.getLogger("EventCore")

# ID Tài khoản sở hữu Ngân Hàng Sự Kiện (Chốt chặn bảo mật tuyệt đối)
YON_ID = 468428368828956692

# Múi giờ chuẩn server Angelic
UTC7 = timezone(timedelta(hours=7))


def _to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Chuyển đổi datetime từ DB về dạng UTC-aware để tính toán chính xác."""
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _parse_amount(raw: str) -> float:
    cleaned = raw.lower().replace(",", "").strip()
    try:
        if cleaned.endswith("m"):
            return float(cleaned[:-1]) * 1_000_000
        elif cleaned.endswith("k"):
            return float(cleaned[:-1]) * 1_000
        else:
            return float(cleaned)
    except ValueError:
        return -1.0

def _fmt(val: float) -> str:
    s = f"{val:,.2f}"
    if s.endswith(".00"): return s[:-3]
    if s.endswith("0"): return s[:-1]
    return s


class EventCoreCog(commands.Cog):
    """Cog quản lý dòng tiền, cày điểm Chat/Voice và lệnh Admin Ngân Hàng."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_minigame_running = False
        self.last_minigame_end = None
        self.msg_count_after_cooldown = 0
        self.voice_scanner.start()
        log.info("🌸 EventCoreCog loaded — Task quét Voice 15p đã khởi động.")

    async def cog_unload(self):
        """Hủy task chạy ngầm khi Cog bị unload."""
        self.voice_scanner.cancel()

    # =====================================================================
    # 1. HỆ THỐNG LẮNG NGHE & CẢM BIẾN COMBO CHAT (ON_MESSAGE)
    # =====================================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.content.startswith(("k", "Y!", "/", "-")):
            return

        user_id = str(message.author.id)
        
        row = await get_or_create_event_profile(self.bot, user_id)
        if not row:
            return

        daily_chat = row["daily_chat_count"]
        last_chat = _to_utc_aware(row["last_chat_time"])
        streak = row["current_streak"]
        p2w = float(row["p2w_multiplier"] or 1.0)

        if daily_chat >= 600:
            return

        if daily_chat < 100:
            base_pts = 3
            cooldown = 45
        elif daily_chat < 300:
            base_pts = 2
            cooldown = max(20, 45 - (streak // 5) * 5)
        else:
            base_pts = 1
            cooldown = 20

        now_utc = datetime.now(timezone.utc)
        if last_chat:
            elapsed = (now_utc - last_chat).total_seconds()
            if elapsed < cooldown:
                return

            if elapsed > 120:
                new_streak = 1
            else:
                new_streak = streak + 1
        else:
            new_streak = 1

        final_pts = float(base_pts * p2w)

        sql_update = """
            UPDATE event_profiles
            SET points = points + $2,
                total_earned = total_earned + $2,
                daily_chat_count = daily_chat_count + 1,
                last_chat_time = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                current_streak = $3
            WHERE discord_id = $1;
        """
        await execute_db(self.bot, sql_update, user_id, final_pts, new_streak)

        # =================================================================
        # [HOOK MINIGAME ĐÁNH ÚP]: Kiểm tra tỉ lệ 1% nổ minigame tại đây
        # =================================================================
        if self.is_minigame_running:
            return

        if self.last_minigame_end is not None:
            if (now_utc - self.last_minigame_end).total_seconds() < 15 * 60:
                return

        self.msg_count_after_cooldown += 1

        if self.msg_count_after_cooldown >= 30:
            import random
            if random.random() < 0.01:
                game_channel = self.bot.get_channel(1498711783223853101)
                if not game_channel:
                    try:
                        game_channel = await self.bot.fetch_channel(1498711783223853101)
                    except discord.HTTPException:
                        game_channel = message.channel

                # ── CHỐT CHẶN PYLANCE: Đảm bảo kênh lấy được có quyền gửi tin nhắn ──
                if not isinstance(game_channel, discord.abc.Messageable):
                    game_channel = message.channel

                self.is_minigame_running = True
                self.msg_count_after_cooldown = 0
                
                game_choice = random.choice(["quick_grab", "fast_hand", "dice_lobby", "mvp_tribute"])
                
                if game_choice == "quick_grab":
                    from cogs.events.minigames.quick_grab import start_quick_grab
                    self.bot.loop.create_task(start_quick_grab(self.bot, game_channel, self))
                elif game_choice == "fast_hand":
                    from cogs.events.minigames.fast_hand import start_fast_words_game
                    self.bot.loop.create_task(start_fast_words_game(self.bot, game_channel, self))
                elif game_choice == "dice_lobby":
                    from cogs.events.minigames.dice_lobby import start_dice_lobby_game
                    self.bot.loop.create_task(start_dice_lobby_game(self.bot, game_channel, self))
                else:
                    from cogs.events.minigames.mvp_tribute import start_mvp_tribute_game
                    self.bot.loop.create_task(start_mvp_tribute_game(self.bot, game_channel, self))

    # =====================================================================
    # 2. TASK QUÉT PHÒNG VOICE MỖI 15 PHÚT (VOICE AFK GUARD)
    # =====================================================================
    @tasks.loop(minutes=15)
    async def voice_scanner(self):
        """Quét toàn bộ phòng voice, lọc AFK và phát lương theo thuật toán giảm dần."""
        total_members_rewarded = 0
        total_points_distributed = 0

        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                # ── CHỐT CHẶN 1: Lọc danh sách thành viên hợp lệ trong phòng ──
                active_listeners = [
                    m for m in channel.members
                    if not m.bot and m.voice and not (m.voice.deaf or m.voice.self_deaf)
                ]

                # Nếu phòng có dưới 2 người đang nghe -> Không đủ điều kiện (Chống treo solo)
                if len(active_listeners) < 2:
                    continue

                # ── CHỐT CHẶN 2: Chống phòng ngủ câm lặng (Mute All) ──
                active_speakers = [
                    m for m in active_listeners
                    if m.voice and not (m.voice.mute or m.voice.self_mute)
                ]
                if len(active_speakers) == 0:
                    continue

                for member in active_listeners:
                    user_id = str(member.id)
                    row = await get_or_create_event_profile(self.bot, user_id)
                    if not row:
                        continue

                    intervals = row["daily_voice_intervals"]
                    
                    if intervals >= 32:
                        continue

                    if intervals < 8:
                        base_pts = 40
                    elif intervals < 16:
                        base_pts = 25
                    elif intervals < 24:
                        base_pts = 10
                    else:
                        base_pts = 5

                    p2w = float(row["p2w_multiplier"] or 1.0)
                    final_pts = float(base_pts * p2w)

                    sql_voice = """
                        UPDATE event_profiles
                        SET points = points + $2,
                            total_earned = total_earned + $2,
                            daily_voice_intervals = daily_voice_intervals + 1,
                            last_voice_time = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                        WHERE discord_id = $1;
                    """
                    await execute_db(self.bot, sql_voice, user_id, final_pts)
                    
                    total_members_rewarded += 1
                    total_points_distributed += final_pts

        if total_members_rewarded > 0:
            log.info(
                f"🎙️ [Voice Scanner] Đã phát tổng {_fmt(total_points_distributed)} điểm "
                f"cho {total_members_rewarded} thành viên đang treo voice hợp lệ."
            )

    @voice_scanner.before_loop
    async def before_voice_scanner(self):
        await self.bot.wait_until_ready()


    # =====================================================================
    # 3. LỆNH ADMIN TỐI THƯỢNG: Y!GIVE VÀ Y!GIVEALL
    # =====================================================================
    def _is_bank_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id == YON_ID
        
    @commands.hybrid_command(name="sendfaq")
    async def sendfaq_cmd(self, ctx: commands.Context):
        """[ADMIN] Gửi cẩm nang EVENT_FAQ dưới dạng Embed vào kênh quy định."""
        if not self._is_bank_owner(ctx):
            return await ctx.send("❌ Chỉ có Bank Owner mới được dùng lệnh này!")
            
        import os, re
        faq_path = os.path.join(os.getcwd(), "EVENT_FAQ.md")
        if not os.path.exists(faq_path):
            return await ctx.send("❌ Không tìm thấy file EVENT_FAQ.md")
            
        channel = self.bot.get_channel(1533131441398091917)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(1533131441398091917)
            except:
                return await ctx.send("❌ Không tìm thấy kênh đích (ID: 1533131441398091917)!")
            
        with open(faq_path, "r", encoding="utf-8") as f:
            content = f.read().replace("{prefix}", ctx.prefix)
            
        parts = re.split(r'(?m)^###\s+Phần', content)
        if len(parts) < 2:
            return await ctx.send("❌ Không tìm thấy các '### Phần' trong EVENT_FAQ.md")
            
        await ctx.send(f"Đang xóa tin nhắn cũ và gửi Cẩm Nang Sự Kiện vào kênh <#{channel.id}>...", ephemeral=True)
        
        if isinstance(channel, discord.TextChannel):
            await channel.purge(limit=100)
        
        for i, part in enumerate(parts[1:], 1):
            part_content = "Phần" + part
            first_newline = part_content.find('\n')
            part_title = part_content[:first_newline].strip()
            part_body = part_content[first_newline:].strip()
            
            emb = discord.Embed(
                title=part_title,
                description=part_body,
                color=0x2b2d31
            )
            emb.set_author(name="HƯỚNG DẪN VÀ CÁC CÂU HỎI THƯỜNG GẶP VỀ SỰ KIỆN CỦA ANGELIC")
            emb.set_footer(text=f"Angelic Event FAQ • Phần {i}/{len(parts)-1}")
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=emb)

    @commands.hybrid_command(name="give", aliases=["givepoints", "addpoints"])
    async def give_cmd(self, ctx: commands.Context, target: discord.Member, amount: str):
        """[Chỉ dành cho Yon] Bơm điểm sự kiện cho một thành viên bất kỳ."""
        if not ctx.guild:
            await ctx.send("Lệnh này chỉ có thể sử dụng bên trong Server!", ephemeral=True)
            return

        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền can thiệp vào Ngân Hàng Sự Kiện!", ephemeral=True)
            return

        val = _parse_amount(amount)
        if val <= 0:
            await ctx.send("Số điểm cần bơm phải lớn hơn 0 và hợp lệ (vd: 10, 10.5, 1.5k)!", ephemeral=True)
            return
        
        success = await add_event_points(self.bot, target.id, val, is_earned=False)
        
        if success:
            embed = discord.Embed(
                title="🏦 Ngân Hàng Sự Kiện Angelic",
                description=f"Đã chuyển thành công **{_fmt(val)} điểm** vào tài khoản của {target.mention}!",
                color=0x57f287
            )
            embed.set_footer(text=f"Thực hiện bởi: {ctx.author.display_name} ໒꒱")
            await ctx.send(embed=embed)
            log.info(f"[GIVE] {ctx.author.display_name} đã bơm {_fmt(val)} điểm cho {target.display_name} ({target.id}).")
        else:
            await ctx.send("Giao dịch thất bại! Có lỗi xảy ra khi cập nhật Database.", ephemeral=True)

    @commands.hybrid_command(name="giveall")
    async def giveall_cmd(self, ctx: commands.Context, amount: str):
        """[Chỉ dành cho Yon] Phát lương/lì xì điểm sự kiện cho TOÀN BỘ thành viên trong Server."""
        if not ctx.guild:
            await ctx.send("Lệnh này chỉ có thể sử dụng bên trong Server!", ephemeral=True)
            return

        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền can thiệp vào Ngân Hàng Sự Kiện!", ephemeral=True)
            return

        val = _parse_amount(amount)
        if val <= 0:
            await ctx.send("Số điểm phát cho toàn server phải lớn hơn 0!", ephemeral=True)
            return

        msg = await ctx.send("Đang quét danh sách thành viên và phân phát điểm, vui lòng chờ...")
        
        valid_members = [m for m in ctx.guild.members if not m.bot]
        member_ids = [str(m.id) for m in valid_members]

        for member in valid_members:
            await get_or_create_event_profile(self.bot, member.id)

        sql_batch = """
            UPDATE event_profiles
            SET points = points + $1
            WHERE discord_id = ANY($2::text[]);
        """
        await execute_db(self.bot, sql_batch, val, member_ids)

        embed = discord.Embed(
            title="🎉 Lì Xì Toàn Server Angelic ໒꒱",
            description=(
                f"**{ctx.author.display_name}** vừa phát lương cho toàn thể server!\n\n"
                f"Mỗi thành viên nhận được: **+{_fmt(val)} điểm**\n"
                f"Tổng số người nhận: **{len(valid_members)} thành viên**"
            ),
            color=0xffb6c1
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"Hãy dùng điểm này để đổi quà trong {ctx.prefix}shop nhé! 🌸")
        
        await msg.edit(content=None, embed=embed)
        log.info(f"🎉 [GIVE ALL] {ctx.author.display_name} đã phát {_fmt(val)} điểm cho {len(valid_members)} thành viên.")

    # =====================================================================
    # 4. LỆNH THU HỒI / ROLLBACK: Y!TAKE VÀ Y!TAKEALL (MỚI THÊM)
    # =====================================================================
    @commands.hybrid_command(name="take", aliases=["takepoints", "removepoints", "rmpoints"])
    async def take_cmd(self, ctx: commands.Context, target: discord.Member, amount: str):
        """[Chỉ dành cho Yon] Tịch thu/rút điểm sự kiện của một thành viên."""
        if not ctx.guild:
            await ctx.send("Lệnh này chỉ có thể sử dụng bên trong Server!", ephemeral=True)
            return

        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền can thiệp vào Ngân Hàng Sự Kiện!", ephemeral=True)
            return

        val = _parse_amount(amount)
        if val <= 0:
            await ctx.send("Số điểm cần rút phải lớn hơn 0 và hợp lệ!", ephemeral=True)
            return

        # Dùng GREATEST(0, points - $2) để tuyệt đối không làm số dư bị âm (không bị nợ điểm)
        sql_take = """
            UPDATE event_profiles
            SET points = GREATEST(0, points - $2)
            WHERE discord_id = $1;
        """
        await get_or_create_event_profile(self.bot, target.id)
        res = await execute_db(self.bot, sql_take, str(target.id), val)

        if res is not None:
            embed = discord.Embed(
                title="⚖️ Ngân Hàng Sự Kiện Angelic — Tịch Thu",
                description=f"Đã rút **{_fmt(val)} điểm** từ tài khoản của {target.mention}!\n*(Số dư được chạm đáy ở mức 0 điểm)*",
                color=0xed4245  # Màu đỏ cảnh báo / xử phạt
            )
            embed.set_footer(text=f"Thực hiện bởi: {ctx.author.display_name} ໒꒱")
            await ctx.send(embed=embed)
            log.info(f"⚖️ [TAKE] {ctx.author.display_name} đã rút {_fmt(val)} điểm từ {target.display_name} ({target.id}).")
        else:
            await ctx.send("Giao dịch thất bại! Có lỗi xảy ra khi cập nhật Database.", ephemeral=True)

    @commands.hybrid_command(name="takeall", aliases=["removeall", "rmall"])
    async def takeall_cmd(self, ctx: commands.Context, amount: str):
        """[Chỉ dành cho Yon] Thu hồi điểm sự kiện của TOÀN BỘ thành viên trong Server."""
        if not ctx.guild:
            await ctx.send("Lệnh này chỉ có thể sử dụng bên trong Server!", ephemeral=True)
            return

        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền can thiệp vào Ngân Hàng Sự Kiện!", ephemeral=True)
            return

        val = _parse_amount(amount)
        if val <= 0:
            await ctx.send("Số điểm cần thu hồi phải lớn hơn 0!", ephemeral=True)
            return

        msg = await ctx.send("🔄 Đang quét danh sách thành viên và thu hồi điểm, vui lòng chờ...")
        
        valid_members = [m for m in ctx.guild.members if not m.bot]
        member_ids = [str(m.id) for m in valid_members]

        sql_batch_take = """
            UPDATE event_profiles
            SET points = GREATEST(0, points - $1)
            WHERE discord_id = ANY($2::text[]);
        """
        await execute_db(self.bot, sql_batch_take, val, member_ids)

        embed = discord.Embed(
            title="🌪️ Thu Hồi Điểm Toàn Server Angelic ໒꒱",
            description=(
                f"**{ctx.author.display_name}** vừa thực hiện thu hồi điểm của toàn thể server!\n\n"
                f"Mỗi thành viên bị trừ: **-{_fmt(val)} điểm** *(tối đa về 0)*\n"
                f"Tổng số bị ảnh hưởng: **{len(valid_members)} thành viên**"
            ),
            color=0xed4245
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="Hệ thống Ngân Hàng Angelic • Cân bằng lại dòng tiền 🌸")
        
        await msg.edit(content=None, embed=embed)
        log.info(f"🌪️ [TAKE ALL] {ctx.author.display_name} đã thu hồi {_fmt(val)} điểm từ {len(valid_members)} thành viên.")

    class DummyCore:
        is_minigame_running = True
        last_minigame_end = None

    def _get_target_channel(self, ctx: commands.Context) -> discord.abc.Messageable:
        """Hàm hỗ trợ: Lọc và đảm bảo kênh lấy được 100% có quyền gửi tin nhắn (Chống lỗi Pylance)."""
        ch = self.bot.get_channel(1498711783223853101)
        if isinstance(ch, discord.abc.Messageable):
            return ch
        return ctx.channel

    @commands.hybrid_command(name="fast_hand")
    async def force_fast_hand(self, ctx: commands.Context):
        """[Chỉ dành cho Yon] Kích hoạt thủ công minigame Fast Hand."""
        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền dùng lệnh này!", ephemeral=True)
            return
        game_channel = self._get_target_channel(ctx)
        from cogs.events.minigames.fast_hand import start_fast_words_game
        self.bot.loop.create_task(start_fast_words_game(self.bot, game_channel, self.DummyCore()))

    @commands.hybrid_command(name="dice_lobby")
    async def force_dice_lobby(self, ctx: commands.Context):
        """[Chỉ dành cho Yon] Kích hoạt thủ công minigame Dice Lobby."""
        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền dùng lệnh này!", ephemeral=True)
            return
        game_channel = self._get_target_channel(ctx)
        from cogs.events.minigames.dice_lobby import start_dice_lobby_game
        self.bot.loop.create_task(start_dice_lobby_game(self.bot, game_channel, self.DummyCore()))

    @commands.hybrid_command(name="quick_grab")
    async def force_quick_grab(self, ctx: commands.Context):
        """[Chỉ dành cho Yon] Kích hoạt thủ công minigame Quick Grab."""
        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền dùng lệnh này!", ephemeral=True)
            return
        game_channel = self._get_target_channel(ctx)
        from cogs.events.minigames.quick_grab import start_quick_grab
        self.bot.loop.create_task(start_quick_grab(self.bot, game_channel, self.DummyCore()))

    @commands.hybrid_command(name="mvp_tribute")
    async def force_mvp_tribute(self, ctx: commands.Context):
        """[Chỉ dành cho Yon] Kích hoạt thủ công minigame MVP Tribute."""
        if not self._is_bank_owner(ctx):
            await ctx.send("Bạn không có quyền dùng lệnh này!", ephemeral=True)
            return
        game_channel = self._get_target_channel(ctx)
        from cogs.events.minigames.mvp_tribute import start_mvp_tribute_game
        self.bot.loop.create_task(start_mvp_tribute_game(self.bot, game_channel, self.DummyCore()))


async def setup(bot: commands.Bot):
    await bot.add_cog(EventCoreCog(bot))