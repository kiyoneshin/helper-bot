"""
fishing_ui.py — Giao diện và Minigame Câu Cá
=============================================

LUỒNG DISCORD INTERACTION CẦN HIỂU ĐÚNG:
Discord yêu cầu response trong vòng 3 giây sau khi người dùng bấm nút.
Vì chúng ta cần asyncio.sleep() lâu hơn 3 giây (2~5s chờ cá cắn),
chúng ta phải RESPOND NGAY trong 3 giây đầu (bước 1),
rồi dùng edit_original_response() — webhook API không bị giới hạn 3s —
để cập nhật tin nhắn trong các bước tiếp theo.
"""

import asyncio
import random
import time
import discord
from discord.ext import commands
from typing import Any, Dict

from .fishing_config import (
    STAMINA_PER_FISH, CATCH_WINDOW_SECONDS, PERFECT_CATCH_THRESHOLD,
    WAIT_MIN_SECONDS, WAIT_MAX_SECONDS,
    FISH_LOOT, get_fishing_loot, get_fishing_display_weights, get_fishing_effective_weights
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA
from cogs.common.db import update_event_stat
from cogs.events.skills.skills_config import FISHING_XP_BY_RANK
from cogs.events.skills.skills_db import add_skill_xp, get_skills, has_profession


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _stamina_bar(stamina: int, bar_len: int = 10) -> str:
    filled = round(stamina / MAX_STAMINA * bar_len)
    return "🟩" * filled + "⬛" * (bar_len - filled)

from cogs.events.mining.mining_ui import _mins_to_full


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_fishing_embed(
    author: discord.Member | discord.User,
    stamina: int,
    farm_data: Dict[str, Any] | None = None,
    regen_interval: int = 18,
    boosts: dict = None,
    skills_data: dict = None,
) -> discord.Embed:
    """Giao diện Hồ Câu Cá, hiển thị thể lực, cấp cần câu, và các loài cá."""
    rod_level = (farm_data or {}).get("rod_level", 1)

    from .fishing_config import ROD_NAMES
    rod_name = ROD_NAMES.get(rod_level, f"Lv{rod_level}")

    # Tính stamina_cost thực tế
    effective_stamina_cost = STAMINA_PER_FISH
    if boosts and "stamina_discount" in boosts:
        effective_stamina_cost = max(1, effective_stamina_cost - int(boosts["stamina_discount"]["value"]))

    embed = discord.Embed(
        title="Hồ Câu Cá Bình Yên",
        description=(
            f"Chào mừng **{author.display_name}** đến với hồ câu!\n"
            f"Mỗi lần quăng cần tốn **{effective_stamina_cost}** thể lực.\n"
            f"Khi thấy <:symbol_alert:1537546957885542450> `CÁ CẮN CÂU!!`, hãy bấm **nhanh nhất có thể** trong "
            f"**{CATCH_WINDOW_SECONDS:.1f} giây** để không bị trượt!\n"
            f"*(Phản xạ < 2s = **Perfect Catch** — x2 cá hiếm!)*\n"
        ),
        color=0x1abc9c,
    )

    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina, regen_interval)})" if stamina < MAX_STAMINA else "<:symbol_right:1536629912515903578> Đã đầy"
    embed.add_field(
        name="<:symbol_stamina:1536644916502077480> Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )
    embed.add_field(
        name="<:symbol_00_fishing:1536007692437422171> Cần Câu",
        value=f"**{rod_name}** (Lv{rod_level})",
        inline=True,
    )

    # Hiển thị tỉ lệ thực tế nếu có buff
    if boosts is not None or skills_data is not None:
        display_weights = get_fishing_effective_weights(rod_level, boosts or {}, skills_data or {})
        label = "<:symbol_fish:1536007699190386740> Các Loài (Thực Tế)"
    else:
        display_weights = get_fishing_display_weights(rod_level)
        label = "<:symbol_fish:1536007699190386740> Các Loài (Base)"

    fish_lines = [
        f"{info['icon']} **{info['name']}** — {display_weights[fish_id]}%"
        for fish_id, info in FISH_LOOT.items()
    ]
    embed.add_field(name=label, value="\n".join(fish_lines), inline=True)
    
    inventory = (farm_data or {}).get("inventory", {})
    inv_lines = [
        f"{info['icon']} {info['name']}: **{inventory.get(fish_id, 0)}**"
        for fish_id, info in FISH_LOOT.items()
        if inventory.get(fish_id, 0) > 0
    ]
    if inv_lines:
        embed.add_field(name="<:icon_07_inventory:1535664855300710422> Giỏ Cá Của Bạn", value="\n".join(inv_lines), inline=False)

    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1535660959224565902.gif")
    embed.set_footer(text=f"Dùng kbag để bán cá. Thể lực hồi 1 điểm mỗi {regen_interval} giây.")
    return embed


# ---------------------------------------------------------------------------
# VIEW 1: Giật Cần (window = CATCH_WINDOW_SECONDS, mặc định 4.5s chống lag)
# ---------------------------------------------------------------------------

class FishCatchView(discord.ui.View):
    """
    View ngắn hạn chỉ hiện khi cá đã cắn câu.
    Ghi lại start_time để tính reaction_time chính xác.
    """

    def __init__(self):
        super().__init__(timeout=120.0)
        self.caught: bool = False
        self.reaction_time: float = CATCH_WINDOW_SECONDS  # worst-case nếu timeout
        self.start_time: float = time.time()

    @discord.ui.button(label="GIẬT CẦN!", style=discord.ButtonStyle.success, emoji="<:symbol_00_fishing:1536007692437422171>")
    async def catch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.reaction_time = round(time.time() - self.start_time, 2)
        self.caught = True
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        self.caught = False
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# VIEW 2: Giao diện chính Hồ Câu Cá
# ---------------------------------------------------------------------------

class FishingView(discord.ui.View):
    """View chứa nút Câu Cá."""

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any], regen_interval: int = 18):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.regen_interval = regen_interval
        self.farm_data = farm_data
        self.cast_btn.disabled = (stamina < STAMINA_PER_FISH)
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

    @discord.ui.button(label="Quăng Cần", emoji="<:button_fishing:1536007667649347624>", style=discord.ButtonStyle.primary)
    async def cast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "<:symbol_ban:1537546960003801319> Đây là cần câu của người khác!", ephemeral=True
            )
            return

        # BƯỚC 1 — Respond ngay trong 3 giây (khoá giao diện cũ)
        await interaction.response.edit_message(
            content="<:button_fishing:1536007667649347624> **Đang thả mồi... Hãy chuẩn bị giật cần!**",
            embed=None,
            view=None,
        )

        # BƯỚC 2 — Kiểm tra thể lực
        from cogs.common.db import get_active_boosts
        boosts = await get_active_boosts(self.bot, self.user_id)
        stamina_cost = STAMINA_PER_FISH
        if "stamina_discount" in boosts:
            stamina_cost = max(1, stamina_cost - int(boosts["stamina_discount"]["value"]))
            
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < stamina_cost:
            button.disabled = True
            farm_data = await get_farm_data(self.bot, self.user_id)
            skills_data_early = await get_skills(self.bot, self.user_id)
            await interaction.response.edit_message(embed=build_fishing_embed(self.author, current_stamina, farm_data, self.regen_interval, boosts=boosts, skills_data=skills_data_early), view=self)
            await interaction.followup.send(f"<:symbol_wrong:1536629915598848072> Bạn đã **kiệt sức**! Hãy đợi thể lực hồi phục.\n*(Hồi đầy sau: {_mins_to_full(current_stamina, self.regen_interval)})*", ephemeral=True)
            return

        # Lấy skills data để áp dụng bonus
        skills_data = await get_skills(self.bot, self.user_id)

        farm_data = await get_farm_data(self.bot, self.user_id)
        farm_data["stamina"] = current_stamina - stamina_cost
        await save_farm_data(self.bot, self.user_id, farm_data)

        # Trapper profession: mở rộng cửa sổ Perfect Catch
        from .fishing_config import PERFECT_CATCH_THRESHOLD
        effective_perfect_threshold = PERFECT_CATCH_THRESHOLD if not hasattr(self, '_perfect_threshold') else self._perfect_threshold
        extra_window = 0.0
        if has_profession(skills_data, "fishing", "trapper"):
            extra_window += 1.5
        effective_perfect_threshold = PERFECT_CATCH_THRESHOLD + extra_window

        effective_catch_window = CATCH_WINDOW_SECONDS

        # BƯỚC 4 — Chờ cá "cắn câu" (2–5 giây ngẫu nhiên)
        wait_time = random.uniform(WAIT_MIN_SECONDS, WAIT_MAX_SECONDS)
        await asyncio.sleep(wait_time)

        # BƯỚC 5 — Hiện nút giật cần (timeout = 4.5s chống lag)
        catch_view = FishCatchView()
        await interaction.edit_original_response(
            content="<:symbol_alert:1537546957885542450> **CÁ CẮN CÂU!! BẤM NHANH!!** <:symbol_alert:1537546957885542450>",
            view=catch_view,
        )

        # BƯỚC 6 — Chờ phản xạ người dùng
        await catch_view.wait()

        # BƯỚC 7 — Xử lý kết quả
        farm_data = await get_farm_data(self.bot, self.user_id)
        new_stamina = int(farm_data.get("stamina", 0))
        rod_level = int(farm_data.get("rod_level", 1))

        if catch_view.caught:
            reaction_time = catch_view.reaction_time

            # RNG theo rod_level + reaction_time + boosts
            from cogs.common.db import get_active_boosts
            boosts = await get_active_boosts(self.bot, self.user_id)
            fish_id, is_perfect, qty = get_fishing_loot(rod_level, reaction_time, boosts, skills_data)
            fish_info = FISH_LOOT[fish_id]

            # 4. Lưu DB (cập nhật lootbox nếu có)
            from cogs.events.lootbox.lootbox_cmd import _get_luck_and_boost, _add_lootbox_to_inventory
            from cogs.events.lootbox.lootbox_config import get_activity_lootbox_drop, TIER_EMOJIS, TIER_NAMES
            luck, boost_active = await _get_luck_and_boost(self.bot, self.user_id)
            lb_tier = get_activity_lootbox_drop("fish", luck, boost_active, boosts)
            lb_msg = ""
            if lb_tier:
                await _add_lootbox_to_inventory(self.bot, self.user_id, lb_tier, 1)
                lb_msg = f"\n<:gift_00_symbol:1536003307011842099> **Rớt thêm:** 1x {TIER_EMOJIS[lb_tier]} {TIER_NAMES[lb_tier]}"

            inventory = farm_data.setdefault("inventory", {})
            inventory[fish_id] = inventory.get(fish_id, 0) + qty
            await save_farm_data(self.bot, self.user_id, farm_data)
            await update_event_stat(self.bot, self.user_id, "fishes", qty)
            await update_event_stat(self.bot, self.user_id, "fish_caught", qty)
            if fish_info.get("rare_rank", 0) >= 3:
                await update_event_stat(self.bot, self.user_id, "legendary_fish", qty)

            # Skill XP theo rare_rank
            xp_gained = FISHING_XP_BY_RANK.get(fish_info.get("rare_rank", 0), 1) * qty
            levelup_info = await add_skill_xp(self.bot, self.user_id, "fishing", xp_gained)

            # Tạo thông báo kết quả
            prefix = "**Perfect Catch!** " if is_perfect else "<:symbol_confetti:1537570146313306183> **Tuyệt vời!** "
            rare_tag = " <:symbol_confetti:1537570146313306183><:symbol_confetti:1537570146313306183><:symbol_confetti:1537570146313306183> **CỰC HIẾM!**" if fish_info["rare_rank"] >= 3 else ""
            
            qty_str = f"{qty}x " if qty > 1 else "1x "

            result_msg = (
                f"{prefix}Bạn đã câu được **{qty_str}{fish_info['icon']} {fish_info['name']}**!{rare_tag}{lb_msg}\n"
                f"*(Phản xạ: **{reaction_time}s** | +{xp_gained} Fishing XP)*"
            )

            if levelup_info:
                from cogs.events.skills.skills_config import SKILLS
                sname = SKILLS["fishing"]["name"]
                result_msg += f"\n<:symbol_arrow_up:1538646239581577226> **Kỹ Năng {sname} lên Cấp {levelup_info['new_level']}!**"
                if levelup_info.get("needs_profession"):
                    result_msg += " Hãy dùng `skill fishing` để chọn Nghề Nghiệp!"

            self.cast_btn.disabled = (new_stamina < stamina_cost)
            new_embed = build_fishing_embed(self.author, new_stamina, farm_data, self.regen_interval, boosts=boosts, skills_data=skills_data)
            await interaction.delete_original_response()
            await interaction.followup.send(
                content=result_msg,
                embed=new_embed,
                view=self,
            )

        else:
            # Hết giờ — cá chạy mất
            self.cast_btn.disabled = (new_stamina < STAMINA_PER_FISH)
            new_embed = build_fishing_embed(self.author, new_stamina, farm_data, self.regen_interval, boosts=boosts, skills_data=skills_data)
            await interaction.delete_original_response()
            await interaction.followup.send(
                content="**Trượt rồi!** Cá đã chạy mất. Hãy thả mồi lại!",
                embed=new_embed,
                view=self,
            )
