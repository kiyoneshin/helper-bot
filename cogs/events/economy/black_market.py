import discord
from discord.ext import commands
import logging
import json
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from cogs.common.db import fetchrow_db, execute_db, get_or_create_event_profile, deduct_event_points

log = logging.getLogger("BlackMarket")

# Múi giờ UTC+7
UTC7 = timezone(timedelta(hours=7))

from cogs.common.item_config import get_items_by_category, ITEM_REGISTRY

# =====================================================================
# II. HÀM HELPER DATABASE - CHỢ NGÀY
# =====================================================================

async def _init_black_market_table(bot: Any) -> None:
    """Khởi tạo bảng black_market_daily nếu chưa tồn tại."""
    await execute_db(
        bot,
        """
        CREATE TABLE IF NOT EXISTS black_market_daily (
            sale_date DATE PRIMARY KEY,
            shop_data JSONB NOT NULL
        );
        """
    )
    log.info("Bảng black_market_daily đã sẵn sàng.")


def _calc_stock(price: int) -> int:
    """Tính tồn kho theo giá vật phẩm."""
    if price < 5000:
        return 10
    elif price < 10000:
        return 5
    else:
        return 2


async def _get_or_refresh_daily_shop(bot: Any) -> Dict[str, Any]:
    """
    Lấy shop hôm nay từ DB. Nếu sang ngày mới, random lại 3 món và lưu DB.
    Trả về shop_data: {"1": {"item_id": ..., "stock": ...}, ...}
    """
    today = datetime.now(UTC7).date()

    row = await fetchrow_db(bot, "SELECT shop_data FROM black_market_daily WHERE sale_date = $1", today)
    if row:
        # Đã có shop hôm nay — parse và kiểm tra định dạng
        try:
            data = json.loads(row['shop_data']) if isinstance(row['shop_data'], str) else row['shop_data']
            # Kiểm tra xem có trường "db_key" của định dạng mới không
            if data and all("db_key" in v for v in data.values()):
                return data
            else:
                log.warning("Định dạng shop_data cũ, sẽ tiến hành làm mới.")
        except Exception as e:
            log.error(f"Lỗi parse shop_data: {e}")

    # Chưa có (hoặc parse lỗi) → Xóa cũ, tạo mới
    await execute_db(bot, "DELETE FROM black_market_daily")

    bm_items = get_items_by_category("blackmarket")
    chosen = random.sample(bm_items, k=3)
    chosen.sort(key=lambda x: x["id"])

    shop_data: Dict[str, Any] = {}
    for item in chosen:
        price = item["price"] or 0
        item_id = str(item["id"])
        shop_data[item_id] = {
            "db_key": item["db_key"],
            "stock": _calc_stock(price),
        }

    await execute_db(
        bot,
        "INSERT INTO black_market_daily (sale_date, shop_data) VALUES ($1, $2::jsonb)",
        today,
        json.dumps(shop_data),
    )
    log.info(f"Chợ Đêm mới ngày {today}: {list(shop_data.keys())}")
    return shop_data


# =====================================================================
# III. COG
# =====================================================================

