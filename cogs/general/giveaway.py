import asyncio
import re
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks

from cogs.common.db import execute_db, query_db

import logging
log = logging.getLogger("GiveawayCog")

UTC7 = timezone(timedelta(hours=7))

ALLOWED_CHANNELS = [
    1498711783223853101,
    1520009693249015948,
    1516781881688068316,
    1512147779328278559,
    1527590521567056024
]
GA_EMOJI = "🎉"

def parse_time(time_str: str) -> int:
    matches = re.findall(r'(\d+)([smhd])', time_str.lower())
    if not matches:
        if time_str.isdigit():
            return int(time_str)
        return 0
    total = 0
    for val, unit in matches:
        if unit == 's': total += int(val)
        elif unit == 'm': total += int(val) * 60
        elif unit == 'h': total += int(val) * 3600
        elif unit == 'd': total += int(val) * 86400
    return total

def format_time(seconds: int) -> str:
    if seconds <= 0: return '0s'
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if d: parts.append(f'{d}d')
    if h: parts.append(f'{h}h')
    if m: parts.append(f'{m}m')
    if s: parts.append(f'{s}s')
    return ' '.join(parts)

def split_prize(prize_str: str, winners: int) -> str:
    if winners <= 1:
        return prize_str

    match = re.search(r'(?i)(\d+(?:\.\d+)?)([kmb]?)\b(.*)', prize_str)
    if not match:
        return prize_str

    number = float(match.group(1))
    unit = match.group(2).lower()
    rest = match.group(3)

    if unit == 'k': number *= 1_000
    elif unit == 'm': number *= 1_000_000
    elif unit == 'b': number *= 1_000_000_000

    divided = number / winners

    if divided >= 1_000_000_000 and divided % 1_000_000_000 == 0:
        res = f'{int(divided // 1_000_000_000)}b'
    elif divided >= 1_000_000 and divided % 1_000_000 == 0:
        res = f'{int(divided // 1_000_000)}m'
    elif divided >= 1_000 and divided % 1_000 == 0:
        res = f'{int(divided // 1_000)}k'
    else:
        if divided.is_integer():
            res = str(int(divided))
        else:
            res = f'{divided:g}'

    return prize_str[:match.start()] + res + rest


class ChannelSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = []
        for ch_id in ALLOWED_CHANNELS:
            ch = guild.get_channel(ch_id)
            if ch:
                options.append(discord.SelectOption(label=f"#{ch.name}", value=str(ch_id)))
        if not options:
            options.append(discord.SelectOption(label="Không có kênh hợp lệ", value="0"))
            
        super().__init__(placeholder="Chọn kênh để thả GA...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: ChannelSelectView = self.view # type: ignore
        view.selected_channel_id = int(self.values[0]) if self.values[0] != "0" else None
        view.stop()
        await interaction.response.defer()

class ChannelSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60.0)
        self.selected_channel_id: Optional[int] = None
        self.add_item(ChannelSelect(guild))

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.selected_role_id: Optional[int] = None
        
        select = discord.ui.RoleSelect(placeholder="Chọn Role yêu cầu (Bỏ trống = Không)", min_values=0, max_values=1)
        select.callback = self.role_callback
        self.add_item(select)

        btn = discord.ui.Button(label="Bỏ qua", style=discord.ButtonStyle.secondary)
        btn.callback = self.skip_callback
        self.add_item(btn)

    async def role_callback(self, interaction: discord.Interaction):
        select = self.children[0]
        if isinstance(select, discord.ui.RoleSelect) and select.values:
            role = select.values[0]
            if isinstance(role, discord.Role):
                self.selected_role_id = role.id
        self.stop()
        await interaction.response.defer()

    async def skip_callback(self, interaction: discord.Interaction):
        self.selected_role_id = None
        self.stop()
        await interaction.response.defer()


