import discord
from discord.ext import commands, tasks
import time
import random
import json
import aiohttp
from typing import Optional

from cogs.common.db import (
    fetchrow_db, execute_db, get_or_create_event_profile,
    get_marriage, update_intimacy, update_marriage_interaction
)
from cogs.common.item_config import get_item_by_id

# ---------------------------------------------------------
# CONSTANTS & CONFIGS
# ---------------------------------------------------------
# Action Tiers: (cooldown_seconds, base_dtm)
ACTION_TIERS = {
    1: {"cd": 5 * 60, "dtm": 2},     # 5 phút, +2 DTM
    2: {"cd": 15 * 60, "dtm": 8},    # 15 phút, +8 DTM
    3: {"cd": 60 * 60, "dtm": 20},   # 1 giờ, +20 DTM
    4: {"cd": 3 * 60 * 60, "dtm": 50} # 3 giờ, +50 DTM
}

ACTIONS = {
    "poke":   {"tier": 1, "msg": [
        "{author} vừa chọc má {partner} đáng yêu quá đi!",
        "{author} lấy ngón tay ấn ấn vào người {partner} chọc ghẹo~",
        "{author} khều khều {partner} đòi sự chú ý!"
    ]},
    "pat":    {"tier": 1, "msg": [
        "{author} đang xoa đầu {partner} thật ngoan ~",
        "{author} vỗ vỗ đầu {partner} an ủi nè!",
        "{author} xoa rối tung tóc của {partner} luôn!"
    ]},
    "slap":   {"tier": 1, "msg": [
        "{author} vừa vả {partner} một cái chát!",
        "{author} giáng một cú tát điếng người vào mặt {partner}!",
        "{partner} ăn trọn cái tát của {author} vì tội lếu láo!"
    ]},
    "punch":  {"tier": 1, "msg": [
        "{author} đấm {partner} cái u đầu!",
        "{author} tung cú đấm ngàn cân vào người {partner}!",
        "{partner} ngã nhào vì cú đấm của {author}!"
    ]},
    "tickle": {"tier": 1, "msg": [
        "{author} thọc léc {partner} cười nắc nẻ!",
        "{author} cù lét {partner} không thở nổi luôn!",
        "{partner} giãy đành đạch vì bị {author} thọc léc!"
    ]},
    "bite":   {"tier": 1, "msg": [
        "{author} cắn nhẹ vào tay {partner}!",
        "{author} há miệng ngoạm {partner} một phát đau điếng!",
        "{author} cắn yêu {partner} để để lại dấu vết~"
    ]},
    
    "hug":    {"tier": 2, "msg": [
        "{author} ôm chầm lấy {partner} thật ấm áp ❤️",
        "{author} vòng tay ôm {partner} từ phía sau 💖",
        "{author} lao vào lòng {partner} ôm thật chặt 💕"
    ]},
    "cuddle": {"tier": 2, "msg": [
        "{author} rúc vào lòng {partner} làm nũng ❤️",
        "{author} âu yếm {partner} thật tình cảm 💖",
        "{author} và {partner} đang nằm ôm nhau thủ thỉ 💖"
    ]},
    "nom":    {"tier": 2, "msg": [
        "{author} gặm gặm {partner} như một chiếc bánh ngọt 🧁",
        "{author} măm măm má của {partner} ngấu nghiến~",
        "{author} nhai nhai {partner} vì quá đáng yêu!"
    ]},
    "snuggle":{"tier": 2, "msg": [
        "{author} cuộn tròn bên cạnh {partner} 💖",
        "{author} cọ cọ vào người {partner} nũng nịu 💕",
        "{author} rúc đầu vào cổ {partner} hít hà ❤️"
    ]},
    
    "kiss":   {"tier": 3, "msg": [
        "{author} trao cho {partner} một nụ hôn nồng cháy 💋",
        "{author} nhón chân lên hôn chụt vào môi {partner} 💋",
        "{author} và {partner} đang chìm đắm trong nụ hôn ngọt ngào 💕"
    ]},
    "lick":   {"tier": 3, "msg": [
        "{author} liếm láp {partner} như một chú cún con 🐶",
        "{author} liếm nhẹ lên má {partner} chụt chụt 😋",
        "{author} liếm môi {partner} gợi tình~"
    ]},
    "saylove":{"tier": 3, "msg": [
        "{author} thì thầm: 'Yêu {partner} nhiều lắm luôn á' 💕",
        "{author} nhìn sâu vào mắt {partner}: 'Mình thuộc về nhau nhé' 💖",
        "{author} hét lớn: '{partner} ƠI ANH/EM YÊU EM/ANH NHẤT TRÊN ĐỜI!' ❤️"
    ]},
    
    "fuck":   {"tier": 4, "msg": [
        "{author} và {partner} đang có những giây phút vô cùng mãnh liệt 🔞🔥",
        "{author} đè {partner} ra và cả hai chìm đắm vào dục vọng 🔞🔥",
        "{author} làm {partner} thở không ra hơi... mệt mỏi nhưng sung sướng 🔞🔥"
    ]},
    "seg":    {"tier": 4, "msg": [
        "{author} và {partner} đang tận hưởng đêm xuân đáng nhớ 🔞🔥",
        "{author} đang nhấp nhô nhịp nhàng cùng {partner} 🔞🔥",
        "Tiếng rên rỉ của {partner} hòa cùng nhịp thở gấp gáp của {author}... 🔞🔥"
    ]},
}

