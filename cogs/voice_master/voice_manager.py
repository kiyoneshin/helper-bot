"""
voice_manager.py - VoiceMaster Nha Lam (Full Edition)
Gom day du: Dropdown UI, Persistent Settings, Claim logic, Permit/Reject
"""
from __future__ import annotations
import logging
import re
from typing import Optional
import asyncpg
import discord
from discord.ext import commands
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
    for gd in STATIC_VOICE_PERMS.values():
        if any(r in gd["roles"] for r in role_ids):
            if gd["perms"].get(perm, False):
                return True
    if not pool:
        return False
    rows = await pool.fetch(
        f"SELECT {perm} FROM voice_role_perms "
        f"WHERE guild_id=$1 AND role_id=ANY($2::bigint[]) ORDER BY priority DESC LIMIT 1",
        guild_id, role_ids
    )
    return bool(rows and rows[0][perm])

# ==============================================================================
# MODALS
# ==============================================================================

class RenameModal(discord.ui.Modal, title="Doi ten phong"):
    name_input = discord.ui.TextInput(label="Ten phong moi", placeholder="Vi du: Phong Chill", max_length=100)

    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        super().__init__()
        self.channel, self.bot, self.owner_id = channel, bot, owner_id

    async def on_submit(self, interaction: discord.Interaction):
        new_name = str(self.name_input).strip()
        if not new_name:
            return await interaction.response.send_message("Ten phong khong duoc de trong!", ephemeral=True)
        try:
            await self.channel.edit(name=new_name)
            pool = getattr(self.bot, "db_pool", None)
            if pool:
                await _save_user_settings(pool, self.owner_id, channel_name=new_name)
            await interaction.response.send_message(f"\u2705 Da doi ten phong: **{new_name}**", ephemeral=True)
        except discord.HTTPException as e:
            msg = "Rate Limit! Discord chi cho doi ten 2 lan/10 phut. Hay cho roi thu lai!" if e.status == 429 else str(e)
            await interaction.response.send_message(f"\u274c {msg}", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Gioi han nguoi dung"):
    limit_input = discord.ui.TextInput(label="So nguoi toi da (0=khong gioi han)", placeholder="Vi du: 5", min_length=1, max_length=2)

    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        super().__init__()
        self.channel, self.bot, self.owner_id = channel, bot, owner_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(str(self.limit_input))
            if not 0 <= limit <= 99:
                return await interaction.response.send_message("Gioi han phai tu 0 den 99!", ephemeral=True)
            await self.channel.edit(user_limit=limit)
            pool = getattr(self.bot, "db_pool", None)
            if pool:
                await _save_user_settings(pool, self.owner_id, user_limit=limit)
            label = "khong gioi han" if limit == 0 else f"**{limit}** nguoi"
            await interaction.response.send_message(f"\u2705 Da dat gioi han: {label}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Vui long nhap mot so hop le!", ephemeral=True)


class PermitModal(discord.ui.Modal, title="Cho phep nguoi dung"):
    user_input = discord.ui.TextInput(label="Nhap ID nguoi dung", placeholder="123456789012345678", max_length=20)

    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        raw   = str(self.user_input).strip()
        match = re.search(r"\d{17,20}", raw)
        if not match:
            return await interaction.response.send_message("Khong tim thay ID hop le!", ephemeral=True)
        if not isinstance(interaction.guild, discord.Guild):
            return
        target = interaction.guild.get_member(int(match.group()))
        if not target:
            return await interaction.response.send_message("Khong tim thay thanh vien trong server!", ephemeral=True)
        ow = self.channel.overwrites_for(target)
        ow.connect, ow.view_channel = True, True
        await self.channel.set_permissions(target, overwrite=ow)
        await interaction.response.send_message(f"\u2705 Da cap quyen vao phong cho **{target.display_name}**!", ephemeral=True)

# ==============================================================================
# USER SELECTS
# ==============================================================================

class RejectSelect(discord.ui.UserSelect):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(placeholder="Chon nguoi can duoi...", min_values=1, max_values=1)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.id == interaction.user.id or target.bot:
            return await interaction.response.send_message("Khong the chon nguoi nay!", ephemeral=True)
        if target in self.channel.members:
            await target.move_to(None)
        ow = self.channel.overwrites_for(target)
        ow.connect, ow.view_channel = False, False
        await self.channel.set_permissions(target, overwrite=ow)
        await interaction.response.send_message(f"\U0001f45e Da duoi **{target.display_name}** va cam vao lai!", ephemeral=True)


class TransferSelect(discord.ui.UserSelect):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot):
        super().__init__(placeholder="Chon nguoi nhan quyen chu...", min_values=1, max_values=1)
        self.channel, self.bot = channel, bot

    async def callback(self, interaction: discord.Interaction):
        new_owner = self.values[0]
        if new_owner.bot or new_owner.id == interaction.user.id:
            return await interaction.response.send_message("Khong the chon nguoi nay!", ephemeral=True)
        if new_owner not in self.channel.members:
            return await interaction.response.send_message("Nguoi nay khong o trong phong!", ephemeral=True)
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            await pool.execute("UPDATE active_voice_channels SET owner_id=$1 WHERE channel_id=$2",
                               new_owner.id, self.channel.id)
        await interaction.response.send_message(f"\U0001f451 Da chuyen quyen chu cho **{new_owner.display_name}**!", ephemeral=True)

