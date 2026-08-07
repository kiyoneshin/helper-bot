"""
voice_manager.py — Hệ Thống VoiceMaster Nhà Làm
=================================================
Giai đoạn 1 & 2:
  - 3 bảng DB: voice_setups, voice_role_perms, active_voice_channels
  - Event on_voice_state_update: Tạo/Xóa kênh tự động
  - UI: Embed + Nút bấm gửi vào text-in-voice khi phòng được tạo

Tính năng UI (Giai đoạn 4):
  🔒 Lock / Unlock  —  👻 Hide / Show  —  👥 Limit (Modal)  —  ✏️ Rename (Modal)  —  👑 Transfer
"""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg
import discord
from discord.ext import commands

log = logging.getLogger("VoiceMaster")


# =============================================================================
# HELPERS: Lấy cấu hình & kiểm tra quyền
# =============================================================================

async def _get_setup(pool: asyncpg.Pool, guild_id: int):
    return await pool.fetchrow(
        "SELECT * FROM voice_setups WHERE guild_id = $1", guild_id
    )

async def _get_active_channel(pool: asyncpg.Pool, channel_id: int):
    return await pool.fetchrow(
        "SELECT * FROM active_voice_channels WHERE channel_id = $1", channel_id
    )

async def _check_perm(pool: asyncpg.Pool, guild_id: int, member: discord.Member, perm: str) -> bool:
    """
    Kiểm tra xem member có quyền 'perm' không dựa vào bảng voice_role_perms.
    perm: 'can_lock', 'can_hide', 'can_change_limit', 'can_change_name', 'can_transfer'
    """
    role_ids = [r.id for r in member.roles]
    if not role_ids:
        return False
    rows = await pool.fetch(
        f"SELECT {perm} FROM voice_role_perms "
        f"WHERE guild_id = $1 AND role_id = ANY($2::bigint[]) "
        f"ORDER BY priority DESC LIMIT 1",
        guild_id, role_ids
    )
    if rows and rows[0][perm]:
        return True
    return False


# =============================================================================
# UI: Modal nhập giới hạn người dùng
# =============================================================================

class LimitModal(discord.ui.Modal, title="Giới hạn người dùng"):
    limit_input = discord.ui.TextInput(
        label="Số người tối đa (0 = không giới hạn)",
        placeholder="Ví dụ: 5",
        min_length=1,
        max_length=3,
    )

    def __init__(self, channel: discord.VoiceChannel, bot: commands.Bot):
        super().__init__()
        self.channel = channel
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(str(self.limit_input))
            if limit < 0 or limit > 99:
                await interaction.response.send_message("❌ Giới hạn phải từ 0 đến 99!", ephemeral=True)
                return
            await self.channel.edit(user_limit=limit)
            label = "không giới hạn" if limit == 0 else f"**{limit}** người"
            await interaction.response.send_message(f"✅ Đã đặt giới hạn phòng: {label}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Vui lòng nhập một số hợp lệ!", ephemeral=True)


# =============================================================================
# UI: Modal đổi tên phòng
# =============================================================================

class RenameModal(discord.ui.Modal, title="Đổi tên phòng"):
    name_input = discord.ui.TextInput(
        label="Tên phòng mới",
        placeholder="Ví dụ: Phòng Chill 🎵",
        max_length=100,
    )

    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        new_name = str(self.name_input).strip()
        if not new_name:
            await interaction.response.send_message("❌ Tên phòng không được để trống!", ephemeral=True)
            return
        await self.channel.edit(name=new_name)
        await interaction.response.send_message(f"✅ Đã đổi tên phòng thành: **{new_name}**", ephemeral=True)


# =============================================================================
# UI: Select menu chuyển chủ
# =============================================================================

class TransferSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, members: list, bot: commands.Bot):
        self.channel = channel
        self.bot = bot
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), emoji="👑")
            for m in members[:25]
        ]
        super().__init__(placeholder="Chọn thành viên...", options=options)

    async def callback(self, interaction: discord.Interaction):
        new_owner_id = int(self.values[0])
        pool = getattr(self.bot, "db_pool", None)
        if pool:
            await pool.execute(
                "UPDATE active_voice_channels SET owner_id = $1 WHERE channel_id = $2",
                new_owner_id, self.channel.id
            )
        new_owner = self.channel.guild.get_member(new_owner_id)
        name = new_owner.display_name if new_owner else f"<@{new_owner_id}>"
        await interaction.response.send_message(f"👑 Đã chuyển quyền chủ phòng cho **{name}**!", ephemeral=True)


# =============================================================================
# UI: View nút bấm điều khiển phòng
# =============================================================================

class VoiceControlView(discord.ui.View):
    """View điều khiển phòng voice — gửi vào text-in-voice khi phòng mới được tạo."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int, bot: commands.Bot):
        super().__init__(timeout=None)  # Persistent: không tự hủy
        self.channel = channel
        self.owner_id = owner_id
        self.bot = bot

    async def _get_pool(self):
        return getattr(self.bot, "db_pool", None)

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        pool = await self._get_pool()
        if pool:
            row = await _get_active_channel(pool, self.channel.id)
            if row and interaction.user.id != row["owner_id"]:
                await interaction.response.send_message(
                    "❌ Chỉ **chủ phòng** mới có thể dùng nút này!", ephemeral=True
                )
                return False
        return True

    async def _check_action_perm(self, interaction: discord.Interaction, perm: str) -> bool:
        pool = await self._get_pool()
        if not pool:
            return True
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return False
        has_perm = await _check_perm(pool, interaction.guild.id, interaction.user, perm)
        if not has_perm:
            await interaction.response.send_message(
                "❌ Role của bạn không có quyền thực hiện hành động này!\n"
                "Hãy đạt đủ điều kiện (Booster, VIP, Level...) để mở khóa tính năng này.",
                ephemeral=True
            )
        return has_perm

    @discord.ui.button(label="🔒 Khóa", style=discord.ButtonStyle.danger, custom_id="vm_lock", row=0)
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_lock"):
            return
        if not isinstance(interaction.guild, discord.Guild):
            return
        overwrite = self.channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = False
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Phòng đã bị **khóa**! Không ai vào thêm được nữa.", ephemeral=True)

    @discord.ui.button(label="🔓 Mở khóa", style=discord.ButtonStyle.success, custom_id="vm_unlock", row=0)
    async def btn_unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_lock"):
            return
        if not isinstance(interaction.guild, discord.Guild):
            return
        overwrite = self.channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = None
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Phòng đã được **mở khóa**!", ephemeral=True)

    @discord.ui.button(label="👻 Ẩn", style=discord.ButtonStyle.secondary, custom_id="vm_hide", row=0)
    async def btn_hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_hide"):
            return
        if not isinstance(interaction.guild, discord.Guild):
            return
        overwrite = self.channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👻 Phòng đã bị **ẩn**! Chỉ thành viên bên trong mới thấy.", ephemeral=True)

    @discord.ui.button(label="👁️ Hiện", style=discord.ButtonStyle.secondary, custom_id="vm_show", row=0)
    async def btn_show(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_hide"):
            return
        if not isinstance(interaction.guild, discord.Guild):
            return
        overwrite = self.channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = None
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👁️ Phòng đã được **hiển thị** lại!", ephemeral=True)

    @discord.ui.button(label="👥 Giới hạn", style=discord.ButtonStyle.primary, custom_id="vm_limit", row=1)
    async def btn_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_change_limit"):
            return
        await interaction.response.send_modal(LimitModal(self.channel, self.bot))

    @discord.ui.button(label="✏️ Đổi tên", style=discord.ButtonStyle.primary, custom_id="vm_rename", row=1)
    async def btn_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_change_name"):
            return
        await interaction.response.send_modal(RenameModal(self.channel))

    @discord.ui.button(label="👑 Chuyển chủ", style=discord.ButtonStyle.secondary, custom_id="vm_transfer", row=1)
    async def btn_transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        if not await self._check_action_perm(interaction, "can_transfer"):
            return
        members = [m for m in self.channel.members if m.id != interaction.user.id and not m.bot]
        if not members:
            await interaction.response.send_message(
                "❌ Không có ai khác trong phòng để chuyển quyền chủ!", ephemeral=True
            )
            return
        select = TransferSelect(self.channel, members, self.bot)
        view = discord.ui.View(timeout=30)
        view.add_item(select)
        await interaction.response.send_message("👑 Chọn người nhận quyền chủ phòng:", view=view, ephemeral=True)


# =============================================================================
# HELPERS: Build Embed điều khiển
# =============================================================================

def _build_control_embed(channel: discord.VoiceChannel, owner: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="⚙️ Chào mừng đến kênh thoại tạm thời của bạn!",
        description=(
            "Điều khiển kênh bằng các nút bên dưới.\n"
            "Kênh sẽ tự động **xóa** khi không còn ai bên trong."
        ),
        color=0x5865F2,
    )
    embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
    embed.add_field(name="🔒 Khóa / Mở khóa", value="Ngăn người lạ tham gia phòng.", inline=True)
    embed.add_field(name="👻 Ẩn / Hiện",       value="Ẩn phòng khỏi danh sách kênh.", inline=True)
    embed.add_field(name="👥 Giới hạn",         value="Đặt số người tối đa.",           inline=True)
    embed.add_field(name="✏️ Đổi tên",          value="Đổi tên phòng tùy ý.",           inline=True)
    embed.add_field(name="👑 Chuyển chủ",       value="Nhường quyền cho người khác.",   inline=True)
    embed.set_footer(text=f"Chủ phòng: {owner.display_name}  •  ID kênh: {channel.id}")
    return embed


# =============================================================================
# COG CHÍNH
# =============================================================================

class VoiceManagerCog(commands.Cog):
    """Cog quản lý hệ thống phòng voice tự tạo (VoiceMaster nhà làm)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def pool(self):
        return getattr(self.bot, "db_pool", None)

    # ── EVENT CORE ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if not self.pool:
            return

        guild = member.guild

        # ── XỬ LÝ JOIN ──────────────────────────────────────────────
        if after.channel is not None:
            setup = await _get_setup(self.pool, guild.id)
            if setup and after.channel.id == setup["join_to_create_channel_id"]:
                category = None
                if setup["category_id"]:
                    category = guild.get_channel(setup["category_id"])

                channel_name = f"{member.display_name}'s Room"
                try:
                    new_channel = await guild.create_voice_channel(
                        name=channel_name,
                        category=category,
                        reason=f"VoiceMaster: Tạo phòng cho {member}",
                    )
                    await member.move_to(new_channel, reason="VoiceMaster: Di chuyển sang phòng mới")

                    await self.pool.execute(
                        """
                        INSERT INTO active_voice_channels (channel_id, guild_id, owner_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (channel_id) DO NOTHING
                        """,
                        new_channel.id, guild.id, member.id,
                    )

                    embed = _build_control_embed(new_channel, member)
                    view = VoiceControlView(new_channel, member.id, self.bot)
                    try:
                        await new_channel.send(embed=embed, view=view)
                    except discord.Forbidden:
                        log.warning(f"VoiceMaster: Bot thiếu quyền gửi tin nhắn vào {new_channel.id}")

                    log.info(f"VoiceMaster: Tạo phòng '{channel_name}' (ID {new_channel.id}) cho {member}")

                except discord.Forbidden:
                    log.error("VoiceMaster: Thiếu quyền tạo kênh!")
                except Exception as e:
                    log.error(f"VoiceMaster: Lỗi khi tạo kênh: {e}", exc_info=True)

        # ── XỬ LÝ LEAVE ─────────────────────────────────────────────
        if before.channel is not None:
            row = await _get_active_channel(self.pool, before.channel.id)
            if row:
                channel = guild.get_channel(before.channel.id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    real_members = [m for m in channel.members if not m.bot]
                    if len(real_members) == 0:
                        try:
                            await channel.delete(reason="VoiceMaster: Phòng trống, tự động xóa")
                            await self.pool.execute(
                                "DELETE FROM active_voice_channels WHERE channel_id = $1",
                                channel.id,
                            )
                            log.info(f"VoiceMaster: Đã xóa phòng trống '{channel.name}' (ID {channel.id})")
                        except discord.NotFound:
                            await self.pool.execute(
                                "DELETE FROM active_voice_channels WHERE channel_id = $1",
                                before.channel.id,
                            )
                        except discord.Forbidden:
                            log.error(f"VoiceMaster: Thiếu quyền xóa kênh {channel.id}")
                        except Exception as e:
                            log.error(f"VoiceMaster: Lỗi khi xóa kênh: {e}", exc_info=True)
                else:
                    await self.pool.execute(
                        "DELETE FROM active_voice_channels WHERE channel_id = $1",
                        before.channel.id,
                    )

    # ── LỆNH SETUP ADMIN ───────────────────────────────────────────────────

    @commands.group(name="voicesetup", aliases=["vs"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup(self, ctx: commands.Context):
        """Nhóm lệnh cấu hình hệ thống phòng voice tự tạo."""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="⚙️ VoiceMaster Setup",
            description=(
                f"`{prefix}voicesetup init <#kênh_join> <#danh_mục>` — Thiết lập JTC\n"
                f"`{prefix}voicesetup role add <@Role> <lock> <hide> <limit> <name>` — Cấp quyền Role\n"
                f"`{prefix}voicesetup role view` — Xem bảng phân quyền\n"
                f"`{prefix}voicesetup status` — Xem trạng thái cấu hình hiện tại"
            ),
            color=0x5865F2,
        )
        await ctx.send(embed=embed)

    @voicesetup.command(name="init")
    @commands.has_permissions(administrator=True)
    async def voicesetup_init(
        self,
        ctx: commands.Context,
        join_channel: discord.VoiceChannel,
        category: discord.CategoryChannel,
    ):
        """Thiết lập kênh Join-to-Create và danh mục chứa phòng tạm."""
        if not self.pool:
            return await ctx.send("❌ Lỗi kết nối Database!")
        await self.pool.execute(
            """
            INSERT INTO voice_setups (guild_id, join_to_create_channel_id, category_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO UPDATE
                SET join_to_create_channel_id = EXCLUDED.join_to_create_channel_id,
                    category_id               = EXCLUDED.category_id
            """,
            ctx.guild.id, join_channel.id, category.id,
        )
        embed = discord.Embed(title="✅ Đã cấu hình VoiceMaster!", color=discord.Color.green())
        embed.add_field(name="📢 Kênh Join-to-Create", value=join_channel.mention)
        embed.add_field(name="📂 Danh mục chứa phòng", value=category.mention)
        embed.set_footer(text=f"Thiết lập bởi {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @voicesetup.group(name="role", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def voicesetup_role(self, ctx: commands.Context):
        """Quản lý quyền Role cho VoiceMaster."""
        await ctx.send(f"Dùng `{ctx.prefix}voicesetup role add` hoặc `{ctx.prefix}voicesetup role view`.")

    @voicesetup_role.command(name="add")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        lock: bool = False,
        hide: bool = False,
        limit: bool = False,
        name: bool = False,
        transfer: bool = False,
        priority: int = 0,
    ):
        """Cấp quyền VoiceMaster cho một Role. Ví dụ: {prefix}voicesetup role add @Booster true true true false false 10"""
        if not self.pool:
            return await ctx.send("❌ Lỗi kết nối Database!")
        await self.pool.execute(
            """
            INSERT INTO voice_role_perms
                (guild_id, role_id, can_lock, can_hide, can_change_limit, can_change_name, can_transfer, priority)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (guild_id, role_id) DO UPDATE
                SET can_lock         = EXCLUDED.can_lock,
                    can_hide         = EXCLUDED.can_hide,
                    can_change_limit = EXCLUDED.can_change_limit,
                    can_change_name  = EXCLUDED.can_change_name,
                    can_transfer     = EXCLUDED.can_transfer,
                    priority         = EXCLUDED.priority
            """,
            ctx.guild.id, role.id, lock, hide, limit, name, transfer, priority,
        )
        embed = discord.Embed(
            title=f"✅ Đã cập nhật quyền cho {role.name}",
            color=role.color or discord.Color.blurple(),
        )
        embed.add_field(name="🔒 Khóa phòng",   value="✅" if lock     else "❌", inline=True)
        embed.add_field(name="👻 Ẩn phòng",     value="✅" if hide     else "❌", inline=True)
        embed.add_field(name="👥 Giới hạn",     value="✅" if limit    else "❌", inline=True)
        embed.add_field(name="✏️ Đổi tên",      value="✅" if name     else "❌", inline=True)
        embed.add_field(name="👑 Chuyển chủ",   value="✅" if transfer else "❌", inline=True)
        embed.add_field(name="⭐ Độ ưu tiên",   value=str(priority),              inline=True)
        await ctx.send(embed=embed)

    @voicesetup_role.command(name="view")
    @commands.has_permissions(administrator=True)
    async def voicesetup_role_view(self, ctx: commands.Context):
        """Xem bảng phân quyền VoiceMaster của server."""
        if not self.pool:
            return await ctx.send("❌ Lỗi kết nối Database!")
        rows = await self.pool.fetch(
            "SELECT * FROM voice_role_perms WHERE guild_id = $1 ORDER BY priority DESC",
            ctx.guild.id,
        )
        if not rows:
            return await ctx.send(f"📭 Chưa có role nào được cấu hình. Dùng `{ctx.prefix}voicesetup role add` để thêm.")
        embed = discord.Embed(title="📋 Bảng Phân Quyền VoiceMaster", color=0x5865F2)
        for row in rows:
            role = ctx.guild.get_role(row["role_id"])
            role_name = role.mention if role else f"<@&{row['role_id']}>"
            perms = []
            if row["can_lock"]:          perms.append("🔒 Khóa")
            if row["can_hide"]:          perms.append("👻 Ẩn")
            if row["can_change_limit"]:  perms.append("👥 Giới hạn")
            if row["can_change_name"]:   perms.append("✏️ Tên")
            if row["can_transfer"]:      perms.append("👑 Chuyển")
            embed.add_field(
                name=f"{role_name} (priority: {row['priority']})",
                value=" · ".join(perms) if perms else "Không có quyền nào",
                inline=False,
            )
        await ctx.send(embed=embed)

    @voicesetup.command(name="status")
    @commands.has_permissions(administrator=True)
    async def voicesetup_status(self, ctx: commands.Context):
        """Xem trạng thái cấu hình VoiceMaster của server."""
        if not self.pool:
            return await ctx.send("❌ Lỗi kết nối Database!")
        setup = await _get_setup(self.pool, ctx.guild.id)
        if not setup:
            return await ctx.send(f"❌ Chưa có cấu hình. Dùng `{ctx.prefix}voicesetup init` để thiết lập.")
        jtc = ctx.guild.get_channel(setup["join_to_create_channel_id"])
        cat = ctx.guild.get_channel(setup["category_id"]) if setup["category_id"] else None
        active_count = await self.pool.fetchval(
            "SELECT COUNT(*) FROM active_voice_channels WHERE guild_id = $1", ctx.guild.id
        )
        embed = discord.Embed(title="📊 Trạng thái VoiceMaster", color=0x5865F2)
        embed.add_field(name="📢 Kênh JTC",            value=jtc.mention if jtc else "❌ Không tìm thấy", inline=True)
        embed.add_field(name="📂 Danh mục",            value=cat.mention if cat else "❌ Không tìm thấy", inline=True)
        embed.add_field(name="🔊 Phòng đang hoạt động", value=str(active_count or 0),                     inline=True)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceManagerCog(bot))