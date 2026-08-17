import discord
from discord.ext import commands
from typing import Any, Dict
import json

from cogs.common.db import fetchrow_db, execute_db, get_or_create_event_profile, extract_id
from cogs.events.generals.achievements_config import ACHIEVEMENTS, ACH_CATEGORIES
from cogs.common.item_config import ITEM_REGISTRY

# =====================================================================
# GIAO DIỆN CHỌN DANH MỤC THÀNH TỰU (DROPDOWN)
# =====================================================================
class AchCategorySelect(discord.ui.Select):
    def __init__(self, author: discord.Member | discord.User):
        self.author = author
        options = [
            discord.SelectOption(
                label=name.split(" ", 1)[1],
                value=cat_id,
                emoji=name.split(" ", 1)[0]
            )
            for cat_id, name in ACH_CATEGORIES.items()
        ]
        options.insert(0, discord.SelectOption(label="Bảng Tổng Kết", value="summary", emoji="<:symbol_trophy:1537550568665649232>"))
        super().__init__(
            placeholder="Chọn danh mục thành tựu...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Bạn không có quyền sử dụng menu này!", ephemeral=True)
            
        category = self.values[0]
        
        # Lấy dữ liệu profile
        uid = str(interaction.user.id)
        row = await fetchrow_db(
            interaction.client,
            "SELECT stats, achievements FROM event_profiles WHERE discord_id = $1",
            uid
        )
        
        if not row:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Bạn chưa có hồ sơ Sự Kiện!", ephemeral=True)
            
        try:
            stats = json.loads(row["stats"]) if isinstance(row["stats"], str) else (row["stats"] or {})
            claimed = json.loads(row["achievements"]) if isinstance(row["achievements"], str) else (row["achievements"] or [])
        except:
            stats = {}
            claimed = []
            
        if category == "summary":
            embed = await build_ach_summary_embed(interaction.client, interaction.user, stats, claimed)
        else:
            embed = await build_ach_embed(interaction.client, interaction.user, category, stats, claimed)
        
        # Build view with claim button
        view = AchView(self.author, category, stats, claimed)
        await interaction.response.edit_message(embed=embed, view=view)


class ClaimButton(discord.ui.Button):
    def __init__(self, author: discord.Member | discord.User, category: str, stats: dict, claimed: list):
        # Tính xem có bao nhiêu thành tựu chưa claim mà ĐỦ ĐIỀU KIỆN
        claimable = 0
        for ach_id, ach in ACHIEVEMENTS.items():
            if (category == "summary" or ach["category"] == category) and ach_id not in claimed:
                stat_val = stats.get(ach["stat_key"], 0)
                if stat_val >= ach["target"]:
                    claimable += 1
                    
        disabled = (claimable == 0)
        label = f"Nhận Thưởng ({claimable})" if claimable > 0 else "Chưa có phần thưởng"
        style = discord.ButtonStyle.success if claimable > 0 else discord.ButtonStyle.secondary
        
        super().__init__(label=label, style=style, disabled=disabled, row=1)
        self.author = author
        self.category = category
        self.stats = stats
        self.claimed = claimed
        
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("<:symbol_ban:1537546960003801319> Bạn không có quyền!", ephemeral=True)
            
        uid = str(interaction.user.id)
        
        # Re-fetch in case of concurrent updates
        row = await fetchrow_db(
            interaction.client,
            "SELECT stats, achievements, unlocked_titles FROM event_profiles WHERE discord_id = $1",
            uid
        )
        if not row: return
        
        stats = json.loads(row["stats"]) if isinstance(row["stats"], str) else (row["stats"] or {})
        claimed = json.loads(row["achievements"]) if isinstance(row["achievements"], str) else (row["achievements"] or [])
        titles = json.loads(row["unlocked_titles"]) if isinstance(row["unlocked_titles"], str) else (row["unlocked_titles"] or [])
        
        newly_claimed = []
        reward_messages = []
        
        # Mở kho đồ
        from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data
        farm_data = await get_farm_data(interaction.client, uid)  # type: ignore
        inventory = (farm_data or {}).setdefault("inventory", {})
        
        for ach_id, ach in ACHIEVEMENTS.items():
            if (self.category == "summary" or ach["category"] == self.category) and ach_id not in claimed:
                stat_val = stats.get(ach["stat_key"], 0)
                if stat_val >= ach["target"]:
                    newly_claimed.append(ach_id)
                    claimed.append(ach_id)
                    
                    title = ach["reward_title"]
                    if title not in titles:
                        titles.append(title)
                        
                    lootbox_id, lootbox_qty = ach["reward_lootbox"]
                    str_id = str(lootbox_id)
                    inventory[str_id] = inventory.get(str_id, 0) + lootbox_qty
                    
                    reward_messages.append(f"**{ach['name']}**: Danh hiệu `{title}` + {lootbox_qty}x Lootbox {lootbox_id}")
                    
        if not newly_claimed:
            return await interaction.response.send_message("<:symbol_wrong:1536629915598848072> Có lỗi xảy ra hoặc bạn đã nhận thưởng rồi.", ephemeral=True)
            
        # Update DB
        await execute_db(
            interaction.client,
            "UPDATE event_profiles SET achievements = $1, unlocked_titles = $2 WHERE discord_id = $3",
            json.dumps(claimed), json.dumps(titles), uid
        )
        await save_farm_data(interaction.client, uid, farm_data)  # type: ignore
        
        msg = f"<:symbol_confetti:1537570146313306183> Chúc mừng bạn đã hoàn thành **{len(newly_claimed)}** thành tựu!\n\n" + "\n".join(reward_messages)
        
        if self.category == "summary":
            embed = await build_ach_summary_embed(interaction.client, interaction.user, stats, claimed)
        else:
            embed = await build_ach_embed(interaction.client, interaction.user, self.category, stats, claimed)
            
        view = AchView(self.author, self.category, stats, claimed)
        await interaction.response.edit_message(embed=embed, view=view)
        
        await interaction.followup.send(msg, ephemeral=True)


