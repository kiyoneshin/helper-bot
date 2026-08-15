"""
skill_cmd.py — Hệ Thống Kỹ Năng (Skills) — Stardew Valley Style
=================================================================
Lệnh: {prefix}skill [skill_name | reset [skill_name]]
"""
import discord
from discord.ext import commands
import json

from cogs.common.db import fetchrow_db, execute_db, deduct_event_points, get_or_create_event_profile
from cogs.events.skills.skills_config import (
    SKILLS, PROFESSIONS, LEVEL_XP_TOTAL, MAX_LEVEL, RESET_COST,
    get_level_from_xp, get_skill_level_info, get_professions_for_skill,
    SKILL_PER_LEVEL_BONUS,
)
from cogs.events.skills.skills_db import (
    get_skills, save_skills, set_profession, reset_profession,
    get_active_professions, check_pending_professions,
)


# ---------------------------------------------------------------------------
# HELPERS UI
# ---------------------------------------------------------------------------

def _progress_bar(current: int, total: int, length: int = 12) -> str:
    if total <= 0:
        return "█" * length
    filled = round(current / total * length)
    filled = min(filled, length)
    return "█" * filled + "░" * (length - filled)


def _skill_alias_map() -> dict[str, str]:
    """Map alias tiếng Việt / tiếng Anh về skill_id."""
    return {
        "farming": "farming", "farm": "farming", "nongtra": "farming",
        "nông trại": "farming", "nongtraì": "farming",
        "mining": "mining", "mine": "mining", "mo": "mining", "khaithac": "mining",
        "chopping": "chopping", "chop": "chopping", "wood": "chopping",
        "woodcutting": "chopping", "chatgo": "chopping",
        "fishing": "fishing", "fish": "fishing", "caucá": "fishing", "cauca": "fishing",
    }


# ---------------------------------------------------------------------------
# EMBED: OVERVIEW (tổng quan tất cả skills)
# ---------------------------------------------------------------------------

async def build_overview_embed(user: discord.Member | discord.User, skills_data: dict) -> discord.Embed:
    embed = discord.Embed(
        description=(
            f"Xem chi tiết của từng kỹ năng bên dưới hoặc dùng lệnh `skill <tên>`\n\u200b"
        ),
        color=0xf39c12,
    )
    embed.set_author(name=f"{user.display_name} — Kỹ Năng", icon_url=user.display_avatar.url)
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1537550568665649232.png")

    for skill_id, skill_cfg in SKILLS.items():
        skill = skills_data.get(skill_id, {})
        level = skill.get("level", 0)
        xp = skill.get("xp", 0)
        _, xp_in, xp_need = get_level_from_xp(xp)

        if level >= MAX_LEVEL:
            bar = _progress_bar(1, 1)
            xp_str = "MAX"
        else:
            bar = _progress_bar(xp_in, xp_need)
            xp_str = f"{xp_in:,}/{xp_need:,}"

        # Kiểm tra profession pending
        pending_note = ""
        if level >= 10 and skill.get("profession_10") is None:
            pending_note = " ⚠️ **Chưa chọn Nghề (Lv10)**"
        elif level >= 5 and skill.get("profession_5") is None:
            pending_note = " ⚠️ **Chưa chọn Nghề (Lv5)**"

        # Bonus mô tả ngắn
        per_level = SKILL_PER_LEVEL_BONUS.get(skill_id, {})
        bonus_desc = skill_cfg["per_level_bonus"]

        embed.add_field(
            name=f"{skill_cfg['icon']} **{skill_cfg['name']}** — Lv.{level}{pending_note}",
            value=(
                f"`{bar}` {xp_str} XP\n"
                f"_{bonus_desc}_"
            ),
            inline=False,
        )

    embed.set_footer(text=f"Dùng 'skill reset <tên>' để reset Nghề Nghiệp (Giá: {RESET_COST:,} <:symbol_points_p:1538282388507987989>).")
    return embed


