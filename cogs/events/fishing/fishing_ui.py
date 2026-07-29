"""
fishing_ui.py — Giao diện và Minigame Câu Cá
=============================================

⚠️  LUỒNG DISCORD INTERACTION CẦN HIỂU ĐÚNG:
    Discord yêu cầu response trong vòng 3 giây sau khi người dùng bấm nút.
    Vì chúng ta cần asyncio.sleep() lâu hơn 3 giây (2~5s chờ cá cắn),
    chúng ta phải RESPOND NGAY trong 3 giây đầu (bước 1),
    rồi dùng edit_original_response() — một API call bình thường không bị giới hạn 3s —
    để cập nhật tin nhắn trong các bước tiếp theo.
"""

import asyncio
import random
import discord
from discord.ext import commands
from typing import Any, Dict

from .fishing_config import (
    STAMINA_PER_FISH, CATCH_WINDOW_SECONDS,
    WAIT_MIN_SECONDS, WAIT_MAX_SECONDS,
    FISH_LOOT, _FISH_KEYS, _FISH_WEIGHTS,
)
from cogs.events.idle_farm.farm_db import get_farm_data, save_farm_data, get_and_update_stamina
from cogs.events.mining.mining_config import MAX_STAMINA


# ---------------------------------------------------------------------------
# HELPER: Thanh thể lực (tái dụng từ mining, không import để tránh circular)
# ---------------------------------------------------------------------------

def _stamina_bar(stamina: int, bar_len: int = 10) -> str:
    filled = round(stamina / MAX_STAMINA * bar_len)
    return "🟦" * filled + "⬛" * (bar_len - filled)


# ---------------------------------------------------------------------------
# EMBED
# ---------------------------------------------------------------------------

def build_fishing_embed(author: discord.Member, stamina: int) -> discord.Embed:
    """Giao diện Hồ Câu Cá, hiển thị thể lực và các loại cá có thể câu được."""
    embed = discord.Embed(
        title="🎣 Hồ Câu Cá Bình Yên",
        description=(
            f"Chào mừng **{author.display_name}** đến với hồ câu!\n"
            f"Mỗi lần quăng cần tốn **{STAMINA_PER_FISH}** thể lực.\n"
            f"Khi thấy `⚠️ CÁ CẮN CÂU!!`, hãy bấm **nhanh nhất có thể** trong "
            f"**{CATCH_WINDOW_SECONDS:.0f} giây** để không bị trượt!\n"
        ),
        color=0x1abc9c,
    )

    bar = _stamina_bar(stamina)
    embed.add_field(
        name="💪 Thể Lực",
        value=f"{bar} **{stamina}/{MAX_STAMINA}**",
        inline=False,
    )

    fish_lines = [
        f"{info['icon']} **{info['name']}** — {info['weight']}%"
        for info in FISH_LOOT.values()
    ]
    embed.add_field(name="🐠 Các Loài Trong Hồ", value="\n".join(fish_lines), inline=False)

    embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_footer(text="Cá câu được sẽ được cất vào y!bag của bạn.")
    return embed


# ---------------------------------------------------------------------------
# VIEW 1: Giật Cần (thời gian phản xạ 2 giây)
# ---------------------------------------------------------------------------

class FishCatchView(discord.ui.View):
    """
    View ngắn hạn chỉ hiện ra khi cá đã cắn câu.
    Người chơi có CATCH_WINDOW_SECONDS để bấm "Giật Cần".
    """

    def __init__(self):
        super().__init__(timeout=CATCH_WINDOW_SECONDS)
        self.caught: bool = False   # Cờ kết quả, đặt True nếu bấm kịp

    @discord.ui.button(label="🎣 GIẬT CẦN!", style=discord.ButtonStyle.success)
    async def catch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.caught = True
        # Ack ngay để không timeout; kết quả được xử lý ở FishingView.cast_btn
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """Không làm gì — cờ caught vẫn là False, FishingView sẽ xử lý."""
        self.caught = False


# ---------------------------------------------------------------------------
# VIEW 2: Giao diện chính Hồ Câu Cá
# ---------------------------------------------------------------------------

