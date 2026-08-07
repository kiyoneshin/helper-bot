"""
fishing_ui.py — Giao diện và Minigame Câu Cá
=============================================

⚠️  LUỒNG DISCORD INTERACTION CẦN HIỂU ĐÚNG:
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
    STAMINA_PER_FISH, CATCH_WINDOW_SECONDS,
    WAIT_MIN_SECONDS, WAIT_MAX_SECONDS,
    FISH_LOOT, get_fishing_loot, get_fishing_display_weights
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA
from cogs.common.db import update_event_stat


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _stamina_bar(stamina: int, bar_len: int = 10) -> str:
    filled = round(stamina / MAX_STAMINA * bar_len)
    return "🟦" * filled + "⬛" * (bar_len - filled)

from cogs.events.mining.mining_ui import _mins_to_full


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_fishing_embed(author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any] | None = None) -> discord.Embed:
    """Giao diện Hồ Câu Cá, hiển thị thể lực, cấp cần câu, và các loại cá."""
    rod_level = (farm_data or {}).get("rod_level", 1)

    from .fishing_config import ROD_NAMES
    rod_name = ROD_NAMES.get(rod_level, f"Lv{rod_level}")

    embed = discord.Embed(
        title="🎣 Hồ Câu Cá Bình Yên",
        description=(
            f"Chào mừng **{author.display_name}** đến với hồ câu!\n"
            f"Mỗi lần quăng cần tốn **{STAMINA_PER_FISH}** thể lực.\n"
            f"Khi thấy `⚠️ CÁ CẮN CÂU!!`, hãy bấm **nhanh nhất có thể** trong "
            f"**{CATCH_WINDOW_SECONDS:.1f} giây** để không bị trượt!\n"
            f"*(Phản xạ < 2s = ⚡ **Perfect Catch** — x2 cá hiếm!)*\n"
        ),
        color=0x1abc9c,
    )

    bar = _stamina_bar(stamina)
    regen_info = f"(Hồi đầy sau: {_mins_to_full(stamina)})" if stamina < MAX_STAMINA else "✅ Đã đầy"
    embed.add_field(
        name="💪 Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}** {regen_info}",
        inline=False,
    )
    embed.add_field(
        name="🎣 Cần Câu",
        value=f"**{rod_name}** (Lv{rod_level})",
        inline=True,
    )

    display_weights = get_fishing_display_weights(rod_level)
    fish_lines = [
        f"{info['icon']} **{info['name']}** — {display_weights[fish_id]}%"
        for fish_id, info in FISH_LOOT.items()
    ]
    embed.add_field(name="🐠 Các Loài (Base)", value="\n".join(fish_lines), inline=True)
    
    inventory = (farm_data or {}).get("inventory", {})
    inv_lines = [
        f"{info['icon']} {info['name']}: **{inventory.get(fish_id, 0)}**"
        for fish_id, info in FISH_LOOT.items()
        if inventory.get(fish_id, 0) > 0
    ]
    if inv_lines:
        embed.add_field(name="🎒 Giỏ Cá Của Bạn", value="\n".join(inv_lines), inline=False)

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Dùng kbag để bán cá. Thể lực hồi 1 điểm mỗi 18 giây.")
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
        super().__init__(timeout=CATCH_WINDOW_SECONDS)
        self.caught: bool = False
        self.reaction_time: float = CATCH_WINDOW_SECONDS  # worst-case nếu timeout
        self.start_time: float = time.time()

    @discord.ui.button(label="🎣 GIẬT CẦN!", style=discord.ButtonStyle.success)
    async def catch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.reaction_time = round(time.time() - self.start_time, 2)
        self.caught = True
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        self.caught = False


# ---------------------------------------------------------------------------
# VIEW 2: Giao diện chính Hồ Câu Cá
# ---------------------------------------------------------------------------

class FishingView(discord.ui.View):
    """View chính chứa nút "Quăng Cần"."""

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member | discord.User, stamina: int, farm_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        self.farm_data = farm_data
        self.cast_btn.disabled = (stamina < STAMINA_PER_FISH)

    @discord.ui.button(label="Quăng Cần", emoji="🎣", style=discord.ButtonStyle.primary)
    async def cast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ Đây là cần câu của người khác!", ephemeral=True
            )
            return

        # BƯỚC 1 — Respond ngay trong 3 giây (khoá giao diện cũ)
        await interaction.response.edit_message(
            content="🎣 **Đang thả mồi... Hãy chuẩn bị giật cần!**",
            embed=None,
            view=None,
        )

        # BƯỚC 2 — Kiểm tra thể lực
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < STAMINA_PER_FISH:
            await interaction.edit_original_response(
                content=(
                    f"😓 **Bạn đã kiệt sức!**\n"
                    f"Cần **{STAMINA_PER_FISH}** thể lực, bạn chỉ còn **{current_stamina}**."
                )
            )
            return

        # BƯỚC 3 — Trừ thể lực và lưu DB (không reset timer hồi)
        farm_data = await get_farm_data(self.bot, self.user_id)
        farm_data["stamina"] = current_stamina - STAMINA_PER_FISH
        await save_farm_data(self.bot, self.user_id, farm_data)

        # BƯỚC 4 — Chờ cá "cắn câu" (2–5 giây ngẫu nhiên)
        wait_time = random.uniform(WAIT_MIN_SECONDS, WAIT_MAX_SECONDS)
        await asyncio.sleep(wait_time)

        # BƯỚC 5 — Hiện nút giật cần (timeout = 4.5s chống lag)
        catch_view = FishCatchView()
        await interaction.edit_original_response(
            content="⚠️ **CÁ CẮN CÂU!! BẤM NHANH!!** ⚠️",
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

            # RNG theo rod_level + reaction_time
            fish_id, is_perfect = get_fishing_loot(rod_level, reaction_time)
            fish_info = FISH_LOOT[fish_id]

            # 4. Lưu DB (cập nhật lootbox nếu có)
            from cogs.events.lootbox.lootbox_cmd import _get_luck_and_boost, _add_lootbox_to_inventory
            from cogs.events.lootbox.lootbox_config import get_activity_lootbox_drop, TIER_EMOJIS, TIER_NAMES
            luck, boost_active = await _get_luck_and_boost(self.bot, self.user_id)
            lb_tier = get_activity_lootbox_drop("fish", luck, boost_active)
            lb_msg = ""
            if lb_tier:
                await _add_lootbox_to_inventory(self.bot, self.user_id, lb_tier, 1)
                lb_msg = f"\n🎁 **Rớt thêm:** 1x {TIER_EMOJIS[lb_tier]} {TIER_NAMES[lb_tier]}"

            inventory = farm_data.setdefault("inventory", {})
            inventory[fish_id] = inventory.get(fish_id, 0) + 1
            await save_farm_data(self.bot, self.user_id, farm_data)
            await update_event_stat(self.bot, self.user_id, "fishes", 1)
            await update_event_stat(self.bot, self.user_id, "fish_caught", 1)
            if fish_info.get("rare_rank", 0) >= 3:
                await update_event_stat(self.bot, self.user_id, "legendary_fish", 1)

            # Tạo thông báo kết quả
            prefix = "⚡ **Perfect Catch!** " if is_perfect else "🎉 **Tuyệt vời!** "
            rare_tag = " 🎉🎉🎉 **CỰC HIẾM!**" if fish_info["rare_rank"] >= 3 else ""
            result_msg = (
                f"{prefix}Bạn đã câu được **1x {fish_info['icon']} {fish_info['name']}**!{rare_tag}{lb_msg}\n"
                f"*(Phản xạ: **{reaction_time}s**)*"
            )

            self.cast_btn.disabled = (new_stamina < STAMINA_PER_FISH)
            new_embed = build_fishing_embed(self.author, new_stamina, farm_data)
            await interaction.delete_original_response()
            await interaction.followup.send(
                content=result_msg,
                embed=new_embed,
                view=self,
            )

        else:
            # Hết giờ — cá chạy mất
            self.cast_btn.disabled = (new_stamina < STAMINA_PER_FISH)
            new_embed = build_fishing_embed(self.author, new_stamina, farm_data)
            await interaction.delete_original_response()
            await interaction.followup.send(
                content="💦 **Trượt rồi!** Cá đã chạy mất. Hãy thả mồi lại!",
                embed=new_embed,
                view=self,
            )
