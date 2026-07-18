import discord
from discord.ext import commands
import logging
import json
import asyncio
from typing import Any

from cogs.common.db import query_db
from cogs.common.logs import send_staff_log, build_log_add

log = logging.getLogger("StaffAdd")

# =====================================================================
# CẤU HÌNH ROLE ID & CHỨC VỤ (Thứ tự ưu tiên từ cao xuống thấp)
# =====================================================================
ROLE_PRIORITY: list[tuple[int, str]] = [
    (1498711782192189494, "owner"),
    (1510230255988900002, "admin"),
    (1511010582826848520, "recep"),
]

# Kênh lưu trữ ảnh cố định (private storage channel)
STORAGE_CHANNEL_ID = 1513465012344193088


# =====================================================================
# MODAL ĐĂNG KÝ HỒ SƠ
# =====================================================================
class StaffRegisterModal(discord.ui.Modal, title="Đăng Ký Hồ Sơ Staff"):
    """Form nhập liệu để Staff tự tạo hồ sơ lần đầu."""

    name_input = discord.ui.TextInput(
        label="Tên hiển thị (Display Name):",
        placeholder="Bỏ trống để dùng tên Discord của bạn...",
        required=False,
        max_length=50,
    )
    desc_input = discord.ui.TextInput(
        label="Giới thiệu bản thân (Description):",
        placeholder="Viết một vài dòng về bản thân bạn...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )
    contact_input = discord.ui.TextInput(
        label="Thông tin liên hệ (Contact):",
        placeholder="Link FB, IG, Discord Tag...",
        required=False,
        max_length=500,
    )
    tags_input = discord.ui.TextInput(
        label="Tags giới thiệu (cách nhau bằng dấu phẩy):",
        placeholder="Ví dụ: Người hướng nội, Thích chơi game, Nói nhiều",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
    )

    def __init__(self, role_name: str):
        super().__init__()
        self.role_name = role_name  # Chức vụ đã được xác định ở bước kiểm tra quyền

    async def on_submit(self, interaction: discord.Interaction):
        bot: Any = interaction.client
        user = interaction.user
        discord_id = str(user.id)

        # --- Xử lý từng trường ---
        display_name = self.name_input.value.strip() or user.display_name
        description  = self.desc_input.value.strip() or None
        contact      = self.contact_input.value.strip() or None

        raw_tags = self.tags_input.value.strip()
        tags: list[str] = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []

        log.info(
            f"[{user.display_name} | {discord_id}] Đang tạo hồ sơ mới: "
            f"role={self.role_name}, display_name={display_name!r}"
        )

        # --- INSERT vào Database ---
        try:
            await query_db(
                bot,
                """
                INSERT INTO profiles
                    (discord_id, display_name, role, description, contact, tags, photos, votes, rating)
                VALUES
                    ($1, $2, $3, $4, $5, $6::text::jsonb, '[]'::jsonb, '{}'::jsonb, 0.0)
                """,
                discord_id,
                display_name,
                self.role_name,
                description,
                contact,
                json.dumps(tags, ensure_ascii=False),
            )
            log.info(f"[{user.display_name} | {discord_id}] Hồ sơ đã được INSERT thành công.")
        except Exception as e:
            log.error(f"Lỗi INSERT hồ sơ [{discord_id}]: {e}")
            await interaction.response.send_message(
                f"Đã xảy ra lỗi khi lưu hồ sơ vào cơ sở dữ liệu:\n`{e}`\n"
                "Vui lòng thử lại hoặc báo Admin.",
                ephemeral=True,
            )
            return

        # --- Gửi Log Audit vào kênh ẩn ---
        log_embed = build_log_add(
            discord_id=discord_id,
            display_name=display_name,
            role=self.role_name,
            description=description,
            contact=contact,
            tags=tags,
        )
        await send_staff_log(bot, log_embed)

        # --- Gửi nút thêm ảnh sau khi lưu thành công ---
        view = AddPhotoAfterRegisterView(bot=bot, author_id=user.id)
        await interaction.response.send_message(
            f"**Hồ sơ của bạn đã được tạo thành công!**\n"
            f"Chức vụ: `{self.role_name.upper()}` | Tên hiển thị: **{display_name}**\n\n"
            "Hãy bấm nút bên dưới để thêm ảnh Profile ngay nhé!",
            view=view,
            ephemeral=True,
        )


# =====================================================================
# VIEW NÚT "THÊM ẢNH MỚI" SAU KHI ĐĂNG KÝ
# =====================================================================
class AddPhotoAfterRegisterView(discord.ui.View):
    """View đơn giản chứa 1 nút Thêm ảnh mới, xuất hiện ngay sau khi đăng ký thành công."""

    def __init__(self, bot: Any, author_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.message: discord.Message | None = None

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Bạn không thể thao tác trên form của người khác!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Thêm ảnh mới", style=discord.ButtonStyle.success)
    async def add_photo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**HÃY GỬI ẢNH NGAY TRONG CHAT NÀY!**\n"
            "Kéo thả hoặc gửi 1 (hoặc nhiều) bức ảnh vào khung chat trong vòng **60 giây tới**.\n"
            "Bot sẽ tự động lưu và thêm vào danh sách ảnh Profile của bạn!",
            ephemeral=True,
        )

        def check(m: discord.Message) -> bool:
            return (
                m.author.id == self.author_id
                and m.channel.id == interaction.channel_id
                and len(m.attachments) > 0
            )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "**Đã hết thời gian 60 giây!** Bạn chưa gửi ảnh nào. "
                "Hãy bấm nút **Thêm ảnh mới** để thử lại, hoặc dùng `y!set` để cập nhật ảnh sau.",
                ephemeral=True,
            )
            return

        # Lọc chỉ lấy đính kèm là hình ảnh hợp lệ
        image_attachments = [
            att for att in msg.attachments
            if att.content_type and att.content_type.startswith("image/")
        ]

        if not image_attachments:
            await interaction.followup.send(
                "File bạn gửi không phải định dạng hình ảnh hợp lệ! Vui lòng thử lại.",
                ephemeral=True,
            )
            return

        # Lấy kênh lưu trữ ảnh cố định
        try:
            storage_channel = (
                self.bot.get_channel(STORAGE_CHANNEL_ID)
                or await self.bot.fetch_channel(STORAGE_CHANNEL_ID)
            )
        except Exception as e:
            log.error(f"Không thể lấy kênh lưu trữ ảnh {STORAGE_CHANNEL_ID}: {e}")
            await interaction.followup.send(
                "Không thể kết nối tới kênh lưu trữ ảnh! Vui lòng báo Admin kiểm tra lại.",
                ephemeral=True,
            )
            return

        if not isinstance(storage_channel, discord.TextChannel):
            await interaction.followup.send(
                "Kênh lưu trữ ảnh không hợp lệ! Vui lòng báo Admin kiểm tra cấu hình.",
                ephemeral=True,
            )
            return

        # Upload ảnh lên kênh lưu trữ để lấy URL CDN vĩnh viễn
        try:
            files = [await att.to_file() for att in image_attachments]
            storage_msg = await storage_channel.send(files=files)
            new_photos = [att.url for att in storage_msg.attachments]
            log.info(
                f"[{interaction.user.display_name} | {self.author_id}] "
                f"Đã upload {len(new_photos)} ảnh lên kênh lưu trữ."
            )
        except Exception as e:
            log.error(f"Lỗi upload ảnh lên storage channel: {e}")
            await interaction.followup.send(
                f"Lỗi khi upload ảnh: `{e}`", ephemeral=True
            )
            return

        # Delay 1 giây rồi xóa tin nhắn gốc của Staff để giữ sạch kênh chat
        await asyncio.sleep(1.0)
        try:
            await msg.delete()
        except discord.Forbidden:
            log.warning(
                f"Không có quyền xóa tin nhắn ảnh của {interaction.user.display_name}."
            )
        except discord.NotFound:
            pass  # Tin nhắn đã bị xóa trước đó, bỏ qua

        # Lấy danh sách ảnh hiện tại trong DB rồi cộng dồn ảnh mới
        discord_id = str(self.author_id)
        try:
            records = await query_db(
                self.bot,
                "SELECT photos FROM profiles WHERE discord_id = $1",
                discord_id,
            )
            existing_photos: list = []
            if records:
                raw = records[0]["photos"]
                if isinstance(raw, str):
                    try:
                        existing_photos = json.loads(raw)
                    except Exception:
                        existing_photos = []
                elif isinstance(raw, list):
                    existing_photos = raw

            existing_photos.extend(new_photos)

            await query_db(
                self.bot,
                "UPDATE profiles SET photos = $1::text::jsonb WHERE discord_id = $2",
                json.dumps(existing_photos, ensure_ascii=False),
                discord_id,
            )
            log.info(
                f"[{interaction.user.display_name} | {discord_id}] "
                f"Đã lưu {len(new_photos)} ảnh mới vào DB. Tổng: {len(existing_photos)} ảnh."
            )
        except Exception as e:
            log.error(f"Lỗi UPDATE photos [{discord_id}]: {e}")
            await interaction.followup.send(
                f"Ảnh đã upload nhưng lưu vào DB thất bại: `{e}`", ephemeral=True
            )
            return

        # Vô hiệu hóa nút sau khi thêm ảnh thành công để tránh spam
        button.disabled = True
        try:
            if interaction.message:
                await interaction.message.edit(view=self)
        except Exception:
            pass

        await interaction.followup.send(
            f"Đã thêm thành công **{len(new_photos)}** bức ảnh vào hồ sơ của bạn!\n"
            "Bạn có thể dùng `y!set` để quản lý thêm/xóa ảnh bất cứ lúc nào.",
            ephemeral=True,
        )