# ---------------------------------------------------------------------------
# EMBED: SKILL DETAIL (chi tiết 1 skill)
# ---------------------------------------------------------------------------

async def build_detail_embed(user: discord.Member | discord.User, skills_data: dict, skill_id: str) -> discord.Embed:
    skill_cfg = SKILLS[skill_id]
    skill = skills_data.get(skill_id, {})
    level = skill.get("level", 0)
    xp = skill.get("xp", 0)
    _, xp_in, xp_need = get_level_from_xp(xp)

    if level >= MAX_LEVEL:
        bar = _progress_bar(1, 1)
        xp_str = f"{xp_in:,}/{xp_need:,} (MAX)"
        pct_str = "100.00%"
    else:
        bar = _progress_bar(xp_in, xp_need)
        pct = (xp_in / xp_need * 100) if xp_need > 0 else 0
        xp_str = f"{xp_in:,}/{xp_need:,}"
        pct_str = f"{pct:.2f}%"

    embed = discord.Embed(color=skill_cfg["color"])
    embed.set_author(name=f"{user.display_name} — Kỹ Năng", icon_url=user.display_avatar.url)

    # Header
    embed.description = (
        f"## {skill_cfg['icon']} {skill_cfg['name']}\n"
        f"**Level:** {level} / {MAX_LEVEL}\n"
        f"**XP:** {xp_str} ({pct_str})\n"
        f"`{bar}`\n\n"
        f"_{skill_cfg['description']}_\n"
        f"📖 **Nguồn XP:** {skill_cfg['xp_source']}\n"
        f"📈 **Passive:** {skill_cfg['per_level_bonus']}"
    )

    # Profession Lv5
    prof5_id = skill.get("profession_5")
    if level < 5:
        prof5_str = "_Đạt Lv.5 để mở khóa_"
    elif prof5_id is None:
        prof5_str = "⚠️ **Chưa chọn!** Bấm nút bên dưới để chọn."
    else:
        p = PROFESSIONS.get(prof5_id, {})
        prof5_str = f"**{p.get('icon','')} {p.get('name','')}** — {p.get('description','')}"

    # Profession Lv10
    prof10_id = skill.get("profession_10")
    if level < 10:
        prof10_str = "_Đạt Lv.10 để mở khóa_"
    elif prof10_id is None:
        prof10_str = "⚠️ **Chưa chọn!** Bấm nút bên dưới để chọn."
    else:
        p = PROFESSIONS.get(prof10_id, {})
        prof10_str = f"**{p.get('icon','')} {p.get('name','')}** — {p.get('description','')}"

    embed.add_field(name="🏅 Lv.5 — Nghề Nghiệp", value=prof5_str, inline=False)
    embed.add_field(name="👑 Lv.10 — Nghề Nghiệp", value=prof10_str, inline=False)

    return embed


# ---------------------------------------------------------------------------
# VIEW: SKILL OVERVIEW (với Dropdown chọn skill)
# ---------------------------------------------------------------------------

