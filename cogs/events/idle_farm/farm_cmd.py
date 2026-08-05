"""
farm_cmd.py — Lệnh người dùng để khởi động giao diện Nông Trại
==============================================================
Nơi tích hợp các thành phần DB, UI vào lệnh bot.
"""

import discord
from discord.ext import commands

from .farm_db import get_farm_data
from cogs.common.db import fetchval_db, check_not_locked
from .farm_ui import FarmView, build_farm_embed
from .upgrade_ui import UpgradeView, build_upgrade_embed
from .machine_ui import MachineView, build_machine_embed, RecipeSelect
from .machine_config import MACHINES, RECIPES, ARTISAN_GOODS


class IdleFarmCog(commands.Cog):
    """🌻 Cog Mini-game Idle Farm (Nông Trại Nhàn Rỗi)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="farm",
        aliases=["nongtrai"],
        description="Quản lý nông trại của bạn (Trồng trọt, thu hoạch, nâng cấp).",
    )
    @check_not_locked()
    async def farm_cmd(self, ctx: commands.Context) -> None:
        """🚜 Mở giao diện Nông Trại của bạn."""
        user_id = str(ctx.author.id)
        
        # 1. Fetch dữ liệu Nông Trại
        farm_data = await get_farm_data(self.bot, user_id)
        
        # 2. Xây dựng Embed trực quan
        embed = build_farm_embed(ctx.author, farm_data)
        
        # 3. Khởi tạo Giao Diện View
        view = FarmView(self.bot, user_id, ctx.author, farm_data)
        
        # 4. Gửi kết quả
        await ctx.send(embed=embed, view=view)


    @commands.hybrid_command(name="upgrade", aliases=["nangcap", "morong"])
    async def upgrade_cmd(self, ctx: commands.Context) -> None:
        """🚜 Mở rộng thêm ô đất cho Nông trại."""
        user_id = str(ctx.author.id)
        
        farm_data = await get_farm_data(self.bot, user_id)
        user_points = await fetchval_db(self.bot, "SELECT points FROM event_profiles WHERE discord_id = $1", user_id)
        points = float(user_points) if user_points else 0.0
        
        embed = build_upgrade_embed(ctx.author, farm_data, points)
        view = UpgradeView(self.bot, user_id, ctx.author, farm_data)
        
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="machine", aliases=["chebien", "maymoc"])
    @check_not_locked()
    async def machine_cmd(self, ctx: commands.Context) -> None:
        """🏭 Khu vực Chế biến Nông sản (Keg, Jar, Furnace)."""
        user_id = str(ctx.author.id)
        farm_data = await get_farm_data(self.bot, user_id)
        embed = build_machine_embed(ctx.author, farm_data)
        view = MachineView(self.bot, user_id, ctx.author, farm_data)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="craft", aliases=["chebien2", "bophuong"])
    @check_not_locked()
    async def craft_cmd(self, ctx: commands.Context, machine: str, recipe: str) -> None:
        """⚙️ Bỏ nguyên liệu vào máy chế biến. VD: y!craft keg keg_beer"""
        import time
        from .farm_db import save_farm_data
        from .machine_ui import _format_duration, _get_item_display_name, _get_queue_list, MAX_QUEUE_SLOTS

        user_id = str(ctx.author.id)
        machine = machine.lower().strip()
        recipe = recipe.lower().strip()

        # --- Kiểm tra tên máy ---
        if machine not in MACHINES:
            valid = " | ".join(f"`{k}`" for k in MACHINES.keys())
            return await ctx.send(
                f"❌ {ctx.author.mention} Không có máy nào tên `{machine}` hết! "
                f"Các máy hiện có: {valid}\n"
                f"*Dùng `y!machine` để xem toàn bộ.*"
            )

        # --- Kiểm tra recipe ---
        if recipe not in RECIPES or recipe not in MACHINES[machine]["recipes"]:
            valid = " | ".join(f"`{r}`" for r in MACHINES[machine]["recipes"])
            machine_name = MACHINES[machine]["name"]
            return await ctx.send(
                f"❌ {ctx.author.mention} **{machine_name}** không có công thức `{recipe}` nào!\n"
                f"Công thức hợp lệ: {valid}"
            )

        farm_data = await get_farm_data(self.bot, user_id)
        inventory = farm_data.get("inventory", {})
        machine_queue = farm_data.setdefault("machine_queue", {})
        now = time.time()
        recipe_cfg = RECIPES[recipe]

        # --- Kiểm tra hàng đợi đầy ---
        queue_list = _get_queue_list(farm_data)
        if len(queue_list) >= MAX_QUEUE_SLOTS and machine not in machine_queue:
            return await ctx.send(
                f"❌ {ctx.author.mention} Hàng đợi chế biến đã đầy rồi! "
                f"({MAX_QUEUE_SLOTS}/{MAX_QUEUE_SLOTS} slot)\n"
                f"Dùng `y!machine` rồi nhấn **Thu Hoạch** để lấy thành phẩm trước nhé!"
            )

        # --- Kiểm tra máy đang bận ---
        if machine in machine_queue:
            existing = machine_queue[machine]
            finish_time = existing.get("finish_time", 0)
            if now < finish_time:
                remaining = _format_duration(int(finish_time - now))
                machine_name = MACHINES[machine]["name"]
                return await ctx.send(
                    f"⏳ {ctx.author.mention} **{machine_name}** đang bận rồi! "
                    f"Còn **{remaining}** nữa mới xong.\n"
                    f"Khi thấy ✅ trong `y!machine` thì mới bỏ thêm được."
                )
            else:
                # Tự thu hoạch khi đã xong
                output_id = existing["output_id"]
                output_qty = existing["output_qty"]
                inventory[output_id] = inventory.get(output_id, 0) + output_qty
                machine_queue.pop(machine, None)
                output_info = ARTISAN_GOODS.get(output_id, {})
                farm_data["inventory"] = inventory
                farm_data["machine_queue"] = machine_queue
                await save_farm_data(self.bot, user_id, farm_data)
                await ctx.send(
                    f"🧺 **{MACHINES[machine]['name']}** vừa xong! Đã tự động lấy: "
                    f"**{output_qty}x {output_info.get('icon', '')} {output_info.get('name', output_id)}**\n"
                    f"*Tiếp tục bỏ nguyên liệu mới vào...*"
                )
                farm_data = await get_farm_data(self.bot, user_id)
                inventory = farm_data.get("inventory", {})
                machine_queue = farm_data.setdefault("machine_queue", {})

        # --- Kiểm tra nguyên liệu --- liệt kê đầy đủ chỗ thiếu
        missing = []
        for item_id, qty_needed in recipe_cfg["ingredients"].items():
            qty_have = inventory.get(item_id, 0)
            if qty_have < qty_needed:
                name = _get_item_display_name(item_id)
                missing.append(f"{name} (thiếu {qty_needed - qty_have}, có {qty_have}/{qty_needed})")

        if missing:
            missing_str = "\n".join(f"• {m}" for m in missing)
            return await ctx.send(
                f"❌ {ctx.author.mention} Không đủ nguyên liệu để chế **{recipe_cfg['name']}**!\n"
                f"{missing_str}"
            )

        # --- Trừ nguyên liệu và bắt đầu chế biến ---
        for item_id, qty_needed in recipe_cfg["ingredients"].items():
            inventory[item_id] = inventory.get(item_id, 0) - qty_needed
            if inventory[item_id] <= 0:
                inventory.pop(item_id, None)

        finish_time = now + recipe_cfg["duration_seconds"]
        machine_queue[machine] = {
            "recipe_id": recipe,
            "recipe_name": recipe_cfg["name"],
            "output_id": recipe_cfg["output_id"],
            "output_qty": recipe_cfg["output_qty"],
            "start_time": now,
            "finish_time": finish_time,
        }
        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, user_id, farm_data)

        duration_str = _format_duration(recipe_cfg["duration_seconds"])
        output_info = ARTISAN_GOODS.get(recipe_cfg["output_id"], {})
        await ctx.send(
            f"⚙️ {ctx.author.mention} Đã cho vào **{MACHINES[machine]['name']}**!\n"
            f"{recipe_cfg['icon']} **{recipe_cfg['name']}** → "
            f"{output_info.get('icon', '')} **{output_info.get('name', '')}**\n"
            f"⌛ Hoàn thành sau **{duration_str}** | Bán được **{output_info.get('price', 0):,} điểm**\n"
            f"*Dùng `y!machine` để theo dõi tiến độ!*"
        )


async def setup(bot: commands.Bot) -> None:
    # Nạp module cog vào bot
    await bot.add_cog(IdleFarmCog(bot))
