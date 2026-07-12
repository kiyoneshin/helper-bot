import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any, List
import asyncio

log = logging.getLogger("StaffEdit")

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
        
        # Tự động điền dữ liệu cũ vào ô input (Pre-fill)
        self.name_input = discord.ui.TextInput(
            label="Tên hiển thị (Display Name):",
            placeholder="Nhập tên hiển thị siêu cute của bạn...",
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
            max_length=100
        )
        
        self.add_item(self.name_input)
        self.add_item(self.desc_input)
        self.add_item(self.contact_input)

    async def on_submit(self, interaction: discord.Interaction):
        bot: Any = interaction.client
        target_id = str(interaction.user.id)
        
        new_name = self.name_input.value.strip()
        new_desc = self.desc_input.value.strip()
        new_contact = self.contact_input.value.strip()

        await query_db(
            bot,
            "UPDATE profiles SET display_name = $1, description = $2, contact = $3 WHERE discord_id = $4",
            new_name, new_desc, new_contact, target_id
        )

        # Cập nhật lại dữ liệu hiển thị trên bảng View
        self.view.user_data['display_name'] = new_name
        self.view.user_data['description'] = new_desc
        self.view.user_data['contact'] = new_contact

        embed = self.view.build_preview_embed()
        if interaction.message:
            await interaction.message.edit(embed=embed, view=self.view)
            
        await interaction.response.send_message("**Đã cập nhật thông tin cá nhân thành công!**", ephemeral=True)


class EditTagsModal(discord.ui.Modal, title="Chỉnh Sửa Tags Giới Thiệu"):
    def __init__(self, view, current_tags: list):
        super().__init__()
        self.view = view
        
        # Biến mảng tags thành chuỗi cách nhau bởi dấu phẩy để dễ gõ
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
        
        raw_str = self.tags_input.value.strip()
        # Tách chuỗi bằng dấu phẩy và xóa khoảng trắng dư thừa
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

# =====================================================================
# 2. VIEW GIAO DIỆN NÚT BẤM CHỈNH SỬA (DÀNH RIÊNG CHO STAFF)
# =====================================================================

class StaffEditView(discord.ui.View):
    def __init__(self, bot: Any, user_data: dict, author_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_data = dict(user_data)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bạn không thể chỉnh sửa hồ sơ của người khác!", ephemeral=True)
            return False
        return True

    def build_preview_embed(self) -> discord.Embed:
        """Hàm tự động xây dựng khung Embed xem trước (Preview) thông tin Staff"""
        data = self.user_data
        role_name = str(data.get('role', 'staff')).upper()
        display_name = data.get('display_name', 'Chưa đặt tên')
        
        embed = discord.Embed(
            title=f"Bảng Chỉnh Sửa Hồ Sơ: {display_name}",
            description="Dưới đây là thông tin hiện tại của bạn trong Database. Hãy bấm các nút bên dưới để chỉnh sửa!",
            color=0xffb6c1
        )
        
        # 1. Chức vụ & Liên hệ
        contact = data.get('contact') or "*Chưa cập nhật*"
        embed.add_field(name="Chức vụ", value=f"`{role_name}`", inline=True)
        embed.add_field(name="Liên hệ", value=contact, inline=True)
        
        # 2. Mô tả
        desc = data.get('description') or "*Chưa có lời giới thiệu nào.*"
        embed.add_field(name="Giới thiệu bản thân", value=desc, inline=False)
        
        # 3. Tags
        tags = data.get('tags', [])
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except Exception: tags = []
        tags_str = "\n".join(f"♱ {t}" for t in tags) if tags else "*Chưa có Tag nào.*"
        embed.add_field(name="Danh sách Tags", value=tags_str, inline=False)

        # 4. Ảnh Profile
        photos = data.get('photos', [])
        if isinstance(photos, str):
            try: photos = json.loads(photos)
            except Exception: photos = []
            
        if photos and len(photos) > 0:
            embed.set_image(url=str(photos[0]).strip())
            embed.add_field(name="Ảnh Profile", value=f"Đang lưu **{len(photos)}** bức ảnh trong hệ thống.", inline=False)
        else:
            embed.add_field(name="Ảnh Profile", value="*Chưa có bức ảnh nào.*", inline=False)
            
        embed.set_footer(text="Angelic Bot • Bấm nút Cập nhật ảnh để gửi trực tiếp ảnh mới vào chat!")
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

    @discord.ui.button(label="🖼️ Cập nhật Ảnh", style=discord.ButtonStyle.success, row=0)
    async def edit_photos_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Tính năng bắt ảnh trực tiếp từ kênh chat"""
        await interaction.response.send_message(
            "**HÃY GỬI ẢNH NGAY TRONG CHAT NÀY!**\n"
            "Bạn hãy kéo thả/gửi 1 (hoặc nhiều) bức ảnh vào khung chat này trong vòng **60 giây tới**.\n"
            "Bot sẽ tự động lấy ảnh bạn vừa gửi để lưu làm ảnh Profile mới!",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.author.id == self.author_id and m.channel.id == interaction.channel_id and len(m.attachments) > 0

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            
            new_photos = [att.url for att in msg.attachments if att.content_type and att.content_type.startswith("image/")]
            
            if not new_photos:
                await interaction.followup.send("File bạn gửi không phải là định dạng hình ảnh hợp lệ!", ephemeral=True)
                return

            # Cập nhật mảng ảnh mới lên Database
            await query_db(
                self.bot,
                "UPDATE profiles SET photos = $1::text::jsonb WHERE discord_id = $2",
                json.dumps(new_photos), str(self.author_id)
            )

            self.user_data['photos'] = new_photos
            embed = self.build_preview_embed()
            
            try:
                await msg.delete()
            except discord.Forbidden:
                pass

            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)

            await interaction.followup.send(f"**Đã cập nhật thành công {len(new_photos)} bức ảnh mới vào hồ sơ của bạn!**", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.followup.send("**Đã hết thời gian 60 giây!** Bạn chưa gửi ảnh nào, vui lòng bấm nút 🖼️ Cập nhật ảnh để thử lại nhé.", ephemeral=True)


# =====================================================================
# 3. COG CHÍNH & LỆNH Y!SET
# =====================================================================

class StaffEditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="set", aliases=["editprofile", "suahoso"])
    async def set_profile(self, ctx: commands.Context):
        """Lệnh cho phép Staff tự kiểm tra và chỉnh sửa hồ sơ cá nhân trong Database"""
        target_id = str(ctx.author.id)
        
        try:
            # Kiểm tra xem ID của người gõ lệnh có tồn tại trong Database không
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
            
            await ctx.send(embed=embed, view=view)
            log.info(f"🛠️ {ctx.author.display_name} vừa mở bảng chỉnh sửa hồ sơ y!set.")
            
        except Exception as e:
            await ctx.send(f"Lỗi khi tải dữ liệu hồ sơ: {e}")
            log.error(f"Lỗi y!set: {e}")

async def setup(bot):
    await bot.add_cog(StaffEditCog(bot))