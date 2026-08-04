import discord
from discord.ext import commands, tasks
import time
import random
import json
import aiohttp
import datetime
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
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
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
        
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        
        ring_info = get_item_by_id(self.ring_id)
        ring_name = ring_info['name'] if ring_info else "Nhẫn Cỏ"
        
        emb = interaction.message.embeds[0] if interaction.message and getattr(interaction.message, "embeds", None) else discord.Embed()
        emb.title = "🎉 CHÚC MỪNG TÂN LANG TÂN NƯƠNG! 🎉"
        emb.description = f"💖 **{self.proposer.display_name}** và **{self.target.display_name}** đã chính thức về chung một nhà với chiếc **{ring_name}**!"
        emb.color = discord.Color.gold()
        
        await interaction.response.edit_message(embed=emb, view=self)
        self.stop()

    @discord.ui.button(label="Từ chối/Hủy", style=discord.ButtonStyle.danger, emoji="💔")
    async def btn_decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.target.id, self.proposer.id):
            await interaction.response.send_message("❌ Xin lỗi, bạn không phải là nhân vật chính.", ephemeral=True)
            return
            
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        emb = interaction.message.embeds[0] if interaction.message and getattr(interaction.message, "embeds", None) else discord.Embed()
        
        if interaction.user.id == self.target.id:
            emb.title = "💔 LỜI CẦU HÔN BỊ TỪ CHỐI..."
            emb.description = f"Rất tiếc, **{self.target.display_name}** đã từ chối lời cầu hôn của **{self.proposer.display_name}**."
        else:
            emb.title = "💔 LỜI CẦU HÔN BỊ HỦY..."
            emb.description = f"**{self.proposer.display_name}** đã rút lại lời cầu hôn với **{self.target.display_name}**."
            
        emb.color = discord.Color.dark_grey()
        
        await interaction.response.edit_message(embed=emb, view=self)
        self.stop()

