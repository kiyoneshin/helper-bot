import os
import json
import logging
import discord
from discord.ext import commands

from cogs.common.db import fetchrow_db, execute_db, add_event_points, check_not_locked, get_or_create_event_profile
from cogs.common.item_config import get_item_by_id

log = logging.getLogger("GiftCodeCog")
CODES_FILE = "data/gift_codes.json"

class GiftCodeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load_codes(self) -> dict:
        if not os.path.exists(CODES_FILE):
            return {}
        try:
            with open(CODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading gift codes: {e}")
            return {}

    @commands.command(name="code", aliases=["giftcode", "nhapcode"], help="Nhập mã quà tặng. Cú pháp: {prefix}code <code>")
    @check_not_locked()
    async def code_cmd(self, ctx: commands.Context, *, code_str: str = None):  # type: ignore
        if not code_str:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Vui lòng nhập mã code! Cú pháp: `{ctx.prefix}code <code>`")
            return

        code_upper = code_str.strip().upper()
        codes_data = self._load_codes()

        if code_upper not in codes_data:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Code **{code_upper}** không tồn tại hoặc đã hết hạn!")
            return

        code_info = codes_data[code_upper]
        uid = str(ctx.author.id)

        # 1. Kiểm tra lịch sử nhận code
        row = await fetchrow_db(self.bot, "SELECT 1 FROM gift_codes_history WHERE discord_id = $1 AND code_name = $2", uid, code_upper)
        if row:
            await ctx.send(f"<:symbol_wrong:1536629915598848072> {ctx.author.mention} Bạn đã sử dụng code **{code_upper}** rồi, không thể nhận lại!")
            return

        # 2. Tính toán phần thưởng gốc
        rewards = code_info.get("rewards", {})
        total_points = rewards.get("points", 0)
        
        # Merge items: { item_id: quantity }
        total_items: dict[int, int] = {}
        for item in rewards.get("items", []):
            item_id = item.get("id")
            if item_id is not None:
                total_items[item_id] = total_items.get(item_id, 0) + item.get("quantity", 1)
        
        # 3. Tính toán role bonus (Cộng dồn từ TẤT CẢ các role hợp lệ)
        # TODO: Người dùng chưa nghĩ ra role bonus cụ thể, nhưng cấu trúc đã có sẵn để họ thêm vào file JSON.
        role_bonus_data = code_info.get("role_bonus", {})
        user_role_ids = [str(r.id) for r in ctx.author.roles]  # type: ignore
        
        for role_id_str, bonus_rewards in role_bonus_data.items():
            if role_id_str in user_role_ids:
                total_points += bonus_rewards.get("points", 0)
                for item in bonus_rewards.get("items", []):
                    item_id = item.get("id")
                    if item_id is not None:
                        total_items[item_id] = total_items.get(item_id, 0) + item.get("quantity", 1)
                        
        # 4. Trả thưởng
        # - Đảm bảo user có profile
        await get_or_create_event_profile(self.bot, uid)
        
        # - Cộng điểm sự kiện (is_earned=False để không tính vào đua top)
        if total_points > 0:
            await add_event_points(self.bot, uid, float(total_points), is_earned=False)

        # - Thêm vật phẩm vào kho
        if total_items:
            inv_row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
            inv = {}
            if inv_row and inv_row["inventory"]:
                raw = inv_row["inventory"]
                inv = json.loads(raw) if isinstance(raw, str) else raw

            for item_id, quantity in total_items.items():
                str_id = str(item_id)
                inv[str_id] = inv.get(str_id, 0) + quantity
                
            await execute_db(self.bot, "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", uid, json.dumps(inv))

        # 5. Lưu lịch sử
        await execute_db(self.bot, "INSERT INTO gift_codes_history (discord_id, code_name) VALUES ($1, $2)", uid, code_upper)

        # 6. Tạo Embed thông báo thành công
        embed = discord.Embed(
            title="Đổi Code Thành Công!",
            description=f"{ctx.author.mention} đã nhận thưởng từ code **{code_upper}**\n\n**Bạn nhận được:**",
            color=0x2ecc71
        )
        
        rewards_list = []
        if total_points > 0:
            # <:symbol_money_2:1537567535229050970> là emoji điểm sự kiện
            rewards_list.append(f"+ **{total_points:,.0f}** <:symbol_money_2:1537567535229050970> Điểm Sự Kiện")
            
        for item_id, quantity in total_items.items():
            item_data = get_item_by_id(item_id)
            if item_data:
                icon = item_data.get("icon", "📦")
                name = item_data.get("name", f"Item {item_id}")
                rewards_list.append(f"+ **{quantity}** {icon} {name}")
            else:
                rewards_list.append(f"+ **{quantity}** Vật phẩm không xác định (ID: {item_id})")

        if rewards_list:
            embed.description += "\n" + "\n".join(rewards_list)  # type: ignore
        else:
            embed.description += "\n*(Không có phần thưởng nào)*"  # type: ignore

        embed.set_footer(text="Cảm ơn bạn đã tham gia sự kiện cùng Angelic!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiftCodeCog(bot))