class FishingView(discord.ui.View):
    """View chính chứa nút "Quăng Cần". Giữ tham chiếu author để dùng trong callback."""

    def __init__(self, bot: commands.Bot, user_id: str, author: discord.Member, stamina: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.author = author
        # Disable nút ngay nếu không đủ thể lực
        self.cast_btn.disabled = (stamina < STAMINA_PER_FISH)

    @discord.ui.button(label="Quăng Cần", emoji="🎣", style=discord.ButtonStyle.primary)
    async def cast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ Đây là cần câu của người khác!", ephemeral=True
            )
            return

        # BƯỚC 1 — Respond ngay trong 3 giây (khóa giao diện, đặt trạng thái chờ)
        # Dùng edit_message để thay thế toàn bộ tin nhắn; embed=None + view=None để dọn sạch
        await interaction.response.edit_message(
            content="🎣 **Đang thả mồi... Hãy chuẩn bị giật cần!**",
            embed=None,
            view=None,
        )

        # BƯỚC 2 — Kiểm tra thể lực (sau khi đã respond, không còn giới hạn 3 giây)
        current_stamina = await get_and_update_stamina(self.bot, self.user_id)
        if current_stamina < STAMINA_PER_FISH:
            await interaction.edit_original_response(
                content=(
                    f"😓 **Bạn đã kiệt sức!**\n"
                    f"Cần **{STAMINA_PER_FISH}** thể lực để quăng cần, "
                    f"bạn chỉ còn **{current_stamina}**."
                )
            )
            return

        # BƯỚC 3 — Trừ thể lực và lưu DB
        farm_data = await get_farm_data(self.bot, self.user_id)
        farm_data["stamina"] = current_stamina - STAMINA_PER_FISH
        # Không reset last_stamina_update để không làm trễ timer hồi phục
        await save_farm_data(self.bot, self.user_id, farm_data)

        # BƯỚC 4 — Chờ cá "cắn câu" (thời gian ngẫu nhiên 2–5 giây)
        wait_time = random.uniform(WAIT_MIN_SECONDS, WAIT_MAX_SECONDS)
        await asyncio.sleep(wait_time)

        # BƯỚC 5 — Hiện nút giật cần với FishCatchView (timeout = 2 giây)
        catch_view = FishCatchView()
        await interaction.edit_original_response(
            content="⚠️ **CÁ CẮN CÂU!! BẤM NHANH!!** ⚠️",
            view=catch_view,
        )

        # BƯỚC 6 — Chờ người dùng phản ứng (hoặc hết 2 giây)
        await catch_view.wait()

        # BƯỚC 7 — Xử lý kết quả
        if catch_view.caught:
            # Random loại cá
            fish_id: str = random.choices(_FISH_KEYS, weights=_FISH_WEIGHTS, k=1)[0]
            fish_info = FISH_LOOT[fish_id]

            # Lấy farm_data mới nhất rồi cộng vào inventory
            farm_data = await get_farm_data(self.bot, self.user_id)
            inventory = farm_data.setdefault("inventory", {})
            inventory[fish_id] = inventory.get(fish_id, 0) + 1
            await save_farm_data(self.bot, self.user_id, farm_data)

            new_stamina = int(farm_data.get("stamina", 0))
            bar = _stamina_bar(new_stamina)

            # Thông báo thành công + khôi phục nút quăng cần
            self.cast_btn.disabled = (new_stamina < STAMINA_PER_FISH)
            new_embed = build_fishing_embed(self.author, new_stamina)

            rare_msg = ""
            if fish_info["rare_rank"] >= 3:
                rare_msg = " 🎉🎉🎉 **CỰC HIẾM!**"

            await interaction.edit_original_response(
                content=(
                    f"🎉 **Tuyệt vời!** Bạn đã câu được "
                    f"**1x {fish_info['icon']} {fish_info['name']}**!{rare_msg}"
                ),
                embed=new_embed,
                view=self,
            )

        else:
            # Hết giờ — cá chạy mất
            farm_data = await get_farm_data(self.bot, self.user_id)
            new_stamina = int(farm_data.get("stamina", 0))
            self.cast_btn.disabled = (new_stamina < STAMINA_PER_FISH)
            new_embed = build_fishing_embed(self.author, new_stamina)

            await interaction.edit_original_response(
                content="💦 **Trượt rồi!** Cá đã chạy mất mà không kịp giật cần.",
                embed=new_embed,
                view=self,
            )
