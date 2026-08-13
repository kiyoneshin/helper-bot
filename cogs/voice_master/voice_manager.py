"""
voice_manager.py - VoiceMaster Nhà Làm (Full Edition)
Gồm đầy đủ: Dropdown UI, Persistent Settings, Claim logic, Permit/Reject, Persistent Channel (Kênh Cá Nhân)
"""
from __future__ import annotations
import logging
import re
from typing import Optional
import asyncpg
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands, tasks
from .config import STATIC_VOICE_PERMS, VOICE_CATEGORY_ID, JOIN_TO_CREATE_CHANNEL_ID

log = logging.getLogger("VoiceMaster")

# ==============================================================================
# DB HELPERS
# ==============================================================================

async def _get_setup(pool, guild_id: int):
    return await pool.fetchrow("SELECT * FROM voice_setups WHERE guild_id = $1", guild_id)

async def _get_active_channel(pool, channel_id: int):
    return await pool.fetchrow("SELECT * FROM active_voice_channels WHERE channel_id = $1", channel_id)

async def _get_user_settings(pool, user_id: int) -> dict:
    row = await pool.fetchrow("SELECT * FROM voice_user_settings WHERE discord_id = $1", user_id)
    return dict(row) if row else {
        "discord_id": user_id, "channel_name": None,
        "user_limit": 0, "is_locked": False, "is_hidden": False
    }

async def _save_user_settings(pool, user_id: int, **kwargs) -> None:
    cur = await _get_user_settings(pool, user_id)
    await pool.execute("""
        INSERT INTO voice_user_settings (discord_id, channel_name, user_limit, is_locked, is_hidden)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (discord_id) DO UPDATE
            SET channel_name=$2, user_limit=$3, is_locked=$4, is_hidden=$5
    """, user_id,
        kwargs.get("channel_name", cur["channel_name"]),
        kwargs.get("user_limit",   cur["user_limit"]),
        kwargs.get("is_locked",    cur["is_locked"]),
        kwargs.get("is_hidden",    cur["is_hidden"]),
    )

# ==============================================================================
# PERMISSION HELPER
# ==============================================================================

async def _check_perm(pool, guild_id: int, member: discord.Member, perm: str) -> bool:
    role_ids = [r.id for r in member.roles]
    if not role_ids:
        return False
    # Check config.py
    for gd in STATIC_VOICE_PERMS.values():
        if any(r in gd["roles"] for r in role_ids):
            if gd["perms"].get(perm, False):
                return True
    if not pool:
        return False
    # Fallback to DB (ignore if column does not exist)
    try:
        rows = await pool.fetch(
            f"SELECT {perm} FROM voice_role_perms "
            f"WHERE guild_id=$1 AND role_id=ANY($2::bigint[]) ORDER BY priority DESC LIMIT 1",
            guild_id, role_ids
        )
        return bool(rows and rows[0][perm])
    except asyncpg.UndefinedColumnError:
        return False

# ==============================================================================
# MODALS
# ==============================================================================

