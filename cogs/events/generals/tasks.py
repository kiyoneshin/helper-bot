import discord
from discord.ext import commands
import random
import json
from datetime import datetime, timedelta, timezone

from cogs.common.db import fetchrow_db, execute_db, add_event_points, UTC7
from .task_config import DAILY_TASKS, WEEKLY_TASKS, QUESTS

def _get_progress_bar(progress: int, target: int, length: int = 10) -> str:
    """Tạo thanh tiến độ dạng [■■■□□]"""
    if target <= 0: return "[■■■■■■■■■■]"
    ratio = min(progress / target, 1.0)
    filled_blocks = int(round(ratio * length))
    empty_blocks = length - filled_blocks
    return f"[{'■' * filled_blocks}{'□' * empty_blocks}]"

class TaskCog(commands.Cog):
    """Hệ thống Nhiệm Vụ Ngày/Tuần/Sự Kiện."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_and_lazy_reset(self, discord_id: int) -> dict:
        uid = discord_id
        row = await fetchrow_db(self.bot, "SELECT * FROM user_tasks WHERE discord_id = $1", uid)
        if not row:
            await execute_db(self.bot, "INSERT INTO user_tasks (discord_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)
            row = await fetchrow_db(self.bot, "SELECT * FROM user_tasks WHERE discord_id = $1", uid)
        
        row_dict = dict(row) # type: ignore
        
        def _parse(val):
            if isinstance(val, dict): return val
            if isinstance(val, str): return json.loads(val)
            return {}

        daily_data = _parse(row_dict["daily_tasks"])
        weekly_data = _parse(row_dict["weekly_tasks"])
        quests_data = _parse(row_dict["quests"])
        
        now = datetime.now(UTC7)
        today_str = now.strftime("%Y-%m-%d")
        # Tuần tính theo (Năm, Tuần thứ mấy)
        year, week_num, _ = now.isocalendar()
        week_str = f"{year}-W{week_num}"

        changed = False

        # --- Xử lý Daily ---
        if daily_data.get("assigned_date") != today_str:
            # Random 2 tasks
            chosen = random.sample(list(DAILY_TASKS.items()), 2)
            new_tasks = {}
            for t_id, t_info in chosen:
                new_tasks[t_id] = {
                    "action": t_info["action"],
                    "target": t_info["target"],
                    "progress": 0,
                    "completed": False,
                    "claimed": False,
                    "reward": random.randint(t_info["reward_min"], t_info["reward_max"])
                }
            daily_data = {"assigned_date": today_str, "tasks": new_tasks}
            changed = True

        # --- Xử lý Weekly ---
        if weekly_data.get("assigned_date") != week_str:
            # Random 1 task
            chosen = random.sample(list(WEEKLY_TASKS.items()), 1)
            new_tasks = {}
            for t_id, t_info in chosen:
                new_tasks[t_id] = {
                    "action": t_info["action"],
                    "target": t_info["target"],
                    "progress": 0,
                    "completed": False,
                    "claimed": False,
                    "reward": random.randint(t_info["reward_min"], t_info["reward_max"])
                }
            weekly_data = {"assigned_date": week_str, "tasks": new_tasks}
            changed = True

        # --- Xử lý Quests ---
        if not quests_data:
            for t_id, t_info in QUESTS.items():
                quests_data[t_id] = {
                    "action": t_info["action"],
                    "target": t_info["target"],
                    "progress": 0,
                    "completed": False,
                    "claimed": False,
                    "reward": t_info["reward_fixed"]
                }
            changed = True

        # Save back if changed
        if changed:
            await execute_db(
                self.bot, 
                "UPDATE user_tasks SET daily_tasks = $1::jsonb, weekly_tasks = $2::jsonb, quests = $3::jsonb WHERE discord_id = $4",
                json.dumps(daily_data), json.dumps(weekly_data), json.dumps(quests_data), uid
            )
            
        row_dict["daily_tasks"] = daily_data
        row_dict["weekly_tasks"] = weekly_data
        row_dict["quests"] = quests_data
        return row_dict

    @commands.hybrid_command(name="task", aliases=["tasks", "nhiemvu"])
    async def task_cmd(self, ctx: commands.Context):
        """Xem và nhận thưởng Nhiệm Vụ Hằng Ngày & Hằng Tuần."""
        uid = ctx.author.id
        data = await self._get_and_lazy_reset(uid)
        
        daily_tasks = data["daily_tasks"].get("tasks", {})
        weekly_tasks = data["weekly_tasks"].get("tasks", {})
        
        embed = discord.Embed(
            title="📜 Bảng Nhiệm Vụ (Task Board)",
            color=0x2b2d31,
            description="Hoàn thành các nhiệm vụ dưới đây để nhận điểm thưởng. Bot sẽ tự động trao thưởng nếu nhiệm vụ hoàn thành khi bạn gõ lệnh này."
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        claimed_messages = []
        db_changed = False

        # --- Hiển thị Daily ---
        daily_text = ""
        idx = 1
        for tid, tdata in daily_tasks.items():
            conf = DAILY_TASKS.get(tid)
            if not conf: continue
            
            # Auto Claim Logic
            if tdata["progress"] >= tdata["target"] and not tdata["claimed"]:
                tdata["claimed"] = True
                await add_event_points(self.bot, uid, tdata["reward"], is_earned=True)
                claimed_messages.append(f"✅ Đã nhận thưởng nhiệm vụ ngày #{idx} (+{tdata['reward']:,} điểm)")
                db_changed = True

            status = "COMPLETED" if tdata["claimed"] else f"{tdata['progress']}/{tdata['target']}"
            bar = _get_progress_bar(tdata["progress"], tdata["target"])
            strike = "~~" if tdata["claimed"] else ""
            
            daily_text += f"**{idx}. {conf['name']}** | 🎁 {tdata['reward']}\n"
            daily_text += f"{strike}Mục tiêu: {conf['desc']}{strike}\n"
            daily_text += f"`{bar}` **{status}**\n\n"
            idx += 1
            
        if not daily_text: daily_text = "Không có nhiệm vụ ngày."
        embed.add_field(name="📅 Nhiệm Vụ Hằng Ngày", value=daily_text, inline=False)
        
        # --- Hiển thị Weekly ---
        weekly_text = ""
        idx = 1
        for tid, tdata in weekly_tasks.items():
            conf = WEEKLY_TASKS.get(tid)
            if not conf: continue
            
            if tdata["progress"] >= tdata["target"] and not tdata["claimed"]:
                tdata["claimed"] = True
                await add_event_points(self.bot, uid, tdata["reward"], is_earned=True)
                claimed_messages.append(f"🌟 Đã nhận thưởng nhiệm vụ tuần #{idx} (+{tdata['reward']:,} điểm)")
                db_changed = True

            status = "COMPLETED" if tdata["claimed"] else f"{tdata['progress']}/{tdata['target']}"
            bar = _get_progress_bar(tdata["progress"], tdata["target"])
            strike = "~~" if tdata["claimed"] else ""
            
            weekly_text += f"**{idx}. {conf['name']}** | 🎁 {tdata['reward']}\n"
            weekly_text += f"{strike}Mục tiêu: {conf['desc']}{strike}\n"
            weekly_text += f"`{bar}` **{status}**\n\n"
            idx += 1

        if not weekly_text: weekly_text = "Không có nhiệm vụ tuần."
        embed.add_field(name="🗓️ Nhiệm Vụ Tuần", value=weekly_text, inline=False)

        # Cập nhật db nếu có claim
        if db_changed:
            await execute_db(
                self.bot, 
                "UPDATE user_tasks SET daily_tasks = $1::jsonb, weekly_tasks = $2::jsonb WHERE discord_id = $3",
                json.dumps(data["daily_tasks"]), json.dumps(data["weekly_tasks"]), uid
            )
            
        if claimed_messages:
            embed.add_field(name="🎉 Thưởng Vừa Nhận", value="\n".join(claimed_messages), inline=False)
            
        embed.set_footer(text="Nhiệm vụ ngày reset lúc 00:00 | Nhiệm vụ tuần reset mỗi Thứ 2")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="quest", aliases=["quests"])
    async def quest_cmd(self, ctx: commands.Context):
        """Xem và nhận thưởng Chuỗi Nhiệm Vụ Dài Hạn."""
        uid = ctx.author.id
        data = await self._get_and_lazy_reset(uid)
        
        quests_data = data["quests"]
        
        embed = discord.Embed(
            title="🏆 Chuỗi Nhiệm Vụ Khám Phá (Quests)",
            color=0xffaa00,
            description="Hoàn thành các nhiệm vụ dài hạn dưới đây để nhận phần thưởng cực lớn!"
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        claimed_messages = []
        db_changed = False

        quest_text = ""
        for tid, tdata in quests_data.items():
            conf = QUESTS.get(tid)
            if not conf: continue
            
            if tdata["progress"] >= tdata["target"] and not tdata["claimed"]:
                tdata["claimed"] = True
                await add_event_points(self.bot, uid, tdata["reward"], is_earned=True)
                claimed_messages.append(f"🏆 Đã hoàn thành siêu nhiệm vụ: **{conf['name']}** (+{tdata['reward']:,} điểm)")
                db_changed = True

            status = "COMPLETED" if tdata["claimed"] else f"{tdata['progress']}/{tdata['target']}"
            bar = _get_progress_bar(tdata["progress"], tdata["target"], length=15)
            strike = "~~" if tdata["claimed"] else ""
            
            quest_text += f"**{conf['name']}** | 🎁 {tdata['reward']}\n"
            quest_text += f"{strike}Mục tiêu: {conf['desc']}{strike}\n"
            quest_text += f"`{bar}` **{status}**\n\n"

        if not quest_text: quest_text = "Không có Quest nào."
        embed.description = embed.description + "\n\n" + quest_text # type: ignore

        if db_changed:
            await execute_db(
                self.bot, 
                "UPDATE user_tasks SET quests = $1::jsonb WHERE discord_id = $2",
                json.dumps(quests_data), uid
            )
            
        if claimed_messages:
            embed.add_field(name="🎉 Thưởng Vừa Nhận", value="\n".join(claimed_messages), inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TaskCog(bot))