class BlackMarketCog(commands.Cog):
    def __init__(self, bot: Any):
        self.bot = bot

    async def cog_load(self) -> None:
        """Đảm bảo bảng DB luôn tồn tại trước khi Cog nhận lệnh."""
        await _init_black_market_table(self.bot)

    # ------------------------------------------------------------------
    # LỆNH XEM SHOP: kchoden / kchodem / kblackmarket
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="choden", aliases=["chodem", "blackmarket", "bm"])
    async def black_market_cmd(self, ctx: commands.Context) -> None:
        """Xem Chợ Đêm hôm nay — 3 vật phẩm bí ẩn, số lượng có hạn!"""
        now_vn = datetime.now(UTC7)
        
        # Kiểm tra thời gian mở cửa (00:00 -> 01:59)
        if not (0 <= now_vn.hour < 2):
            # Tính thời gian mở cửa tiếp theo (00:00 UTC+7 ngày mai)
            next_open = (now_vn + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            reset_ts = int(next_open.timestamp())
            embed = discord.Embed(
                title="Chợ Đêm Đã Đóng Cửa",
                description=(
                    "Chợ đêm chỉ hoạt động từ **00:00 đến 02:00 sáng** mỗi ngày.\n\n"
                    f"<:symbol_hour_glass:1537570149215899658> Phiên chợ tiếp theo sẽ mở cửa vào lúc <t:{reset_ts}:F> (tức là **<t:{reset_ts}:R>**).\n"
                    "Hãy trở lại sau nhé!"
                ),
                color=0x2b2d31,
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1513465012344193088/1530634452357742733/pepe-evil.gif?ex=6a6649eb&is=6a64f86b&hm=be3d5c561533f9f25e490ab00930c0a8a12aab0813351080116ee9e19a7c2808&")
            await ctx.send(embed=embed)
            return

        shop_data = await _get_or_refresh_daily_shop(self.bot)

        # Tính thời gian đóng cửa hôm nay (02:00 UTC+7 hôm nay)
        close_time = now_vn.replace(hour=2, minute=0, second=0, microsecond=0)
        close_ts = int(close_time.timestamp())

        embed = discord.Embed(
            title="Chợ Đêm Angelic — Hàng Hiếm Độc Quyền",
            description=(
                "Chợ Đêm chỉ mở mỗi ngày với **3 vật phẩm ngẫu nhiên** và số lượng cực hạn.\n"
                f"Sẽ đóng cửa sau **<t:{close_ts}:R>**.\n\n"
                f"<:symbol_light_bulb:1537739278765924422> Mua nhanh: `{ctx.prefix}ebuy <mã số> [số lượng]`\n"
                f"<:icon_07_inventory:1535664855300710422> Xài item: `{ctx.prefix}use <mã số> [@mục tiêu]`\n\u200b"
            ),
            color=0x2b2d31,
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1513465012344193088/1530634452357742733/pepe-evil.gif?ex=6a6649eb&is=6a64f86b&hm=be3d5c561533f9f25e490ab00930c0a8a12aab0813351080116ee9e19a7c2808&")  # Optional

        for slot_id, slot_info in shop_data.items():
            db_key = slot_info["db_key"]
            stock  = slot_info["stock"]
            
            # Find item from registry
            item_data = ITEM_REGISTRY[int(slot_id)]
            price     = item_data["price"] or 0
            name      = item_data["name"]
            desc      = item_data["description"]
            icon      = item_data["icon"]

            stock_text = f"**{stock}** chiếc" if stock > 0 else "~~Cháy hàng~~"
            embed.add_field(
                name=f"Mã số `[{slot_id}]` — {icon} {name}",
                value=f"Giá: **{price:,}** <:symbol_points_p:1538282388507987989> | Còn lại: {stock_text}\n*{desc}*",
                inline=False,
            )

        embed.set_footer(text="Hàng đã bán hết sẽ không được nhập thêm cho đến ngày mai! 🌸")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # LỆNH MUA NHANH: kebuy <slot_id> [quantity]
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="ebuy", aliases=["muadem", "bmbuy"])
    async def event_buy_cmd(self, ctx: commands.Context, slot_id: str, quantity: int = 1) -> None:
        """Mua vật phẩm từ Chợ Đêm theo mã số ID vật phẩm"""
        now_vn = datetime.now(UTC7)
        if not (0 <= now_vn.hour < 2):
            await ctx.send(f"<:symbol_wrong:1536629915598848072> Chợ Đêm hiện đang đóng cửa! Gõ `{ctx.prefix}choden` để xem thời gian mở lại.", delete_after=5.0)
            return

        uid = str(ctx.author.id)

        # 1. Kiểm tra đầu vào
        if quantity <= 0:
            await ctx.send("<:symbol_wrong:1536629915598848072> Số lượng mua phải lớn hơn 0!", delete_after=5.0)
            return

        shop_data = await _get_or_refresh_daily_shop(self.bot)

        if slot_id not in shop_data:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Mã số không hợp lệ! Vui lòng nhập đúng mã số vật phẩm đang bán trong `{ctx.prefix}choden`.",
                delete_after=5.0,
            )
            return

        # 2. Kiểm tra tồn kho
        slot_info = shop_data[slot_id]
        db_key    = slot_info["db_key"]
        stock     = slot_info["stock"]
        
        item_data = ITEM_REGISTRY[int(slot_id)]
        item_name = item_data["name"]
        price     = item_data["price"] or 0

        if stock == 0:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> **{item_name}** đã **cháy hàng** rồi! Chờ ngày mai nhé.",
                delete_after=5.0,
            )
            return

        if quantity > stock:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Chỉ còn **{stock}** chiếc **{item_name}**, không đủ để mua **{quantity}** chiếc!",
                delete_after=5.0,
            )
            return

        # 3. Thanh toán
        total_price = price * quantity
        await get_or_create_event_profile(self.bot, uid)
        success = await deduct_event_points(self.bot, uid, total_price)
        if not success:
            await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Số dư không đủ! Bạn cần **{total_price:,}** <:symbol_points_p:1538282388507987989> để mua {quantity}x **{item_name}**.",
                delete_after=5.0,
            )
            return

        # 4. Trừ tồn kho — cập nhật shop_data trong DB
        shop_data[slot_id]["stock"] -= quantity
        today = datetime.now(UTC7).date()
        await execute_db(
            self.bot,
            "UPDATE black_market_daily SET shop_data = $2::jsonb WHERE sale_date = $1",
            today,
            json.dumps(shop_data),
        )

        # 5. Cộng vào inventory người dùng
        inv_row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        inv: Dict[str, int] = {}
        if inv_row and inv_row["inventory"]:
            try:
                inv = json.loads(inv_row["inventory"]) if isinstance(inv_row["inventory"], str) else inv_row["inventory"]
            except Exception as e:
                log.error(f"Lỗi parse inventory khi ebuy cho {uid}: {e}")

        inv[db_key] = inv.get(db_key, 0) + quantity
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1",
            uid,
            json.dumps(inv),
        )

        # 6. Thông báo thành công
        await ctx.send(
            f"Mua thành công **{quantity}x {item_name}** với giá **{total_price:,}** <:symbol_points_p:1538282388507987989>. "
            f"Hãy dùng `{ctx.prefix}use {slot_id}` để xài!"
        )

async def setup(bot: Any) -> None:
    await bot.add_cog(BlackMarketCog(bot))