class RenameModal(discord.ui.Modal, title="Đổi tên phòng"):
    name_input = discord.ui.TextInput(label="Tên phòng mới", placeholder="Ví dụ: Phòng Chill", max_length=100)

    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        super().__init__()
        self.channel, self.bot, self.owner_id = channel, bot, owner_id

    async def on_submit(self, interaction: discord.Interaction):
        new_name = str(self.name_input).strip()
        if not new_name:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Tên phòng không được để trống!", ephemeral=True)
            return
        try:
            await self.channel.edit(name=new_name)
            pool = getattr(self.bot, "db_pool", None)
            if pool:
                await _save_user_settings(pool, self.owner_id, channel_name=new_name)
            await interaction.response.send_message(f"<:symbol_right:1536629912515903578> Đã đổi tên phòng: **{new_name}**", ephemeral=True)
        except discord.HTTPException as e:
            msg = "Rate Limit! Discord chỉ cho đổi tên 2 lần/10 phút. Hãy đợi rồi thử lại!" if e.status == 429 else str(e)
            await interaction.response.send_message(f"<:symbol_wrong:1536629915598848072> {msg}", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Giới hạn người dùng"):
    limit_input = discord.ui.TextInput(label="Số người tối đa (0 = không giới hạn)", placeholder="Ví dụ: 5", min_length=1, max_length=2)

    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        super().__init__()
        self.channel, self.bot, self.owner_id = channel, bot, owner_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(str(self.limit_input))
            if not 0 <= limit <= 99:
                await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Giới hạn phải từ 0 đến 99!", ephemeral=True)
                return
            await self.channel.edit(user_limit=limit)
            pool = getattr(self.bot, "db_pool", None)
            if pool:
                await _save_user_settings(pool, self.owner_id, user_limit=limit)
            label = "không giới hạn" if limit == 0 else f"**{limit}** người"
            await interaction.response.send_message(f"<:symbol_right:1536629912515903578> Đã đặt giới hạn: {label}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Vui lòng nhập số hợp lệ!", ephemeral=True)


class PermitModal(discord.ui.Modal, title="Cho phép người dùng"):
    user_input = discord.ui.TextInput(label="Nhập ID người dùng", placeholder="123456789012345678", max_length=20)

    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        raw   = str(self.user_input).strip()
        match = re.search(r"\d{17,20}", raw)
        if not match:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Không tìm thấy ID hợp lệ!", ephemeral=True)
            return
        if not isinstance(interaction.guild, discord.Guild):
            return
        target = interaction.guild.get_member(int(match.group()))
        if not target:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Không tìm thấy thành viên trong server!", ephemeral=True)
            return
        ow = self.channel.overwrites_for(target)
        ow.connect, ow.view_channel = True, True
        await self.channel.set_permissions(target, overwrite=ow)
        await interaction.response.send_message(f"<:symbol_right:1536629912515903578> Đã cấp quyền vào phòng cho **{target.display_name}**!", ephemeral=True)

# ==============================================================================
# USER SELECTS
# ==============================================================================

class RejectSelect(discord.ui.UserSelect):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(placeholder="Chọn người cần đuổi...", min_values=1, max_values=1)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.id == interaction.user.id or target.bot:
            await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Không thể chọn người này!", ephemeral=True)
            return
        
        if isinstance(interaction.guild, discord.Guild):
            target_member = interaction.guild.get_member(target.id)
            if target_member:
                if target_member in self.channel.members:
                    await target_member.move_to(None)
                
                ow = self.channel.overwrites_for(target_member)
                ow.connect, ow.view_channel = False, False
                await self.channel.set_permissions(target_member, overwrite=ow)
                
        await interaction.response.send_message(f"🥾 Đã đuổi **{target.display_name}** và cấm vào lại!", ephemeral=True)


class TransferSelect(discord.ui.UserSelect):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot):
        super().__init__(placeholder="Chọn người nhận quyền chủ...", min_values=1, max_values=1)
        self.channel, self.bot = channel, bot

    async def callback(self, interaction: discord.Interaction):
        new_owner = self.values[0]
        if new_owner.bot or new_owner.id == interaction.user.id:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Không thể chọn người này!", ephemeral=True)
        if new_owner not in self.channel.members:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Người này không có trong phòng!", ephemeral=True)
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            await pool.execute("UPDATE active_voice_channels SET owner_id=$1 WHERE channel_id=$2",
                               new_owner.id, self.channel.id)
        await interaction.response.send_message(f"👑 Đã chuyển quyền chủ cho **{new_owner.display_name}**!", ephemeral=True)

# ==============================================================================
# DROPDOWN MENUS
# ==============================================================================

class SettingsSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        self.channel, self.bot, self.owner_id = channel, bot, owner_id
        super().__init__(
            placeholder="⚙️ Đổi cài đặt kênh...",
            row=0,
            options=[
                discord.SelectOption(label="Đổi tên kênh",            description="Đặt tên riêng cho phòng", emoji="✏️", value="rename"),
                discord.SelectOption(label="Đổi giới hạn người dùng", description="Số lượng người tối đa",   emoji="👥",    value="limit"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chỉ **chủ phòng** mới có thể thay đổi!", ephemeral=True)
        if not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return
        perm_key = "can_change_name" if self.values[0] == "rename" else "can_change_limit"
        has_perm = await _check_perm(pool, interaction.guild.id, interaction.user, perm_key) if pool else False
        if not has_perm:
            return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Role của bạn chưa có quyền này!", ephemeral=True)
        if self.values[0] == "rename":
            await interaction.response.send_modal(RenameModal(self.channel, self.bot, self.owner_id))
        else:
            await interaction.response.send_modal(LimitModal(self.channel, self.bot, self.owner_id))


class PermissionsSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        self.channel, self.bot, self.owner_id = channel, bot, owner_id
        super().__init__(
            placeholder="🔑 Đổi quyền kênh...",
            row=1,
            options=[
                discord.SelectOption(label="Khóa",     description="Khóa kênh",                            emoji="<:symbol_locked:1537566880066441296>", value="lock"),
                discord.SelectOption(label="Mở khóa",  description="Mở lại kênh",                          emoji="<:symbol_unlocked:1537566882180366466>", value="unlock"),
                discord.SelectOption(label="Ẩn",       description="Ẩn kênh khỏi danh sách",               emoji="👻", value="hide"),
                discord.SelectOption(label="Hiện",     description="Hiển thị lại kênh",                    emoji="👁️", value="show"),
                discord.SelectOption(label="Cho phép", description="Cấp quyền vào cho 1 người",            emoji="<:symbol_right:1536629912515903578>",    value="permit"),
                discord.SelectOption(label="Từ chối",  description="Đuổi và cấm người dùng vào kênh",      emoji="🥾", value="reject"),
                discord.SelectOption(label="Mời",      description="Cấp quyền mà không đuổi",              emoji="📨", value="invite"),
                discord.SelectOption(label="Chuyển",   description="Chuyển quyền chủ phòng",               emoji="👑", value="transfer"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "db_pool", None)
        val  = self.values[0]
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chỉ **chủ phòng** mới có thể đổi quyền!", ephemeral=True)
        if not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return

        if val in ("lock", "unlock"):
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_lock") if pool else False:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chưa có quyền khóa/mở phòng!", ephemeral=True)
            ow = self.channel.overwrites_for(interaction.guild.default_role)
            ow.connect = False if val == "lock" else None
            await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
            if pool:
                await _save_user_settings(pool, interaction.user.id, is_locked=(val == "lock"))
            msg = "<:symbol_locked:1537566880066441296> Phòng đã **khóa**!" if val == "lock" else "<:symbol_unlocked:1537566882180366466> Phòng đã **mở khóa**!"
            await interaction.response.send_message(msg, ephemeral=True)

        elif val in ("hide", "show"):
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_hide") if pool else False:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chưa có quyền ẩn/hiện phòng!", ephemeral=True)
            ow = self.channel.overwrites_for(interaction.guild.default_role)
            ow.view_channel = False if val == "hide" else None
            await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
            if pool:
                await _save_user_settings(pool, interaction.user.id, is_hidden=(val == "hide"))
            msg = "👻 Phòng đã **ẩn**!" if val == "hide" else "👁️ Phòng đã **hiện** lại!"
            await interaction.response.send_message(msg, ephemeral=True)

        elif val in ("permit", "invite"):
            await interaction.response.send_modal(PermitModal(self.channel))

        elif val == "reject":
            v = discord.ui.View(timeout=30); v.add_item(RejectSelect(self.channel))
            await interaction.response.send_message("Chọn người cần đuổi:", view=v, ephemeral=True)

        elif val == "transfer":
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_transfer") if pool else False:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chưa có quyền chuyển chủ phòng!", ephemeral=True)
            if await _check_perm(pool, interaction.guild.id, interaction.user, "is_persistent") if pool else False:
                return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Kênh cá nhân (Level 50+) không thể chuyển nhượng!", ephemeral=True)
            v = discord.ui.View(timeout=30); v.add_item(TransferSelect(self.channel, self.bot))
            await interaction.response.send_message("Chọn người nhận quyền chủ:", view=v, ephemeral=True)

# ==============================================================================
# MAIN VIEW
# ==============================================================================

class VoiceControlView(discord.ui.View):
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, bot: commands.Bot):
        super().__init__(timeout=None)
        self.channel, self.owner_id, self.bot = channel, owner_id, bot
        self.add_item(SettingsSelect(channel, bot, owner_id))
        self.add_item(PermissionsSelect(channel, bot, owner_id))

    @discord.ui.button(label="Nhận quyền chủ phòng", style=discord.ButtonStyle.primary,
                       custom_id="vm_claim", row=2)
    async def btn_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        pool = getattr(self.bot, "db_pool", None)
        if not pool or not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Lỗi hệ thống!", ephemeral=True)

        row = await _get_active_channel(pool, self.channel.id)
        if not row:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Không tìm thấy thông tin phòng!", ephemeral=True)

        claimer = interaction.user
        current_owner_id = row["owner_id"]

        if claimer.id == current_owner_id:
            return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Bạn đang là chủ phòng rồi!", ephemeral=True)
        if claimer not in self.channel.members:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Bạn phải ở trong phòng để nhận quyền!", ephemeral=True)
            
        old_owner = self.channel.guild.get_member(current_owner_id)
        if old_owner:
            if old_owner in self.channel.members:
                return await interaction.response.send_message(
                    f"<:symbol_ban:1537546960003801319> **{old_owner.display_name}** vẫn trong phòng! Không thể Claim.", ephemeral=True
                )
            if await _check_perm(pool, interaction.guild.id, old_owner, "is_persistent"):
                return await interaction.response.send_message(
                    "<:symbol_ban:1537546960003801319> Đây là Kênh Cá Nhân của người khác. Không thể Claim!", ephemeral=True
                )

        # Apply claimer config
        cfg     = await _get_user_settings(pool, claimer.id)
        n_limit = cfg.get("user_limit", 0) or 0
        n_name  = cfg.get("channel_name") or f"{claimer.display_name}'s Room"
        n_lock  = cfg.get("is_locked", False)
        n_hide  = cfg.get("is_hidden", False)

        real_count = len([m for m in self.channel.members if not m.bot])
        if 0 < n_limit < real_count:
            n_limit = real_count

        try:
            await self.channel.edit(name=n_name, user_limit=n_limit)
        except discord.HTTPException:
            try:
                await self.channel.edit(user_limit=n_limit)
            except Exception:
                pass

        ow = self.channel.overwrites_for(interaction.guild.default_role)
        ow.connect      = False if n_lock else None
        ow.view_channel = False if n_hide else None
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
        
        # Apply native overrides if claimer has them
        has_priority = await _check_perm(pool, interaction.guild.id, claimer, "priority_speaker")
        has_move = await _check_perm(pool, interaction.guild.id, claimer, "move_members")
        has_status = await _check_perm(pool, interaction.guild.id, claimer, "set_status")

        if has_priority or has_move:
            claimer_ow = self.channel.overwrites_for(claimer)
            if has_priority: claimer_ow.priority_speaker = True
            if has_move: claimer_ow.move_members = True
            await self.channel.set_permissions(claimer, overwrite=claimer_ow)

        await pool.execute("UPDATE active_voice_channels SET owner_id=$1 WHERE channel_id=$2",
                           claimer.id, self.channel.id)

        embed = discord.Embed(
            title="👑 Quyền chủ phòng đã được chuyển!",
            description=f"**{claimer.display_name}** đã nhận quyền.",
            color=0xF1C40F
        )
        embed.set_footer(text="Cấu hình lấy từ hồ sơ cá nhân của chủ mới.")
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Xóa Kênh", style=discord.ButtonStyle.danger, custom_id="vm_delete", row=2)
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Chỉ **chủ phòng** mới có quyền xóa kênh thủ công!", ephemeral=True)
        
        await interaction.response.send_message("<:symbol_right:1536629912515903578> Đang xóa kênh...", ephemeral=True)
        try:
            await self.channel.delete(reason="Chủ phòng tự xóa")
            if pool:
                await pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", self.channel.id)
        except discord.NotFound:
            pass

# ==============================================================================
# EMBED
# ==============================================================================

def _build_control_embed(channel: discord.VoiceChannel, owner: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="⚙️ Chào mừng đến kênh thoại tạm thời của bạn!",
        description=(
            "Điều khiển kênh bằng **menu bên dưới**.\n"
            "• **Đổi cài đặt**: Đổi tên & giới hạn người.\n"
            "• **Đổi quyền**: Khóa, ẩn, cho phép & đuổi người.\n"
            "• **Nhận quyền**: Cho phép người khác lấy phòng khi bạn rời đi.\n"
            "• **Xóa Kênh**: Chủ phòng có thể chủ động xóa kênh.\n\n"
            "Kênh sẽ tự xóa khi không còn ai (Trừ kênh cá nhân Persistent)."
        ),
        color=0x5865F2,
    )
    embed.set_author(name=f"Chủ phòng: {owner.display_name}", icon_url=owner.display_avatar.url)
    embed.set_footer(text=f"Kênh: {channel.name} | ID: {channel.id}")
    return embed

# ==============================================================================
# MAIN COG
# ==============================================================================

class VoiceManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self):
        pass


    @property
    def pool(self):
        return getattr(self.bot, "db_pool", None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not self.pool:
            return
        guild = member.guild

        # JOIN
        if after.channel is not None:
            setup  = await _get_setup(self.pool, guild.id)
            jtc_id = JOIN_TO_CREATE_CHANNEL_ID if JOIN_TO_CREATE_CHANNEL_ID != 0 else (setup["join_to_create_channel_id"] if setup else 0)
            
            if jtc_id and after.channel.id == jtc_id:
                # KIỂM TRA: User đã có kênh cá nhân hay chưa (Chống spam)
                existing = await self.pool.fetchrow("SELECT channel_id FROM active_voice_channels WHERE owner_id=$1", member.id)
                if existing:
                    old_channel = guild.get_channel(existing["channel_id"])
                    if isinstance(old_channel, discord.VoiceChannel):
                        # Kéo vào kênh cũ
                        try:
                            await member.move_to(old_channel, reason="VoiceMaster: Move to existing persistent channel")
                            return
                        except discord.HTTPException:
                            pass
                    else:
                        # Kênh trên Discord đã mất -> Xóa DB
                        await self.pool.execute("DELETE FROM active_voice_channels WHERE owner_id=$1", member.id)
                
                cat_id   = VOICE_CATEGORY_ID if VOICE_CATEGORY_ID != 0 else (setup["category_id"] if setup else None)
                category = guild.get_channel(cat_id) if cat_id else None
                settings = await _get_user_settings(self.pool, member.id)
                ch_name  = settings.get("channel_name") or f"{member.display_name}'s Room"
                ch_limit = settings.get("user_limit", 0) or 0
                is_lock  = settings.get("is_locked", False)
                is_hide  = settings.get("is_hidden", False)
                
                try:
                    kw: dict = {"name": ch_name, "category": category, "reason": f"VoiceMaster: tạo cho {member}"}
                    if ch_limit > 0:
                        kw["user_limit"] = ch_limit
                    if isinstance(category, discord.CategoryChannel) and category.voice_channels:
                        kw["position"] = max(vc.position for vc in category.voice_channels) + 1
                        
                    new_ch = await guild.create_voice_channel(**kw)
                    
                    # Quyền khóa/ẩn theo settings
                    if is_lock or is_hide:
                        ow = new_ch.overwrites_for(guild.default_role)
                        if is_lock: ow.connect      = False
                        if is_hide: ow.view_channel = False
                        await new_ch.set_permissions(guild.default_role, overwrite=ow)
                        
                    # Quyền native (Discord features)
                    has_priority = await _check_perm(self.pool, guild.id, member, "priority_speaker")
                    has_move = await _check_perm(self.pool, guild.id, member, "move_members")
                    has_status = await _check_perm(self.pool, guild.id, member, "set_status")
                    
                    if has_priority or has_move:
                        owner_ow = new_ch.overwrites_for(member)
                        if has_priority: owner_ow.priority_speaker = True
                        if has_move: owner_ow.move_members = True
                        await new_ch.set_permissions(member, overwrite=owner_ow)

                    await member.move_to(new_ch)
                    await self.pool.execute("""
                        INSERT INTO active_voice_channels (channel_id, guild_id, owner_id)
                        VALUES ($1,$2,$3) ON CONFLICT (channel_id) DO NOTHING
                    """, new_ch.id, guild.id, member.id)
                    
                    try:
                        await new_ch.send(embed=_build_control_embed(new_ch, member),
                                          view=VoiceControlView(new_ch, member.id, self.bot))
                    except discord.Forbidden:
                        pass
                        
                    log.info(f"VM: Tạo kênh '{ch_name}' cho {member}")
                except discord.Forbidden:
                    log.error("VM: Thiếu quyền tạo kênh!")
                except Exception as e:
                    log.error(f"VM: Lỗi tạo kênh: {e}", exc_info=True)

        # LEAVE
        if before.channel is not None:
            row = await _get_active_channel(self.pool, before.channel.id)
            if row:
                ch = guild.get_channel(before.channel.id)
                if ch and isinstance(ch, discord.VoiceChannel):
                    if not [m for m in ch.members if not m.bot]:
                        # Check persistent channel (Level 50+)
                        owner_id = row["owner_id"]
                        owner_member = guild.get_member(owner_id)
                        is_persistent = False
                        if owner_member:
                            is_persistent = await _check_perm(self.pool, guild.id, owner_member, "is_persistent")
                            
                        
                        if is_persistent:
                            is_booster = False
                            if owner_member:
                                booster_roles = STATIC_VOICE_PERMS.get("booster", {}).get("roles", [])
                                is_booster = any(r.id in booster_roles for r in owner_member.roles)
                                
                            now_hcmc = datetime.now(timezone(timedelta(hours=7)))
                            created_at = row.get("created_at")
                            is_old_month = False
                            if created_at:
                                created_hcmc = created_at.astimezone(timezone(timedelta(hours=7)))
                                if created_hcmc.year < now_hcmc.year or created_hcmc.month < now_hcmc.month:
                                    is_old_month = True
                                    
                            if is_old_month and not is_booster:
                                is_persistent = False
                                
                        if is_persistent:
                            log.info(f"VM: Phòng '{ch.name}' là Kênh Cá Nhân, bỏ qua auto-delete.")
                        else:
                            try:
                                await ch.delete(reason="VM: Phòng trống")
                                await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", ch.id)
                                log.info(f"VM: Xóa phòng '{ch.name}' (ID {ch.id})")
                            except discord.NotFound:
                                await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", before.channel.id)
                            except discord.Forbidden:
                                pass
                            except Exception:
                                pass
                else:
                    await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", before.channel.id)

    # ── ADMIN COMMANDS ───────────────────────────────────────────────────────

    @commands.group(name="voicesetup", aliases=["vs"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup(self, ctx: commands.Context):
        if not ctx.guild: return
        p = ctx.prefix
        embed = discord.Embed(title="VoiceMaster Setup", color=0x5865F2, description=(
            f"`{p}voicesetup init <#kênh_join> <#danh_mục>`\n"
            f"`{p}voicesetup role add <@Role> <lock> <hide> <limit> <name> [priority]`\n"
            f"`{p}voicesetup role view`\n"
            f"`{p}voicesetup status`"
        ))
        await ctx.send(embed=embed)

    @voicesetup.command(name="init")
    @commands.has_permissions(administrator=True)
    async def voicesetup_init(self, ctx: commands.Context, join_channel: discord.VoiceChannel, category: discord.CategoryChannel):
        if not ctx.guild: return
        if not self.pool: return await ctx.send("Lỗi DB!")
        await self.pool.execute("""
            INSERT INTO voice_setups (guild_id, join_to_create_channel_id, category_id) VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE
                SET join_to_create_channel_id=EXCLUDED.join_to_create_channel_id, category_id=EXCLUDED.category_id
        """, ctx.guild.id, join_channel.id, category.id)
        embed = discord.Embed(title="Đã cấu hình VoiceMaster!", color=discord.Color.green())
        embed.add_field(name="Kênh JTC", value=join_channel.mention)
        embed.add_field(name="Danh mục", value=category.mention)
        await ctx.send(embed=embed)

    @voicesetup.group(name="role", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup_role(self, ctx: commands.Context):
        await ctx.send(f"Dùng `{ctx.prefix}voicesetup role add` hoặc `{ctx.prefix}voicesetup role view`.")

    @voicesetup_role.command(name="add")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_add(self, ctx: commands.Context, role: discord.Role,
                                  lock: bool=False, hide: bool=False, limit: bool=False,
                                  name: bool=False, transfer: bool=False, priority: int=0):
        if not ctx.guild: return
        if not self.pool: return await ctx.send("Lỗi DB!")
        await self.pool.execute("""
            INSERT INTO voice_role_perms (guild_id,role_id,can_lock,can_hide,can_change_limit,can_change_name,can_transfer,priority)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (guild_id,role_id) DO UPDATE
                SET can_lock=$3,can_hide=$4,can_change_limit=$5,can_change_name=$6,can_transfer=$7,priority=$8
        """, ctx.guild.id, role.id, lock, hide, limit, name, transfer, priority)
        e = discord.Embed(title=f"Cấp quyền cho {role.name}", color=role.color or discord.Color.blurple())
        for lbl, val in [("Khóa",lock),("Ẩn",hide),("Giới hạn",limit),("Tên",name),("Chuyển",transfer)]:
            e.add_field(name=lbl, value="OK" if val else "X", inline=True)
        e.add_field(name="Ưu tiên", value=str(priority), inline=True)
        await ctx.send(embed=e)

    @voicesetup_role.command(name="view")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_view(self, ctx: commands.Context):
        if not ctx.guild: return
        if not self.pool: return await ctx.send("Lỗi DB!")
        rows = await self.pool.fetch("SELECT * FROM voice_role_perms WHERE guild_id=$1 ORDER BY priority DESC", ctx.guild.id)
        if not rows: return await ctx.send("Chưa có role nào.")
        embed = discord.Embed(title="Bảng Phân Quyền VoiceMaster", color=0x5865F2)
        for row in rows:
            role  = ctx.guild.get_role(row["role_id"])
            rname = role.mention if role else f"<@&{row['role_id']}>"
            perms = (["Lock"] if row["can_lock"] else []) + (["Hide"] if row["can_hide"] else []) + \
                    (["Limit"] if row["can_change_limit"] else []) + (["Name"] if row["can_change_name"] else []) + \
                    (["Transfer"] if row["can_transfer"] else [])
            embed.add_field(name=f"{rname} (p:{row['priority']})", value=" ".join(perms) or "None", inline=False)
        await ctx.send(embed=embed)

    @voicesetup.command(name="status")
    @commands.has_permissions(administrator=True)
    async def voicesetup_status(self, ctx: commands.Context):
        if not ctx.guild: return
        if not self.pool: return await ctx.send("Lỗi DB!")
        setup = await _get_setup(self.pool, ctx.guild.id)
        if not setup: return await ctx.send(f"Chưa cấu hình. Dùng `{ctx.prefix}voicesetup init`.")
        jtc   = ctx.guild.get_channel(setup["join_to_create_channel_id"])
        cat   = ctx.guild.get_channel(setup["category_id"]) if setup["category_id"] else None
        count = await self.pool.fetchval("SELECT COUNT(*) FROM active_voice_channels WHERE guild_id=$1", ctx.guild.id)
        embed = discord.Embed(title="Trạng thái VoiceMaster", color=0x5865F2)
        embed.add_field(name="Kênh JTC",       value=jtc.mention if jtc else "X", inline=True)
        embed.add_field(name="Danh mục",       value=cat.mention if cat else "X", inline=True)
        embed.add_field(name="Phòng hoạt động",value=str(count or 0),             inline=True)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceManagerCog(bot))