class AchView(discord.ui.View):
    def __init__(self, author: discord.Member | discord.User, category: str, stats: dict, claimed: list):
        super().__init__(timeout=120.0)
        
        select = AchCategorySelect(author)
        # Set default value in dropdown based on category
        for opt in select.options:
            if opt.value == category:
                opt.default = True
                
        self.add_item(select)
        self.add_item(ClaimButton(author, category, stats, claimed))



    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass


async def build_ach_summary_embed(bot, user, stats: dict, claimed: list) -> discord.Embed:
    # Nếu stat_key là total_earned thì lấy trực tiếp từ DB
    row = await fetchrow_db(bot, "SELECT total_earned FROM event_profiles WHERE discord_id = $1", str(user.id))
    if row:
        stats["total_earned"] = row["total_earned"] or 0
        
    row_love = await fetchrow_db(
        bot,
        "SELECT intimacy_points, pet_level, ring_id FROM marriages WHERE user1_id = $1 OR user2_id = $1",
        str(user.id)
    )
    if row_love:
        stats["intimacy"] = row_love["intimacy_points"] or 0
        stats["pet_level"] = row_love["pet_level"] or 1
        stats["ring_level"] = max(1, (row_love["ring_id"] or 31) - 30)

    total_achievements = len(ACHIEVEMENTS)
    total_claimed = len(claimed)

    embed = discord.Embed(
        description=f"<:symbol_trophy:1537550568665649232> **{total_claimed}/{total_achievements}**\n\nXem chi tiết thành tựu của từng danh mục thông qua Menu lựa chọn bên dưới.\n\u200b",
        color=0xffd700
    )
    embed.set_author(name=f"{user.display_name} — Thành Tựu", icon_url=user.display_avatar.url)
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535664842977976400.png")

    for cat_id, cat_name in ACH_CATEGORIES.items():
        cat_total = 0
        cat_claimed = 0
        for ach_id, ach in ACHIEVEMENTS.items():
            if ach["category"] == cat_id:
                cat_total += 1
                if ach_id in claimed:
                    cat_claimed += 1
                    
        embed.add_field(
            name=f"**{cat_name}**",
            value=f"{cat_claimed}/{cat_total}",
            inline=True
        )

    return embed