class SkillSelect(discord.ui.Select):
    def __init__(self, author: discord.Member | discord.User, skills_data: dict):
        self.author = author
        self.skills_data = skills_data
        options = [
            discord.SelectOption(label="Tổng Quan", value="overview", emoji="📊", description="Xem tổng quan tất cả kỹ năng"),
        ]
        for skill_id, skill_cfg in SKILLS.items():
            skill = skills_data.get(skill_id, {})
            level = skill.get("level", 0)
            options.append(discord.SelectOption(
                label=f"{skill_cfg['name']} — Lv.{level}",
                value=skill_id,
                emoji=skill_cfg["icon"],
                description=skill_cfg["description"][:50],
            ))
        super().__init__(
            placeholder="Chọn kỹ năng để xem chi tiết...",
            min_values=1, max_values=1,
            options=options, row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Không phải menu của bạn!", ephemeral=True)

        chosen = self.values[0]
        # Refresh skills
        skills_data = await get_skills(interaction.client, str(self.author.id))

        if chosen == "overview":
            embed = await build_overview_embed(self.author, skills_data)
            view = SkillOverviewView(self.author, skills_data)
        else:
            embed = await build_detail_embed(self.author, skills_data, chosen)
            view = SkillDetailView(self.author, skills_data, chosen)

        await interaction.response.edit_message(embed=embed, view=view)


class SkillOverviewView(discord.ui.View):
    def __init__(self, author: discord.Member | discord.User, skills_data: dict):
        super().__init__(timeout=120.0)
        self.add_item(SkillSelect(author, skills_data))

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# VIEW: SKILL DETAIL (với nút chọn Profession)
# ---------------------------------------------------------------------------

class ProfessionChoiceView(discord.ui.View):
    """View hiện khi người chơi chọn Profession — có 2 nút bấm."""

    def __init__(
        self,
        author: discord.Member | discord.User,
        skills_data: dict,
        skill_id: str,
        tier: int,
        professions: list[dict],
    ):
        super().__init__(timeout=60.0)
        self.author = author
        self.skills_data = skills_data
        self.skill_id = skill_id
        self.tier = tier

        for prof in professions:
            btn = discord.ui.Button(
                label=f"{prof['icon']} {prof['name']}",
                style=discord.ButtonStyle.primary,
                custom_id=prof["id"],
            )
            btn.callback = self._make_callback(prof)
            self.add_item(btn)

        # Nút hủy
        cancel_btn = discord.ui.Button(label="Hủy", style=discord.ButtonStyle.secondary, row=1)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    def _make_callback(self, prof: dict):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.author.id:
                return await interaction.response.send_message("❌ Không phải menu của bạn!", ephemeral=True)

            ok = await set_profession(interaction.client, str(self.author.id), self.skill_id, self.tier, prof["id"])
            if not ok:
                return await interaction.response.send_message("❌ Không thể chọn profession này!", ephemeral=True)

            skills_data = await get_skills(interaction.client, str(self.author.id))
            embed = await build_detail_embed(self.author, skills_data, self.skill_id)
            view = SkillDetailView(self.author, skills_data, self.skill_id)
            await interaction.response.edit_message(
                content=f"✅ Đã chọn nghề **{prof['icon']} {prof['name']}**!",
                embed=embed,
                view=view,
            )
            self.stop()
        return _cb

    async def _cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌", ephemeral=True)
        skills_data = await get_skills(interaction.client, str(self.author.id))
        embed = await build_detail_embed(self.author, skills_data, self.skill_id)
        view = SkillDetailView(self.author, skills_data, self.skill_id)
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        self.stop()


class ChooseProfession5Button(discord.ui.Button):
    def __init__(self, author, skills_data, skill_id):
        super().__init__(label="Chọn Nghề Lv.5", style=discord.ButtonStyle.success, emoji="🏅", row=1)
        self.author = author
        self.skills_data = skills_data
        self.skill_id = skill_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌", ephemeral=True)
        profs = get_professions_for_skill(self.skill_id, 5)
        view = ProfessionChoiceView(self.author, self.skills_data, self.skill_id, 5, profs)
        skill_cfg = SKILLS[self.skill_id]
        embed = discord.Embed(
            title=f"{skill_cfg['icon']} Chọn Nghề Nghiệp Lv.5 — {skill_cfg['name']}",
            description="Lựa chọn sẽ **ảnh hưởng** đến các Profession ở Lv.10. Hãy chọn cẩn thận!",
            color=skill_cfg["color"],
        )
        for p in profs:
            embed.add_field(
                name=f"{p['icon']} {p['name']}",
                value=p["description"],
                inline=False,
            )
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class ChooseProfession10Button(discord.ui.Button):
    def __init__(self, author, skills_data, skill_id):
        super().__init__(label="Chọn Nghề Lv.10", style=discord.ButtonStyle.success, emoji="👑", row=1)
        self.author = author
        self.skills_data = skills_data
        self.skill_id = skill_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌", ephemeral=True)
        skill = self.skills_data.get(self.skill_id, {})
        parent = skill.get("profession_5")
        profs = get_professions_for_skill(self.skill_id, 10, parent)
        view = ProfessionChoiceView(self.author, self.skills_data, self.skill_id, 10, profs)
        skill_cfg = SKILLS[self.skill_id]
        embed = discord.Embed(
            title=f"{skill_cfg['icon']} Chọn Nghề Nghiệp Lv.10 — {skill_cfg['name']}",
            description="Đây là bước cuối cùng trong nhánh nghề nghiệp của bạn.",
            color=skill_cfg["color"],
        )
        for p in profs:
            embed.add_field(
                name=f"{p['icon']} {p['name']}",
                value=p["description"],
                inline=False,
            )
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class SkillDetailView(discord.ui.View):
    def __init__(self, author: discord.Member | discord.User, skills_data: dict, skill_id: str):
        super().__init__(timeout=120.0)
        skill = skills_data.get(skill_id, {})
        level = skill.get("level", 0)

        # Nút chọn profession (chỉ hiện nếu đủ điều kiện)
        if level >= 5 and skill.get("profession_5") is None:
            self.add_item(ChooseProfession5Button(author, skills_data, skill_id))
        if level >= 10 and skill.get("profession_5") is not None and skill.get("profession_10") is None:
            self.add_item(ChooseProfession10Button(author, skills_data, skill_id))

        # Dropdown quay lại
        self.add_item(SkillSelect(author, skills_data))
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# VIEW: RESET CONFIRM
# ---------------------------------------------------------------------------

class ResetConfirmView(discord.ui.View):
    def __init__(self, author, skill_id: str):
        super().__init__(timeout=30.0)
        self.author = author
        self.skill_id = skill_id
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Xác Nhận Reset", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌", ephemeral=True)

        uid = str(self.author.id)
        # Trừ điểm
        ok = await deduct_event_points(interaction.client, uid, RESET_COST)
        if not ok:
            await interaction.response.edit_message(
                content=f"<:symbol_wrong:1536629915598848072> Không đủ điểm! Cần **{RESET_COST:,}** <:symbol_points_p:1538282388507987989>.",
                view=None,
            )
            return

        await reset_profession(interaction.client, uid, self.skill_id)
        skill_cfg = SKILLS[self.skill_id]
        skills_data = await get_skills(interaction.client, uid)
        embed = await build_detail_embed(self.author, skills_data, self.skill_id)
        view = SkillDetailView(self.author, skills_data, self.skill_id)
        await interaction.response.edit_message(
            content=f"<:symbol_right:1536629912515903578> Đã reset Nghề Nghiệp **{skill_cfg['icon']} {skill_cfg['name']}**! Trừ **{RESET_COST:,}** <:symbol_points_p:1538282388507987989>.",
            embed=embed,
            view=view,
        )
        self.stop()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌", ephemeral=True)
        await interaction.response.edit_message(content="Đã hủy reset.", view=None, embed=None)
        self.stop()


