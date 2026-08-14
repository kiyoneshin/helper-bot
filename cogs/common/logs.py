import discord
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

log = logging.getLogger("StaffLog")

# ── Kênh log ẩn dành cho Admin ────────────────────────────────────────
LOG_CHANNEL_ID = 1527697681978495027

# ── Múi giờ UTC+7 ──────────────────────────────────────────────────────
UTC7 = timezone(timedelta(hours=7))

# ── Màu sắc chuẩn ─────────────────────────────────────────────────────
COLOR_ADD    = 0x2ecc71   #  Xanh lá    — Thêm mới hồ sơ
COLOR_EDIT   = 0xf1c40f   #  Vàng       — Chỉnh sửa hồ sơ / Đánh giá
COLOR_SYNC   = 0x3498db   #  Xanh dương — Đồng bộ biệt danh
COLOR_DELETE = 0xe74c3c   #  Đỏ         — Xóa / Rời server


# =============================================================================
# HÀM GỬI LOG TẬP TRUNG (KHÔNG LÀM CRASH LUỒNG CHÍNH)
# =============================================================================

async def send_staff_log(bot: Any, embed: discord.Embed) -> None:
    """
    Gửi Embed vào kênh log ẩn.
    Cô lập hoàn toàn: nếu thất bại chỉ ghi logging, không raise exception.
    """
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        log.error(f"[StaffLog] Không thể gửi log vào kênh {LOG_CHANNEL_ID}: {e}")


def _now_str() -> str:
    """Trả về chuỗi thời gian hiện tại theo UTC+7."""
    return datetime.now(UTC7).strftime("%d/%m/%Y %H:%M:%S")


# =============================================================================
# CÁC HÀM BUILD EMBED CHUẨN HÓA THEO TỪNG LOẠI SỰ KIỆN
# =============================================================================

