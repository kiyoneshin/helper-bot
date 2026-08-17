import discord
from discord.ext import commands
from typing import Any, Dict

from .woodcutting_config import (
    STAMINA_PER_CHOP, WOODCUTTING_LOOT, AXE_NAMES,
    get_woodcutting_loot, get_woodcutting_display_weights, get_woodcutting_effective_weights
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA
from cogs.events.mining.mining_ui import _mins_to_full
from cogs.common.db import update_event_stat
from cogs.events.skills.skills_config import CHOPPING_XP
from cogs.events.skills.skills_db import add_skill_xp, get_skills, has_profession

def _stamina_bar(stamina: int, bar_len: int = 10) -> str:
    filled = round(stamina / MAX_STAMINA * bar_len)
    return "🟩" * filled + "⬛" * (bar_len - filled)

def build_woodcutting_embed(
    author: discord.Member | discord.User,
    stamina: int,
    farm_data: Dict[str, Any],
    regen_interval: int = 18,
    boosts: dict = None,  # type: ignore
    skills_data: dict = None,  # type: ignore
) -> discord.Embed:
    axe_level = int(farm_data.get("axe_level", 1))
    axe_name = AXE_NAMES.get(axe_level, f"Lv{axe_level}")

    # Tính stamina_cost thực tế
    effective_stamina_cost = STAMINA_PER_CHOP
    if boosts and "stamina_discount" in boosts:
        effective_stamina_cost = max(1, effective_stamina_cost - int(boosts["stamina_discount"]["value"]))
    # Gatherer profession: giảm thêm 1
    if skills_data:
        from cogs.events.skills.skills_db import has_profession
        if has_profession(skills_data, "chopping", "gatherer"):
            effective_stamina_cost = max(1, effective_stamina_cost - 1)

    embed = discord.Embed(
        title="Rừng Sâu (Woodcutting)",
        description=(
            f"Chào mừng **{author.display_name}** đến với khu rừng bí ẩn!\n"
            f"Hãy đốn củi để tìm vật liệu. Mỗi lần chặt tốn **{effective_stamina_cost}** thể lực.\n"
        ),
        color=0x27ae60,
    )

    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina, regen_interval)})" if stamina < MAX_STAMINA else "<:symbol_right:1536629912515903578> Đã đầy"
    
    embed.add_field(
        name="<:symbol_stamina:1536644916502077480> Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )
    
    embed.add_field(
        name="<:symbol_00_woodcutting:1536007697491558491> Rìu Hiện Tại",
        value=f"**{axe_name}** (Lv{axe_level})",
        inline=True,
    )

    # Hiển thị tỉ lệ thực tế nếu có buff
    if boosts is not None or skills_data is not None:
        display_weights = get_woodcutting_effective_weights(axe_level, boosts or {}, skills_data or {})
        label = "<:symbol_log:1536007701518229544> Tỉ Lệ Rớt (Thực Tế)"
    else:
        display_weights = get_woodcutting_display_weights(axe_level)
        label = "<:symbol_log:1536007701518229544> Tỉ Lệ Rớt (Base)"

    loot_lines = [
        f"{item['icon']} **{item['name']}** — {display_weights[item_id]}%"
        for item_id, item in WOODCUTTING_LOOT.items()
    ]
    embed.add_field(name=label, value="\n".join(loot_lines), inline=True)

    inventory = farm_data.get("inventory", {})
    inv_lines = [
        f"{item['icon']} {item['name']}: **{inventory.get(item_id, 0)}**"
        for item_id, item in WOODCUTTING_LOOT.items()
        if inventory.get(item_id, 0) > 0
    ]
    if inv_lines:
        embed.add_field(name="<:icon_07_inventory:1535664855300710422> Kho Gỗ Của Bạn", value="\n".join(inv_lines), inline=False)

    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660965637652510.gif")
    embed.set_footer(text=f"Dùng kbag để bán vật phẩm. Thể lực hồi 1 điểm mỗi {regen_interval} giây.")
    return embed

class WoodcuttingView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any] = None, regen_interval: int = 18):  # type: ignore
        super().__init__(timeout=120.0)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.regen_interval = regen_interval
        self.chop_btn.disabled = (stamina < STAMINA_PER_CHOP)

    @discord.ui.button(label="Chặt Cây", emoji="<:button_woodcutting:1536007674674806915>", style=discord.ButtonStyle.success)
    async def chop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("<:symbol_ban:1537546960003801319> Khu rừng của người khác, cấm chặt trộm!", ephemeral=True)
            return

        from cogs.common.db import get_active_boosts
        boosts = await get_active_boosts(self.bot, self.user_id)
        skills_data = await get_skills(self.bot, self.user_id)
        stamina_cost = STAMINA_PER_CHOP
        if "stamina_discount" in boosts:
            stamina_cost = max(1, stamina_cost - int(boosts["stamina_discount"]["value"]))
        # Gatherer profession: giảm thêm 1 thể lực
        if has_profession(skills_data, "chopping", "gatherer"):
            stamina_cost = max(1, stamina_cost - 1)
            
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < stamina_cost:
            button.disabled = True
            farm_data = await get_farm_data(self.bot, self.user_id)
            await interaction.response.edit_message(embed=build_woodcutting_embed(self.author, current_stamina, farm_data, self.regen_interval, boosts=boosts, skills_data=skills_data), view=self)
            await interaction.followup.send(f"<:symbol_wrong:1536629915598848072> Bạn đã **kiệt sức**! Hãy đợi thể lực hồi phục.\n*(Hồi đầy sau: {_mins_to_full(current_stamina, self.regen_interval)})*", ephemeral=True)
            return

        farm_data = await get_farm_data(self.bot, self.user_id)
        new_stamina = current_stamina - stamina_cost
        farm_data["stamina"] = new_stamina
        axe_level = int(farm_data.get("axe_level", 1))

        loot_id, quantity = get_woodcutting_loot(axe_level, boosts, skills_data)
        loot_info = WOODCUTTING_LOOT[loot_id]

        inventory = farm_data.setdefault("inventory", {})
        inventory[loot_id] = inventory.get(loot_id, 0) + quantity

        # Lootbox hook
        from cogs.events.lootbox.lootbox_cmd import _get_luck_and_boost, _add_lootbox_to_inventory
        from cogs.events.lootbox.lootbox_config import get_activity_lootbox_drop, TIER_EMOJIS, TIER_NAMES
        luck, boost_active = await _get_luck_and_boost(self.bot, self.user_id)
        lb_tier = get_activity_lootbox_drop("chop", luck, boost_active, boosts, skills_data)
        lb_msg = ""
        if lb_tier:
            await _add_lootbox_to_inventory(self.bot, self.user_id, lb_tier, 1)
            lb_msg = f"\n<:gift_00_symbol:1536003307011842099> **Rớt thêm:** 1x {TIER_EMOJIS[lb_tier]} {TIER_NAMES[lb_tier]}"
            
        # Tracker cross-drop
        tracker_msg = ""
        import random
        if has_profession(skills_data, "chopping", "tracker") and random.random() < 0.25:
            if random.random() < 0.5:
                # Mine
                from cogs.events.mining.mining_config import get_mining_loot, MINING_LOOT
                pickaxe_level = int(farm_data.get("pickaxe_level", 1))
                t_loot_id, t_qty = get_mining_loot(pickaxe_level, boosts, skills_data)
                t_info = MINING_LOOT[t_loot_id]
            else:
                # Fish
                from cogs.events.fishing.fishing_config import get_fishing_loot, FISH_LOOT
                rod_level = int(farm_data.get("fishing_rod", 1))
                t_loot_id, _, t_qty = get_fishing_loot(rod_level, 3.0, boosts, skills_data)
                t_info = FISH_LOOT[t_loot_id]
                
            inventory[t_loot_id] = inventory.get(t_loot_id, 0) + t_qty
            tracker_msg = f"\n<:symbol_arrow_right:1538646237757186078> **Thợ Sưu Tầm:** Rớt thêm {t_qty}x {t_info['icon']} {t_info['name']}"

        await save_farm_data(self.bot, self.user_id, farm_data)

        # Skill XP
        xp_gained = CHOPPING_XP.get(loot_id, 1) * quantity
        levelup_info = await add_skill_xp(self.bot, self.user_id, "chopping", xp_gained)

        self.chop_btn.disabled = (new_stamina < stamina_cost)
        new_embed = build_woodcutting_embed(self.author, new_stamina, farm_data, self.regen_interval, boosts=boosts, skills_data=skills_data)
        await interaction.response.edit_message(embed=new_embed, view=self)

        levelup_str = ""
        if levelup_info:
            from cogs.events.skills.skills_config import SKILLS
            sname = SKILLS["chopping"]["name"]
            levelup_str = f"\n<:symbol_arrow_up:1538646239581577226> **Kỹ Năng {sname} lên Cấp {levelup_info['new_level']}!**"
            if levelup_info.get("needs_profession"):
                levelup_str += " Hãy dùng `skill chopping` để chọn Nghề Nghiệp!"

        await update_event_stat(self.bot, self.user_id, "works", 1)
        await update_event_stat(self.bot, self.user_id, "wood_chopped", quantity)
        if loot_info.get("name") in ["Gỗ Sồi (Hiếm)", "Gỗ Gụ (Cực Hiếm)"] or "rare" in loot_id or "epic" in loot_id:
            await update_event_stat(self.bot, self.user_id, "rare_wood_chopped", quantity)

        await interaction.followup.send(
            f"<:symbol_00_woodcutting:1536007697491558491> Bạn vừa đốn được **{quantity}x {loot_info['icon']} {loot_info['name']}**!{lb_msg}{tracker_msg}\n"
            f"*(Thể lực: {new_stamina}/{MAX_STAMINA} | +{xp_gained} Chopping XP)*{levelup_str}",
            ephemeral=True
        )


    async def on_timeout(self) -> None:
        for child in getattr(self, "children", []):
            if hasattr(child, "disabled"):
                child.disabled = True
        try:
            if hasattr(self, "message") and getattr(self, "message", None):
                await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass

