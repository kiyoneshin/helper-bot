import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any, List
import asyncio

log = logging.getLogger("StaffEdit")

from cogs.common.logs import send_staff_log, build_log_edit_info, build_log_edit_tags, build_log_edit_photos

# =====================================================================
# HÀM TỰ ĐỘNG DÒ TÌM DATABASE
# =====================================================================
async def query_db(bot: Any, sql: str, *args) -> list:
    possible_names = ['db', 'pool', 'database', 'db_pool', 'conn', 'postgres', 'pg', 'connection']
    for name in possible_names:
        if hasattr(bot, name):
            db_obj = getattr(bot, name)
            if hasattr(db_obj, 'fetch'):
                return await db_obj.fetch(sql, *args)
    return []

# =====================================================================
# 1. CÁC MODAL (FORM) CHỈNH SỬA THÔNG TIN & TAGS
# =====================================================================

class EditInfoModal(discord.ui.Modal, title="Chỉnh Sửa Hồ Sơ Staff"):
    def __init__(self, view, current_data: dict):
        super().__init__()
        self.view = view
        
        self.name_input = discord.ui.TextInput(
            label="Tên hiển thị (Display Name):",
            placeholder="Nhập tên hiển thị của bạn...",
            default=current_data.get('display_name') or "",
            required=True,
            max_length=50
        )
        self.desc_input = discord.ui.TextInput(
            label="Mô tả giới thiệu bản thân (Description):",
            placeholder="Viết một vài dòng giới thiệu về bạn...",
            default=current_data.get('description') or "",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.contact_input = discord.ui.TextInput(
            label="Thông tin liên hệ (Contact/Facebook/IG):",
            placeholder="Link FB, IG hoặc Discord Tag...",
            default=current_data.get('contact') or "",
            required=False,
            max_length=500
        )
        
        self.add_item(self.name_input)
        self.add_item(self.desc_input)
        self.add_item(self.contact_input)

    async def on_submit(self, interaction: discord.Interaction):
        bot: Any = interaction.client
        target_id = str(interaction.user.id)

        # Ghi lại giá trị cũ trước khi ghi đè
        old_name    = str(self.view.user_data.get('display_name') or '')
        old_desc    = str(self.view.user_data.get('description') or '')
        old_contact = str(self.view.user_data.get('contact') or '')

        new_name    = self.name_input.value.strip()
        new_desc    = self.desc_input.value.strip()
        new_contact = self.contact_input.value.strip()

        await query_db(
            bot,
            "UPDATE profiles SET display_name = $1, description = $2, contact = $3 WHERE discord_id = $4",
            new_name, new_desc, new_contact, target_id
        )

        self.view.user_data['display_name'] = new_name
        self.view.user_data['description'] = new_desc
        self.view.user_data['contact'] = new_contact

        embed = self.view.build_preview_embed()
        if interaction.message:
            await interaction.message.edit(embed=embed, view=self.view)

        await interaction.response.send_message("**Đã cập nhật thông tin cá nhân thành công!**", ephemeral=True)

        # --- Log Audit ---
        log_embed = build_log_edit_info(
            discord_id=target_id,
            old_name=old_name, new_name=new_name,
            old_desc=old_desc, new_desc=new_desc,
            old_contact=old_contact, new_contact=new_contact,
        )
        await send_staff_log(bot, log_embed)


class EditTagsModal(discord.ui.Modal, title="Chỉnh Sửa Tags Giới Thiệu"):
    def __init__(self, view, current_tags: list):
        super().__init__()
        self.view = view
        
        default_tags_str = ", ".join(current_tags) if current_tags else ""
        
        self.tags_input = discord.ui.TextInput(
            label="Nhập các Tag (Cách nhau bởi dấu phẩy):",
            placeholder="Ví dụ: Người hướng nội, Thích chơi game, Nói nhiều",
            default=default_tags_str,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300
        )
        self.add_item(self.tags_input)

    async def on_submit(self, interaction: discord.Interaction):
        bot: Any = interaction.client
        target_id = str(interaction.user.id)

        # Ghi lại tags cũ trước khi ghi đè
        old_tags: list = list(self.view.user_data.get('tags', []))
        if isinstance(old_tags, str):
            import json as _json
            try: old_tags = _json.loads(old_tags)
            except Exception: old_tags = []

        raw_str = self.tags_input.value.strip()
        new_tags = [t.strip() for t in raw_str.split(",") if t.strip()] if raw_str else []

        await query_db(
            bot,
            "UPDATE profiles SET tags = $1::text::jsonb WHERE discord_id = $2",
            json.dumps(new_tags), target_id
        )

        self.view.user_data['tags'] = new_tags
        embed = self.view.build_preview_embed()
        if interaction.message:
            await interaction.message.edit(embed=embed, view=self.view)

        await interaction.response.send_message("**Đã cập nhật danh sách Tags thành công!**", ephemeral=True)

        # --- Log Audit ---
        log_embed = build_log_edit_tags(
            discord_id=target_id,
            old_tags=old_tags,
            new_tags=new_tags,
        )
        await send_staff_log(bot, log_embed)


# =====================================================================
# 2. VIEW QUẢN LÝ ẢNH PROFILE (LƯỚT ẢNH, XÓA & THÊM MỚI)
# =====================================================================

class StaffPhotoEditView(discord.ui.View):
    # ĐÃ SỬA LỖI PYLANCE: Đổi parent_view từ discord.ui.View thành Any
    def __init__(self, bot: Any, user_data: dict, author_id: int, parent_view: Any):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_data = user_data
        self.author_id = author_id
        self.parent_view = parent_view
        self.photo_index = 0
        self.message: Optional[discord.Message] = None
        self.update_button_states()

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    def get_photos_list(self) -> list:
        photos = self.user_data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
        if not isinstance(photos, list):
            photos = []
        return photos

    def update_button_states(self):
        photos = self.get_photos_list()
        has_multiple = len(photos) > 1
        has_any = len(photos) > 0
        
        self.prev_btn.disabled = not has_multiple
        self.next_btn.disabled = not has_multiple
        self.delete_btn.disabled = not has_any

    def build_photo_embed(self) -> discord.Embed:
        photos = self.get_photos_list()
        display_name = self.user_data.get('display_name', 'Chưa đặt tên')
        role_name = str(self.user_data.get('role', 'staff')).upper()

        embed = discord.Embed(
            title=f"Quản Lý Ảnh Profile: {display_name}",
            color=0xffb6c1
        )

        if photos and len(photos) > 0:
            self.photo_index = self.photo_index % len(photos)
            img_url = str(photos[self.photo_index]).strip()
            embed.set_image(url=img_url)
            embed.description = f"Đang xem bức ảnh thứ **{self.photo_index + 1}/{len(photos)}**.\nBấm **Xóa ảnh** để loại bỏ bức ảnh này, hoặc **Thêm ảnh mới** để tải thêm."
            embed.set_footer(text=f"Vị trí: {role_name} • Ảnh {self.photo_index + 1}/{len(photos)}")
        else:
            embed.description = "Hiện tại hồ sơ của bạn **chưa có bức ảnh nào**.\nHãy bấm nút **Thêm ảnh mới** để tải ảnh lên ngay nhé!"
            embed.set_footer(text=f"Vị trí: {role_name} • Ảnh 0/0")

        self.update_button_states()
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bạn không thể thao tác trên bảng quản lý của người khác!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Ảnh trước", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.get_photos_list()
        if photos:
            self.photo_index = (self.photo_index - 1) % len(photos)
        await interaction.response.edit_message(embed=self.build_photo_embed(), view=self)

    @discord.ui.button(label="Ảnh sau", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.get_photos_list()
        if photos:
            self.photo_index = (self.photo_index + 1) % len(photos)
        await interaction.response.edit_message(embed=self.build_photo_embed(), view=self)

    @discord.ui.button(label="Xóa ảnh", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self.get_photos_list()
        if not photos:
            await interaction.response.send_message("Không có ảnh nào để xóa!", ephemeral=True)
            return

        photos.pop(self.photo_index)
        if self.photo_index >= len(photos) and self.photo_index > 0:
            self.photo_index -= 1

        self.user_data['photos'] = photos
        await query_db(
            self.bot,
            "UPDATE profiles SET photos = $1::text::jsonb WHERE discord_id = $2",
            json.dumps(photos), str(self.author_id)
        )

        await interaction.response.edit_message(embed=self.build_photo_embed(), view=self)
        await interaction.followup.send("Đã xóa bức ảnh này khỏi Database thành công!", ephemeral=True)

        # --- Log Audit ---
        log_embed = build_log_edit_photos(
            discord_id=str(self.author_id),
            action="delete",
            count=1,
            total_after=len(photos),
        )
        await send_staff_log(interaction.client, log_embed)

    @discord.ui.button(label="Thêm ảnh mới", style=discord.ButtonStyle.success, row=0)
    async def add_photo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**HÃY GỬI ẢNH NGAY TRONG CHAT NÀY!**\n"
            "Bạn hãy kéo thả/gửi 1 (hoặc nhiều) bức ảnh vào khung chat này trong vòng **60 giây tới**.\n"
            "Bot sẽ tự động lưu và thêm vào danh sách ảnh Profile của bạn!",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.author.id == self.author_id and m.channel.id == interaction.channel_id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60.0)

            # Lọc chỉ lấy các tệp đính kèm là hình ảnh hợp lệ
            image_attachments = [att for att in msg.attachments if att.content_type and att.content_type.startswith("image/")]

            if not image_attachments:
                await interaction.followup.send("File bạn gửi không phải là định dạng hình ảnh hợp lệ!", ephemeral=True)
                return

            # Lấy kênh lưu trữ ảnh cố định để tránh lỗi CDN chết sau khi xóa tin nhắn gốc
            STORAGE_CHANNEL_ID = 1513465012344193088
            storage_channel = self.bot.get_channel(STORAGE_CHANNEL_ID) or await self.bot.fetch_channel(STORAGE_CHANNEL_ID)

            if not isinstance(storage_channel, discord.TextChannel):
                await interaction.followup.send("❌ Không thể kết nối tới kênh lưu trữ ảnh! Vui lòng báo Admin kiểm tra lại.", ephemeral=True)
                return

            # Chuyển đổi từng ảnh thành file object rồi upload lên kênh lưu trữ cố định
            files = [await att.to_file() for att in image_attachments]
            storage_msg = await storage_channel.send(files=files)

            # Lấy URL ổn định từ kênh lưu trữ (không bị chết khi tin nhắn gốc bị xóa)
            new_photos = [att.url for att in storage_msg.attachments]

            # Delay 1 giây rồi mới xóa tin nhắn gốc của Staff để giữ sạch kênh chat
            await asyncio.sleep(1.0)
            try:
                await msg.delete()
            except discord.Forbidden:
                pass

            photos = self.get_photos_list()
            photos.extend(new_photos)  # Cộng dồn ảnh mới vào danh sách hiện tại
            self.user_data['photos'] = photos

            await query_db(
                self.bot,
                "UPDATE profiles SET photos = $1::text::jsonb WHERE discord_id = $2",
                json.dumps(photos), str(self.author_id)
            )

            if interaction.message:
                await interaction.message.edit(embed=self.build_photo_embed(), view=self)

            await interaction.followup.send(f"Đã thêm thành công **{len(new_photos)}** bức ảnh mới vào hồ sơ!", ephemeral=True)

            # --- Log Audit ---
            log_embed = build_log_edit_photos(
                discord_id=str(self.author_id),
                action="add",
                count=len(new_photos),
                total_after=len(photos),
            )
            await send_staff_log(interaction.client, log_embed)

        except asyncio.TimeoutError:
            await interaction.followup.send("**Đã hết thời gian 60 giây!** Bạn chưa gửi ảnh nào, vui lòng bấm nút Thêm ảnh mới để thử lại nhé.", ephemeral=True)

    @discord.ui.button(label="Quay lại", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message:
            await interaction.response.edit_message(embed=self.parent_view.build_preview_embed(), view=self.parent_view)


# =====================================================================
# 3. VIEW GIAO DIỆN CHÍNH CHỈNH SỬA (DÀNH RIÊNG CHO STAFF)
# =====================================================================

class StaffEditView(discord.ui.View):
    def __init__(self, bot: Any, user_data: dict, author_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_data = dict(user_data)
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

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
            await interaction.response.send_message("Bạn không thể chỉnh sửa hồ sơ của người khác!", ephemeral=True)
            return False
        return True

    def build_preview_embed(self) -> discord.Embed:
        data = self.user_data
        role_name = str(data.get('role', 'staff')).upper()
        display_name = data.get('display_name', 'Chưa đặt tên')
        
        embed = discord.Embed(
            title=f"Bảng Chỉnh Sửa Hồ Sơ: {display_name}",
            description="Dưới đây là thông tin hiện tại của bạn trong Database. Hãy bấm các nút bên dưới để chỉnh sửa!",
            color=0xffb6c1
        )
        
        contact = data.get('contact') or "*Chưa cập nhật*"
        embed.add_field(name="Chức vụ", value=f"`{role_name}`", inline=True)
        embed.add_field(name="Liên hệ", value=contact, inline=True)
        
        desc = data.get('description') or "*Chưa có lời giới thiệu nào.*"
        embed.add_field(name="Giới thiệu bản thân", value=desc, inline=False)
        
        tags = data.get('tags', [])
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except Exception: tags = []
        tags_str = "\n".join(f"♱ {t}" for t in tags) if tags else "*Chưa có Tag nào.*"
        embed.add_field(name="Danh sách Tags", value=tags_str, inline=False)

        photos = data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
            
        if photos and len(photos) > 0:
            embed.set_image(url=str(photos[0]).strip())
            embed.add_field(name="Ảnh Profile", value=f"Đang lưu **{len(photos)}** bức ảnh trong hệ thống.", inline=False)
        else:
            embed.add_field(name="Ảnh Profile", value="*Chưa có bức ảnh nào.*", inline=False)
            
        embed.set_footer(text="Angelic Bot • Bấm Cập nhật ảnh để xem danh sách ảnh, xóa hoặc tải ảnh mới!")
        return embed

    @discord.ui.button(label="Sửa Thông Tin", style=discord.ButtonStyle.primary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditInfoModal(self, self.user_data))

    @discord.ui.button(label="Sửa Tags", style=discord.ButtonStyle.primary, row=0)
    async def edit_tags_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        tags = self.user_data.get('tags', [])
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except Exception: tags = []
        await interaction.response.send_modal(EditTagsModal(self, tags))

    @discord.ui.button(label="Cập nhật Ảnh", style=discord.ButtonStyle.success, row=0)
    async def edit_photos_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mở bảng giao diện con chuyên dụng để quản lý, lướt và xóa từng ảnh"""
        photo_view = StaffPhotoEditView(self.bot, self.user_data, self.author_id, self)
        await interaction.response.edit_message(embed=photo_view.build_photo_embed(), view=photo_view)


# =====================================================================
# 4. COG CHÍNH & LỆNH Y!SET
# =====================================================================

class StaffEditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="set", aliases=["editprofile", "suahoso"])
    async def set_profile(self, ctx: commands.Context):
        """Lệnh cho phép Staff tự kiểm tra và chỉnh sửa hồ sơ cá nhân trong Database"""
        target_id = str(ctx.author.id)
        
        try:
            records = await query_db(self.bot, "SELECT * FROM profiles WHERE discord_id = $1", target_id)
            
            if not records:
                await ctx.send(
                    "**ID của bạn chưa có trong hệ thống Database!**\n"
                    "Lệnh `y!set` chỉ dành cho các thành viên Ban Quản Trị (Owner, Admin, Recep) đã được thêm vào danh sách.\n"
                    "Nếu bạn là Staff mới, vui lòng nhờ Admin sử dụng lệnh thêm nhân sự trước nhé!"
                )
                return

            user_data = dict(records[0])
            view = StaffEditView(self.bot, user_data=user_data, author_id=ctx.author.id)
            embed = view.build_preview_embed()
            
            view.message = await ctx.send(embed=embed, view=view)
            log.info(f"🛠️ {ctx.author.display_name} vừa mở bảng chỉnh sửa hồ sơ y!set.")
            
        except Exception as e:
            await ctx.send(f"Lỗi khi tải dữ liệu hồ sơ: {e}")
            log.error(f"Lỗi y!set: {e}")

async def setup(bot):
    await bot.add_cog(StaffEditCog(bot))