API_MAPPING = {
    "poke": "poke", "pat": "pat", "slap": "slap", "punch": "bonk", 
    "tickle": "smile", "bite": "bite", "hug": "hug", "cuddle": "cuddle", 
    "nom": "nom", "snuggle": "cuddle", "kiss": "kiss", "lick": "lick", 
    "saylove": "blush", "fuck": "nsfw/waifu", "seg": "nsfw/waifu"
}

async def fetch_anime_gif(action: str) -> Optional[str]:
    cat = API_MAPPING.get(action, "hug")
    url = f"https://api.waifu.pics/{cat}" if "nsfw" in cat else f"https://api.waifu.pics/sfw/{cat}"
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
    except Exception:
        pass
    return None

RING_BUFFS = {
    31: {"dtm_bonus": 0.0, "cd_reduction": 0.0, "work_bonus": 1.0},
    32: {"dtm_bonus": 0.1, "cd_reduction": 0.0, "work_bonus": 1.0},
    33: {"dtm_bonus": 0.2, "cd_reduction": 0.1, "work_bonus": 1.0},
    34: {"dtm_bonus": 0.5, "cd_reduction": 0.25, "work_bonus": 1.5},
}

class MarryConfirmView(discord.ui.View):
    def __init__(self, bot, proposer: discord.Member, target: discord.Member, ring_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.proposer = proposer
        self.target = target
        self.ring_id = ring_id

    @discord.ui.button(label="Đồng ý", style=discord.ButtonStyle.success, emoji="💍")
    async def btn_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Người ta cầu hôn bạn đâu mà bấm?", ephemeral=True)
            return
            
        uid1, uid2 = str(self.proposer.id), str(self.target.id)
        
        # Double check nếu ai đó kết hôn trong lúc chờ
        if await get_marriage(self.bot, uid1) or await get_marriage(self.bot, uid2):
            await interaction.response.send_message("❌ Một trong hai người đã kết hôn với người khác rồi!", ephemeral=True)
            self.stop()
            return
            
        # Trừ nhẫn trong inventory của người cầu hôn
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid1)
        if not row or not row["inventory"]:
            await interaction.response.send_message("❌ Không tìm thấy túi đồ của người cầu hôn!", ephemeral=True)
            return
        
        inv = json.loads(row["inventory"]) if isinstance(row["inventory"], str) else row["inventory"]
        ring_key = f"ring_{self.ring_id}"
        if inv.get(ring_key, 0) < 1:
            await interaction.response.send_message("❌ Người cầu hôn đã làm mất chiếc nhẫn rồi!", ephemeral=True)
            return
            
        inv[ring_key] -= 1
        await execute_db(self.bot, "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", uid1, json.dumps(inv))
        
        # Insert marriage
        sql = """
            INSERT INTO marriages (user1_id, user2_id, ring_id) 
            VALUES ($1, $2, $3)
        """
        await execute_db(self.bot, sql, uid1, uid2, self.ring_id)
        
        # Update event_profiles marry_to
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = $2 WHERE discord_id = $1", uid1, uid2)
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = $2 WHERE discord_id = $1", uid2, uid1)
        
        for child in self.children: child.disabled = True
        
        ring_info = get_item_by_id(self.ring_id)
        ring_name = ring_info['name'] if ring_info else "Nhẫn Cỏ"
        
        emb = interaction.message.embeds[0]
        emb.title = "🎉 CHÚC MỪNG TÂN LANG TÂN NƯƠNG! 🎉"
        emb.description = f"💖 **{self.proposer.display_name}** và **{self.target.display_name}** đã chính thức về chung một nhà với chiếc **{ring_name}**!"
        emb.color = discord.Color.gold()
        
        await interaction.response.edit_message(embed=emb, view=self)
        self.stop()

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.danger, emoji="💔")
    async def btn_decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Xin lỗi, bạn không phải là nhân vật chính.", ephemeral=True)
            return
            
        for child in self.children: child.disabled = True
        emb = interaction.message.embeds[0]
        emb.title = "💔 LỜI CẦU HÔN BỊ TỪ CHỐI..."
        emb.description = f"Rất tiếc, **{self.target.display_name}** đã từ chối lời cầu hôn của **{self.proposer.display_name}**."
        emb.color = discord.Color.dark_grey()
        
        await interaction.response.edit_message(embed=emb, view=self)
        self.stop()


class MarriageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.action_cooldowns: dict[str, dict[str, float]] = {} # uid -> {action_tier -> timestamp}
        self.anti_ghosting_loop.start()

    def cog_unload(self):
        self.anti_ghosting_loop.cancel()

    @commands.hybrid_command(name="marry", aliases=["kethon"])
    async def marry_cmd(self, ctx: commands.Context, target: Optional[discord.Member] = None, ring_id: int = 31):
        """💍 Cầu hôn ai đó hoặc xem Profile Tình Yêu (nếu không tag ai)."""
        uid = str(ctx.author.id)
        
        # 1. Nếu không tag ai -> Hiển thị Profile Tình Yêu
        if not target:
            mar = await get_marriage(self.bot, uid)
            if not mar:
                return await ctx.send("❌ Bạn chưa kết hôn với ai cả! Hãy dùng `y!marry @user` để cầu hôn nhé.")
                
            partner_id = mar["user2_id"] if mar["user1_id"] == uid else mar["user1_id"]
            partner = ctx.guild.get_member(int(partner_id))
            partner_name = partner.display_name if partner else f"User {partner_id}"
            
            days = (discord.utils.utcnow() - mar["marry_date"]).days
            
            ring_info = get_item_by_id(mar["ring_id"])
            ring_name = f"{ring_info['icon']} {ring_info['name']}" if ring_info else "🌿 Nhẫn Cỏ"
            
            pet_text = f"{mar['pet_type']} (Lv{mar['pet_level']})" if mar['pet_type'] else "Chưa nhận nuôi (Cần 200 DTM)"
            
            marry_date_str = mar['marry_date'].strftime('%d/%m/%Y')
            
            promise = mar['promise_text']
            if promise:
                promise_lines = promise.split('\n')
                formatted_promise = "\n".join(f"🎀 {line.strip()}" for line in promise_lines if line.strip())
            else:
                formatted_promise = "🎀 Chưa có lời thề non hẹn biển nào... (Dùng y!promise)"
                
            desc = (
                f"💖 **So Sweet** 💖\n\n"
                f"{ctx.author.mention} 💖 <@{partner_id}>\n"
                f"💞 **Love Points:** {mar['intimacy_points']:,} Pts\n"
                f"💎 **Married day:** {marry_date_str}\n"
                f"🎀 **Been married for {days} days**\n\n"
                f"***Promises for loving:***\n"
                f"{formatted_promise}"
            )
            
            emb = discord.Embed(description=desc, color=discord.Color.from_rgb(255, 182, 193))
            emb.set_author(name="And after that... They live happily ever after~")
            emb.set_thumbnail(url=ctx.author.display_avatar.url)
            
            now_str = discord.utils.utcnow().strftime("%H:%M")
            emb.set_footer(text=f"💖 Happily ever after~ 💖 - Today at {now_str}")
            
            return await ctx.send(embed=emb)
            
        # 2. Cầu hôn
        if target.id == ctx.author.id or target.bot:
            return await ctx.send("❌ Bạn không thể cầu hôn chính mình hoặc Bot!")
            
        uid2 = str(target.id)
        if await get_marriage(self.bot, uid) or await get_marriage(self.bot, uid2):
            return await ctx.send("❌ Một trong hai người đã có gia đình! Cấm ngoại tình!")
            
        if ring_id not in RING_BUFFS:
            return await ctx.send("❌ Nhẫn không hợp lệ! Vui lòng chọn nhẫn ID từ 31 đến 34.")
            
        # Kiểm tra inventory
        await get_or_create_event_profile(self.bot, uid)
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        inv = json.loads(row["inventory"]) if (row and row["inventory"]) else {}
        if isinstance(inv, str): inv = json.loads(inv)
        
        if inv.get(f"ring_{ring_id}", 0) < 1:
            return await ctx.send(f"❌ Bạn không có chiếc nhẫn này trong túi đồ! Dùng `y!shop` để mua nhé.")
            
        ring_info = get_item_by_id(ring_id)
        ring_name = f"{ring_info['icon']} {ring_info['name']}" if ring_info else "🌿 Nhẫn Cỏ"
        
        emb = discord.Embed(
            title="💍 LỜI CẦU HÔN TỪ TRÁI TIM!",
            description=f"💖 {target.mention} ơi!\n**{ctx.author.display_name}** đang quỳ một chân và đưa ra chiếc **{ring_name}** để cầu hôn bạn!\nBạn có đồng ý đi cùng người ấy đến cuối con đường không?",
            color=discord.Color.pink()
        )
        view = MarryConfirmView(self.bot, ctx.author, target, ring_id)
        await ctx.send(content=target.mention, embed=emb, view=view)

    @commands.hybrid_command(name="divorce", aliases=["lydi", "lyhon"])
    async def divorce_cmd(self, ctx: commands.Context):
        """💔 Ly hôn với người hiện tại (Sẽ xóa toàn bộ DTM)."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Bạn chưa kết hôn mà đòi ly hôn cái gì?")
            
        await execute_db(self.bot, "DELETE FROM marriages WHERE id = $1", mar["id"])
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", mar["user1_id"])
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", mar["user2_id"])
        
        await ctx.send(f"💔 **{ctx.author.display_name}** đã chính thức đệ đơn ly hôn. Đường ai nấy đi, tình nghĩa đôi mình từ nay chấm dứt.")

    @commands.hybrid_command(name="promise", aliases=["hua"])
    async def promise_cmd(self, ctx: commands.Context, *, text: str):
        """💌 Khắc ghi lời thề non hẹn biển (Chỉ hiện trong y!marry)."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Cần phải kết hôn mới có người để thề non hẹn biển chứ!")
            
        if len(text) > 200:
            return await ctx.send("❌ Lời hứa quá dài! Hãy viết ngắn gọn dưới 200 ký tự thôi.")
            
        await execute_db(self.bot, "UPDATE marriages SET promise_text = $1 WHERE id = $2", text, mar["id"])
        await ctx.send("💌 Lời hứa của hai bạn đã được khắc ghi vào Cây Tình Yêu!")

    @commands.hybrid_command(name="adopt")
    async def adopt_cmd(self, ctx: commands.Context, pet_type: str):
        """🐶 Nhận nuôi thú cưng chung (dog/cat). Yêu cầu > 200 DTM."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        
        if not mar: return await ctx.send("❌ Hãy tìm một nửa của mình trước khi nghĩ đến việc nuôi con nhé!")
        if mar["pet_type"]: return await ctx.send(f"❌ Hai bạn đã nuôi một bé **{mar['pet_type']}** rồi!")
        if mar["intimacy_points"] < 200: return await ctx.send("❌ Tình cảm chưa đủ chín muồi (Cần 200 DTM) để gánh vác trách nhiệm nuôi Pet!")
        
        ptype = pet_type.lower()
        if ptype not in ["dog", "cat", "chó", "mèo"]:
            return await ctx.send("❌ Hiện tại trại thú giống chỉ cung cấp `dog` hoặc `cat` thôi nhé.")
            
        pet_display = "Chó Corgi 🐶" if ptype in ["dog", "chó"] else "Mèo Anh Lông Ngắn 🐱"
        await execute_db(self.bot, "UPDATE marriages SET pet_type = $1 WHERE id = $2", pet_display, mar["id"])
        await ctx.send(f"🎉 Chúc mừng hai bạn đã nhận nuôi thành công bé **{pet_display}**!")

    @commands.hybrid_command(name="upgradering", aliases=["nangcapnhan"])
    async def upgradering_cmd(self, ctx: commands.Context, ring_id: int):
        """💍 Đổi nhẫn cưới hiện tại sang nhẫn xịn hơn (yêu cầu có nhẫn trong túi đồ)."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Bạn chưa kết hôn nên không thể nâng cấp nhẫn!")
            
        current_ring = mar.get("ring_id", 31)
        if ring_id not in RING_BUFFS:
            return await ctx.send("❌ ID Nhẫn không hợp lệ! Vui lòng chọn nhẫn ID từ 32 đến 34.")
            
        if ring_id <= current_ring:
            return await ctx.send(f"❌ Bạn chỉ có thể đổi sang nhẫn xịn hơn (ID > {current_ring})!")
            
        # Check inventory
        from cogs.common.db import fetchrow_db
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        inv = json.loads(row["inventory"]) if (row and row["inventory"]) else {}
        if isinstance(inv, str): inv = json.loads(inv)
        
        ring_key = f"ring_{ring_id}"
        if inv.get(ring_key, 0) < 1:
            return await ctx.send(f"❌ Bạn không có chiếc nhẫn này trong túi đồ! Dùng `y!shop` để mua trước nhé.")
            
        # Deduct ring from inventory
        inv[ring_key] -= 1
        await execute_db(self.bot, "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", uid, json.dumps(inv))
        
        # Update marriage ring
        await execute_db(self.bot, "UPDATE marriages SET ring_id = $1 WHERE id = $2", ring_id, mar["id"])
        
        from cogs.common.item_config import get_item_by_id
        ring_info = get_item_by_id(ring_id)
        ring_name = f"{ring_info['icon']} {ring_info['name']}" if ring_info else f"Nhẫn ID {ring_id}"
        
        await ctx.send(f"🎉 Chúc mừng! Cuộc hôn nhân của hai bạn vừa được nâng tầm với chiếc **{ring_name}** siêu lấp lánh!")

    @commands.hybrid_command(name="gift", aliases=["tangqua"])
    async def gift_cmd(self, ctx: commands.Context, target: discord.Member, amount: int):
        """🎁 Tặng tiền cho vợ/chồng để tăng Điểm Thân Mật (1000 điểm = 10 DTM)."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar or (mar["user1_id"] != str(target.id) and mar["user2_id"] != str(target.id)):
            return await ctx.send("❌ Bạn chỉ có thể tặng quà đặc biệt này cho vợ/chồng hợp pháp của mình thôi!")
            
        if amount < 1000:
            return await ctx.send("❌ Phải tặng ít nhất 1,000 điểm mới bõ công chứ!")
            
        # Deduct money from sender
        from cogs.common.db import deduct_event_points, add_event_points
        ok = await deduct_event_points(self.bot, uid, float(amount))
        if not ok:
            return await ctx.send("❌ Bạn không có đủ tiền để tặng quà!")
            
        # Add money to receiver
        await add_event_points(self.bot, str(target.id), float(amount), is_earned=False)
        
        # Calculate DTM (1000 points = 10 DTM)
        dtm_gain = int(amount / 100)
        await update_intimacy(self.bot, uid, dtm_gain)
        
        emb = discord.Embed(
            title="🎁 Tặng Quà Thành Công!",
            description=f"**{ctx.author.display_name}** vừa ting ting cho **{target.display_name}** số tiền **{amount:,}** điểm!\nTình cảm của hai bạn tăng thêm `{dtm_gain} DTM` 💖",
            color=discord.Color.brand_red()
        )
        await ctx.send(embed=emb)

    @commands.hybrid_command(name="coupletask")
    async def coupletask_cmd(self, ctx: commands.Context):
        """📋 Xem nhiệm vụ cặp đôi hàng ngày."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Đã kết hôn đâu mà đòi làm nhiệm vụ chung?")
            
        task_str = mar.get("couple_task")
        task_data = json.loads(task_str) if (task_str and isinstance(task_str, str)) else (task_str or {})
        today_str = discord.utils.utcnow().strftime("%Y-%m-%d")
        
        if task_data.get("date") != today_str:
            COUPLE_TASKS = [
                {"type": "hug", "target": 3, "desc": "ôm nhau 3 lần"},
                {"type": "kiss", "target": 3, "desc": "hôn nhau 3 lần"},
                {"type": "work", "target": 2, "desc": "làm việc chung 2 lần"},
                {"type": "poke", "target": 5, "desc": "chọc ghẹo nhau 5 lần"},
                {"type": "pat", "target": 5, "desc": "xoa đầu nhau 5 lần"},
            ]
            task = random.choice(COUPLE_TASKS)
            task_data = {
                "date": today_str,
                "type": task["type"],
                "target": task["target"],
                "desc": task["desc"],
                "progress": 0,
                "completed": False
            }
            await execute_db(self.bot, "UPDATE marriages SET couple_task = $1::jsonb WHERE id = $2", json.dumps(task_data), mar["id"])
            
        if task_data["completed"]:
            return await ctx.send("✅ Hai bạn đã hoàn thành nhiệm vụ của ngày hôm nay rồi! Hãy quay lại vào ngày mai nhé.")
            
        emb = discord.Embed(
            title="📋 Nhiệm Vụ Cặp Đôi (Daily)",
            description=f"Nhiệm vụ hôm nay: **Hai người phải {task_data['desc']}**.\n\nTiến độ: **{task_data['progress']} / {task_data['target']}**",
            color=discord.Color.pink()
        )
        emb.set_footer(text="Hoàn thành để nhận +100 Điểm Thân Mật (DTM)!")
        await ctx.send(embed=emb)

    # ---------------------------------------------------------
    # ACTION COMMANDS LOGIC
    # ---------------------------------------------------------
    async def handle_action(self, ctx: commands.Context, target: discord.Member, action: str):
        if target.id == ctx.author.id or target.bot:
            return await ctx.send("❌ Tự kỷ à? Hoặc tha cho con Bot đi!")
            
        uid1 = str(ctx.author.id)
        uid2 = str(target.id)
        
        mar = await get_marriage(self.bot, uid1)
        if not mar or (mar["user1_id"] != uid2 and mar["user2_id"] != uid2):
            return await ctx.send("❌ Úi! Hành động thân mật này chỉ dành cho vợ chồng hợp pháp thôi nhé! (Bạn phải kết hôn với người này trước).")
            
        # Calculate Ring Buffs
        ring_id = mar.get("ring_id", 31)
        buffs = RING_BUFFS.get(ring_id, RING_BUFFS[31])
        
        act = ACTIONS[action]
        tier = str(act["tier"])
        base_cd = ACTION_TIERS[act["tier"]]["cd"]
        base_dtm = ACTION_TIERS[act["tier"]]["dtm"]
        
        actual_cd = base_cd * (1.0 - buffs["cd_reduction"])
        
        # Check Cooldown
        if uid1 not in self.action_cooldowns: self.action_cooldowns[uid1] = {}
        last_time = self.action_cooldowns[uid1].get(tier, 0)
        now = time.time()
        
        if now - last_time < actual_cd:
            rem = int(actual_cd - (now - last_time))
            m, s = divmod(rem, 60)
            h, m = divmod(m, 60)
            wait_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
            return await ctx.send(f"⏳ Cứ từ từ thôi! Quấn quýt quá lại nhanh chán. Đợi thêm **{wait_str}** nữa mới được dùng lại hành động này nhé!")
            
        self.action_cooldowns[uid1][tier] = now
        
        # Calculate DTM
        actual_dtm = int(base_dtm * (1.0 + buffs["dtm_bonus"]))
        
        # Random fail for tier 1 (Chọc ghẹo)
        if act["tier"] == 1 and random.random() < 0.2:
            actual_dtm = -1 # Trừ 1 điểm nếu đối phương quạu
            msg = f"💢 {ctx.author.display_name} chọc ghẹo không đúng lúc, {target.display_name} đang quạu! (Trừ 1 DTM)"
        else:
            msg = random.choice(act["msg"]).format(author=ctx.author.display_name, partner=target.mention) + f" `(+{actual_dtm} DTM)`"
            
            # Tiên quyết: Chỉ update task nếu thành công (không fail)
            task_str = mar.get("couple_task")
            if task_str:
                task_data = json.loads(task_str) if isinstance(task_str, str) else task_str
                today_str = discord.utils.utcnow().strftime("%Y-%m-%d")
                if task_data.get("date") == today_str and task_data.get("type") == action and not task_data.get("completed"):
                    task_data["progress"] = task_data.get("progress", 0) + 1
                    if task_data["progress"] >= task_data["target"]:
                        task_data["completed"] = True
                        actual_dtm += 100
                        msg += f"\n🎉 **Nhiệm Vụ Cặp Đôi Hoàn Thành!** (+100 DTM)"
                    await execute_db(self.bot, "UPDATE marriages SET couple_task = $1::jsonb WHERE id = $2", json.dumps(task_data), mar["id"])
        
        # Update DB
        await update_intimacy(self.bot, uid1, actual_dtm)
        await update_marriage_interaction(self.bot, uid1)
        
        emb = discord.Embed(description=msg, color=discord.Color.pink())
        
        gif_url = await fetch_anime_gif(action)
        if gif_url:
            emb.set_image(url=gif_url)
            
        await ctx.send(embed=emb)

    # Lệnh Action Tiers
    @commands.hybrid_command(aliases=["choc"])
    async def poke(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "poke")
    @commands.hybrid_command(aliases=["xoadau"])
    async def pat(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "pat")
    @commands.hybrid_command(aliases=["tat"])
    async def slap(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "slap")
    @commands.hybrid_command(aliases=["dam"])
    async def punch(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "punch")
    @commands.hybrid_command(aliases=["choclet"])
    async def tickle(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "tickle")
    @commands.hybrid_command(aliases=["can"])
    async def bite(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "bite")
    
    @commands.hybrid_command(aliases=["om"])
    async def hug(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "hug")
    @commands.hybrid_command(aliases=["auyem"])
    async def cuddle(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "cuddle")
    @commands.hybrid_command(aliases=["mam"])
    async def nom(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "nom")
    @commands.hybrid_command(aliases=["nung", "nũng"])
    async def snuggle(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "snuggle")
    
    @commands.hybrid_command(aliases=["hon", "hun"])
    async def kiss(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "kiss")
    @commands.hybrid_command(aliases=["liem"])
    async def lick(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "lick")
    @commands.hybrid_command(aliases=["noiyeu", "iuem", "iuanh"])
    async def saylove(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "saylove")
    
    @commands.hybrid_command(aliases=["seg"])
    async def fuck(self, ctx, target: discord.Member): await self.handle_action(ctx, target, "fuck")


    # ---------------------------------------------------------
    # BACKGROUND TASK: ANTI GHOSTING
    # ---------------------------------------------------------
    @tasks.loop(hours=24)
    async def anti_ghosting_loop(self):
        """Trừ DTM nếu không tương tác > 3 ngày, xóa DB nếu DTM <= 0."""
        # Chạy lúc 00:00 hoặc mỗi 24h tùy config, tạm thời loop mỗi 24h
        sql_get = "SELECT id, user1_id, user2_id, intimacy_points, last_interaction FROM marriages"
        pool = self.bot.db_pool
        if not pool: return
        
        try:
            rows = await pool.fetch(sql_get)
            now = discord.utils.utcnow()
            channel = self.bot.get_channel(1514504541104640170)
            
            for row in rows:
                last_interaction = row["last_interaction"]
                if not last_interaction: continue
                
                days_diff = (now - last_interaction).days
                if days_diff > 3:
                    new_dtm = row["intimacy_points"] - 50
                    if new_dtm <= 0:
                        # Ly Hôn Tự Động
                        await pool.execute("DELETE FROM marriages WHERE id = $1", row["id"])
                        await pool.execute("UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", row["user1_id"])
                        await pool.execute("UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", row["user2_id"])
                        
                        if channel:
                            await channel.send(f"💔 **Tình cảm nhạt phai...**\nDo quá thờ ơ lơ lạnh, <@{row['user1_id']}> và <@{row['user2_id']}> đã chính thức ly hôn bởi hệ thống.")
                    else:
                        # Trừ điểm
                        await pool.execute("UPDATE marriages SET intimacy_points = $1 WHERE id = $2", new_dtm, row["id"])
                        
        except Exception as e:
            print(f"Lỗi Anti Ghosting Loop: {e}")

    @anti_ghosting_loop.before_loop
    async def before_anti_ghosting(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MarriageCog(bot))
