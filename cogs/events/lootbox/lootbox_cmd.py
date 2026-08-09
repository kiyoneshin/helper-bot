"""
lootbox_cmd.py — Cog lệnh Lootbox & Pray
==========================================
klootbox (klb): open, info, history
kpray: +1 luck, cooldown 30p
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from cogs.common.db import (
    execute_db,
    fetchrow_db,
    add_event_points,
    get_or_create_event_profile,
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data

from .lootbox_config import (
    TIER_NAMES, TIER_EMOJIS, TIER_COLORS, TIER_PRICES,
    LB_GODLY,
    parse_tier, roll_lootbox, roll_godly_bonus,
    PRAY_COOLDOWN_MINUTES,
    LB_BUY_COOLDOWN_HOURS,
    LUCK_MAX_CAP,
)
from .lootbox_ui import (
    build_open_result_embed,
    build_bulk_result_embed,
    build_info_embed,
    build_history_embed,
    LootboxInfoView,
)

log = logging.getLogger("LootboxCog")
UTC7 = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

async def _get_luck_and_boost(bot, uid: str) -> tuple[int, bool]:
    """Lấy luck_points và kiểm tra item 6 còn active không."""
    row = await fetchrow_db(bot, "SELECT luck_points, inventory FROM event_profiles WHERE discord_id = $1", uid)
    if not row:
        return 0, False
    luck = int(row["luck_points"] or 0)
    inv = row["inventory"]
    if isinstance(inv, str):
        inv = json.loads(inv)
    boost_until_ts = inv.get("lb_boost_until")
    item6_active = False
    if boost_until_ts:
        boost_until = datetime.fromtimestamp(boost_until_ts, tz=timezone.utc)
        item6_active = datetime.now(timezone.utc) < boost_until
    return luck, item6_active


async def _add_lootbox_to_inventory(bot, uid: str, tier_id: int, qty: int = 1) -> None:
    """Thêm lootbox vào inventory JSONB của event_profiles."""
    row = await fetchrow_db(bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
    if not row:
        return
    inv = row["inventory"]
    if isinstance(inv, str):
        inv = json.loads(inv)
    inv = inv or {}
    lb_key = f"lb_{tier_id}"
    inv[lb_key] = inv.get(lb_key, 0) + qty
    await execute_db(
        bot,
        "UPDATE event_profiles SET inventory = $1::jsonb WHERE discord_id = $2",
        json.dumps(inv), uid,
    )


async def _consume_lootbox_from_inventory(bot, uid: str, tier_id: int, qty: int = 1) -> bool:
    """Tiêu lootbox từ inventory. Trả về False nếu không đủ."""
    row = await fetchrow_db(bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
    if not row:
        return False
    inv = row["inventory"]
    if isinstance(inv, str):
        inv = json.loads(inv)
    inv = inv or {}
    lb_key = f"lb_{tier_id}"
    current = int(inv.get(lb_key, 0))
    if current < qty:
        return False
    inv[lb_key] = current - qty
    await execute_db(
        bot,
        "UPDATE event_profiles SET inventory = $1::jsonb WHERE discord_id = $2",
        json.dumps(inv), uid,
    )
    return True


async def _save_lb_history(bot, uid: str, tier_id: int, drops, count: int = 1) -> None:
    """Lưu lịch sử mở lootbox."""
    drops_json = json.dumps([
        {"item": d.item_id, "name": d.name, "icon": d.icon, "qty": d.qty, "rank": d.rank}
        for d in drops
    ])
    await execute_db(
        bot,
        "INSERT INTO lootbox_history (discord_id, tier_id, drops, count) VALUES ($1, $2, $3::jsonb, $4)",
        uid, tier_id, drops_json, count,
    )


async def _apply_drops_to_farm(bot, uid: str, drops, bonus: Optional[dict] = None) -> None:
    """Thêm vật phẩm nhận được vào farm_data.inventory."""
    farm_data = await get_farm_data(bot, uid)
    inv = farm_data.setdefault("inventory", {})
    for drop in drops:
        inv[drop.item_id] = inv.get(drop.item_id, 0) + drop.qty

    # Vật phẩm BM / hạt giống đặc biệt từ godly bonus
    if bonus and bonus["type"] in ("bm_item", "seed"):
        item_key = f"item_{bonus['item_id']}" if bonus["type"] == "bm_item" else f"seed_star"
        # Lưu vào event_profiles inventory
        row = await fetchrow_db(bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        if row:
            e_inv = row["inventory"]
            if isinstance(e_inv, str):
                e_inv = json.loads(e_inv)
            e_inv = e_inv or {}
            e_inv[item_key] = e_inv.get(item_key, 0) + 1
            await execute_db(
                bot,
                "UPDATE event_profiles SET inventory = $1::jsonb WHERE discord_id = $2",
                json.dumps(e_inv), uid,
            )
    await save_farm_data(bot, uid, farm_data)


# ---------------------------------------------------------------------------
# COG
# ---------------------------------------------------------------------------

class LootboxCog(commands.Cog):
    """Hệ Thống Lootbox & Pray"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────────
    # LỆNH kpray
    # ─────────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="pray", aliases=["caunguyen", "prayer"])
    async def pray_cmd(self, ctx: commands.Context):
        """Cầu nguyện để tăng Luck. Luck giúp tăng tỉ lệ drop lootbox."""
        uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, uid)

        row = await fetchrow_db(
            self.bot,
            "SELECT luck_points, last_pray FROM event_profiles WHERE discord_id = $1",
            uid,
        )
        if not row:
            await ctx.send("❌ Không tìm thấy hồ sơ của bạn.", ephemeral=True)
            return

        last_pray = row["last_pray"]
        luck = int(row["luck_points"] or 0)
        now = datetime.now(timezone.utc)

        if last_pray:
            if last_pray.tzinfo is None:
                last_pray = last_pray.replace(tzinfo=timezone.utc)
            elapsed = now - last_pray
            if elapsed < timedelta(minutes=PRAY_COOLDOWN_MINUTES):
                next_pray = last_pray + timedelta(minutes=PRAY_COOLDOWN_MINUTES)
                ts = int(next_pray.timestamp())
                embed = discord.Embed(
                    title="🙏 Cầu Nguyện",
                    description=f"Bạn đã cầu nguyện rồi. Quay lại <t:{ts}:R> nhé!",
                    color=discord.Color.orange(),
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

        new_luck = luck + 1
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET luck_points = $1, last_pray = $2 WHERE discord_id = $3",
            new_luck, now, uid,
        )

        bar_filled = min(new_luck, LUCK_MAX_CAP)
        dots = LUCK_MAX_CAP // 10
        filled_dots = bar_filled // dots
        bar = "🟡" * filled_dots + "⚫" * (10 - filled_dots)
        embed = discord.Embed(
            title="🙏 Cầu Nguyện Thành Công!",
            description=(
                f"✨ **+1 Luck** — Tổng: **{new_luck}** / {LUCK_MAX_CAP}\n"
                f"`{bar}` {new_luck}/{LUCK_MAX_CAP}\n\n"
                f"*Luck tăng tỉ lệ drop lootbox từ fish/mine/chop và tỉ lệ nhận đồ hiếm khi mở hộp.*\n"
                f"*Có thể cầu nguyện lại sau **{PRAY_COOLDOWN_MINUTES} phút**.*"
            ),
            color=0xffd700,
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────────────────
    # LỆNH klootbox / klb
    # ─────────────────────────────────────────────────────────────────────
    @commands.group(name="lootbox", aliases=["lb"], invoke_without_command=True)
    async def lootbox_group(self, ctx: commands.Context):
        """Hệ Thống Lootbox. Dùng {prefix}lb open/info/history."""
        prefix = ctx.prefix or ctx.bot.custom_prefix
        embed = discord.Embed(
            title="<:gift_00_symbol:1536003307011842099> Hệ Thống Lootbox",
            description=(
                f"**Lệnh có sẵn:**\n"
                f"• `{prefix}lb open <tier> [số_lượng]` — Mở lootbox\n"
                f"• `{prefix}lb info [tier]` — Xem bảng tỉ lệ\n"
                f"• `{prefix}lb history [tier]` — Lịch sử & thống kê\n\n"
                f"**Viết tắt tier:** `c` Common | `u` Uncommon | `r` Rare | `e` Epic | `l` Legendary | `g` Godly\n"
                f"**VD:** `{prefix}lb open e 3` — Mở 3 Epic box"
            ),
            color=0xffd700,
        )
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────────────────
    # Subcommand: open
    # ─────────────────────────────────────────────────────────────────────
    @lootbox_group.command(name="open", aliases=["mo"])
    async def open_cmd(self, ctx: commands.Context, tier_raw: str, qty: int = 1):
        """Mở lootbox. VD: {prefix}lb open epic 3 | {prefix}lb open e 1"""
        tier_id = parse_tier(tier_raw)
        if tier_id is None:
            await ctx.send(
                f"❌ Tier không hợp lệ! Dùng: `c/u/r/e/l/g` hoặc tên đầy đủ như `epic`.",
                ephemeral=True,
            )
            return

        if qty < 1 or qty > 50:
            await ctx.send("❌ Số lượng phải từ 1 đến 50.", ephemeral=True)
            return

        uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, uid)

        # Kiểm tra inventory
        row = await fetchrow_db(
            self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid
        )
        if not row:
            await ctx.send("❌ Không tìm thấy hồ sơ!", ephemeral=True)
            return

        inv = row["inventory"]
        if isinstance(inv, str):
            inv = json.loads(inv)
        inv = inv or {}
        lb_key = f"lb_{tier_id}"
        has_qty = int(inv.get(lb_key, 0))

        if has_qty < qty:
            tier_name = TIER_NAMES[tier_id]
            tier_emoji = TIER_EMOJIS[tier_id]
            await ctx.send(
                f"❌ Bạn chỉ có **{has_qty}x {tier_emoji} {tier_name}** lootbox, "
                f"không đủ để mở {qty}x!",
                ephemeral=True,
            )
            return

        # Animation reveal
        emoji = TIER_EMOJIS[tier_id]
        embed_opening = discord.Embed(
            title=f"Đang mở {qty}x {TIER_NAMES[tier_id]}...",
            description=f"{emoji} **Rương đang được mở... Hãy chờ chút nhé!** ✨",
            color=TIER_COLORS[tier_id]
        )
        embed_opening.set_image(url="https://cdn.discordapp.com/emojis/1535664849017774080.gif")
        msg = await ctx.send(embed=embed_opening)
        await asyncio.sleep(2.5)

        luck, item6_active = await _get_luck_and_boost(self.bot, uid)

        all_drops: list = []
        all_bonuses: list = []
        for _ in range(qty):
            drop = roll_lootbox(tier_id, luck=luck, item6_active=item6_active)
            all_drops.append([drop])
            bonus = roll_godly_bonus() if tier_id == LB_GODLY else None
            all_bonuses.append(bonus)

        # Tiêu inventory
        inv[lb_key] = has_qty - qty
        await execute_db(
            self.bot,
            "UPDATE event_profiles SET inventory = $1::jsonb WHERE discord_id = $2",
            json.dumps(inv), uid,
        )

        # Áp dụng drops
        flat_drops = [d for drops in all_drops for d in drops]
        for i, drops in enumerate(all_drops):
            await _apply_drops_to_farm(self.bot, uid, drops, all_bonuses[i])
            if all_bonuses[i] and all_bonuses[i]["type"] == "points":
                await add_event_points(self.bot, uid, all_bonuses[i]["value"], is_earned=True)

        # Lưu lịch sử 1 record gộp qty
        await _save_lb_history(self.bot, uid, tier_id, flat_drops, count=qty)

        # Gửi embed kết quả
        if qty == 1:
            embed = build_open_result_embed(ctx.author, tier_id, flat_drops, all_bonuses[0])
        else:
            embed = build_bulk_result_embed(ctx.author, tier_id, all_drops, all_bonuses)

        await msg.edit(content=None, embed=embed)

    # ─────────────────────────────────────────────────────────────────────
    # Subcommand: info
    # ─────────────────────────────────────────────────────────────────────
    @lootbox_group.command(name="info", aliases=["tyle", "xem"])
    async def info_cmd(self, ctx: commands.Context, tier_raw: Optional[str] = None):
        """Xem bảng tỉ lệ drop. VD: {prefix}lb info epic | {prefix}lb info"""
        if tier_raw:
            tier_id = parse_tier(tier_raw)
            if tier_id is None:
                await ctx.send("❌ Tier không hợp lệ!", ephemeral=True)
                return
            embed = build_info_embed(tier_id)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="📊 Bảng Tỉ Lệ Lootbox",
                description="Chọn tier bên dưới để xem chi tiết:",
                color=0x7289da,
            )
            view = LootboxInfoView(ctx.author.id)
            await ctx.send(embed=embed, view=view)

    # ─────────────────────────────────────────────────────────────────────
    # Subcommand: history
    # ─────────────────────────────────────────────────────────────────────
    @lootbox_group.command(name="history", aliases=["lichsu", "hs"])
    async def history_cmd(self, ctx: commands.Context, tier_raw: Optional[str] = None):
        """Xem lịch sử 20 lần mở gần nhất + thống kê."""
        uid = str(ctx.author.id)

        if tier_raw:
            tier_id = parse_tier(tier_raw)
            if tier_id is None:
                await ctx.send("❌ Tier không hợp lệ!", ephemeral=True)
                return
            tiers_to_show = [tier_id]
        else:
            # Hiện tất cả tier, gộp lại
            from .lootbox_config import LB_COMMON, LB_UNCOMMON, LB_RARE, LB_EPIC, LB_LEGENDARY, LB_GODLY
            tiers_to_show = [LB_COMMON, LB_UNCOMMON, LB_RARE, LB_EPIC, LB_LEGENDARY, LB_GODLY]

        if tier_raw:
            tier_id = parse_tier(tier_raw)  # type: ignore
            rows = await self.bot.db_pool.fetch(
                "SELECT drops, opened_at, count FROM lootbox_history "
                "WHERE discord_id = $1 AND tier_id = $2 "
                "ORDER BY opened_at DESC LIMIT 20",
                uid, tier_id,
            )
            records = []
            for r in rows:
                drops = r["drops"]
                if isinstance(drops, str):
                    drops = json.loads(drops)
                records.append({"drops": drops, "opened_at": str(r["opened_at"]), "count": r["count"]})
            embed = build_history_embed(ctx.author, tier_id, records)
            await ctx.send(embed=embed)
        else:
            # Summary gộp
            rows = await self.bot.db_pool.fetch(
                "SELECT tier_id, COUNT(*) as sessions, SUM(count) as total "
                "FROM lootbox_history WHERE discord_id = $1 GROUP BY tier_id",
                uid,
            )
            embed = discord.Embed(
                title="📋 Tổng Lịch Sử Mở Lootbox",
                color=0x7289da,
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            if not rows:
                embed.description = "Bạn chưa mở lootbox nào cả."
            else:
                lines = []
                for r in rows:
                    tid = r["tier_id"]
                    name = TIER_NAMES.get(tid, f"#{tid}")
                    emoji = TIER_EMOJIS.get(tid, "📦")
                    lines.append(f"{emoji} **{name}**: {r['total']} hộp ({r['sessions']} phiên)")
                embed.description = "\n".join(lines)
            embed.set_footer(text="Dùng {prefix}lb history <tier> để xem chi tiết từng loại.")
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LootboxCog(bot))

async def setup(bot: commands.Bot):
    await bot.add_cog(LootboxCog(bot))
