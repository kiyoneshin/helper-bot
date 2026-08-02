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

def get_ga_title(ch_id: Optional[int]) -> str:
    if ch_id == 1520009693249015948:
        return "Daily Giveaway 🎀"
    elif ch_id == 1516781881688068316:
        return "Big Giveaway 🎀"
    return "Giveaway 🎀"

def build_giveaway_embed(
    is_fga: bool,
    prize_split: str,
    total_winners: int,
    host_id: int,
    host_avatar_url: Optional[str],
    end_time_dt: Optional[datetime],
    channel_id: Optional[int],
    role_id: Optional[int] = None,
    current_flash: Optional[int] = None,
    total_flash: Optional[int] = None,
    is_ended: bool = False,
    winner_mentions: Optional[str] = None
) -> discord.Embed:
    emb = discord.Embed(color=0x2b2d31 if not is_ended else discord.Color.red())
    
    emb.set_author(name=get_ga_title(channel_id))
    if host_avatar_url:
        emb.set_thumbnail(url=host_avatar_url)
    
    prize_str = prize_split if prize_split else "???"
    winners_str = total_winners if total_winners else "?"
    
    desc = f"## <a:_:1509023822454460517> **{prize_str}** <a:_:1509023858613817384>\n\n"
    desc += f" — *Host:* <@{host_id}>\n"
    
    if is_ended:
        desc += f" — *Time:* Đã kết thúc\n"
        if winner_mentions:
            desc += f" — *Winner:* {winner_mentions}\n"
        else:
            desc += f" — *Winner:* Không có ai hợp lệ\n"
    else:
        if end_time_dt:
            end_unix_time = int(end_time_dt.timestamp())
            desc += f" — *Time:* <t:{end_unix_time}:R>\n"
        else:
            desc += f" — *Time:* ???\n"
            
    desc += f"\n- 𝓡𝓸𝓵𝓮 𝔂𝓮̂𝓾 𝓬𝓪̂̀𝓾\n"
    if role_id:
        desc += f"  <@&{role_id}>\n"
    else:
        desc += f"  Không yêu cầu\n"
         
    if is_fga and current_flash is not None and total_flash is not None:
        desc += f"\n- 𝓕𝓵𝓪𝓼𝓱 𝓘𝓷𝓯𝓸\n"
        desc += f"  • Tiến độ: {current_flash}/{total_flash}\n"
        
    footer_emojis = "<:_:1526668102216061009><:_:1526668571391037541><:_:1526668198500630590><:_:1526668262123896934><:_:1526668347700416592><:_:1526889619319296000><:_:1526889807400402945>"
    desc += f"\n\n{footer_emojis}"
        
    emb.description = desc
    
    emb.set_image(url="https://cdn.discordapp.com/attachments/1532630679219732490/1533556575200084028/dg3gryc-10c81a9c-012f-45c9-8b66-9ea2470e3ca7.gif?ex=6a70eb5b&is=6a6f99db&hm=a8b215c3fdf42acbf01636089fa83a9e2b886c8e7612c815fa9165b0e6a6f9b8&")
    
    if is_ended:
        end_time_str = end_time_dt.strftime("%d/%m/%Y %H:%M:%S") if end_time_dt else "???"
        emb.set_footer(text=f"Số người thắng: {winners_str} | Kết thúc lúc {end_time_str}")
    else:
        emb.set_footer(text=f"Số người thắng: {winners_str}")
        
    return emb


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

        self.msg: Optional[discord.Message] = None
        self.prompt_msg: Optional[discord.Message] = None

    async def start(self):
        emb = self._build_preview_embed()
        self.msg = await self.ctx.send(embed=emb)
        self.prompt_msg = await self.ctx.send("🔄 Đang khởi tạo...")
        
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

    def _build_preview_embed(self) -> discord.Embed:
        batch = min(self.batch_size, self.total_fga) if self.is_fga else 1
        total_winners = self.winners * batch
        end_time = None
        if self.duration_sec > 0:
            end_time = datetime.now(UTC7) + timedelta(seconds=self.duration_sec)
            
        host = self.ctx.author
        host_avatar = host.display_avatar.url if host.display_avatar else None
            
        return build_giveaway_embed(
            is_fga=self.is_fga,
            prize_split=self.prize_split,
            total_winners=total_winners,
            host_id=host.id,
            host_avatar_url=host_avatar,
            end_time_dt=end_time,
            channel_id=self.channel_id,
            role_id=self.role_id,
            current_flash=batch if self.is_fga else None,
            total_flash=self.total_fga if self.is_fga else None,
            is_ended=False
        )

    def _update_fields(self):
        if self.msg:
            self.bot.loop.create_task(self.msg.edit(embed=self._build_preview_embed()))

    async def _ask_text(self, prompt: str) -> str:
        if self.prompt_msg:
            await self.prompt_msg.edit(content=f"**⏳ Đang cấu hình...**\n{prompt}", view=None)
        
        while True:
            try:
                ans = await self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author and m.channel == self.ctx.channel, timeout=60.0)
                try: await ans.delete()
                except: pass
                return ans.content.strip()
            except asyncio.TimeoutError:
                if self.prompt_msg:
                    await self.prompt_msg.edit(content="❌ Đã hủy do quá thời gian (60s).", view=None)
                if self.msg:
                    emb = self.msg.embeds[0]
                    emb.color = discord.Color.red()
                    await self.msg.edit(embed=emb)
                raise TimeoutError

    async def _ask_view(self, prompt: str, view: discord.ui.View):
        if self.prompt_msg:
            await self.prompt_msg.edit(content=f"**⏳ Đang cấu hình...**\n{prompt}", view=view)
        res = await view.wait()
        if res:
            if self.prompt_msg:
                await self.prompt_msg.edit(content="❌ Đã hủy do quá thời gian (60s).", view=None)
            if self.msg:
                emb = self.msg.embeds[0]
                emb.color = discord.Color.red()
                await self.msg.edit(embed=emb)
            raise TimeoutError
        if self.prompt_msg:
            await self.prompt_msg.edit(view=None)

    async def ask_1_ga(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Thời gian** (VD: 1m, 1h30m, 100s):")
            t = parse_time(ans)
            if t > 0:
                self.duration_sec = t
                self._update_fields()
                break
            msg_err = await self.ctx.send("❌ Thời gian không hợp lệ. Hãy thử lại (VD: 1m).")
            self.bot.loop.create_task(msg_err.delete(delay=3))

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
            msg_err = await self.ctx.send("❌ Không hợp lệ. Hãy thử lại (VD: `1m 10`).")
            self.bot.loop.create_task(msg_err.delete(delay=3))

    async def ask_2(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **Số lượng người thắng** (phải là số nguyên > 0):")
            if ans.isdigit() and int(ans) > 0:
                self.winners = int(ans)
                if self.prize_raw:
                    self.prize_split = split_prize(self.prize_raw, self.winners)
                self._update_fields()
                break
            msg_err = await self.ctx.send("❌ Vui lòng nhập một số nguyên dương.")
            self.bot.loop.create_task(msg_err.delete(delay=3))

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
            msg_err = await self.ctx.send("❌ Vui lòng nhập một số nguyên dương.")
            self.bot.loop.create_task(msg_err.delete(delay=3))

    async def ask_role_step(self):
        while True:
            ans = await self._ask_text("Vui lòng nhập **ID Role** hoặc **Ping Role** (Nhập `0` hoặc `none` để bỏ qua):")
            if ans.lower() in ['0', 'none', 'skip', 'không']:
                self.role_id = None
                self._update_fields()
                break
            
            m = re.search(r'\d+', ans)
            if m:
                r_id = int(m.group())
                role = self.ctx.guild.get_role(r_id) if self.ctx.guild else None
                if role:
                    self.role_id = r_id
                    self._update_fields()
                    break
            msg_err = await self.ctx.send("❌ Role không hợp lệ. Vui lòng thử lại.")
            self.bot.loop.create_task(msg_err.delete(delay=3))

    async def ask_channel_step(self):
        if self.ctx.guild:
            view = ChannelSelectView(self.ctx.guild)
            await self._ask_view(f"Vui lòng chọn **Kênh gửi** GA ở Menu bên dưới:", view)
            self.channel_id = view.selected_channel_id
        self._update_fields()

    async def show_confirm(self):
        view = ConfirmView()
        if self.prompt_msg:
            await self.prompt_msg.edit(content="✅ **Cấu hình hoàn tất!** Vui lòng kiểm tra lại thông tin và xác nhận.", view=view)
        res = await view.wait()
        
        if res:
            if self.prompt_msg:
                await self.prompt_msg.edit(content="❌ Đã hủy do quá thời gian (60s).", view=None)
            if self.msg:
                emb = self.msg.embeds[0]
                emb.color = discord.Color.red()
                await self.msg.edit(embed=emb)
            return

        if view.action == "confirm":
            if not self.channel_id:
                msg_err = await self.ctx.send("❌ Bạn chưa chọn kênh hợp lệ. Vui lòng sửa lại Kênh.")
                self.bot.loop.create_task(msg_err.delete(delay=5))
                return await self.show_confirm()
                
            cog = self.bot.get_cog("GiveawayCog")
            if cog and isinstance(cog, GiveawayCog):
                await cog.start_giveaway(self)
            
            if self.prompt_msg:
                await self.prompt_msg.edit(content="✅ Đã lên lịch Giveaway thành công!", view=None)
            
        elif view.action == "edit":
            await self.show_edit()
        elif view.action == "cancel":
            ask_view = YesNoView()
            if self.prompt_msg:
                await self.prompt_msg.edit(content="⚠️ Bạn có chắc chắn muốn hủy phiên cài đặt này không?", view=ask_view)
            await ask_view.wait()
            if ask_view.value:
                if self.msg: await self.msg.delete()
                if self.prompt_msg: await self.prompt_msg.delete()
            else:
                self._update_fields()
                await self.show_confirm()

    async def show_edit(self):
        view = EditSelectView(self.is_fga)
        if self.prompt_msg:
            await self.prompt_msg.edit(content="✏️ Vui lòng chọn mục bạn muốn chỉnh sửa ở menu bên dưới:", view=view)
        res = await view.wait()
        
        if res:
            if self.prompt_msg:
                await self.prompt_msg.edit(content="❌ Đã hủy do quá thời gian (60s).", view=None)
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
        
        host = s.ctx.author
        host_avatar = host.display_avatar.url if host.display_avatar else None

        emb = build_giveaway_embed(
            is_fga=s.is_fga,
            prize_split=s.prize_split,
            total_winners=total_winners,
            host_id=s.ctx.author.id,
            host_avatar_url=host_avatar,
            end_time_dt=end_time,
            channel_id=s.channel_id,
            role_id=s.role_id,
            current_flash=current_flash,
            total_flash=s.total_fga,
            is_ended=False
        )

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
            db_end_time = row['end_time']

            await execute_db(self.bot, "DELETE FROM active_giveaways WHERE message_id = $1", msg_id)

            channel = self.bot.get_channel(ch_id)
            if not channel or not hasattr(channel, 'fetch_message'):
                continue
            
            host_avatar = None
            if hasattr(channel, 'guild'):
                host_member = channel.guild.get_member(host_id) # type: ignore
                if host_member and host_member.display_avatar:
                    host_avatar = host_member.display_avatar.url
            
            try:
                msg = await channel.fetch_message(msg_id) # type: ignore
                emb = msg.embeds[0] if msg.embeds else discord.Embed()
                
                reaction = discord.utils.get(msg.reactions, emoji=GA_EMOJI)
                participants = []
                if reaction:
                    async for u in reaction.users():
                        if u.bot: continue
                        member = getattr(channel, 'guild', None) and channel.guild.get_member(u.id) # type: ignore
                        if not member: continue
                        if role_req:
                            role = channel.guild.get_role(role_req) # type: ignore
                            if not role or role not in member.roles:
                                continue
                        participants.append(u)

                k = winners_per_fga
                if is_flash:
                    desc_str = emb.description or ""
                    m = re.search(r'\*\*(\d+)e\*\*', desc_str)
                    if m: k = int(m.group(1))
                
                winners = []
                if participants:
                    actual_k = min(k, len(participants))
                    winners = random.sample(participants, actual_k)

                winner_mentions = ", ".join(w.mention for w in winners) if winners else None
                new_emb = build_giveaway_embed(
                    is_fga=is_flash,
                    prize_split=prize,
                    total_winners=k,
                    host_id=host_id,
                    host_avatar_url=host_avatar,
                    end_time_dt=db_end_time,
                    channel_id=ch_id,
                    role_id=role_req,
                    current_flash=current_flash,
                    total_flash=total_flash,
                    is_ended=True,
                    winner_mentions=winner_mentions
                )
                
                await msg.edit(content="__**Giveaway đã kết thúc**__", embed=new_emb)
                
                if winners:
                    await msg.reply(f"🎉 Chúc mừng {winner_mentions} đã trúng **{prize}**! (Host: <@{host_id}>)")
                else:
                    await msg.reply(f"😔 Không có ai tham gia hợp lệ đợt này. (Host: <@{host_id}>)")
                    
            except discord.NotFound:
                pass
            except Exception as e:
                log.error(f"Lỗi kết thúc GA {msg_id}: {e}")

            if is_flash and current_flash < total_flash:
                asyncio.create_task(self.drop_next_fga(ch_id, host_id, host_avatar, prize, dur, total_flash, current_flash, per_batch, role_req, winners_per_fga))


    async def drop_next_fga(self, ch_id: int, host_id: int, host_avatar: Optional[str], prize: str, dur: int, total_flash: int, current_flash: int, per_batch: int, role_req: Optional[int], winners_per_fga: int):
        await asyncio.sleep(30)
        
        batch = min(per_batch, total_flash - current_flash)
        new_current = current_flash + batch
        total_winners = winners_per_fga * batch
        
        end_time = datetime.now(UTC7) + timedelta(seconds=dur)

        emb = build_giveaway_embed(
            is_fga=True,
            prize_split=prize,
            total_winners=total_winners,
            host_id=host_id,
            host_avatar_url=host_avatar,
            end_time_dt=end_time,
            channel_id=ch_id,
            role_id=role_req,
            current_flash=new_current,
            total_flash=total_flash,
            is_ended=False
        )

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