def build_log_add(
    discord_id: str,
    display_name: str,
    role: str,
    description: Optional[str],
    contact: Optional[str],
    tags: list,
) -> discord.Embed:
    """Thêm Mới Hồ Sơ (kadd)"""
    embed = discord.Embed(
        title="Nhật Ký: Đăng Ký Hồ Sơ Mới",
        color=COLOR_ADD,
    )
    embed.add_field(name="Thao tác", value="Đăng ký Staff", inline=True)
    embed.add_field(name="Người thực hiện", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(name="Chức vụ được cấp", value=f"`{role.upper()}`", inline=True)
    embed.add_field(name="Tên hiển thị", value=display_name, inline=True)
    embed.add_field(
        name="Giới thiệu",
        value=description or "*Chưa có*",
        inline=False,
    )
    embed.add_field(name="Liên hệ", value=contact or "*Chưa có*", inline=True)
    embed.add_field(
        name="Tags",
        value=", ".join(tags) if tags else "*Chưa có*",
        inline=True,
    )
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_edit_info(
    discord_id: str,
    old_name: str,
    new_name: str,
    old_desc: str,
    new_desc: str,
    old_contact: str,
    new_contact: str,
) -> discord.Embed:
    """Chỉnh Sửa Thông Tin Hồ Sơ (kset → Sửa Thông Tin)"""
    embed = discord.Embed(
        title="✏️ Nhật Ký: Cập Nhật Thông Tin Hồ Sơ",
        color=COLOR_EDIT,
    )
    embed.add_field(name="Thao tác", value="Sửa thông tin hồ sơ", inline=True)
    embed.add_field(name="Người thực hiện", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    if old_name != new_name:
        embed.add_field(name="Tên hiển thị", value=f"`{old_name}` ➔ `{new_name}`", inline=False)
    if old_desc != new_desc:
        embed.add_field(
            name="Giới thiệu",
            value=f"**Cũ:** {old_desc or '*(trống)*'}\n**Mới:** {new_desc or '*(trống)*'}",
            inline=False,
        )
    if old_contact != new_contact:
        embed.add_field(
            name="Liên hệ",
            value=f"**Cũ:** {old_contact or '*(trống)*'}\n**Mới:** {new_contact or '*(trống)*'}",
            inline=False,
        )

    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_edit_tags(
    discord_id: str,
    old_tags: list,
    new_tags: list,
) -> discord.Embed:
    """Chỉnh Sửa Tags (kset → Sửa Tags)"""
    embed = discord.Embed(
        title="<:icon_05_bm:1536017187243032736> Nhật Ký: Cập Nhật Tags",
        color=COLOR_EDIT,
    )
    embed.add_field(name="Thao tác", value="Sửa danh sách Tags", inline=True)
    embed.add_field(name="Người thực hiện", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(
        name="Tags cũ",
        value=", ".join(old_tags) if old_tags else "*(trống)*",
        inline=False,
    )
    embed.add_field(
        name="Tags mới",
        value=", ".join(new_tags) if new_tags else "*(trống)*",
        inline=False,
    )
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_edit_photos(
    discord_id: str,
    action: str,  # "add" | "delete"
    count: int,
    total_after: int,
) -> discord.Embed:
    """Thêm / Xóa Ảnh (kset → Cập nhật Ảnh)"""
    action_str = f"Thêm {count} ảnh mới" if action == "add" else f"Xóa 1 ảnh"
    embed = discord.Embed(
        title="Nhật Ký: Cập Nhật Ảnh Profile",
        color=COLOR_EDIT,
    )
    embed.add_field(name="Thao tác", value=action_str, inline=True)
    embed.add_field(name="Người thực hiện", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(name="Tổng ảnh sau thao tác", value=str(total_after), inline=True)
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_vote(
    voter_id: str,
    target_id: str,
    target_name: str,
    new_score: float,
    review_text: str,
    is_update: bool,
    old_score: Optional[str] = None,
) -> discord.Embed:
    """Gửi Mới / Cập Nhật Đánh Giá (Vote)"""
    action_str = "Chỉnh sửa đánh giá cũ" if is_update else "Gửi đánh giá mới"
    embed = discord.Embed(
        title="<a:symbol_star_yellow:1537739289834553385> Nhật Ký: Đánh Giá Staff",
        color=COLOR_EDIT,
    )
    embed.add_field(name="Thao tác", value=action_str, inline=True)
    embed.add_field(name="Người đánh giá (Voter)", value=f"<@{voter_id}> (`{voter_id}`)", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Nhân sự được đánh giá", value=f"<@{target_id}> ({target_name})", inline=False)

    if is_update and old_score is not None:
        rating_str = f"<a:symbol_star_yellow:1537739289834553385> {old_score} ➔ {new_score} / 5.0"
    else:
        rating_str = f"<a:symbol_star_yellow:1537739289834553385> {new_score} / 5.0"
    embed.add_field(name="Mức điểm (Rating)", value=rating_str, inline=True)
    embed.add_field(name="Nội dung nhận xét", value=review_text, inline=False)
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_nickname_sync(
    discord_id: str,
    old_name: str,
    new_name: str,
) -> discord.Embed:
    """Đồng Bộ Biệt Danh Tự Động (on_member_update)"""
    embed = discord.Embed(
        title="Nhật Ký: Đồng Bộ Biệt Danh",
        color=COLOR_SYNC,
    )
    embed.add_field(name="Thao tác", value="Đồng bộ biệt danh", inline=True)
    embed.add_field(name="Người thực hiện", value="Hệ thống tự động (Auto-Sync)", inline=True)
    embed.add_field(name="Nhân sự", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(name="Biệt danh cũ", value=f"`{old_name}`", inline=True)
    embed.add_field(name="Biệt danh mới", value=f"`{new_name}`", inline=True)
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed


def build_log_delete(
    discord_id: str,
    display_name: str,
    reason: str = "Đã rời server",
) -> discord.Embed:
    """Xóa / Vô hiệu hóa Hồ Sơ"""
    embed = discord.Embed(
        title="Nhật Ký: Hồ Sơ Bị Xóa / Vô Hiệu Hóa",
        color=COLOR_DELETE,
    )
    embed.add_field(name="Thao tác", value="Xóa hồ sơ", inline=True)
    embed.add_field(name="Đối tượng bị xóa", value=f"<@{discord_id}> (`{discord_id}`)", inline=True)
    embed.add_field(name="Tên hiển thị cũ", value=display_name, inline=True)
    embed.add_field(name="Lý do", value=reason, inline=False)
    embed.set_footer(text=f"Hệ thống log tự động • {_now_str()} UTC+7")
    return embed
