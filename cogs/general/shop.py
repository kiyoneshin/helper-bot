"""
shop_cog.py — Cog Cửa Hàng Hợp Nhất (kshop & kbuy)
=====================================================
Hiển thị toàn bộ shop theo Dropdown Menu, mua đồ bằng ID số.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    deduct_event_points,
    execute_db,
    fetchrow_db,
    fetchval_db,
    get_or_create_event_profile,
)
from cogs.common.item_config import (
    ITEM_REGISTRY,
    ItemEntry,
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
    return f"{price:,} điểm" if price is not None else "Không bán"


def build_shop_embed(category: str, author: discord.Member | discord.User, prefix: str = 'k') -> discord.Embed:
    """Tạo Embed danh sách cửa hàng theo category."""
    CATEGORY_META = {
        "event":       ("<:icon_08_shop:1536025530728587384> Cửa Hàng Sự Kiện",       0x9b59b6),
        "farm":        ("<:icon_03_farm_field:1536017183216369815> Cửa Hàng Nông Trại",      0xe67e22),
        "blackmarket": ("<:icon_05_bm:1536017187243032736> Cửa Hàng Chợ Đen",        0x2b2d31),
        "ring":        ("<:icon_02_ring:1536017180951318528> Tiệm Kim Hoàn",           0xffb6c1),
        "gift":        ("<:gift_00_symbol:1536003307011842099> Quà Tặng",                0xff69b4),
        "lootbox":     ("<:lootbox:1535664857276489749> Cửa Hàng Lootbox",        0x3498db),
    }
    title, color = CATEGORY_META.get(category, ("🛒 Cửa Hàng", 0x7289da))

    embed = discord.Embed(title=title, color=color)
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    items = get_buyable_items(category)
    if items:
        lines = []
        for item in items:
            desc = item['description']
            if category == "ring":
                try:
                    from cogs.events.social.marriage import RING_BUFFS
                    buffs = RING_BUFFS.get(item["id"])
                    if buffs:
                        buff_texts = []
                        if buffs["dtm_bonus"] > 0: buff_texts.append(f"+{int(buffs['dtm_bonus']*100)}% DTM")
                        if buffs["cd_reduction"] > 0: buff_texts.append(f"-{int(buffs['cd_reduction']*100)}% Cooldown")
                        if buffs["work_bonus"] > 1.0: buff_texts.append(f"x{buffs['work_bonus']} Lương")
                        if buff_texts:
                            desc = f"Buff: {', '.join(buff_texts)}"
                except ImportError:
                    pass
            
            lines.append(
                f"`[{item['id']}]` {item['icon']} **{item['name']}** | "
                f"Giá: **{_format_price(item['price'])}** | {desc}"
            )
        embed.description = "\n".join(lines)
    else:
        embed.description = "*Không có vật phẩm nào để mua ở mục này.*"

    if category == "blackmarket":
        embed.set_footer(text=f"💡 Lưu ý: Cửa hàng này chỉ để xem. Bạn chỉ có thể mua bằng lệnh {prefix}ebuy khi Chợ Đêm mở ({prefix}choden)!")
    else:
        embed.set_footer(text=f"💡 Hướng dẫn: Dùng lệnh {prefix}buy <id> [số_lượng] để mua vật phẩm.")
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
                emoji="<:icon_08_shop:1536025530728587384>",
                description="Vé xổ số và vật phẩm sự kiện",
                default=(current_category == "event"),
            ),
            discord.SelectOption(
                label="Nông trại",
                value="farm",
                emoji="<:icon_03_farm_field:1536017183216369815>",
                description="Hạt giống cây trồng",
                default=(current_category == "farm"),
            ),
            discord.SelectOption(
                label="Chợ đen",
                value="blackmarket",
                emoji="<:icon_05_bm:1536017187243032736>",
                description="Vật phẩm đặc biệt — phá phách đối thủ",
                default=(current_category == "blackmarket"),
            ),
            discord.SelectOption(
                label="Nhẫn Cưới & Trang sức",
                value="ring",
                emoji="<:icon_02_ring:1536017180951318528>",
                description="Nhẫn cưới",
                default=(current_category == "ring"),
            ),
            discord.SelectOption(
                label="Quà Tặng",
                value="gift",
                emoji="<:gift_00_symbol:1536003307011842099>",
                description="Quà để tặng người thương (lệnh gift)",
                default=(current_category == "gift"),
            ),
            discord.SelectOption(
                label="Lootbox",
                value="lootbox",
                emoji="<:icon_01_chest:1536017178615091311>",
                description="Hộp quà may mắn (có giới hạn mua)",
                default=(current_category == "lootbox"),
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
                "<:symbol_wrong:1536629915598848072> Đây không phải cửa hàng của bạn!", ephemeral=True
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
    item: ItemEntry,
    amount: int,
) -> None:
    """Xử lý mua vật phẩm sự kiện (ID 0–9)."""
    if item["id"] == 0:
        # ID 0 = Vé Xổ Số — gọi helper lottery
        lottery_cog: Lottery | None = bot.cogs.get("Lottery")  # type: ignore
        is_locked = lottery_cog.is_locked if lottery_cog else False
        ok, msg = await buy_lottery_tickets(bot, str(ctx.author.id), amount, is_locked)
        await ctx.send(f"{ctx.author.mention} {msg}", delete_after=10.0)
    elif item["category"] in ["event", "ring", "gift", "lootbox"]:
        uid = str(ctx.author.id)
        price = item["price"]
        if price is None:
            await ctx.send("<:symbol_wrong:1536629915598848072> Vật phẩm này không thể mua!", delete_after=5.0)
            return

        total = price * amount

        # Special logic for ID 4 (Role Vĩnh Viễn)
        if item["id"] == 4:
            count = await fetchval_db(
                bot,
                "SELECT COUNT(*) FROM event_profiles WHERE COALESCE((inventory->>'item_4')::int, 0) > 0"
            )
            if count is not None and count >= 5:
                await ctx.send("<:symbol_wrong:1536629915598848072> Rất tiếc, vật phẩm này đã đạt giới hạn 5 người đổi!", delete_after=5.0)
                return

        # Special logic for lootbox 6h cooldown
        from datetime import datetime, timezone, timedelta
        if item["category"] == "lootbox":
            row = await fetchrow_db(bot, "SELECT lb_buy_cooldown FROM event_profiles WHERE discord_id = $1", uid)
            if row:
                cd_data = row["lb_buy_cooldown"]
                if isinstance(cd_data, str):
                    cd_data = json.loads(cd_data)
                cd_data = cd_data or {}
                
                last_buy_ts = max(cd_data.values()) if cd_data else None
                now = datetime.now(timezone.utc)
                if last_buy_ts:
                    last_buy = datetime.fromtimestamp(last_buy_ts, tz=timezone.utc)
                    from cogs.events.lootbox.lootbox_config import LB_BUY_COOLDOWN_HOURS
                    if now < last_buy + timedelta(hours=LB_BUY_COOLDOWN_HOURS):
                        next_time = last_buy + timedelta(hours=LB_BUY_COOLDOWN_HOURS)
                        await ctx.send(f"<:symbol_wrong:1536629915598848072> Bạn đã mua một hộp quà (bất kỳ) gần đây rồi. Mỗi {LB_BUY_COOLDOWN_HOURS} tiếng chỉ được mua 1 hộp. Hãy quay lại vào <t:{int(next_time.timestamp())}:R>!", delete_after=10.0)
                        return
                
                # Lưu lại biến để cập nhật sau khi trừ điểm thành công
                new_cd_data = cd_data.copy()
                # Cập nhật cooldown cho hộp này
                new_cd_data[str(item["id"])] = int(now.timestamp())

        await get_or_create_event_profile(bot, uid)
        ok = await deduct_event_points(bot, uid, total)
        if not ok:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không đủ điểm! Cần **{total:,}** điểm để mua **{amount}x {item['name']}**.",
                delete_after=5.0
            )
            return

        if item["category"] == "lootbox" and 'new_cd_data' in locals():
            await execute_db(bot, "UPDATE event_profiles SET lb_buy_cooldown = $1::jsonb WHERE discord_id = $2", json.dumps(new_cd_data), uid)

        # Write to inventory
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

        # Notify
        if item["id"] == 5:
            await ctx.send(
                f"<:symbol_right:1536629912515903578> {ctx.author.mention} Đã mua thành công **{item['name']}**! "
                f"Yêu cầu của bạn đã được ghi nhận. Ban Quản Trị sẽ sớm liên hệ."
            )
            await ctx.channel.send(
                f"👑 Chúc mừng {ctx.author.mention} vừa đổi thành công **{item['name']}** "
                f"(với giá {total:,} điểm)! Hãy chờ Admin trao giải nhé!"
            )
        else:
            await ctx.send(
                f"<:symbol_right:1536629912515903578> {ctx.author.mention} Đã mua **{amount}x {item['icon']} {item['name']}** "
                f"với giá **{total:,}** điểm. Vật phẩm đã nằm trong `{bot.custom_prefix}inv`!",
                delete_after=10.0,
            )
    else:
        await ctx.send(
            f"<:symbol_wrong:1536629915598848072> Vật phẩm **{item['name']}** không thể mua trong shop hiện tại.",
            delete_after=5.0,
        )


async def _buy_farm_item(
    ctx: commands.Context,
    bot: commands.Bot,
    item: ItemEntry,
    amount: int,
) -> None:
    """Xử lý mua hạt giống Farm (ID 51-60) - gọi buy_seed trong farm_db."""
    # db_key của farm item là "seed_wheat", "seed_sunflower", v.v.
    seed_key = item["db_key"]  # "seed_wheat"
    seed_id = seed_key.removeprefix("seed_")  # "wheat"

    ok, msg = await buy_seed(bot, str(ctx.author.id), seed_id, amount)
    status = "<:symbol_right:1536629912515903578>" if ok else "<:symbol_wrong:1536629915598848072>"
    await ctx.send(f"{status} {ctx.author.mention} {msg}", delete_after=10.0)


async def _buy_blackmarket_item(
    ctx: commands.Context,
    bot: commands.Bot,
    item: ItemEntry,
    amount: int,
) -> None:
    """Xử lý mua vật phẩm Chợ đen (ID 20–29)."""
    uid = str(ctx.author.id)
    price = item["price"]
    if price is None:
        await ctx.send("<:symbol_wrong:1536629915598848072> Vật phẩm này không thể mua!", delete_after=5.0)
        return

    total = price * amount
    await get_or_create_event_profile(bot, uid)
    ok = await deduct_event_points(bot, uid, total)
    if not ok:
        await ctx.send(
            f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không đủ điểm! Cần **{total:,}** điểm để mua "
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
        f"<:symbol_right:1536629912515903578> {ctx.author.mention} Đã mua **{amount}x {item['icon']} {item['name']}** "
        f"với giá **{total:,}** điểm. Dùng `{bot.custom_prefix}use {item['id']}` để sử dụng!",
        delete_after=10.0,
    )


# ============================================================
# COG CHÍNH
# ============================================================

class ShopCog(commands.Cog):
    """Cog Cửa Hàng Hợp Nhất."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="shop",
        aliases=["cuahang", "store"],
        description="🛒 Xem cửa hàng vật phẩm. Mở nhanh tab: shop [farm/bm/ring/gift]",
    )
    async def shop_cmd(self, ctx: commands.Context, tab: Optional[str] = None) -> None:
        """Mở cửa hàng tổng hợp bằng Dropdown UI."""
        category = "event"
        if tab:
            tab = tab.lower()
            if tab in ["farm", "nongtrai"]: category = "farm"
            elif tab in ["bm", "blackmarket", "choden"]: category = "blackmarket"
            elif tab in ["ring", "nhan", "nhẫn"]: category = "ring"
            elif tab in ["gift", "qua", "quà"]: category = "gift"
            elif tab in ["event", "sukien"]: category = "event"
            elif tab in ["lb", "lootbox", "hopqua"]: category = "lootbox"

        embed = build_shop_embed(category, ctx.author, prefix=ctx.prefix or ctx.bot.custom_prefix)
        view = ShopView(ctx.author, category)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="buy",
        aliases=["mua"],
        description="🛒 Mua vật phẩm theo ID. Cú pháp: buy <id> [số_lượng]",
    )
    async def buy_cmd(self, ctx: commands.Context, item_id: int, amount: int = 1) -> None:
        """Mua vật phẩm theo ID số trong ITEM_REGISTRY."""
        if amount <= 0:
            await ctx.send("<:symbol_wrong:1536629915598848072> Số lượng mua phải lớn hơn 0!", delete_after=5.0)
            return

        item = get_item_by_id(item_id)
        if item is None:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Không tìm thấy vật phẩm với ID `{item_id}`! "
                f"Dùng `{self.bot.custom_prefix}shop` để xem danh sách.",
                delete_after=5.0,
            )
            return

        # Block black market buying
        if item["category"] == "blackmarket":
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Bạn không thể mua trực tiếp vật phẩm chợ đen ở đây! Hãy chờ Chợ Đêm mở (`{self.bot.custom_prefix}choden`) và dùng lệnh `{self.bot.custom_prefix}ebuy`.",
                delete_after=7.0,
            )
            return

        if item["price"] is None:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> **{item['name']}** không có bán trong cửa hàng!",
                delete_after=5.0,
            )
            return

        # Route đến đúng handler theo category
        if item["category"] == "lootbox":
            amount = 1  # Force amount to 1 for lootboxes to prevent buying multiple in one cooldown
            await _buy_event_item(ctx, self.bot, item, amount)
        elif item["category"] in ["event", "ring", "gift"]:
            await _buy_event_item(ctx, self.bot, item, amount)
        elif item["category"] == "farm":
            await _buy_farm_item(ctx, self.bot, item, amount)
        elif item["category"] == "blackmarket":
            await _buy_blackmarket_item(ctx, self.bot, item, amount)
        else:
            await ctx.send("<:symbol_wrong:1536629915598848072> Danh mục không hợp lệ.", delete_after=5.0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot))
