"""
farm_cmd.py — Lệnh người dùng để khởi động giao diện Nông Trại
==============================================================
Nơi tích hợp các thành phần DB, UI vào lệnh bot.
"""

import discord
from discord.ext import commands

from .farm_db import get_farm_data, plant_seeds_batch
from cogs.common.db import fetchval_db, check_not_locked
from .farm_ui import FarmView, build_farm_embed
from .upgrade_ui import UpgradeView, build_upgrade_embed
from .machine_ui import MachineView, build_machine_embed, RecipeSelect
from .machine_config import MACHINES, RECIPES, ARTISAN_GOODS


class IdleFarmCog(commands.Cog):
    """Cog Mini-game Idle Farm (Nông Trại Nhàn Rỗi)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="farm",
        aliases=["nongtrai"],
        description="Quản lý nông trại của bạn (Trồng trọt, thu hoạch, nâng cấp).",
    )
    @check_not_locked()
    async def farm_cmd(self, ctx: commands.Context) -> None:
        """Mở giao diện Nông Trại của bạn."""
        user_id = str(ctx.author.id)
        
        # 1. Fetch dữ liệu Nông Trại và Kỹ năng
        farm_data = await get_farm_data(self.bot, user_id)
        from cogs.events.skills.skills_db import get_skills
        skills_data = await get_skills(self.bot, user_id)
        
        # 2. Xây dựng Embed trực quan
        embed = build_farm_embed(ctx.author, farm_data, skills_data)
        
        # 3. Khởi tạo Giao Diện View
        view = FarmView(self.bot, user_id, ctx.author, farm_data, skills_data)
        
        # 4. Gửi kết quả
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="plant",
        aliases=["gieo", "trong"],
        description="🌱 Gieo hạt giống vào ô đất. VD: plant wheat 1 2",
    )
    @check_not_locked()
    async def plant_cmd(self, ctx: commands.Context, seed_type: str, *, slots_str: str) -> None:
        """Gieo hạt giống vào các ô đất chỉ định."""
        from cogs.events.idle_farm.config import SEEDS
        user_id = str(ctx.author.id)
        prefix = ctx.prefix or ctx.bot.custom_prefix

        # Parse seed type: có thể là tên tiếng anh hoặc ID item_config
        seed_key = seed_type.lower()
        
        if seed_key.isdigit():
            from cogs.common.item_config import get_item_by_id
            item = get_item_by_id(int(seed_key))
            if item and item.get("category") == "farm" and item["db_key"].startswith("seed_"):
                seed_key = item["db_key"].replace("seed_", "")

        if seed_key not in SEEDS:
            # Thử tìm theo tên tiếng Việt
            found = next((k for k, v in SEEDS.items() if v["name"].lower() == seed_key), None)
            if found:
                seed_key = found
            else:
                from cogs.common.item_config import ITEM_REGISTRY
                seed_id_map = {}
                for i_id, i_data in ITEM_REGISTRY.items():
                    if i_data.get("category") == "farm" and i_data.get("db_key", "").startswith("seed_"):
                        s_key = i_data["db_key"].replace("seed_", "")
                        seed_id_map[s_key] = i_id
                        
                seed_list = "\n".join(
                    f"• `{seed_id_map.get(k, '?')}/{k}` — {v['icon']} {v['name']} ({v['grow_time_seconds']//60} phút, giá {v['cost']:,} <:symbol_points_p:1538282388507987989>)"
                    for k, v in SEEDS.items()
                )
                return await ctx.send(  # type: ignore
                    f"<:symbol_wrong:1536629915598848072> Không tìm thấy hạt giống `{seed_type}`!\n"
                    f"**Danh sách hạt giống hợp lệ:**\n{seed_list}\n\n"
                    f"*Cú pháp: `{prefix}plant <loại_hạt/id_hạt> <ô 1> <ô 2> ...`*"
                )

        # Parse danh sách ô đất (tách bằng khoảng trắng hoặc dấu phẩy)
        import re
        raw_numbers = re.findall(r'\d+', slots_str)
        if not raw_numbers:
            return await ctx.send(  # type: ignore
                f"<:symbol_wrong:1536629915598848072> Bạn chưa nhập số ô đất nào!\n"
                f"*Cú pháp: `{prefix}plant <loại_hạt/id_hạt> <ô 1> <ô 2> ...`\n"
                f"Ví dụ: `{prefix}plant wheat 1 2 3` hoặc `{prefix}plant 51 1 2 3`*"
            )

        slot_ids = [int(n) for n in raw_numbers]
        ok, msg = await plant_seeds_batch(self.bot, user_id, seed_key, slot_ids)
        await ctx.send(msg)

    @commands.hybrid_command(
        name="pick",
        aliases=["cuoc"],
        description="⛏️ Cuốc bỏ cây trồng ở ô đất chỉ định. VD: pick 1 2",
    )
    @check_not_locked()
    async def pick_cmd(self, ctx: commands.Context, *, slots_str: str) -> None:
        """Cuốc bỏ cây trồng ở các ô đất chỉ định."""
        user_id = str(ctx.author.id)
        prefix = ctx.prefix or ctx.bot.custom_prefix

        import re
        raw_numbers = re.findall(r'\d+', slots_str)
        if not raw_numbers:
            return await ctx.send(  # type: ignore
                f"<:symbol_wrong:1536629915598848072> Bạn chưa nhập số ô đất nào!\n"
                f"*Cú pháp: `{prefix}pick <ô 1> <ô 2> ...`\n"
                f"Ví dụ: `{prefix}pick 1 2 3`*"
            )

        slot_ids = list(set([int(n) for n in raw_numbers]))
        
        from .farm_db import get_farm_data
        farm_data = await get_farm_data(self.bot, user_id)
        crops = farm_data.get("crops", {})
        valid_slots = sorted([s for s in slot_ids if str(s) in crops])
        
        if not valid_slots:
            return await ctx.send(  # type: ignore
                f"<:symbol_wrong:1536629915598848072> Các ô bạn chọn đều đang trống hoặc không tồn tại!"
            )
            
        slot_str = ", ".join(map(str, valid_slots))
        from .farm_ui import PickConfirmView
        view = PickConfirmView(self.bot, user_id, valid_slots, ctx.author)
        
        await ctx.send(
            f"<:symbol_alert:1537546957885542450> **CẢNH BÁO:** Bạn sắp cuốc bỏ cây trồng tại các **ô {slot_str}**.\n"
            f"Cây sẽ bị biến mất và không được hoàn lại hạt giống.\n"
            f"Bạn có chắc chắn muốn cuốc không?",
            view=view
        )

    @commands.hybrid_command(name="upgrade", aliases=["nangcap", "morong"])
    async def upgrade_cmd(self, ctx: commands.Context) -> None:
        """Mở rộng thêm ô đất cho Nông trại."""
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
        """Khu vực Chế biến Nông sản (Keg, Jar, Furnace)."""
        user_id = str(ctx.author.id)
        farm_data = await get_farm_data(self.bot, user_id)
        view = MachineView(self.bot, user_id, farm_data, ctx.author)
        embed = build_machine_embed(ctx.author, farm_data, page=view.page, per_page=view.per_page)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @commands.hybrid_command(name="craft", aliases=["chebien2", "bophuong"])
    @check_not_locked()
    async def craft_cmd(self, ctx: commands.Context, machine_id_str: str = None, quantity: int = 1) -> discord.Message | None:
        """ Chế tạo máy mới. VD: kcraft 101 2 hoặc kcraft keg 2 (101 = Keg)"""
        from .farm_db import get_farm_data, save_farm_data
        from .machine_config import MACHINE_BY_ID, MACHINES
        from .machine_ui import _get_queue_list, MAX_QUEUE_SLOTS, _get_item_display_name
        import uuid

        user_id = str(ctx.author.id)

        if not machine_id_str:
            lines = []
            for m_key, m_info in MACHINES.items():
                m_id = m_info["id"]
                m_icon = m_info["icon"]
                m_name = m_info["name"]
                ing_str = " + ".join(f"{_get_item_display_name(k)} x{v}" for k, v in m_info["ingredients"].items())
                lines.append(f"• `{m_id}` / `{m_key}` — {m_icon} **{m_name}**:\n  Cần: {ing_str}")
            embed = discord.Embed(
                title="<:symbol_machine:1536297937498275850> Chế Tạo Máy Chế Biến",
                description=f"Dùng lệnh `{ctx.prefix}craft <id_hoặc_tên_máy> [số_lượng]` để chế tạo.\n\n" + "\n\n".join(lines),
                color=0xe67e22,
            )
            embed.set_footer(text=f"Ví dụ: {ctx.prefix}craft 101 2 hoặc {ctx.prefix}craft keg 2")
            return await ctx.send(embed=embed)

        machine_key = None
        if machine_id_str.isdigit():
            m_num = int(machine_id_str)
            if m_num in MACHINE_BY_ID:
                machine_key = MACHINE_BY_ID[m_num]
        else:
            s = machine_id_str.lower().strip()
            name_map = {
                "keg": "keg", "thung": "keg", "u": "keg", "ruou": "keg",
                "jar": "jar", "mut": "jar", "lo": "jar", "hu": "jar",
                "furnace": "furnace", "loren": "furnace", "ren": "furnace",
            }
            if s in name_map:
                machine_key = name_map[s]
            elif s in MACHINES:
                machine_key = s

        if not machine_key:
            return await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không tìm thấy máy `{machine_id_str}`!\n"
                f"*Dùng `{ctx.prefix}craft` để xem danh sách máy và nguyên liệu.*"
            )

        machine = MACHINES[machine_key]

        if quantity <= 0:
            return await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Số lượng phải lớn hơn 0!")

        farm_data = await get_farm_data(self.bot, user_id)
        queue_list = _get_queue_list(farm_data)
        machine_queue = farm_data.setdefault("machine_queue", {})
        inventory = farm_data.get("inventory", {})

        current_slots = len(queue_list)
        if current_slots >= MAX_QUEUE_SLOTS:
            return await ctx.send(
                f"<:symbol_ban:1537546960003801319> {ctx.author.mention} Khu chế biến của bạn đã đầy (tối đa {MAX_QUEUE_SLOTS} máy)!\n"
                f"*Vui lòng dùng nút `Phá Dỡ Máy` trong lệnh `{ctx.prefix}machine` để giải phóng slot.*"
            )
        elif current_slots + quantity > MAX_QUEUE_SLOTS:
            free_slots = MAX_QUEUE_SLOTS - current_slots
            return await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Bạn không đủ slot trống! "
                f"(Đang có {current_slots}/{MAX_QUEUE_SLOTS}, muốn xây {quantity}).\n"
                f"*Số slot trống hiện tại: {free_slots}*"
            )

        # Kiểm tra nguyên liệu
        missing = []
        for item_id, qty_needed in machine["ingredients"].items():
            total_needed = qty_needed * quantity
            if item_id in ("wood", "wood_normal"):
                qty_have = inventory.get("wood", 0) + inventory.get("wood_normal", 0)
            else:
                qty_have = inventory.get(item_id, 0)
            if qty_have < total_needed:
                name = _get_item_display_name(item_id)
                missing.append(f"{name} (thiếu {total_needed - qty_have}, có {qty_have}/{total_needed})")

        if missing:
            missing_str = "\n".join(f"• {m}" for m in missing)
            return await ctx.send(
                f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Không đủ nguyên liệu để xây **{quantity}x {machine['name']}**!\n"
                f"{missing_str}"
            )

        # Trừ nguyên liệu
        for item_id, qty_needed in machine["ingredients"].items():
            total_needed = qty_needed * quantity
            if item_id in ("wood", "wood_normal"):
                rem = total_needed
                for w_key in ("wood_normal", "wood"):
                    avail = inventory.get(w_key, 0)
                    deduct = min(avail, rem)
                    if deduct > 0:
                        inventory[w_key] -= deduct
                        if inventory[w_key] <= 0:
                            del inventory[w_key]
                        rem -= deduct
                    if rem <= 0:
                        break
            else:
                inventory[item_id] -= total_needed
                if inventory[item_id] <= 0:
                    del inventory[item_id]

        # Thêm vào slots (như là idle machines)
        import time
        now = time.time()
        for i in range(quantity):
            slot_id = str(uuid.uuid4())
            machine_queue[slot_id] = {
                "machine_id": machine_key,
                "status": "idle",
                "start_time": now + i # To keep sorted order
            }

        farm_data["inventory"] = inventory
        farm_data["machine_queue"] = machine_queue
        await save_farm_data(self.bot, user_id, farm_data)

        await ctx.send(
            f"<:symbol_machine:1536297937498275850> {ctx.author.mention} Đã xây thành công **{quantity}x {machine['icon']} {machine['name']}**!\n"
            f"*Dùng `{ctx.prefix}machine` để xem máy mới trong nhà và bắt đầu chế biến.*"
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IdleFarmCog(bot))
