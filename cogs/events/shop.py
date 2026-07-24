import discord
from discord.ext import commands
import logging
import json
from typing import Optional, Any

# Bổ sung thêm query_db vào import để dùng cho lệnh Bảng Xếp Hạng (y!etop)
from cogs.common.db import get_or_create_event_profile, deduct_event_points, execute_db, fetchval_db, fetchrow_db, query_db

log = logging.getLogger("EventShop")

SHOP_ITEMS = {
    "item_1": {"name": "🎁 Hộp Quà Bí Ẩn (Gacha)", "price": 1500},
    "item_2": {"name": "🎭 Role Màu Sự Kiện (Hạn 7 ngày)", "price": 3500},
    "item_3": {"name": "🎨 Role Màu Thiết Kế Riêng (Hạn 30 ngày)", "price": 10000},
    "item_4": {"name": "👑 Role Biểu Tượng Vĩnh Viễn", "price": 25000},
    "item_5": {"name": "🏆 Vật Phẩm Tối Cao (Nitro / Custom Đặc Quyền)", "price": 50000}
}


class ShopSelect(discord.ui.Select):
    def __init__(self, bot: Any):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="🎁 Hộp Quà Bí Ẩn (Gacha)",
                description="Giá: 1,500 điểm",
                value="item_1"
            ),
            discord.SelectOption(
                label="🎭 Role Màu Sự Kiện (7 ngày)",
                description="Giá: 3,500 điểm",
                value="item_2"
            ),
            discord.SelectOption(
                label="🎨 Role Màu Thiết Kế (30 ngày)",
                description="Giá: 10,000 điểm",
                value="item_3"
            ),
            discord.SelectOption(
                label="👑 Role Biểu Tượng Vĩnh Viễn",
                description="Giá: 25,000 điểm (Giới hạn: 5 slot)",
                value="item_4"
            ),
            discord.SelectOption(
                label="🏆 Vật Phẩm Tối Cao",
                description="Giá: 50,000 điểm (Nitro / Custom)",
                value="item_5"
            ),
        ]
        super().__init__(
            placeholder="🛒 Chọn vật phẩm muốn đổi...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None and isinstance(self.view, ShopView)
        item_id = self.values[0]
        item_data = SHOP_ITEMS[item_id]
        price = item_data["price"]
        name = item_data["name"]
        uid = str(interaction.user.id)

        # 1. Trừ điểm an toàn
        success = await deduct_event_points(self.bot, uid, price)
        if not success:
            await interaction.response.send_message(
                "❌ Số dư của bạn không đủ để đổi vật phẩm này!",
                ephemeral=True
            )
            return

        # 2. Xử lý logic từng loại vật phẩm
        if item_id == "item_4":
            # Kiểm tra xem đã có đủ 5 người sở hữu chưa
            count = await fetchval_db(
                self.bot,
                "SELECT COUNT(*) FROM event_profiles WHERE COALESCE((inventory->>'item_4')::int, 0) > 0"
            )
            if count is not None and count >= 5:
                # Hoàn tiền
                await execute_db(self.bot, "UPDATE event_profiles SET points = points + $2 WHERE discord_id = $1", uid, price)
                await interaction.response.send_message(
                    "❌ Rất tiếc, vật phẩm này đã đạt giới hạn 5 người đổi! Số điểm đã được hoàn lại vào ví của bạn.",
                    ephemeral=True
                )
                return

        # 3. Cập nhật Inventory
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        inv = {}
        if row and row['inventory']:
            try:
                inv = json.loads(row['inventory']) if isinstance(row['inventory'], str) else row['inventory']
            except Exception as e:
                log.error(f"Lỗi parse inventory cho {uid}: {e}")
                
        inv[item_id] = inv.get(item_id, 0) + 1
        
        await execute_db(
            self.bot, 
            "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", 
            uid, 
            json.dumps(inv)
        )

        # 4. Phản hồi thông báo
        embed = discord.Embed(
            title="🎉 Đổi Quà Thành Công!",
            color=0x57f287
        )
        
        if item_id == "item_5":
            embed.description = f"Bạn đã đổi thành công **{name}**!\nYêu cầu của bạn đã được gửi đến Ban Quản Trị."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Sửa lỗi Pylance: Dùng isinstance để chứng minh kênh có hỗ trợ gửi tin nhắn
            if isinstance(interaction.channel, discord.abc.Messageable):
                await interaction.channel.send(
                    f"👑 Chúc mừng <@{uid}> vừa đổi thành công **{name}**!\n"
                    f"Hãy chờ Admin liên hệ và trao giải nhé!"
                )
        else:
            embed.description = f"Bạn đã đổi thành công **{name}**!\nVật phẩm đã được thêm vào túi đồ (inventory) của bạn."
            await interaction.response.send_message(embed=embed, ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self, author_id: int, bot: Any):
        super().__init__(timeout=120)  # Tự động vô hiệu hóa sau 2 phút
        self.author_id = author_id
        self.bot = bot
        self.message: Optional[discord.Message] = None
        self.add_item(ShopSelect(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Bạn không thể dùng bảng cửa hàng của người khác! Hãy tự gõ lệnh `y!shop` nhé.", 
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        # Sửa lỗi Pylance: Chỉ disable nếu item là Button hoặc Select (những class có thuộc tính disabled)
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class EventShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="point", aliases=["bal", "vi"])
    async def point_cmd(self, ctx: commands.Context):
        """Kiểm tra số dư và tổng điểm sự kiện của bạn"""
        uid = str(ctx.author.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        
        if not profile:
            await ctx.send("Không thể lấy dữ liệu hồ sơ sự kiện của bạn lúc này. Vui lòng thử lại sau!")
            return

        points = profile.get("points", 0)
        total_earned = profile.get("total_earned", 0)
        p2w = float(profile.get("p2w_multiplier", 1.0))
        
        if p2w <= 1.0:
            rank = "Dân Cày Chay 👥"
        elif p2w < 1.75:
            rank = "Đại Gia Tầm Trung 🌸"
        else:
            rank = "Chúa Tể P2W 👑"

        embed = discord.Embed(
            title=f"💳 Ví Sự Kiện Angelic — {ctx.author.display_name}",
            description=f"Hạng của bạn: **{rank}**",
            color=0xffb6c1
        )
        embed.add_field(
            name="🪙 Số dư hiện tại",
            value=f"`{points:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="🏆 Tổng điểm tích lũy",
            value=f"`{total_earned:,}` điểm",
            inline=True
        )
        embed.add_field(
            name="⚡ Hệ số P2W",
            value=f"`x{p2w:.2f}`",
            inline=True
        )
        
        embed.set_footer(text="Gõ y!shop để xem cửa hàng đổi quà nhé! 🌸")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="shop", aliases=["cuahang", "store"])
    async def shop_cmd(self, ctx: commands.Context):
        """Mở cửa hàng đổi điểm sự kiện lấy quà"""
        uid = str(ctx.author.id)
        profile = await get_or_create_event_profile(self.bot, uid)
        points = profile.get("points", 0) if profile else 0

        embed = discord.Embed(
            title="🛒 Cửa Hàng Sự Kiện Angelic",
            description=(
                f"🪙 **Số dư hiện tại của bạn:** `{points:,}` điểm\n\n"
                "Chào mừng bạn đến với Cửa Hàng Sự Kiện!\n"
                "Hãy chọn một vật phẩm từ menu thả xuống bên dưới để đổi quà.\n\n"
                "**Bảng Giá:**\n"
                "🎟️ **50 điểm** ── Vé số Xổ Số (Dùng `y!xoso mua <sl>`)\n"
                "🎁 **1,500 điểm** ── Hộp Quà Bí Ẩn (Gacha)\n"
                "🎭 **3,500 điểm** ── Role Màu Sự Kiện (7 ngày)\n"
                "🎨 **10,000 điểm** ── Role Màu Thiết Kế Riêng (30 ngày)\n"
                "👑 **25,000 điểm** ── Role Biểu Tượng Vĩnh Viễn (Tối đa 5 slot)\n"
                "🏆 **50,000 điểm** ── Vật Phẩm Tối Cao (Nitro / Custom Đặc Quyền)"
            ),
            color=0xffb6c1
        )
        
        view = ShopView(author_id=ctx.author.id, bot=self.bot)
        view.message = await ctx.send(embed=embed, view=view)

    # =====================================================================
    # LỆNH ĐUA TOP: Y!ETOP / Y!EVTOP / Y!EVENTOP (MỚI THÊM)
    # =====================================================================
    @commands.hybrid_command(name="etop", aliases=["evtop", "eventtop", "eventop"])
    async def etop_cmd(self, ctx: commands.Context):
        """Xem Bảng Xếp Hạng Đua Top Điểm Sự Kiện"""
        # Sắp xếp theo total_earned (tổng điểm kiếm được) để đảm bảo công bằng cho người đã đổi quà
        sql = """
            SELECT discord_id, total_earned, points 
            FROM event_profiles 
            WHERE total_earned > 0 
            ORDER BY total_earned DESC 
            LIMIT 10;
        """
        rows = await query_db(self.bot, sql)

        if not rows:
            await ctx.send("📊 Bảng xếp hạng sự kiện hiện đang trống! Hãy là người đầu tiên chat để lấy điểm nhé.")
            return

        embed = discord.Embed(
            title="🏆 Bảng Xếp Hạng Sự Kiện Angelic ໒꒱",
            color=0xffb6c1
        )

        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = ""

        for idx, row in enumerate(rows):
            rank_icon = medals[idx] if idx < 3 else f"**#{idx + 1}.**"
            user_id = row["discord_id"]
            total_pts = row["total_earned"]
            current_pts = row["points"]

            leaderboard_text += (
                f"{rank_icon} <@{user_id}>\n"
                f"└ 🏆 Tổng cày: **`{total_pts:,}`** điểm *(Dư: `{current_pts:,}`)*\n\n"
            )

        embed.description = (
            "Vinh danh Top 10 chiến thần tích lũy nhiều điểm nhất trong sự kiện:\n\n"
            f"{leaderboard_text}"
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None)
        embed.set_footer(text="Bảng xếp hạng dựa trên tổng điểm cày được (không bị trừ khi mua shop) 🌸")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EventShopCog(bot))