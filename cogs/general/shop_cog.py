"""
shop_cog.py — Cog Cửa Hàng Hợp Nhất (y!shop & y!buy)
=====================================================
Hiển thị toàn bộ shop theo Dropdown Menu, mua đồ bằng ID số.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import discord
from discord.ext import commands

from cogs.common.db import (
    deduct_event_points,
    execute_db,
    fetchrow_db,
    get_or_create_event_profile,
)
from cogs.common.item_config import (
    ITEM_REGISTRY,
    get_buyable_items,
    get_item_by_id,
)

# Import helper mua vé xổ số — không lặp code
from cogs.events.gambling.lottery import (
    Lottery,
    buy_lottery_tickets,
)

# Import hàm mua hạt giống từ farm_db — không lặp code
from cogs.events.idle_farm.farm_db import buy_seed

log = logging.getLogger("ShopCog")


# ============================================================
# EMBED BUILDERS
# ============================================================

def _format_price(price: int | None) -> str:
    return f"{price:,} pts" if price is not None else "Không bán"


def build_shop_embed(category: str, author: discord.Member | discord.User) -> discord.Embed:
    """Tạo Embed danh sách cửa hàng theo category."""
    CATEGORY_META = {
        "event":       ("🎪 Cửa Hàng Sự Kiện",       0x9b59b6),
        "farm":        ("🌾 Cửa Hàng Nông Trại",      0xe67e22),
        "blackmarket": ("🌙 Cửa Hàng Chợ Đen",        0x2b2d31),
    }
    title, color = CATEGORY_META.get(category, ("🛒 Cửa Hàng", 0x7289da))

    embed = discord.Embed(title=title, color=color)
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    items = get_buyable_items(category)
    if items:
        lines = [
            f"`[{item['id']}]` {item['icon']} **{item['name']}** | "
            f"Giá: **{_format_price(item['price'])}** | {item['description']}"
            for item in items
        ]
        embed.description = "\n".join(lines)
    else:
        embed.description = "*Không có vật phẩm nào để mua ở mục này.*"

    embed.set_footer(text="💡 Hướng dẫn: Dùng lệnh y!buy <id> [số_lượng] để mua vật phẩm.")
    return embed


# ============================================================
# UI COMPONENTS
# ============================================================

class ShopSelect(discord.ui.Select):
    """Dropdown để chuyển đổi giữa các tab cửa hàng."""

    def __init__(self, author: discord.Member | discord.User, current_category: str = "event"):
        self.author = author

        options = [
            discord.SelectOption(
                label="Sự kiện",
                value="event",
                emoji="🎪",
                description="Vé xổ số và vật phẩm sự kiện",
                default=(current_category == "event"),
            ),
            discord.SelectOption(
                label="Nông trại",
                value="farm",
                emoji="🌾",
                description="Hạt giống cây trồng",
                default=(current_category == "farm"),
            ),
            discord.SelectOption(
                label="Chợ đen",
                value="blackmarket",
                emoji="🌙",
                description="Vật phẩm đặc biệt — phá phách đối thủ",
                default=(current_category == "blackmarket"),
            ),
        ]
        super().__init__(
            placeholder="Chọn danh mục cửa hàng...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        for opt in self.options:
            opt.default = (opt.value == selected)

        embed = build_shop_embed(selected, interaction.user)
        await interaction.response.edit_message(embed=embed, view=self.view)


class ShopView(discord.ui.View):
    """View bao bọc Select Menu cửa hàng."""

    def __init__(self, author: discord.Member | discord.User, category: str = "event"):
        super().__init__(timeout=120.0)
        self.author = author
        self.add_item(ShopSelect(author, category))
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Đây không phải cửa hàng của bạn!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ============================================================
# LOGIC MUA HÀNG (theo từng category)
# ============================================================

async def _buy_event_item(
    ctx: commands.Context,
    bot: commands.Bot,
    item: dict[str, Any],
    amount: int,
) -> None:
    """Xử lý mua vật phẩm sự kiện (ID 0–9)."""
    if item["id"] == 0:
        # ID 0 = Vé Xổ Số — gọi helper lottery
        lottery_cog: Lottery | None = bot.cogs.get("Lottery")  # type: ignore
        is_locked = lottery_cog.is_locked if lottery_cog else False
        ok, msg = await buy_lottery_tickets(bot, str(ctx.author.id), amount, is_locked)
        await ctx.send(f"{ctx.author.mention} {msg}", delete_after=10.0)
    else:
        await ctx.send(
            f"❌ Vật phẩm **{item['name']}** không thể mua trong shop hiện tại.",
            delete_after=5.0,
        )


async def _buy_farm_item(
    ctx: commands.Context,
    bot: commands.Bot,
    item: dict[str, Any],
    amount: int,
) -> None:
    """Xử lý mua hạt giống Farm (ID 10–19) — gọi buy_seed trong farm_db."""
    # db_key của farm item là "seed_wheat", "seed_sunflower", v.v.
    seed_key = item["db_key"]  # "seed_wheat"
    seed_id = seed_key.removeprefix("seed_")  # "wheat"

    ok, msg = await buy_seed(bot, str(ctx.author.id), seed_id, amount)
    status = "✅" if ok else "❌"
    await ctx.send(f"{status} {ctx.author.mention} {msg}", delete_after=10.0)


async def _buy_blackmarket_item(
    ctx: commands.Context,
    bot: commands.Bot,
    item: dict[str, Any],
    amount: int,
) -> None:
    """Xử lý mua vật phẩm Chợ đen (ID 20–29)."""
    uid = str(ctx.author.id)
    price = item["price"]
    if price is None:
        await ctx.send("❌ Vật phẩm này không thể mua!", delete_after=5.0)
        return

    total = price * amount
    await get_or_create_event_profile(bot, uid)
    ok = await deduct_event_points(bot, uid, total)
    if not ok:
        await ctx.send(
            f"❌ {ctx.author.mention} Không đủ điểm! Cần **{total:,}** điểm để mua "
            f"**{amount}x {item['name']}**.",
            delete_after=5.0,
        )
        return

    # Ghi vào inventory của event_profiles
    row = await fetchrow_db(bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
    inv: dict[str, int] = {}
    if row and row["inventory"]:
        try:
            inv = json.loads(row["inventory"]) if isinstance(row["inventory"], str) else row["inventory"]
        except Exception:
            pass

    db_key = item["db_key"]
    inv[db_key] = inv.get(db_key, 0) + amount

    await execute_db(
        bot,
        "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1",
        uid,
        json.dumps(inv),
    )

    await ctx.send(
        f"✅ {ctx.author.mention} Đã mua **{amount}x {item['icon']} {item['name']}** "
        f"với giá **{total:,}** điểm. Dùng `y!use {item['id']}` để sử dụng!",
        delete_after=10.0,
    )


# ============================================================
# COG CHÍNH
# ============================================================

class ShopCog(commands.Cog):
    """🛒 Cog Cửa Hàng Hợp Nhất."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="shop",
        aliases=["cuahang", "store"],
        description="🛒 Xem cửa hàng vật phẩm (Sự kiện, Nông trại, Chợ đen)",
    )
    async def shop_cmd(self, ctx: commands.Context) -> None:
        """Mở cửa hàng tổng hợp bằng Dropdown UI."""
        embed = build_shop_embed("event", ctx.author)
        view = ShopView(ctx.author, "event")
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="buy",
        aliases=["mua"],
        description="🛒 Mua vật phẩm theo ID. Cú pháp: y!buy <id> [số_lượng]",
    )
    async def buy_cmd(self, ctx: commands.Context, item_id: int, amount: int = 1) -> None:
        """Mua vật phẩm theo ID số trong ITEM_REGISTRY."""
        if amount <= 0:
            await ctx.send("❌ Số lượng phải lớn hơn 0!", delete_after=5.0)
            return

        item = get_item_by_id(item_id)
        if item is None:
            await ctx.send(
                f"❌ Không tìm thấy vật phẩm với ID `{item_id}`! "
                f"Dùng `y!shop` để xem danh sách.",
                delete_after=5.0,
            )
            return

        if item["price"] is None:
            await ctx.send(
                f"❌ **{item['name']}** không có bán trong cửa hàng!",
                delete_after=5.0,
            )
            return

        # Route đến đúng handler theo category
        if item["category"] == "event":
            await _buy_event_item(ctx, self.bot, item, amount)
        elif item["category"] == "farm":
            await _buy_farm_item(ctx, self.bot, item, amount)
        elif item["category"] == "blackmarket":
            await _buy_blackmarket_item(ctx, self.bot, item, amount)
        else:
            await ctx.send("❌ Danh mục không hợp lệ.", delete_after=5.0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot))