# ==============================================================================
# DROPDOWN MENUS
# ==============================================================================

class SettingsSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        self.channel, self.bot, self.owner_id = channel, bot, owner_id
        super().__init__(
            placeholder="\u2699\ufe0f Doi cai dat kenh...",
            row=0,
            options=[
                discord.SelectOption(label="Doi ten kenh",            description="Dat ten rieng cho phong", emoji="\u270f\ufe0f", value="rename"),
                discord.SelectOption(label="Doi gioi han nguoi dung", description="So luong nguoi toi da",   emoji="\U0001f465",    value="limit"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                return await interaction.response.send_message("Chi **chu phong** moi co the thay doi!", ephemeral=True)
        if not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return
        perm_key = "can_change_name" if self.values[0] == "rename" else "can_change_limit"
        has_perm = await _check_perm(pool, interaction.guild.id, interaction.user, perm_key) if pool else False
        if not has_perm:
            return await interaction.response.send_message("\u274c Role cua ban chua co quyen nay! (Can Booster/VIP)", ephemeral=True)
        if self.values[0] == "rename":
            await interaction.response.send_modal(RenameModal(self.channel, self.bot, self.owner_id))
        else:
            await interaction.response.send_modal(LimitModal(self.channel, self.bot, self.owner_id))


class PermissionsSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot, owner_id: int):
        self.channel, self.bot, self.owner_id = channel, bot, owner_id
        super().__init__(
            placeholder="\U0001f511 Doi quyen kenh...",
            row=1,
            options=[
                discord.SelectOption(label="Khoa",     description="Khoa kenh",                            emoji="\U0001f512", value="lock"),
                discord.SelectOption(label="Mo khoa",  description="Mo lai kenh",                          emoji="\U0001f513", value="unlock"),
                discord.SelectOption(label="An",       description="An kenh khoi danh sach",               emoji="\U0001f47b", value="hide"),
                discord.SelectOption(label="Hien",     description="Hien thi lai kenh",                    emoji="\U0001f441\ufe0f", value="show"),
                discord.SelectOption(label="Cho phep", description="Cap quyen vao cho 1 nguoi",            emoji="\u2705",    value="permit"),
                discord.SelectOption(label="Tu choi",  description="Duoi va cam nguoi dung vao kenh",      emoji="\U0001f45e", value="reject"),
                discord.SelectOption(label="Moi",      description="Cap quyen ma khong duoi",              emoji="\U0001f4e8", value="invite"),
                discord.SelectOption(label="Chuyen",   description="Chuyen quyen chu phong",               emoji="\U0001f451", value="transfer"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "db_pool", None)
        val  = self.values[0]
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                return await interaction.response.send_message("Chi **chu phong** moi co the doi quyen!", ephemeral=True)
        if not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return

        if val in ("lock", "unlock"):
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_lock") if pool else False:
                return await interaction.response.send_message("\u274c Chua co quyen khoa/mo phong!", ephemeral=True)
            ow = self.channel.overwrites_for(interaction.guild.default_role)
            ow.connect = False if val == "lock" else None
            await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
            if pool:
                await _save_user_settings(pool, interaction.user.id, is_locked=(val == "lock"))
            msg = "\U0001f512 Phong da **khoa**!" if val == "lock" else "\U0001f513 Phong da **mo khoa**!"
            await interaction.response.send_message(msg, ephemeral=True)

        elif val in ("hide", "show"):
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_hide") if pool else False:
                return await interaction.response.send_message("\u274c Chua co quyen an/hien phong!", ephemeral=True)
            ow = self.channel.overwrites_for(interaction.guild.default_role)
            ow.view_channel = False if val == "hide" else None
            await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
            if pool:
                await _save_user_settings(pool, interaction.user.id, is_hidden=(val == "hide"))
            msg = "\U0001f47b Phong da **an**!" if val == "hide" else "\U0001f441\ufe0f Phong da **hien** lai!"
            await interaction.response.send_message(msg, ephemeral=True)

        elif val in ("permit", "invite"):
            await interaction.response.send_modal(PermitModal(self.channel))

        elif val == "reject":
            v = discord.ui.View(timeout=30); v.add_item(RejectSelect(self.channel))
            await interaction.response.send_message("Chon nguoi can duoi:", view=v, ephemeral=True)

        elif val == "transfer":
            if not await _check_perm(pool, interaction.guild.id, interaction.user, "can_transfer") if pool else False:
                return await interaction.response.send_message("\u274c Chua co quyen chuyen chu phong!", ephemeral=True)
            v = discord.ui.View(timeout=30); v.add_item(TransferSelect(self.channel, self.bot))
            await interaction.response.send_message("Chon nguoi nhan quyen chu:", view=v, ephemeral=True)

# ==============================================================================
# MAIN VIEW
# ==============================================================================

class VoiceControlView(discord.ui.View):
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, bot: commands.Bot):
        super().__init__(timeout=None)
        self.channel, self.owner_id, self.bot = channel, owner_id, bot
        self.add_item(SettingsSelect(channel, bot, owner_id))
        self.add_item(PermissionsSelect(channel, bot, owner_id))

    @discord.ui.button(label="\U0001f451 Nhan quyen chu phong", style=discord.ButtonStyle.primary,
                       custom_id="vm_claim", row=2)
    async def btn_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        pool = getattr(self.bot, "db_pool", None)
        if not pool or not isinstance(interaction.guild, discord.Guild) or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Loi he thong!", ephemeral=True)

        row = await _get_active_channel(pool, self.channel.id)
        if not row:
            return await interaction.response.send_message("Khong tim thay thong tin phong!", ephemeral=True)

        claimer = interaction.user
        current_owner_id = row["owner_id"]

        if claimer.id == current_owner_id:
            return await interaction.response.send_message("Ban dang la chu phong roi!", ephemeral=True)
        if claimer not in self.channel.members:
            return await interaction.response.send_message("Ban phai o trong phong de nhan quyen!", ephemeral=True)
        old_owner = self.channel.guild.get_member(current_owner_id)
        if old_owner and old_owner in self.channel.members:
            return await interaction.response.send_message(
                f"**{old_owner.display_name}** van trong phong! Khong the Claim khi chu phong con day.", ephemeral=True
            )

        # Lay config cua claimer
        cfg     = await _get_user_settings(pool, claimer.id)
        n_limit = cfg.get("user_limit", 0) or 0
        n_name  = cfg.get("channel_name") or f"{claimer.display_name}s Room"
        n_lock  = cfg.get("is_locked", False)
        n_hide  = cfg.get("is_hidden", False)

        # Edge case: config cua chu moi < so nguoi hien tai -> giu nguyen so nguoi hien tai
        real_count = len([m for m in self.channel.members if not m.bot])
        if 0 < n_limit < real_count:
            n_limit = real_count

        # Ap dung thay doi
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
        await pool.execute("UPDATE active_voice_channels SET owner_id=$1 WHERE channel_id=$2",
                           claimer.id, self.channel.id)

        embed = discord.Embed(
            title="\U0001f451 Quyen chu phong da duoc chuyen!",
            description=f"**{claimer.display_name}** da nhan quyen chu phong.",
            color=0xF1C40F
        )
        embed.add_field(name="Ten phong", value=n_name, inline=True)
        embed.add_field(name="Trang thai", value="Khoa" if n_lock else "Mo", inline=True)
        embed.add_field(name="Hien thi",   value="An"   if n_hide else "Hien", inline=True)
        embed.add_field(name="Gioi han",   value=f"{n_limit} nguoi" if n_limit else "Khong gioi han", inline=True)
        embed.set_footer(text="Cau hinh lay tu ho so ca nhan cua chu moi.")
        await interaction.response.send_message(embed=embed)

# ==============================================================================
# EMBED
# ==============================================================================

def _build_control_embed(channel: discord.VoiceChannel, owner: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="\u2699\ufe0f Chao mung den kenh thoai tam thoi cua ban!",
        description=(
            "Dieu khien kenh bang **menu ben duoi**.\n"
            "- **Doi cai dat**: Doi ten & gioi han nguoi.\n"
            "- **Doi quyen**: Khoa, an, cho phep & duoi nguoi.\n"
            "- Nut **Nhan quyen chu phong** khi chu cu da roi di.\n\n"
            "Kenh se tu xoa khi khong con ai ben trong."
        ),
        color=0x5865F2,
    )
    embed.set_author(name=f"Chu phong: {owner.display_name}", icon_url=owner.display_avatar.url)
    embed.set_footer(text=f"Kenh: {channel.name} | ID: {channel.id}")
    return embed

# ==============================================================================
# MAIN COG
# ==============================================================================

class VoiceManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
                cat_id   = VOICE_CATEGORY_ID if VOICE_CATEGORY_ID != 0 else (setup["category_id"] if setup else None)
                category = guild.get_channel(cat_id) if cat_id else None
                settings = await _get_user_settings(self.pool, member.id)
                ch_name  = settings.get("channel_name") or f"{member.display_name}s Room"
                ch_limit = settings.get("user_limit", 0) or 0
                is_lock  = settings.get("is_locked", False)
                is_hide  = settings.get("is_hidden", False)
                try:
                    kw: dict = {"name": ch_name, "category": category, "reason": f"VoiceMaster: tao cho {member}"}
                    if ch_limit > 0:
                        kw["user_limit"] = ch_limit
                    if category and category.voice_channels:
                        kw["position"] = max(vc.position for vc in category.voice_channels) + 1
                    new_ch = await guild.create_voice_channel(**kw)
                    if is_lock or is_hide:
                        ow = new_ch.overwrites_for(guild.default_role)
                        if is_lock: ow.connect      = False
                        if is_hide: ow.view_channel = False
                        await new_ch.set_permissions(guild.default_role, overwrite=ow)
                    await member.move_to(new_ch)
                    await self.pool.execute("""
                        INSERT INTO active_voice_channels (channel_id, guild_id, owner_id)
                        VALUES ($1,$2,$3) ON CONFLICT (channel_id) DO NOTHING
                    """, new_ch.id, guild.id, member.id)
                    try:
                        await new_ch.send(embed=_build_control_embed(new_ch, member),
                                          view=VoiceControlView(new_ch, member.id, self.bot))
                    except discord.Forbidden:
                        log.warning(f"VM: Thieu quyen gui msg vao {new_ch.id}")
                    log.info(f"VM: Tao kenh \'{ch_name}\' cho {member}")
                except discord.Forbidden:
                    log.error("VM: Thieu quyen tao kenh!")
                except Exception as e:
                    log.error(f"VM: Loi tao kenh: {e}", exc_info=True)

        # LEAVE
        if before.channel is not None:
            row = await _get_active_channel(self.pool, before.channel.id)
            if row:
                ch = guild.get_channel(before.channel.id)
                if ch and isinstance(ch, discord.VoiceChannel):
                    if not [m for m in ch.members if not m.bot]:
                        try:
                            await ch.delete(reason="VM: Phong trong")
                            await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", ch.id)
                            log.info(f"VM: Xoa phong \'{ch.name}\' (ID {ch.id})")
                        except discord.NotFound:
                            await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", before.channel.id)
                        except discord.Forbidden:
                            log.error(f"VM: Thieu quyen xoa kenh {ch.id}")
                        except Exception as e:
                            log.error(f"VM: Loi xoa kenh: {e}", exc_info=True)
                else:
                    await self.pool.execute("DELETE FROM active_voice_channels WHERE channel_id=$1", before.channel.id)

    # ── ADMIN COMMANDS ───────────────────────────────────────────────────────

    @commands.group(name="voicesetup", aliases=["vs"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup(self, ctx: commands.Context):
        p = ctx.prefix
        embed = discord.Embed(title="VoiceMaster Setup", color=0x5865F2, description=(
            f"`{p}voicesetup init <#kenh_join> <#danh_muc>`\n"
            f"`{p}voicesetup role add <@Role> <lock> <hide> <limit> <name> [priority]`\n"
            f"`{p}voicesetup role view`\n"
            f"`{p}voicesetup status`"
        ))
        await ctx.send(embed=embed)

    @voicesetup.command(name="init")
    @commands.has_permissions(administrator=True)
    async def voicesetup_init(self, ctx: commands.Context, join_channel: discord.VoiceChannel, category: discord.CategoryChannel):
        if not self.pool: return await ctx.send("Loi DB!")
        await self.pool.execute("""
            INSERT INTO voice_setups (guild_id, join_to_create_channel_id, category_id) VALUES ($1,$2,$3)
            ON CONFLICT (guild_id) DO UPDATE
                SET join_to_create_channel_id=EXCLUDED.join_to_create_channel_id, category_id=EXCLUDED.category_id
        """, ctx.guild.id, join_channel.id, category.id)
        embed = discord.Embed(title="Da cau hinh VoiceMaster!", color=discord.Color.green())
        embed.add_field(name="Kenh JTC", value=join_channel.mention)
        embed.add_field(name="Danh muc", value=category.mention)
        await ctx.send(embed=embed)

    @voicesetup.group(name="role", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup_role(self, ctx: commands.Context):
        await ctx.send(f"Dung `{ctx.prefix}voicesetup role add` hoac `{ctx.prefix}voicesetup role view`.")

    @voicesetup_role.command(name="add")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_add(self, ctx: commands.Context, role: discord.Role,
                                  lock: bool=False, hide: bool=False, limit: bool=False,
                                  name: bool=False, transfer: bool=False, priority: int=0):
        if not self.pool: return await ctx.send("Loi DB!")
        await self.pool.execute("""
            INSERT INTO voice_role_perms (guild_id,role_id,can_lock,can_hide,can_change_limit,can_change_name,can_transfer,priority)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (guild_id,role_id) DO UPDATE
                SET can_lock=$3,can_hide=$4,can_change_limit=$5,can_change_name=$6,can_transfer=$7,priority=$8
        """, ctx.guild.id, role.id, lock, hide, limit, name, transfer, priority)
        e = discord.Embed(title=f"Cap quyen cho {role.name}", color=role.color or discord.Color.blurple())
        for lbl, val in [("Khoa",lock),("An",hide),("Gioi han",limit),("Ten",name),("Chuyen",transfer)]:
            e.add_field(name=lbl, value="OK" if val else "X", inline=True)
        e.add_field(name="Uu tien", value=str(priority), inline=True)
        await ctx.send(embed=e)

    @voicesetup_role.command(name="view")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_view(self, ctx: commands.Context):
        if not self.pool: return await ctx.send("Loi DB!")
        rows = await self.pool.fetch("SELECT * FROM voice_role_perms WHERE guild_id=$1 ORDER BY priority DESC", ctx.guild.id)
        if not rows: return await ctx.send("Chua co role nao.")
        embed = discord.Embed(title="Bang Phan Quyen VoiceMaster", color=0x5865F2)
        for row in rows:
            role  = ctx.guild.get_role(row["role_id"])
            rname = role.mention if role else f"<@&{row['role_id']}>"
            perms = (["Lock"] if row["can_lock"] else []) + (["Hide"] if row["can_hide"] else []) +                     (["Limit"] if row["can_change_limit"] else []) + (["Name"] if row["can_change_name"] else []) +                     (["Transfer"] if row["can_transfer"] else [])
            embed.add_field(name=f"{rname} (p:{row['priority']})", value=" ".join(perms) or "None", inline=False)
        await ctx.send(embed=embed)

    @voicesetup.command(name="status")
    @commands.has_permissions(administrator=True)
    async def voicesetup_status(self, ctx: commands.Context):
        if not self.pool: return await ctx.send("Loi DB!")
        setup = await _get_setup(self.pool, ctx.guild.id)
        if not setup: return await ctx.send(f"Chua cau hinh. Dung `{ctx.prefix}voicesetup init`.")
        jtc   = ctx.guild.get_channel(setup["join_to_create_channel_id"])
        cat   = ctx.guild.get_channel(setup["category_id"]) if setup["category_id"] else None
        count = await self.pool.fetchval("SELECT COUNT(*) FROM active_voice_channels WHERE guild_id=$1", ctx.guild.id)
        embed = discord.Embed(title="Trang thai VoiceMaster", color=0x5865F2)
        embed.add_field(name="Kenh JTC",       value=jtc.mention if jtc else "X", inline=True)
        embed.add_field(name="Danh muc",       value=cat.mention if cat else "X", inline=True)
        embed.add_field(name="Phong hoat dong",value=str(count or 0),             inline=True)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceManagerCog(bot))