class PetAdoptConfirmView(discord.ui.View):
    def __init__(self, bot, author, mar_id, new_base_name):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.mar_id = mar_id
        self.new_base_name = new_base_name

    @discord.ui.button(label="Chắc chắn Đổi", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Bạn không phải là người đưa ra yêu cầu!", ephemeral=True)
            
        from cogs.common.db import execute_db
        await execute_db(self.bot, "UPDATE marriages SET pet_type = $1, pet_name = NULL, pet_exp = 0.0 WHERE id = $2", self.new_base_name, self.mar_id)
        
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        await interaction.response.edit_message(content=f"🎉 Bạn đã đổi thú cưng thành công! Chào mừng bé **{self.new_base_name} Sơ Sinh** đến với gia đình! (Kinh nghiệm thú cưng đã reset về 0). Dùng `y!namepet` để đặt tên nhé.", view=self)

    @discord.ui.button(label="Hủy bỏ", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Bạn không phải là người đưa ra yêu cầu!", ephemeral=True)
            
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        await interaction.response.edit_message(content="Đã hủy bỏ việc đổi thú cưng. Bé cưng cũ vẫn ở lại với bạn!", view=self)


class DivorceConfirmView(discord.ui.View):
    def __init__(self, bot, proposer: discord.Member, target_id: int, mar_id: int, user1_id: str, user2_id: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.proposer = proposer
        self.target_id = target_id
        self.mar_id = mar_id
        self.user1_id = user1_id
        self.user2_id = user2_id

    @discord.ui.button(label="Đồng ý Ly Hôn", style=discord.ButtonStyle.success, emoji="💔")
    async def btn_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.proposer.id, self.target_id):
            return await interaction.response.send_message("❌ Đây không phải chuyện của bạn!", ephemeral=True)
            
        await interaction.response.defer()
        
        await execute_db(self.bot, "DELETE FROM marriages WHERE id = $1", self.mar_id)
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", self.user1_id)
        await execute_db(self.bot, "UPDATE event_profiles SET marry_to = NULL WHERE discord_id = $1", self.user2_id)
        
        for child in self.children:
            if getattr(child, 'disabled', None) is not None or isinstance(child, discord.ui.Button):
                child.disabled = True # type: ignore
                
        emb = interaction.message.embeds[0] if interaction.message and getattr(interaction.message, "embeds", None) else discord.Embed()
        emb.title = "💔 ĐÃ LY HÔN"
        emb.description = f"Đơn ly hôn đã được xác nhận bởi **{interaction.user.display_name}**. Đường ai nấy đi, tình nghĩa đôi mình từ nay chấm dứt."
        emb.color = discord.Color.dark_grey()
        
        await interaction.edit_original_response(embed=emb, view=self)
        self.stop()

    @discord.ui.button(label="Hủy Bỏ", style=discord.ButtonStyle.danger)
    async def btn_decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.proposer.id, self.target_id):
            return await interaction.response.send_message("❌ Đây không phải chuyện của bạn!", ephemeral=True)
            
        for child in self.children:
            if getattr(child, 'disabled', None) is not None or isinstance(child, discord.ui.Button):
                child.disabled = True # type: ignore
                
        emb = interaction.message.embeds[0] if interaction.message and getattr(interaction.message, "embeds", None) else discord.Embed()
        emb.title = "❌ HỦY LY HÔN"
        emb.description = f"**{interaction.user.display_name}** đã hủy bỏ quyết định ly hôn. Hãy cố gắng trân trọng nhau nhé!"
        emb.color = discord.Color.green()
        
        await interaction.response.edit_message(embed=emb, view=self)
        self.stop()

class MarriageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.action_cooldowns: dict[str, dict[str, float]] = {} # uid -> {action -> timestamp}
        self.anti_ghosting_loop.start()

    async def cog_unload(self):
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
            
            days = (discord.utils.utcnow() - mar["marry_date"]).days
            days = max(0, days)
            
            ring_info = get_item_by_id(mar["ring_id"])
            
            promise = mar.get('promise_text')
            promise_data = {}
            if promise:
                try:
                    promise_data = json.loads(promise)
                except Exception:
                    # Nếu là dạng chuỗi cũ, tự động gán cho người dùng 1
                    promise_data = {str(mar["user1_id"]): promise}

            formatted_promise = ""
            for uid_str in (str(mar["user1_id"]), str(mar["user2_id"])):
                member2 = ctx.guild.get_member(int(uid_str)) if ctx.guild else None
                p_name = member2.display_name if member2 else f"User {uid_str}"
                if uid_str in promise_data:
                    ptext = promise_data[uid_str]
                    ptext_lines = ptext.split('\n')
                    for i, line in enumerate(ptext_lines):
                        if line.strip():
                            if i == 0:
                                formatted_promise += f"💖 **{p_name}**: {line.strip()}\n"
                            else:
                                formatted_promise += f"    {line.strip()}\n"
                else:
                    formatted_promise += f"💔 **{p_name}**: chưa có lời thề non hẹn biển nào...\n"
                
            marry_date_str = mar['marry_date'].strftime('%d/%m/%Y')
            
            desc = (
                f"💖 **So Sweet** 💖\n\n"
                f"{ctx.author.mention} 💖 <@{partner_id}>\n"
                f"💞 **Love Points:** {float(mar['intimacy_points']):,.1f} Pts\n"
                f"💎 **Married day:** {marry_date_str}\n"
                f"*** Been married for {days} days\n\n"
            )
            
            if mar.get("pet_type"):
                pet_exp = float(mar.get('pet_exp', 0.0))
                if pet_exp < 1000:
                    stage = "Sơ Sinh 🐣"
                elif pet_exp < 5000:
                    stage = "Trưởng Thành 🐾"
                else:
                    stage = "Thần Thú 🌟"
                    
                icon_map = {
                    "Chó": "🐶", "Mèo": "🐱", "Cáo": "🦊", "Sói": "🐺", 
                    "Cánh Cụt": "🐧", "Thỏ": "🐰", "Gấu": "🐻", "Rồng": "🐉"
                }
                base_type = mar["pet_type"]
                icon = icon_map.get(base_type, "🐾")
                pet_level = int(pet_exp / 200) + 1
                
                pet_name_db = mar.get("pet_name")
                display_name = f"{pet_name_db}" if pet_name_db else f"{base_type}"
                desc += f"🐾 **Thú Cưng Chung**: {display_name} {icon} *(Lv.{pet_level} - {stage})*\n\n"
                
            desc += (
                f"***Promises for loving:***\n"
                f"{formatted_promise}"
            )
            
            emb = discord.Embed(description=desc, color=discord.Color.from_rgb(255, 182, 193))
            emb.set_author(name="And after that... They live happily ever after~")
            
            if mar.get("custom_image"):
                emb.set_image(url=mar["custom_image"])
                
            emb.set_thumbnail(url=ctx.author.display_avatar.url)
            
            now_str = (discord.utils.utcnow() + datetime.timedelta(hours=7)).strftime("%H:%M")
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
        if not isinstance(ctx.author, discord.Member):
            return await ctx.send("❌ Lệnh này chỉ dùng trong server!")
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
            
        # Lấy promise_text hiện tại và cập nhật
        try:
            promise_data = json.loads(mar["promise_text"]) if mar["promise_text"] else {}
        except Exception:
            promise_data = {str(mar["user1_id"]): mar["promise_text"]} if mar["promise_text"] else {}
            
        promise_data[uid] = text
        
        await execute_db(self.bot, "UPDATE marriages SET promise_text = $1 WHERE id = $2", json.dumps(promise_data), mar["id"])
        await ctx.send("💌 Lời hứa của bạn đã được khắc ghi vào Cây Tình Yêu!")

    @commands.hybrid_command(name="adopt")
    async def adopt_cmd(self, ctx: commands.Context, pet_type: str):
        """🐶 Nhận nuôi thú cưng (dog/cat/fox/wolf/penguin/rabbit/bear/dragon). Yêu cầu > 200 DTM."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        
        if not mar: return await ctx.send("❌ Hãy tìm một nửa của mình trước khi nghĩ đến việc nuôi con nhé!")
        if float(mar["intimacy_points"]) < 200: return await ctx.send("❌ Tình cảm chưa đủ chín muồi (Cần 200 DTM) để gánh vác trách nhiệm nuôi Pet!")
        
        ptype = pet_type.lower()
        PET_MAP = {
            "dog": "Chó", "chó": "Chó",
            "cat": "Mèo", "mèo": "Mèo",
            "fox": "Cáo", "cáo": "Cáo",
            "wolf": "Sói", "sói": "Sói",
            "penguin": "Cánh Cụt",
            "rabbit": "Thỏ", "thỏ": "Thỏ",
            "bear": "Gấu", "gấu": "Gấu",
            "dragon": "Rồng", "rồng": "Rồng",
        }
        
        if ptype not in PET_MAP:
            return await ctx.send("❌ Hiện tại trại thú chỉ cung cấp: `dog, cat, fox, wolf, penguin, rabbit, bear, dragon`.")
            
        base_name = PET_MAP[ptype]
        
        if mar["pet_type"]:
            if mar["pet_type"] == base_name:
                return await ctx.send(f"❌ Bạn đang nuôi loài **{base_name}** rồi, không thể nhận nuôi lại!")
            
            view = PetAdoptConfirmView(self.bot, ctx.author, mar["id"], base_name)
            await ctx.send(f"⚠️ Hai bạn đang nuôi một bé **{mar['pet_type']}**. Nếu bạn nhận nuôi **{base_name}**, thú cưng cũ sẽ ra đi và **Kinh nghiệm thú cưng (Pet EXP) sẽ bị reset về 0** (Level 1). Bạn có chắc chắn muốn đổi không?", view=view)
        else:
            from cogs.common.db import execute_db
            await execute_db(self.bot, "UPDATE marriages SET pet_type = $1, pet_exp = 0.0 WHERE id = $2", base_name, mar["id"])
            await ctx.send(f"🎉 Chúc mừng hai bạn đã nhận nuôi thành công bé **{base_name} Sơ Sinh**! Dùng `y!namepet` để đặt tên nhé.")

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

    @commands.hybrid_command(name="setimage", aliases=["setanh"])
    async def setimage_cmd(self, ctx: commands.Context, url: str):
        """🖼️ Thiết lập ảnh kỉ niệm cho profile y!marry của 2 bạn."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Bạn chưa kết hôn nên không thể cài ảnh được!")
            
        if not url.startswith("http"):
            return await ctx.send("❌ Link ảnh không hợp lệ (Phải bắt đầu bằng http/https).")
            
        await execute_db(self.bot, "UPDATE marriages SET custom_image = $1 WHERE id = $2", url, mar["id"])
        await ctx.send("✅ Đã cập nhật ảnh thành công! Bạn có thể gõ `y!marry` để kiểm tra.")

    @commands.hybrid_command(name="pet", aliases=["thucung"])
    async def pet_cmd(self, ctx: commands.Context):
        """🐶 Xem thông tin thú cưng của cặp đôi."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Bạn chưa kết hôn!")
        if not mar.get("pet_type"):
            return await ctx.send("❌ Hai bạn chưa nhận nuôi thú cưng nào cả! Dùng `y!adopt` nhé.")
            
        pet_exp = float(mar.get('pet_exp', 0.0))
        base_type = mar["pet_type"]
        
        from cogs.common.db import fetchrow_db
        mar_db = await fetchrow_db(self.bot, "SELECT pet_name FROM marriages WHERE id = $1", mar["id"])
        pet_name_db = mar_db["pet_name"] if mar_db else None
        
        if pet_exp < 1000:
            stage = "Sơ Sinh 🐣"
        elif pet_exp < 5000:
            stage = "Trưởng Thành 🐾"
        else:
            stage = "Thần Thú 🌟"
            
        icon_map = {
            "Chó": "🐶", "Mèo": "🐱", "Cáo": "🦊", "Sói": "🐺", 
            "Cánh Cụt": "🐧", "Thỏ": "🐰", "Gấu": "🐻", "Rồng": "🐉"
        }
        icon = icon_map.get(base_type, "🐾")
        
        display_name = f"{pet_name_db}" if pet_name_db else f"{base_type}"
        pet_level = int(pet_exp / 200) + 1
        
        skill_name = "Chưa rõ"
        skill_desc = ""
        
        if base_type == "Chó":
            skill_name = "Vui Vẻ"
            buff = min(pet_level * 1.0, 50.0)
            skill_desc = f"Tăng **{buff:.1f}%** DTM nhận được mỗi lần tương tác."
        elif base_type == "Mèo":
            skill_name = "Linh Hoạt"
            buff = min(pet_level * 0.75, 45.0)
            skill_desc = f"Giảm **{buff:.2f}%** thời gian chờ (Cooldown) của các lệnh tương tác."
        elif base_type == "Cáo":
            skill_name = "Ranh Mãnh"
            buff = min(pet_level * 0.25, 25.0)
            skill_desc = f"Mỗi lần tương tác có **{buff:.2f}%** tỷ lệ gây Bạo Kích (x2 DTM)."
        elif base_type == "Sói":
            skill_name = "Kiên Trì"
            buff = min(pet_level * 2.5, 125.0)
            skill_desc = f"Tăng **{buff:.1f}%** DTM thưởng thêm khi làm Nhiệm Vụ Cặp Đôi."
        elif base_type == "Cánh Cụt":
            skill_name = "Bình Tĩnh"
            buff = min(pet_level * 1.0, 50.0)
            bonus = pet_level * 0.1
            skill_desc = f"Giảm **{buff:.1f}%** tỷ lệ đối phương quạu khi chọc ghẹo. Thưởng cố định +{bonus:.1f} DTM."
        elif base_type == "Thỏ":
            skill_name = "Nhanh Nhẹn"
            buff = min(pet_level * 0.2, 15.0)
            skill_desc = f"Mỗi lần tương tác có **{buff:.2f}%** tỷ lệ lập tức Bỏ Qua Hồi Chiêu."
        elif base_type == "Gấu":
            skill_name = "Ấm Áp"
            buff = min(pet_level * 2.0, 100.0)
            skill_desc = f"Tăng **{buff:.1f}%** DTM nhận được khi dùng lệnh tặng quà (y!gift)."
        elif base_type == "Rồng":
            skill_name = "Uy Cực"
            dtm_b = pet_level * 0.35
            cd_b = pet_level * 0.35
            task_b = pet_level * 1.0
            gift_b = pet_level * 0.5
            skill_desc = f"Toàn năng: Tăng +{dtm_b:.2f}% DTM, Giảm -{cd_b:.2f}% Cooldown, +{task_b:.1f}% Task, +{gift_b:.1f}% Quà."
            
        current_exp_in_level = pet_exp % 200
        desc = (
            f"**Tên:** {display_name} {icon}\n"
            f"**Loài:** {base_type}\n"
            f"**Trạng Thái:** {stage}\n"
            f"**Cấp Độ:** Lv.{pet_level}  *(EXP: {current_exp_in_level:.1f}/200)*\n\n"
            f"🌟 **Kỹ Năng Độc Quyền:** `{skill_name}`\n"
            f"-> {skill_desc}\n\n"
            f"*(Nhận EXP thú cưng bằng cách tương tác, làm nhiệm vụ hoặc đi làm `y!work`)*"
        )
        
        emb = discord.Embed(title="🐾 Hồ Sơ Thú Cưng", description=desc, color=discord.Color.gold())
        await ctx.send(embed=emb)

    @commands.hybrid_command(name="namepet")
    async def namepet_cmd(self, ctx: commands.Context, *, pet_name: str):
        """🏷️ Đặt tên riêng cho thú cưng của bạn!"""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar:
            return await ctx.send("❌ Bạn chưa kết hôn!")
        if not mar.get("pet_type"):
            return await ctx.send("❌ Hai bạn chưa nhận nuôi thú cưng nào cả! Dùng `y!adopt` nhé.")
        
        if len(pet_name) > 30:
            return await ctx.send("❌ Tên thú cưng quá dài (tối đa 30 ký tự).")
            
        await execute_db(self.bot, "UPDATE marriages SET pet_name = $1 WHERE id = $2", pet_name, mar["id"])
        await ctx.send(f"✅ Đã đặt tên thú cưng của hai bạn thành: **{pet_name}**!")

    @commands.hybrid_command(name="gift", aliases=["tangqua"])
    async def gift_cmd(self, ctx: commands.Context, target: discord.Member, item_id: int):
        """🎁 Tặng quà mua từ Cửa Hàng (Quà Tặng) cho vợ/chồng."""
        uid = str(ctx.author.id)
        mar = await get_marriage(self.bot, uid)
        if not mar or (mar["user1_id"] != str(target.id) and mar["user2_id"] != str(target.id)):
            return await ctx.send("❌ Quà tặng này chứa chan tình cảm, chỉ dành riêng cho vợ/chồng của bạn thôi!")
            
        from cogs.common.item_config import get_item_by_id
        item = get_item_by_id(item_id)
        if not item or item["category"] != "gift":
            return await ctx.send("❌ ID vật phẩm không hợp lệ! Hãy chọn ID của Quà Tặng trong `y!shop`.")
            
        # Check inventory
        from cogs.common.db import fetchrow_db
        row = await fetchrow_db(self.bot, "SELECT inventory FROM event_profiles WHERE discord_id = $1", uid)
        inv = json.loads(row["inventory"]) if (row and row["inventory"]) else {}
        if isinstance(inv, str): inv = json.loads(inv)
        
        db_key = item["db_key"]
        if inv.get(db_key, 0) < 1:
            return await ctx.send(f"❌ Bạn không có **{item['name']}** trong túi đồ! Dùng `y!buy {item_id}` để mua trước nhé.")
            
        # Deduct item
        inv[db_key] -= 1
        await execute_db(self.bot, "UPDATE event_profiles SET inventory = $2::jsonb WHERE discord_id = $1", uid, json.dumps(inv))
        
        # Calculate DTM from description (+XXX DTM)
        import re
        dtm_match = re.search(r'\+([\d\.]+)\s*DTM', item['description'])
        dtm_gain = float(dtm_match.group(1)) if dtm_match else 0.0
        
        # Apply Pet Buff (Bear / Dragon)
        pet_exp = float(mar.get('pet_exp', 0.0))
        pet_type = mar.get("pet_type")
        pet_level = int(pet_exp / 200) + 1 if pet_type else 0
        pet_gift_bonus = 0.0
        
        if pet_type == "Gấu":
            pet_gift_bonus = min(pet_level * 0.02, 1.0)
        elif pet_type == "Rồng":
            pet_gift_bonus = pet_level * 0.005
            
        dtm_gain = dtm_gain * (1.0 + pet_gift_bonus)
        await update_intimacy(self.bot, str(ctx.author.id), int(dtm_gain))
        
        # Thưởng EXP thú cưng bằng DTM_gain x 2
        exp_gain = dtm_gain * 2
        if pet_type:
            await execute_db(self.bot, "UPDATE marriages SET pet_exp = pet_exp + $1 WHERE id = $2", exp_gain, mar["id"])
            exp_msg = f"\n✨ *Thú cưng nhận {exp_gain:.1f} EXP*"
        else:
            exp_msg = ""
            
        emb = discord.Embed(
            title="🎁 Tặng Quà Thành Công!",
            description=f"**{ctx.author.display_name}** vừa tặng **{item['icon']} {item['name']}** cho **{target.display_name}**!\nTình cảm của hai bạn tăng thêm `{dtm_gain:.1f} DTM` 💖\n\n_{item['description']}_{exp_msg}",
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
        is_married = mar is not None and (mar["user1_id"] == uid2 or mar["user2_id"] == uid2)
        if mar is None and is_married:
            return
        act = ACTIONS[action]
        
        if not is_married or mar is None:
            # Nếu chưa cưới, chỉ gửi embed biểu cảm (không cộng DTM, không hiệu ứng phụ)
            msg = random.choice(act["msg"]).format(author=ctx.author.display_name, partner=target.mention)
            emb = discord.Embed(description=msg, color=discord.Color.light_embed())
            gif_url = await fetch_anime_gif(action)
            if gif_url:
                emb.set_image(url=gif_url)
            return await ctx.send(embed=emb)
            
        # Calculate Ring Buffs
        ring_id = mar.get("ring_id", 31)
        buffs = RING_BUFFS.get(ring_id, RING_BUFFS[31])
        
        # Calculate Pet Buffs
        pet_exp = float(mar.get('pet_exp', 0.0))
        pet_type = mar.get("pet_type")
        pet_level = int(pet_exp / 200) + 1 if pet_type else 0
        
        pet_cd_reduction = 0.0
        pet_dtm_bonus = 0.0
        pet_fail_reduction = 0.0
        pet_crit_chance = 0.0
        pet_reset_chance = 0.0
        pet_task_bonus = 0.0
        
        if pet_type == "Chó":
            pet_dtm_bonus = min(pet_level * 0.01, 0.50)
        elif pet_type == "Mèo":
            pet_cd_reduction = min(pet_level * 0.0075, 0.45)
        elif pet_type == "Cáo":
            pet_crit_chance = min(pet_level * 0.0025, 0.25)
        elif pet_type == "Sói":
            pet_task_bonus = min(pet_level * 0.025, 1.25)
        elif pet_type == "Cánh Cụt":
            pet_fail_reduction = min(pet_level * 0.01, 0.50)
        elif pet_type == "Thỏ":
            pet_reset_chance = min(pet_level * 0.002, 0.15)
        elif pet_type == "Rồng":
            pet_dtm_bonus = pet_level * 0.0035
            pet_cd_reduction = pet_level * 0.0035
            pet_task_bonus = pet_level * 0.01
            
        act = ACTIONS[action]
        tier = str(act["tier"])
        base_cd = ACTION_TIERS[act["tier"]]["cd"]
        base_dtm = ACTION_TIERS[act["tier"]]["dtm"]
        
        actual_cd = base_cd * (1.0 - buffs["cd_reduction"] - pet_cd_reduction)
        
        # Check Cooldown
        if uid1 not in self.action_cooldowns: self.action_cooldowns[uid1] = {}
        last_time = self.action_cooldowns[uid1].get(action, 0)
        now = time.time()
        
        if now - last_time < actual_cd:
            rem = int(actual_cd - (now - last_time))
            m, s = divmod(rem, 60)
            h, m = divmod(m, 60)
            wait_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
            return await ctx.send(f"⏳ Cứ từ từ thôi! Quấn quýt quá lại nhanh chán. Đợi thêm **{wait_str}** nữa mới được dùng lại hành động này nhé!")
            
        reset_msg = ""
        if pet_reset_chance > 0 and random.random() < pet_reset_chance:
            self.action_cooldowns[uid1][action] = 0
            reset_msg = "\n🐰 *Thỏ Nhanh Nhẹn đã giúp bạn hồi chiêu ngay lập tức!*"
        else:
            self.action_cooldowns[uid1][action] = now
        
        # Calculate DTM
        actual_dtm = float(base_dtm * (1.0 + buffs["dtm_bonus"] + pet_dtm_bonus))
        
        crit_msg = ""
        if pet_crit_chance > 0 and random.random() < pet_crit_chance:
            actual_dtm *= 2.0
            crit_msg = "\n🦊 *Cáo Ranh Mãnh giúp hành động này Bạo Kích (x2 DTM)!*"
            
        # Random fail for tier 1 (Chọc ghẹo)
        fail_chance = 0.2 - pet_fail_reduction
        if act["tier"] == 1 and random.random() < fail_chance:
            actual_dtm = -1.0 # Trừ 1 điểm nếu đối phương quạu
            msg = f"💢 {ctx.author.display_name} chọc ghẹo không đúng lúc, {target.display_name} đang quạu! (Trừ 1 DTM)"
        else:
            if act["tier"] == 1 and pet_type == "Cánh Cụt":
                actual_dtm += pet_level * 0.1 # Cánh cụt bonus
            msg = random.choice(act["msg"]).format(author=ctx.author.display_name, partner=target.mention) + f" `(+{actual_dtm:.1f} DTM)`"
            
            # Tiên quyết: Chỉ update task nếu thành công (không fail)
            task_str = mar.get("couple_task")
            if task_str:
                task_data = json.loads(task_str) if isinstance(task_str, str) else task_str
                today_str = discord.utils.utcnow().strftime("%Y-%m-%d")
                if task_data.get("date") == today_str and task_data.get("type") == action and not task_data.get("completed"):
                    task_data["progress"] = task_data.get("progress", 0) + 1
                    if task_data["progress"] >= task_data["target"]:
                        task_data["completed"] = True
                        task_reward = 100 * (1.0 + pet_task_bonus)
                        actual_dtm += task_reward
                        msg += f"\n🎉 **Nhiệm Vụ Cặp Đôi Hoàn Thành!** (+{task_reward:.1f} DTM)"
                    await execute_db(self.bot, "UPDATE marriages SET couple_task = $1::jsonb WHERE id = $2", json.dumps(task_data), mar["id"])
            
            # Pet EXP gain
            if pet_type:
                gained_exp = base_dtm * 2
                await execute_db(self.bot, "UPDATE marriages SET pet_exp = pet_exp + $1 WHERE id = $2", gained_exp, mar["id"])
                msg += f"\n✨ *Thú cưng nhận {gained_exp:.1f} EXP*"
            
        msg += reset_msg + crit_msg
        
        # Update DB
        await update_intimacy(self.bot, uid1, int(actual_dtm))
        await update_marriage_interaction(self.bot, uid1)
        
        emb = discord.Embed(description=msg, color=discord.Color.pink())
        
        gif_url = await fetch_anime_gif(action)
        if gif_url:
            emb.set_image(url=gif_url)
            
        await ctx.send(embed=emb)

    @commands.hybrid_command(name="actions", aliases=["hd", "hanhdong"])
    async def actions_cmd(self, ctx: commands.Context):
        """💞 Xem danh sách các hành động tương tác cặp đôi."""
        embed = discord.Embed(
            title="💞 Hành Động Cặp Đôi",
            description="Các lệnh tương tác đặc biệt dành cho vợ/chồng. Thời gian hồi chiêu và DTM nhận được tùy thuộc vào độ thân mật và Nhẫn cưới.\nCú pháp: `y!<hành_động> <@user>`",
            color=discord.Color.pink()
        )
        embed.add_field(name="🤜 Bạo lực", value="`y!slap` (tat), `y!punch` (dam), `y!bite` (can), `y!tickle` (choclet)", inline=False)
        embed.add_field(name="💖 Nhẹ nhàng", value="`y!poke` (choc), `y!pat` (xoadau), `y!saylove` (noiyeu, iuem, iuanh)", inline=False)
        embed.add_field(name="🤗 Ôm ấp", value="`y!hug` (om), `y!cuddle` (auyem), `y!snuggle` (nung, nũng)", inline=False)
        embed.add_field(name="💋 Thân mật", value="`y!kiss` (hon, hun), `y!lick` (liem), `y!nom` (mam), `y!fuck` (seg)", inline=False)
        await ctx.send(embed=embed)

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
        pool = getattr(self.bot, "db_pool", None)
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
                        
                        if isinstance(channel, discord.TextChannel):
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
