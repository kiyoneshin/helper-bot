"""
lootbox_ui.py — Giao diện hệ thống Lootbox
============================================
OpenView animation, BulkResult embed, HistoryView, InfoEmbed.
"""
from __future__ import annotations

import asyncio
import json
import discord
from typing import Optional

from .lootbox_config import (
    TIER_NAMES, TIER_EMOJIS, TIER_COLORS, RANK_COLORS,
    DropItem, LB_GODLY,
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _rank_label(rank: int) -> str:
    labels = {0: "Common", 1: "Uncommon", 2: "Rare", 3: "Epic", 4: "Legendary", 5: "Godly"}
    return labels.get(rank, "???")


def build_open_result_embed(
    author: discord.Member | discord.User,
    tier_id: int,
    drops: list[DropItem],
    bonus: Optional[dict] = None,
) -> discord.Embed:
    """Embed kết quả sau khi mở lootbox."""
    tier_name = TIER_NAMES[tier_id]
    tier_emoji = TIER_EMOJIS[tier_id]
    color = TIER_COLORS[tier_id]

    embed = discord.Embed(
        title=f"{tier_emoji} {tier_name} Lootbox — Kết Quả",
        color=color,
    )
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    lines = []
    for drop in drops:
        rank_dot = RANK_COLORS.get(drop.rank, "⬜")
        lines.append(
            f"{rank_dot} **{drop.qty}x {drop.icon} {drop.name}** "
            f"*(rank {drop.rank} — {_rank_label(drop.rank)})*"
        )

    embed.description = "\n".join(lines) if lines else "*(Không nhận được gì)*"

    if bonus:
        if bonus["type"] == "points":
            embed.add_field(
                name="✨ Godly Bonus!",
                value=f"<:symbol_confetti:1537570146313306183> Nhận thêm **{bonus['value']:,} điểm** sự kiện!",
                inline=False,
            )
        elif bonus["type"] in ("bm_item", "seed"):
            embed.add_field(
                name="✨ Godly Bonus!",
                value=f"<:symbol_confetti:1537570146313306183> Nhận thêm **{bonus['icon']} {bonus['name']}**!",
                inline=False,
            )

    embed.set_footer(text=f"Dùng klootbox history {tier_name.lower()} để xem lịch sử.")
    return embed


def build_bulk_result_embed(
    author: discord.Member | discord.User,
    tier_id: int,
    all_drops: list[list[DropItem]],
    bonuses: list[Optional[dict]],
) -> discord.Embed:
    """Embed gộp kết quả mở nhiều box cùng lúc."""
    tier_name = TIER_NAMES[tier_id]
    tier_emoji = TIER_EMOJIS[tier_id]
    color = TIER_COLORS[tier_id]
    count = len(all_drops)

    embed = discord.Embed(
        title=f"{tier_emoji} <a:chest_opening:1535664849017774080> Mở {count}x {tier_name} Lootbox",
        color=color,
    )
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    # Gộp tất cả drops
    tally: dict[str, tuple[str, str, int, int]] = {}
    for drops in all_drops:
        for drop in drops:
            key = drop.item_id
            if key in tally:
                prev_name, prev_icon, prev_qty, prev_rank = tally[key]
                tally[key] = (prev_name, prev_icon, prev_qty + drop.qty, prev_rank)
            else:
                tally[key] = (drop.name, drop.icon, drop.qty, drop.rank)

    lines = []
    for item_id, (name, icon, qty, rank) in sorted(tally.items(), key=lambda x: -x[1][3]):
        rank_dot = RANK_COLORS.get(rank, "⬜")
        lines.append(f"{rank_dot} **{qty}x {icon} {name}**")

    embed.description = "\n".join(lines) if lines else "*(Không nhận được gì)*"

    # Bonus từ godly
    bonus_lines = []
    for b in bonuses:
        if b is None:
            continue
        if b["type"] == "points":
            bonus_lines.append(f"• **+{b['value']:,} điểm** <:symbol_money_bag:1537567538097954896>")
        else:
            bonus_lines.append(f"• **{b['icon']} {b['name']}**")
    if bonus_lines:
        embed.add_field(name="Godly Bonus", value="\n".join(bonus_lines), inline=False)

    embed.set_footer(text=f"Tổng {count} hộp đã mở.")
    return embed


def build_info_embed(tier_id: int) -> discord.Embed:
    """Embed bảng tỉ lệ drop của 1 tier."""
    from .lootbox_config import TIER_RANK_WEIGHTS, RANK_POOL, TIER_PRICES

    tier_name = TIER_NAMES[tier_id]
    tier_emoji = TIER_EMOJIS[tier_id]
    color = TIER_COLORS[tier_id]
    weights = TIER_RANK_WEIGHTS[tier_id]
    total = sum(weights)

    embed = discord.Embed(
        title=f"{tier_emoji} {tier_name} Lootbox — Bảng Tỉ Lệ Drop",
        color=color,
    )

    rank_labels = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Godly"]
    lines = []
    for rank, w in enumerate(weights):
        if w == 0:
            continue
        pct = w / total * 100
        dot = RANK_COLORS.get(rank, "⬜")
        items = RANK_POOL.get(rank, [])
        items_str = ", ".join(f"{icon}{name}" for _, name, icon in items)
        lines.append(f"{dot} **{rank_labels[rank]}** ({pct:.1f}%): {items_str}")

    embed.description = "\n".join(lines)

    price = TIER_PRICES.get(tier_id)
    if price:
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Giá Mua", value=f"{price:,} điểm (tối đa 1 lần/6h)", inline=True)
    else:
        embed.add_field(name="<:symbol_money_bag:1537567538097954896> Giá Mua", value="Không thể mua — chỉ earn qua hoạt động", inline=True)

    if tier_id == LB_GODLY:
        embed.add_field(
            name="✨ Godly Bonus",
            value="30% điểm event (1k-5k) | 10% thẻ BM | 5% Hạt Giống Ngôi Sao",
            inline=False,
        )

    embed.set_footer(text="💡 Luck từ kpray tăng tỉ lệ drop và tỉ lệ rank cao hơn.")
    return embed


def build_history_embed(
    author: discord.Member | discord.User,
    tier_id: int,
    records: list[dict],
) -> discord.Embed:
    """Embed lịch sử 20 lần mở + thống kê."""
    tier_name = TIER_NAMES[tier_id]
    tier_emoji = TIER_EMOJIS[tier_id]
    color = TIER_COLORS[tier_id]

    embed = discord.Embed(
        title=f"{tier_emoji} Lịch Sử Mở [{tier_name}] — 20 lần gần nhất",
        color=color,
    )
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    if not records:
        embed.description = "Bạn chưa mở hộp này lần nào."
        return embed

    # Thống kê tổng hợp
    total_opened = sum(r.get("count", 1) for r in records)
    rank_sum = 0
    rank_total_items = 0
    item_tally: dict[str, tuple[str, str, int]] = {}

    for rec in records:
        drops = rec.get("drops", [])
        for d in drops:
            item_id = d.get("item")
            qty = d.get("qty", 1)
            rank = d.get("rank", 0)
            rank_sum += rank * qty
            rank_total_items += qty
            if item_id not in item_tally:
                item_tally[item_id] = (d.get("name", item_id), d.get("icon", "📦"), 0)
            name, icon, old_qty = item_tally[item_id]
            item_tally[item_id] = (name, icon, old_qty + qty)

    avg_rank = rank_sum / rank_total_items if rank_total_items > 0 else 0

    # Top items nhận được
    top_items = sorted(item_tally.values(), key=lambda x: -x[2])[:8]
    top_str = "\n".join(f"{icon} **{qty}x** {name}" for name, icon, qty in top_items)

    embed.add_field(
        name="<:symbol_chart:1536317815336869918> Thống Kê",
        value=(
            f"**Tổng mở:** {total_opened} hộp\n"
            f"**Rank TB nhận được:** {avg_rank:.2f}\n"
        ),
        inline=True,
    )
    embed.add_field(
        name="<:icon_07_inventory:1535664855300710422> Đồ Nhận Nhiều Nhất",
        value=top_str or "*(chưa có)*",
        inline=True,
    )

    # 5 lần mở gần nhất dạng ngắn gọn
    history_lines = []
    for i, rec in enumerate(records[:5]):
        opened_at = rec.get("opened_at", "")[:10]
        drops = rec.get("drops", [])
        count = rec.get("count", 1)
        summary = ", ".join(
            f"{d.get('icon','')} {d.get('qty',1)}x" for d in drops[:3]
        )
        if len(drops) > 3:
            summary += f" +{len(drops)-3} nữa"
        history_lines.append(f"**#{i+1}** [{opened_at}] ×{count}: {summary}")

    embed.add_field(
        name="<:symbol_boards:1536007665153474681> 5 Lần Gần Nhất",
        value="\n".join(history_lines) or "*(trống)*",
        inline=False,
    )

    embed.set_footer(text="Gõ klb history <tier> để xem chi tiết.")
    return embed


# ---------------------------------------------------------------------------
# INFO VIEW — Dropdown chọn tier
# ---------------------------------------------------------------------------

class LootboxInfoSelect(discord.ui.Select):
    def __init__(self, author_id: int):
        self.author_id = author_id
        from .lootbox_config import LB_COMMON, LB_UNCOMMON, LB_RARE, LB_EPIC, LB_LEGENDARY, LB_GODLY
        options = [
            discord.SelectOption(
                label="Common", 
                value=str(LB_COMMON), 
                emoji="<:lb_01_common:1535552629092913172>"
            ),
            discord.SelectOption(
                label="Uncommon", 
                value=str(LB_UNCOMMON), 
                emoji="<:lb_02_uncommon:1535552631257174138>"
            ),
            discord.SelectOption(
                label="Rare", 
                value=str(LB_RARE), 
                emoji="<:lb_03_rare:1535552633660776509>"
            ),
            discord.SelectOption(
                label="Epic", 
                value=str(LB_EPIC), 
                emoji="<:lb_04_epic:1535552635778760774>"
            ),
            discord.SelectOption(
                label="Legendary", 
                value=str(LB_LEGENDARY), 
                emoji="<:lb_05_legendary:1535552637850624011>"
            ),
            discord.SelectOption(
                label="Godly", 
                value=str(LB_GODLY), 
                emoji="<:lb_06_godly:1535552639834783764>"
            ),
        ]
        super().__init__(placeholder="Chọn tier để xem tỉ lệ...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("<:symbol_ban:1537546960003801319> Đây không phải lượt của bạn!", ephemeral=True)
            return
        tier_id = int(self.values[0])
        embed = build_info_embed(tier_id)
        await interaction.response.edit_message(embed=embed)


class LootboxInfoView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.add_item(LootboxInfoSelect(author_id))

    async def on_timeout(self):
        self.clear_items()