async def build_ach_embed(bot, user, category: str, stats: dict, claimed: list) -> discord.Embed:
    # Nếu stat_key là total_earned thì lấy trực tiếp từ DB
    row = await fetchrow_db(bot, "SELECT total_earned FROM event_profiles WHERE discord_id = $1", str(user.id))
    if row:
        stats["total_earned"] = row["total_earned"] or 0
        
    # Tính toán đặc biệt cho love
    if category == "love":
        row_love = await fetchrow_db(
            bot,
            "SELECT intimacy_points, pet_level, ring_id FROM marriages WHERE user1_id = $1 OR user2_id = $1",
            str(user.id)
        )
        if row_love:
            stats["intimacy"] = row_love["intimacy_points"] or 0
            stats["pet_level"] = row_love["pet_level"] or 1
            # Nhẫn level = ring_id - 30 (Vì 31 là cấp 1)
            stats["ring_level"] = max(1, (row_love["ring_id"] or 31) - 30)

    cat_name = ACH_CATEGORIES.get(category, "Thành Tựu")
    parts = cat_name.split(" ", 1)
    if len(parts) == 2:
        emoji_str, cat_label = parts[0], parts[1]
    else:
        emoji_str, cat_label = "", cat_name

    embed = discord.Embed(
        title=f"Bảng Thành Tựu | {cat_label}",
        description="Hoàn thành các cột mốc để nhận phần thưởng Danh Hiệu và Lootbox.\n\n",
        color=0xffd700
    )
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    
    import re
    match = re.search(r"<a?:[^:]+:(\d+)>", emoji_str)
    if match:
        emoji_id = match.group(1)
        ext = "gif" if emoji_str.startswith("<a:") else "png"
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}")
    
    total_in_cat = 0
    claimed_in_cat = 0
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach["category"] == category:
            total_in_cat += 1
            is_claimed = ach_id in claimed
            
            if is_claimed:
                claimed_in_cat += 1
                status_emoji = "<:symbol_right:1536629912515903578>"
                progress_str = f"Hoàn thành ({ach['target']}/{ach['target']})"
            else:
                stat_val = stats.get(ach["stat_key"], 0)
                if stat_val >= ach["target"]:
                    status_emoji = "<:gift_00_symbol:1536003307011842099>" # Ready to claim
                    progress_str = f"Sẵn sàng nhận thưởng! ({stat_val}/{ach['target']})"
                else:
                    status_emoji = "<:symbol_hour_glass:1537570149215899658>"
                    # Rút gọn số hiển thị nếu quá lớn
                    val_display = f"{stat_val:,.0f}" if isinstance(stat_val, (int, float)) else stat_val
                    target_display = f"{ach['target']:,.0f}"
                    progress_str = f"Tiến độ: {val_display}/{target_display}"
                    
            embed.add_field(
                name=f"{status_emoji} {ach['name']}",
                value=f"_{ach['desc']}_\n**Phần thưởng:** `{ach['reward_title']}` + Hộp Quà\n**{progress_str}**",
                inline=False
            )
            
    embed.set_footer(text=f"Hoàn thành: {claimed_in_cat}/{total_in_cat}")
    return embed


class AchievementCog(commands.Cog):
    """Hệ thống Thành Tựu và Danh Hiệu."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.hybrid_command(name="achievements", aliases=["ach", "thanhtuu"])
    async def ach_cmd(self, ctx: commands.Context):
        """Xem Bảng Thành Tựu (Achievements)."""
        uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, uid)
        
        row = await fetchrow_db(
            self.bot,
            "SELECT stats, achievements FROM event_profiles WHERE discord_id = $1",
            uid
        )
        
        stats = json.loads(row["stats"]) if isinstance(row["stats"], str) else (row["stats"] or {})  # type: ignore
        claimed = json.loads(row["achievements"]) if isinstance(row["achievements"], str) else (row["achievements"] or [])  # type: ignore
        
        embed = await build_ach_summary_embed(self.bot, ctx.author, stats, claimed)
        view = AchView(ctx.author, "summary", stats, claimed)
        await ctx.send(embed=embed, view=view)
        
    @commands.hybrid_command(name="title", aliases=["danhhieu"])
    async def title_cmd(self, ctx: commands.Context, action: str = None, *, arg: str = None):  # type: ignore
        """Quản lý Danh Hiệu. Cú pháp: ktitle | ktitle use <tên>"""
        uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, uid)
        
        row = await fetchrow_db(
            self.bot,
            "SELECT title, unlocked_titles FROM event_profiles WHERE discord_id = $1",
            uid
        )
        
        current_title = row["title"] or "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang"  # type: ignore
        titles = json.loads(row["unlocked_titles"]) if isinstance(row["unlocked_titles"], str) else (row["unlocked_titles"] or [])  # type: ignore
        
        if "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang" not in titles:
            titles.insert(0, "<:symbol_heart_breaking:1536296911655673936> Kẻ Lang Thang")
            
        if action and action.lower() in ["use", "equip", "dung", "xai"]:
            if not arg:
                return await ctx.send("<:symbol_wrong:1536629915598848072> Vui lòng nhập tên danh hiệu. Vd: `ktitle use Kẻ Đang Yêu`", ephemeral=True)
                
            # Fuzzy match
            found = None
            for t in titles:
                if arg.lower() in t.lower():
                    found = t
                    break
                    
            if not found:
                return await ctx.send(f"<:symbol_wrong:1536629915598848072> Bạn không sở hữu danh hiệu nào có tên `{arg}`!", ephemeral=True)
                
            await execute_db(
                self.bot,
                "UPDATE event_profiles SET title = $1 WHERE discord_id = $2",
                found, uid
            )
            return await ctx.send(f"<:symbol_right:1536629912515903578> Đã trang bị danh hiệu: **{found}**")
            
        # Hiển thị danh sách
        lines = []
        for t in titles:
            if t == current_title:
                lines.append(f"• **{t}** 👈 (Đang trang bị)")
            else:
                lines.append(f"• {t}")
                
        embed = discord.Embed(
            title="Bộ Sưu Tập Danh Hiệu",
            description="Dùng `ktitle use <tên>` để trang bị.\n\n" + "\n".join(lines),
            color=0xffd700
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementCog(bot))