# ---------------------------------------------------------------------------
# COG
# ---------------------------------------------------------------------------

class SkillCog(commands.Cog):
    """Hệ Thống Kỹ Năng — Stardew Valley Style."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="skill",
        aliases=["skills", "kynang"],
        help="Xem kỹ năng. Cú pháp: {prefix}skill | {prefix}skill <tên> | {prefix}skill reset [tên]"
    )
    async def skill_cmd(self, ctx: commands.Context, *args):
        uid = str(ctx.author.id)
        await get_or_create_event_profile(self.bot, uid)
        skills_data = await get_skills(self.bot, uid)

        alias_map = _skill_alias_map()

        # Không có arg → Overview
        if not args:
            embed = await build_overview_embed(ctx.author, skills_data)
            view = SkillOverviewView(ctx.author, skills_data)
            await ctx.send(embed=embed, view=view)
            return

        first_arg = args[0].lower().strip()

        # reset [skill_name]
        if first_arg == "reset":
            if len(args) >= 2:
                skill_name = " ".join(args[1:]).lower().strip()
                skill_id = alias_map.get(skill_name)
            else:
                skill_id = None

            if skill_id is None:
                # Hiện danh sách skill có thể reset
                lines = []
                for sid, scfg in SKILLS.items():
                    sk = skills_data.get(sid, {})
                    lv = sk.get("level", 0)
                    if lv >= 5:
                        p5 = sk.get("profession_5")
                        p10 = sk.get("profession_10")
                        p5_name = PROFESSIONS[p5]["name"] if p5 else "Chưa có"
                        p10_name = PROFESSIONS[p10]["name"] if p10 else "Chưa có"
                        lines.append(
                            f"{scfg['icon']} **{scfg['name']}** (Lv{lv}) — "
                            f"Lv5: {p5_name} | Lv10: {p10_name}"
                        )
                if not lines:
                    return await ctx.send(
                        f"<:symbol_wrong:1536629915598848072> Bạn chưa có kỹ năng nào đủ **Lv.5** để reset nghề!"
                    )
                embed = discord.Embed(
                    title="<:symbol_reload:1536007679640600648> Reset Nghề Nghiệp",
                    description=f"**Giá:** {RESET_COST:,} <:symbol_points_p:1538282388507987989>\n\n"
                                "Dùng `skill reset <tên>` để reset. Ví dụ: `skill reset mining`\n\n"
                                + "\n".join(lines),
                    color=0xe74c3c,
                )
                await ctx.send(embed=embed)
                return

            # Kiểm tra điều kiện
            sk = skills_data.get(skill_id, {})
            if sk.get("level", 0) < 5:
                scfg = SKILLS[skill_id]
                return await ctx.send(
                    f"<:symbol_wrong:1536629915598848072> Kỹ năng **{scfg['name']}** chưa đủ **Lv.5** để reset nghề!"
                )

            scfg = SKILLS[skill_id]
            p5 = sk.get("profession_5")
            p10 = sk.get("profession_10")
            p5_name = PROFESSIONS[p5]["name"] if p5 else "Chưa có"
            p10_name = PROFESSIONS[p10]["name"] if p10 else "Chưa có"

            embed = discord.Embed(
                title=f"<:symbol_alert:1537546957885542450> Xác Nhận Reset — {scfg['icon']} {scfg['name']}",
                description=(
                    f"Bạn sắp **reset** toàn bộ nghề nghiệp của kỹ năng **{scfg['name']}**.\n\n"
                    f"• Lv.5: **{p5_name}** → Mất\n"
                    f"• Lv.10: **{p10_name}** → Mất\n\n"
                    f"**Chi phí:** {RESET_COST:,} <:symbol_points_p:1538282388507987989>\n\n"
                    "_Hãy chọn lại nghề nghiệp sau khi reset._"
                ),
                color=0xe74c3c,
            )
            view = ResetConfirmView(ctx.author, skill_id)
            await ctx.send(embed=embed, view=view)
            return

        # skill <tên> → Detail view
        skill_name = " ".join(args).lower().strip()
        skill_id = alias_map.get(skill_name)

        if skill_id is None:
            valid = ", ".join(f"`{k}`" for k in SKILLS)
            return await ctx.send(
                f"<:symbol_wrong:1536629915598848072> Tên kỹ năng không hợp lệ! Các kỹ năng có sẵn: {valid}"
            )

        embed = await build_detail_embed(ctx.author, skills_data, skill_id)
        view = SkillDetailView(ctx.author, skills_data, skill_id)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(SkillCog(bot))