# =====================================================================
# VIEW TẠM THỜI ĐỂ MỞ MODAL (bắt buộc khi dùng prefix command)
# =====================================================================
class _OpenRegisterModalView(discord.ui.View):
    """View tạm thời chứa 1 nút để kích hoạt StaffRegisterModal.
    Cần thiết vì prefix command không thể gọi send_modal trực tiếp."""

    def __init__(self, role_name: str, author_id: int):
        super().__init__(timeout=120)
        self.role_name = role_name
        self.author_id = author_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Chỉ người gọi lệnh mới có thể mở Form đăng ký này!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Mở Form Đăng Ký", style=discord.ButtonStyle.primary)
    async def open_modal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StaffRegisterModal(role_name=self.role_name))
        # Vô hiệu hóa nút ngay sau khi mở Form để tránh mở nhiều lần
        button.disabled = True
        try:
            if interaction.message:
                await interaction.message.edit(view=self)
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# =====================================================================
# COG CHÍNH & LỆNH Y!ADD
# =====================================================================
class StaffAddCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="add", aliases=["register", "dangky", "themhoso"])
    async def add_profile(self, ctx: commands.Context):
        """Lệnh cho phép Staff tự tạo hồ sơ cá nhân lần đầu thông qua Form (Modal)."""
        author = ctx.author
        discord_id = str(author.id)

        log.info(f"[{author.display_name} | {discord_id}] Gọi lệnh y!add.")

        # --- Bước 1: Lệnh chỉ dùng trong Server ---
        if not isinstance(author, discord.Member):
            await ctx.send("Lệnh này chỉ dùng được trong Server, không dùng được qua DM!")
            return

        # --- Bước 2: Xác định chức vụ dựa trên Role Discord (ưu tiên từ cao xuống thấp) ---
        assigned_role: str | None = None
        author_role_ids = {role.id for role in author.roles}

        for role_id, role_name in ROLE_PRIORITY:
            if role_id in author_role_ids:
                assigned_role = role_name
                break  # Đã lấy được role cao nhất, dừng vòng lặp

        if assigned_role is None:
            log.warning(
                f"[{author.display_name} | {discord_id}] Không có role hợp lệ, từ chối lệnh y!add."
            )
            await ctx.send(
                "**Bạn không có chức vụ hợp lệ để thực hiện lệnh này!**\n"
                "Lệnh `y!add` chỉ dành cho Owner, Admin và Recep của Server.",
                delete_after=15,
            )
            return

        log.info(f"[{author.display_name} | {discord_id}] Role hợp lệ: {assigned_role}.")

        # --- Bước 3: Kiểm tra chéo DB — hồ sơ đã tồn tại chưa? ---
        try:
            records = await query_db(
                self.bot,
                "SELECT discord_id FROM profiles WHERE discord_id = $1",
                discord_id,
            )
        except Exception as e:
            log.error(f"Lỗi truy vấn DB khi kiểm tra tồn tại [{discord_id}]: {e}")
            await ctx.send(f"Lỗi khi truy vấn cơ sở dữ liệu: `{e}`")
            return

        if records:
            log.info(
                f"[{author.display_name} | {discord_id}] Hồ sơ đã tồn tại, hướng dẫn dùng y!set."
            )
            await ctx.send(
                "**Hồ sơ của bạn đã tồn tại trong hệ thống!**\n"
                "Vui lòng dùng lệnh `y!set` để chỉnh sửa thông tin của mình.",
                delete_after=15,
            )
            return

        # --- Bước 4: Hiển thị nút mở Form đăng ký ---
        view = _OpenRegisterModalView(role_name=assigned_role, author_id=author.id)
        view.message = await ctx.send(
            f"Chào **{author.display_name}**!\n"
            f"Bạn đang đăng ký với chức vụ: `{assigned_role.upper()}`.\n"
            "Hãy bấm nút bên dưới để mở Form đăng ký hồ sơ Staff.",
            view=view,
        )
        log.info(f"[{author.display_name} | {discord_id}] Đã gửi nút mở Form đăng ký.")


async def setup(bot):
    await bot.add_cog(StaffAddCog(bot))
    log.info("StaffAddCog đã được tải thành công.")