class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.action = None

    @discord.ui.button(label="Xác nhận", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "confirm"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Sửa", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "edit"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "cancel"
        self.stop()
        await interaction.response.defer()

class EditSelectView(discord.ui.View):
    def __init__(self, is_fga: bool):
        super().__init__(timeout=60.0)
        self.step_idx = -1
        opts = [
            discord.SelectOption(label="1. Thời gian", value="1"),
            discord.SelectOption(label="2. Số lượng Win", value="2"),
            discord.SelectOption(label="3. Phần thưởng", value="3"),
        ]
        if is_fga:
            opts.append(discord.SelectOption(label="4. Số đợt thả trong 1 lần (Batch)", value="4"))
            opts.append(discord.SelectOption(label="5. Role yêu cầu", value="5"))
            opts.append(discord.SelectOption(label="6. Kênh gửi", value="6"))
        else:
            opts.append(discord.SelectOption(label="4. Role yêu cầu", value="4"))
            opts.append(discord.SelectOption(label="5. Kênh gửi", value="5"))
            
        select = discord.ui.Select(placeholder="Chọn mục cần sửa...", options=opts)
        select.callback = self.select_cb
        self.add_item(select)

    async def select_cb(self, interaction: discord.Interaction):
        select = self.children[0]
        if isinstance(select, discord.ui.Select) and select.values:
            self.step_idx = int(select.values[0])
        self.stop()
        await interaction.response.defer()

class YesNoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.value = False

    @discord.ui.button(label="Có", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Không", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()


class GiveawaySession:
    def __init__(self, ctx: commands.Context, bot: commands.Bot, is_fga: bool = False):
        self.ctx = ctx
        self.bot = bot
        self.is_fga = is_fga
        
        self.duration_sec = 0
        self.total_fga = 1
        self.winners = 1
        self.prize_raw = ""
        self.prize_split = ""
        self.batch_size = 1
        self.role_id: Optional[int] = None
        self.channel_id: Optional[int] = None

        self.embed = discord.Embed(title="🎁 Thiết lập Giveaway", color=0x2b2d31)
        self.msg: Optional[discord.Message] = None
        
        self.done_role = False
        self.done_ch = False

    async def start(self):
        self.msg = await self.ctx.send(embed=self.embed)
        try:
            if self.is_fga:
                await self.ask_1_fga()
                await self.ask_2()
                await self.ask_3()
                await self.ask_4_fga()
                await self.ask_role_step()
                await self.ask_channel_step()
            else:
                await self.ask_1_ga()
                await self.ask_2()
                await self.ask_3()
                await self.ask_role_step()
                await self.ask_channel_step()
            
            await self.show_confirm()
        except TimeoutError:
            pass

    async def _ask_text(self, prompt: str) -> str:
        self.embed.description = f"**⏳ Đang cấu hình...**\n{prompt}"
        if self.msg:
            await self.msg.edit(embed=self.embed, view=None)
        
        while True:
            try:
                ans = await self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author and m.channel == self.ctx.channel, timeout=60.0)
                try: await ans.delete()
                except: pass
                return ans.content.strip()
            except asyncio.TimeoutError:
                self.embed.color = discord.Color.red()
                self.embed.description = "❌ Đã hủy do quá thời gian (60s)."
                if self.msg:
                    await self.msg.edit(embed=self.embed, view=None)
                raise TimeoutError

    async def _ask_view(self, prompt: str, view: discord.ui.View):
        self.embed.description = f"**⏳ Đang cấu hình...**\n{prompt}"
        if self.msg:
            await self.msg.edit(embed=self.embed, view=view)
        res = await view.wait()
        if res:
            self.embed.color = discord.Color.red()
            self.embed.description = "❌ Đã hủy do quá thời gian (60s)."
            if self.msg:
                await self.msg.edit(embed=self.embed, view=None)
            raise TimeoutError
        if self.msg:
            await self.msg.edit(view=None)

    def _update_fields(self):
        self.embed.clear_fields()
        
        if self.is_fga:
            self.embed.add_field(name="1. Thời gian & Tổng GA", value=f"{format_time(self.duration_sec)} | Tổng: {self.total_fga} đợt" if self.duration_sec else "...", inline=False)
            self.embed.add_field(name="2. Số người win / đợt", value=str(self.winners) if self.winners else "...", inline=False)
            self.embed.add_field(name="3. Phần thưởng / người", value=self.prize_split if self.prize_split else "...", inline=False)
            self.embed.add_field(name="4. Số lượng thả / lần", value=str(self.batch_size) if self.batch_size else "...", inline=False)
            role_val = f"<@&{self.role_id}>" if self.role_id else "Không có"
            self.embed.add_field(name="5. Role yêu cầu", value=role_val if self.done_role else "...", inline=False)
            ch_val = f"<#{self.channel_id}>" if self.channel_id else "..."
            self.embed.add_field(name="6. Kênh gửi", value=ch_val if self.done_ch else "...", inline=False)
        else:
            self.embed.add_field(name="1. Thời gian", value=format_time(self.duration_sec) if self.duration_sec else "...", inline=False)
            self.embed.add_field(name="2. Số người win", value=str(self.winners) if self.winners else "...", inline=False)
            self.embed.add_field(name="3. Phần thưởng / người", value=self.prize_split if self.prize_split else "...", inline=False)
            role_val = f"<@&{self.role_id}>" if self.role_id else "Không có"
            self.embed.add_field(name="4. Role yêu cầu", value=role_val if self.done_role else "...", inline=False)
            ch_val = f"<#{self.channel_id}>" if self.channel_id else "..."
            self.embed.add_field(name="5. Kênh gửi", value=ch_val if self.done_ch else "...", inline=False)

    async def ask_1_ga(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Thời gian** (VD: 1m, 1h30m, 100s):")
            t = parse_time(ans)
            if t > 0:
                self.duration_sec = t
                self._update_fields()
                break
            await self.ctx.send("❌ Thời gian không hợp lệ. Hãy thử lại (VD: 1m).", delete_after=3)

    async def ask_1_fga(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Thời gian mỗi đợt & Tổng số đợt** (VD: `1m 10`):")
            parts = ans.split()
            if len(parts) >= 2:
                t = parse_time(parts[0])
                if t > 0 and parts[1].isdigit() and int(parts[1]) > 0:
                    self.duration_sec = t
                    self.total_fga = int(parts[1])
                    self._update_fields()
                    break
            await self.ctx.send("❌ Không hợp lệ. Hãy thử lại (VD: `1m 10`).", delete_after=3)

    async def ask_2(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Số lượng người thắng** (phải là số nguyên > 0):")
            if ans.isdigit() and int(ans) > 0:
                self.winners = int(ans)
                if self.prize_raw:
                    self.prize_split = split_prize(self.prize_raw, self.winners)
                self._update_fields()
                break
            await self.ctx.send("❌ Vui lòng nhập một số nguyên dương.", delete_after=3)

    async def ask_3(self):
        ans = await self._ask_text("Vui lòng nhập **Phần thưởng** (VD: `200k owo`):")
        self.prize_raw = ans
        self.prize_split = split_prize(self.prize_raw, self.winners)
        self._update_fields()

    async def ask_4_fga(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Số đợt thả trong 1 lần** (Batch size, VD: 5):")
            if ans.isdigit() and int(ans) > 0:
                self.batch_size = int(ans)
                self._update_fields()
                break
            await self.ctx.send("❌ Vui lòng nhập một số nguyên dương.", delete_after=3)

    async def ask_role_step(self):
        view = RoleSelectView()
        await self._ask_view(f"Vui lòng chọn **Role yêu cầu** cho GA:", view)
        self.role_id = view.selected_role_id
        self.done_role = True
        self._update_fields()

    async def ask_channel_step(self):
        if self.ctx.guild:
            view = ChannelSelectView(self.ctx.guild)
            await self._ask_view(f"Vui lòng chọn **Kênh gửi** GA:", view)
            self.channel_id = view.selected_channel_id
        self.done_ch = True
        self._update_fields()

    async def show_confirm(self):
        self.embed.description = "✅ **Cấu hình hoàn tất!** Vui lòng kiểm tra lại thông tin và xác nhận."
        view = ConfirmView()
        if self.msg:
            await self.msg.edit(embed=self.embed, view=view)
        res = await view.wait()
        
        if res:
            self.embed.color = discord.Color.red()
            self.embed.description = "❌ Đã hủy do quá thời gian (60s)."
            if self.msg:
                await self.msg.edit(embed=self.embed, view=None)
            return

        if view.action == "confirm":
            if not self.channel_id:
                await self.ctx.send("❌ Bạn chưa chọn kênh hợp lệ. Vui lòng sửa lại Kênh.", delete_after=5)
                return await self.show_confirm()
                
            cog = self.bot.get_cog("GiveawayCog")
            if cog and isinstance(cog, GiveawayCog):
                await cog.start_giveaway(self)
            self.embed.color = discord.Color.green()
            self.embed.description = "✅ Đã lên lịch Giveaway thành công!"
            if self.msg:
                await self.msg.edit(embed=self.embed, view=None)
            
        elif view.action == "edit":
            await self.show_edit()
        elif view.action == "cancel":
            ask_view = YesNoView()
            self.embed.description = "⚠️ Bạn có chắc chắn muốn hủy phiên cài đặt này không?"
            if self.msg:
                await self.msg.edit(embed=self.embed, view=ask_view)
            await ask_view.wait()
            if ask_view.value:
                if self.msg:
                    await self.msg.delete()
            else:
                self._update_fields()
                await self.show_confirm()

    async def show_edit(self):
        view = EditSelectView(self.is_fga)
        self.embed.description = "✏️ Vui lòng chọn mục bạn muốn chỉnh sửa ở menu bên dưới:"
        if self.msg:
            await self.msg.edit(embed=self.embed, view=view)
        res = await view.wait()
        
        if res:
            return 
            
        step = view.step_idx
        try:
            if self.is_fga:
                if step == 1: await self.ask_1_fga()
                elif step == 2: await self.ask_2()
                elif step == 3: await self.ask_3()
                elif step == 4: await self.ask_4_fga()
                elif step == 5: await self.ask_role_step()
                elif step == 6: await self.ask_channel_step()
            else:
                if step == 1: await self.ask_1_ga()
                elif step == 2: await self.ask_2()
                elif step == 3: await self.ask_3()
                elif step == 4: await self.ask_role_step()
                elif step == 5: await self.ask_channel_step()
        except TimeoutError:
            return

        await self.show_confirm()


class GiveawayCog(commands.Cog):
    """Cog hệ thống Giveaway và Flash Giveaway."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        sql = """
        CREATE TABLE IF NOT EXISTS active_giveaways (
            message_id BIGINT PRIMARY KEY,
            channel_id BIGINT,
            host_id BIGINT,
            prize TEXT,
            winners_per_fga INT,
            end_time TIMESTAMP,
            duration_seconds INT,
            is_flash BOOLEAN,
            total_flash INT,
            current_flash INT,
            per_batch INT,
            role_id_required BIGINT
        )
        """
        await execute_db(self.bot, sql)
        self.ga_task.start()
        log.info("GiveawayCog: Đã khởi tạo bảng và chạy background task.")

    async def cog_unload(self):
        self.ga_task.cancel()

    @commands.hybrid_command(name="ga", description="Tạo Giveaway thường")
    @commands.has_permissions(administrator=True)
    async def ga_cmd(self, ctx: commands.Context):
        session = GiveawaySession(ctx, self.bot, is_fga=False)
        await session.start()

    @commands.hybrid_command(name="fga", description="Tạo Flash Giveaway")
    @commands.has_permissions(administrator=True)
    async def fga_cmd(self, ctx: commands.Context):
        session = GiveawaySession(ctx, self.bot, is_fga=True)
        await session.start()

    async def start_giveaway(self, s: GiveawaySession):
        batch = min(s.batch_size, s.total_fga) if s.is_fga else 1
        current_flash = batch if s.is_fga else 0
        total_winners = s.winners * batch
        
        end_time = datetime.now(UTC7) + timedelta(seconds=s.duration_sec)
        unix_time = int(end_time.timestamp())

        emb = discord.Embed(title=s.prize_raw if not s.is_fga else f"Flash Giveaway (Tiến độ: {current_flash}/{s.total_fga})", color=0x2b2d31)
        emb.description = (f"Click {GA_EMOJI} để tham gia!\n\n"
                           f"🎁 **Phần thưởng:** {s.prize_split} (x{total_winners})\n"
                           f"⏳ **Kết thúc:** <t:{unix_time}:R> (<t:{unix_time}:f>)\n"
                           f"👑 **Host:** <@{s.ctx.author.id}>")
        if s.role_id:
            emb.description += f"\n📌 **Yêu cầu Role:** <@&{s.role_id}>"

        channel = self.bot.get_channel(s.channel_id) if s.channel_id else None
        if not channel or not hasattr(channel, 'send'):
            return
            
        msg = await channel.send(embed=emb) # type: ignore
        await msg.add_reaction(GA_EMOJI)

        sql = """
        INSERT INTO active_giveaways 
        (message_id, channel_id, host_id, prize, winners_per_fga, end_time, duration_seconds, is_flash, total_flash, current_flash, per_batch, role_id_required)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """
        await execute_db(self.bot, sql, msg.id, channel.id, s.ctx.author.id, s.prize_split, s.winners, end_time.replace(tzinfo=None), s.duration_sec, s.is_fga, s.total_fga, current_flash, s.batch_size, s.role_id)


    @tasks.loop(seconds=5)
    async def ga_task(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        now = now + timedelta(hours=7)

        sql = "SELECT * FROM active_giveaways WHERE end_time <= $1"
        ended = await query_db(self.bot, sql, now)
        if not ended:
            return

        for row in ended:
            msg_id = row['message_id']
            ch_id = row['channel_id']
            host_id = row['host_id']
            prize = row['prize']
            winners_per_fga = row['winners_per_fga']
            is_flash = row['is_flash']
            total_flash = row['total_flash']
            current_flash = row['current_flash']
            per_batch = row['per_batch']
            role_req = row['role_id_required']
            dur = row['duration_seconds']

            # Xóa khỏi DB để không quét lại lần sau
            await execute_db(self.bot, "DELETE FROM active_giveaways WHERE message_id = $1", msg_id)

            channel = self.bot.get_channel(ch_id)
            if not channel or not hasattr(channel, 'fetch_message'):
                continue
            
            try:
                msg = await channel.fetch_message(msg_id) # type: ignore
                emb = msg.embeds[0] if msg.embeds else discord.Embed(title=prize, color=0x2b2d31)
                emb.color = discord.Color.red()
                
                reaction = discord.utils.get(msg.reactions, emoji=GA_EMOJI)
                participants = []
                if reaction:
                    async for u in reaction.users():
                        if u.bot: continue
                        member = getattr(channel, 'guild', None) and channel.guild.get_member(u.id) # type: ignore
                        if not member: continue
                        if role_req:
                            role = channel.guild.get_role(role_req) # type: ignore
                            if role not in member.roles:
                                continue
                        participants.append(u)

                # Tìm số người thắng
                k = winners_per_fga
                if is_flash:
                    desc_str = emb.description or ""
                    m = re.search(r'\(x(\d+)\)', desc_str)
                    if m:
                        k = int(m.group(1))
                
                winners = []
                if participants:
                    actual_k = min(k, len(participants))
                    winners = random.sample(participants, actual_k)

                if winners:
                    winner_mentions = ", ".join(w.mention for w in winners)
                    desc = emb.description or ""
                    desc = re.sub(r'⏳ \*\*Kết thúc:\*\*.*', f'🎉 **Người thắng cuộc:** {winner_mentions}', desc)
                    emb.description = desc
                    emb.title = f"[ĐÃ KẾT THÚC] {emb.title}"
                    await msg.edit(embed=emb)
                    
                    await msg.reply(f"🎉 Chúc mừng {winner_mentions} đã trúng **{prize}**! (Host: <@{host_id}>)")
                else:
                    desc = emb.description or ""
                    desc = re.sub(r'⏳ \*\*Kết thúc:\*\*.*', '🎉 **Người thắng cuộc:** Không có ai hợp lệ', desc)
                    emb.description = desc
                    emb.title = f"[ĐÃ KẾT THÚC] {emb.title}"
                    await msg.edit(embed=emb)
                    await msg.reply(f"😔 Không có ai tham gia hợp lệ đợt này. (Host: <@{host_id}>)")
                    
            except discord.NotFound:
                pass
            except Exception as e:
                log.error(f"Lỗi kết thúc GA {msg_id}: {e}")

            # Xử lý FGA batch tiếp theo
            if is_flash and current_flash < total_flash:
                asyncio.create_task(self.drop_next_fga(ch_id, host_id, prize, dur, total_flash, current_flash, per_batch, role_req, winners_per_fga))


    async def drop_next_fga(self, ch_id: int, host_id: int, prize: str, dur: int, total_flash: int, current_flash: int, per_batch: int, role_req: Optional[int], winners_per_fga: int):
        await asyncio.sleep(30)
        
        batch = min(per_batch, total_flash - current_flash)
        new_current = current_flash + batch
        total_winners = winners_per_fga * batch
        
        end_time = datetime.now(UTC7) + timedelta(seconds=dur)
        unix_time = int(end_time.timestamp())

        emb = discord.Embed(title=f"Flash Giveaway (Tiến độ: {new_current}/{total_flash})", color=0x2b2d31)
        emb.description = (f"Click {GA_EMOJI} để tham gia!\n\n"
                           f"🎁 **Phần thưởng:** {prize} (x{total_winners})\n"
                           f"⏳ **Kết thúc:** <t:{unix_time}:R> (<t:{unix_time}:f>)\n"
                           f"👑 **Host:** <@{host_id}>")
        if role_req:
            emb.description += f"\n📌 **Yêu cầu Role:** <@&{role_req}>"

        channel = self.bot.get_channel(ch_id)
        if not channel or not hasattr(channel, 'send'):
            return
            
        msg = await channel.send(embed=emb) # type: ignore
        await msg.add_reaction(GA_EMOJI)

        sql = """
        INSERT INTO active_giveaways 
        (message_id, channel_id, host_id, prize, winners_per_fga, end_time, duration_seconds, is_flash, total_flash, current_flash, per_batch, role_id_required)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """
        await execute_db(self.bot, sql, msg.id, channel.id, host_id, prize, winners_per_fga, end_time.replace(tzinfo=None), dur, True, total_flash, new_current, per_batch, role_req)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
