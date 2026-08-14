"""
skills_db.py — Các hàm DB cho Hệ Thống Kỹ Năng
=================================================
"""
import json
import logging
from typing import Any

from cogs.common.db import fetchrow_db, execute_db
from cogs.events.skills.skills_config import (
    SKILLS, PROFESSIONS, LEVEL_XP_TOTAL, MAX_LEVEL,
    get_level_from_xp, get_skill_level_info,
    SKILL_PER_LEVEL_BONUS,
)

log = logging.getLogger("SkillsDB")

# ---------------------------------------------------------------------------
# DEFAULT SKILLS DATA STRUCTURE
# ---------------------------------------------------------------------------

def _default_skills() -> dict:
    return {
        skill_id: {
            "xp": 0,
            "level": 0,
            "profession_5": None,
            "profession_10": None,
        }
        for skill_id in SKILLS
    }


def _parse_skills(raw) -> dict:
    """Parse JSONB skills từ DB, merge với default để đảm bảo đủ keys."""
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}

    default = _default_skills()
    for skill_id in SKILLS:
        if skill_id not in data:
            data[skill_id] = default[skill_id]
        else:
            # Merge để đảm bảo đủ keys
            for k, v in default[skill_id].items():
                data[skill_id].setdefault(k, v)
    return data


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def get_skills(bot: Any, discord_id: str | int) -> dict:
    """Lấy toàn bộ skills data của user, tự động fill default nếu thiếu."""
    uid = str(discord_id)
    row = await fetchrow_db(bot, "SELECT skills FROM event_profiles WHERE discord_id = $1", uid)
    if not row:
        return _default_skills()
    return _parse_skills(row["skills"])


async def save_skills(bot: Any, discord_id: str | int, skills_data: dict) -> None:
    """Lưu skills data vào DB."""
    uid = str(discord_id)
    await execute_db(
        bot,
        "UPDATE event_profiles SET skills = $2::jsonb WHERE discord_id = $1",
        uid, json.dumps(skills_data)
    )


async def add_skill_xp(bot: Any, discord_id: str | int, skill_id: str, amount: int) -> dict | None:
    """
    Thêm XP cho 1 kỹ năng. Tự động xử lý level-up.
    Trả về dict thông tin level-up nếu có:
        {"old_level": N, "new_level": M, "skill_id": ..., "needs_profession": [5, 10]}
    Trả về None nếu không có level-up.
    """
    if skill_id not in SKILLS or amount <= 0:
        return None

    uid = str(discord_id)
    skills = await get_skills(bot, uid)
    skill = skills[skill_id]

    old_xp = skill["xp"]
    old_level = skill["level"]

    # Cộng XP, nhưng không vượt quá tổng XP max
    max_xp = LEVEL_XP_TOTAL[MAX_LEVEL] + 9999  # Cho phép tích thêm sau Lv10
    new_xp = min(old_xp + amount, max_xp)
    skill["xp"] = new_xp

    # Tính level mới
    new_level, _, _ = get_level_from_xp(new_xp)
    new_level = min(new_level, MAX_LEVEL)
    skill["level"] = new_level

    await save_skills(bot, uid, skills)

    # Kiểm tra level-up
    if new_level > old_level:
        needs_profession = []
        # Kiểm tra xem có cần chọn profession không
        if new_level >= 5 and old_level < 5 and skill.get("profession_5") is None:
            needs_profession.append(5)
        if new_level >= 10 and old_level < 10 and skill.get("profession_10") is None:
            needs_profession.append(10)

        return {
            "old_level": old_level,
            "new_level": new_level,
            "skill_id": skill_id,
            "needs_profession": needs_profession,
        }
    return None


async def set_profession(
    bot: Any,
    discord_id: str | int,
    skill_id: str,
    tier: int,
    profession_id: str
) -> bool:
    """Lưu lựa chọn profession cho skill tại tier 5 hoặc 10."""
    if profession_id not in PROFESSIONS:
        return False
    prof = PROFESSIONS[profession_id]
    if prof["skill"] != skill_id or prof["tier"] != tier:
        return False

    uid = str(discord_id)
    skills = await get_skills(bot, uid)
    skill = skills[skill_id]

    if tier == 5:
        skill["profession_5"] = profession_id
        # Reset profession_10 nếu đổi nhánh
        skill["profession_10"] = None
    elif tier == 10:
        # Kiểm tra parent
        if skill.get("profession_5") != prof["parent"]:
            return False
        skill["profession_10"] = profession_id

    await save_skills(bot, uid, skills)
    return True


async def reset_profession(bot: Any, discord_id: str | int, skill_id: str) -> bool:
    """Reset cả profession_5 và profession_10 của skill. Trả về True nếu thành công."""
    if skill_id not in SKILLS:
        return False
    uid = str(discord_id)
    skills = await get_skills(bot, uid)
    skill = skills[skill_id]
    skill["profession_5"] = None
    skill["profession_10"] = None
    await save_skills(bot, uid, skills)
    return True


# ---------------------------------------------------------------------------
# PASSIVE BONUS GETTERS — Dùng trong mining/fishing/chopping/farming
# ---------------------------------------------------------------------------

def get_skill_bonus(skills_data: dict, skill_id: str, bonus_key: str) -> float:
    """
    Lấy tổng bonus của skill_id theo bonus_key.
    Bao gồm: bonus từ level + bonus từ professions đang active.
    """
    skill = skills_data.get(skill_id, {})
    level = skill.get("level", 0)
    total = 0.0

    # 1. Per-level passive bonus
    per_level = SKILL_PER_LEVEL_BONUS.get(skill_id, {})
    if bonus_key in per_level:
        total += per_level[bonus_key] * level

    # 2. Profession bonus
    for tier_key in ["profession_5", "profession_10"]:
        prof_id = skill.get(tier_key)
        if prof_id and prof_id in PROFESSIONS:
            prof = PROFESSIONS[prof_id]
            if prof["bonus_key"] == bonus_key:
                total += prof["bonus_value"]

    return total


def has_profession(skills_data: dict, skill_id: str, profession_id: str) -> bool:
    """Kiểm tra nhanh xem user có đang sở hữu profession cụ thể không."""
    skill = skills_data.get(skill_id, {})
    return skill.get("profession_5") == profession_id or skill.get("profession_10") == profession_id


def get_active_professions(skills_data: dict, skill_id: str) -> list[dict]:
    """Lấy danh sách professions đang được kích hoạt của 1 skill."""
    skill = skills_data.get(skill_id, {})
    active = []
    for tier_key in ["profession_5", "profession_10"]:
        prof_id = skill.get(tier_key)
        if prof_id and prof_id in PROFESSIONS:
            active.append(PROFESSIONS[prof_id])
    return active


async def check_pending_professions(bot: Any, discord_id: str | int) -> list[tuple[str, int]]:
    """
    Kiểm tra xem có kỹ năng nào đã đủ level nhưng chưa chọn profession chưa.
    Trả về list of (skill_id, tier).
    """
    skills = await get_skills(bot, discord_id)
    pending = []
    for skill_id, skill in skills.items():
        level = skill.get("level", 0)
        if level >= 5 and skill.get("profession_5") is None:
            pending.append((skill_id, 5))
        elif level >= 10 and skill.get("profession_10") is None:
            pending.append((skill_id, 10))
    return pending
