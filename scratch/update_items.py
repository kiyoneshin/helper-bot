import os, re

path = 'd:/Code/Projects/helper-bot/cogs/general/inventory.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''        if db_key == "timeout_1m":
            assert isinstance(target, discord.Member)
            # try:
            #     await target.timeout(timedelta(minutes=1), reason=f"Bị {ctx.author} dùng Búa Gõ 1 Phút")
            # except discord.Forbidden:
            #     await ctx.send("❌ Bot không đủ quyền timeout người này!")
            #     return
            await ctx.send(f"🔨 {target.mention} đã bị dán băng keo vào miệng trong 1 phút!")

        elif db_key == "timeout_5m":
            assert isinstance(target, discord.Member)
            # try:
            #     await target.timeout(timedelta(minutes=5), reason=f"Bị {ctx.author} dùng Búa Gõ 5 Phút")
            # except discord.Forbidden:
            #     await ctx.send("❌ Bot không đủ quyền timeout người này!")
            #     return
            await ctx.send(f"🔨 {target.mention} đã bị dán băng keo vào miệng trong 5 phút!")

        elif db_key == "ghost_ping_card":
            assert isinstance(target, discord.Member)
            # for _ in range(3):
            #     msg = await ctx.channel.send(target.mention)
            #     await msg.delete()
            await ctx.send(f"👻 Đã chọc ghẹo {target.mention} thành công!")

        elif db_key == "disconnect_card":
            assert isinstance(target, discord.Member)
            # if target.voice and target.voice.channel:
            #     try:
            #         await target.move_to(None)
            #     except discord.Forbidden:
            #         await ctx.send("❌ Bot không đủ quyền sút người này!")
            #         return
            # else:
            #     await ctx.send(f"❌ {target.mention} không ở trong kênh thoại nào cả!")
            #     return
            await ctx.send(f"🔌 {target.mention} vừa bị sút văng khỏi kênh thoại!")

        elif db_key == "fake_ban_card":
            assert isinstance(target, discord.Member)
            fake_embed = discord.Embed(
                title="🔨 THÔNG BÁO BAN!",
                description=f"**{target.mention}** đã bị cấm vĩnh viễn khỏi máy chủ.\\n**Lý do:** Vi phạm nội quy cực kỳ nghiêm trọng.",
                color=0xFF0000
            )
            fake_embed.set_footer(text="Đùa tí thôi! Bị lừa rồi nhé 😂")
            await ctx.send(embed=fake_embed)

        elif db_key == "jail_card":
            assert isinstance(target, discord.Member)
            # jail_cog: Any = self.bot.get_cog("JailSystem")
            # if jail_cog:
            #     try:
            #         await jail_cog.phattu_cmd.callback(jail_cog, ctx, target, 50, reason=f"Bị {ctx.author} dùng Thẻ Bỏ Tù")
            #     except Exception as e:
            #         await ctx.send(f"❌ Lỗi khi bỏ tù: {e}")
            #         return
            # else:
            #     await ctx.send("❌ Tính năng Chuồng Chó hiện đang bảo trì!")
            #     return
            await ctx.send(f"🚔 {target.mention} đã bị tống vào chuồng chó!")

        elif db_key == "thief_card":
            assert isinstance(target, discord.Member)
            # Tác dụng trộm điểm hoặc tiền từ target
            # import random
            # stolen_amount = random.randint(50, 500)
            # ... cập nhật DB ...
            await ctx.send(f"🕵️ {ctx.author.mention} đã trộm thành công đồ của {target.mention}!")
            
        elif db_key == "nickname_change":
            assert isinstance(target, discord.Member)
            import random
            funny_names = ["Thánh Hề", "Kẻ Trộm Chó", "Đại Vương Móm", "Chúa Tể Báo Thủ", "Chú Bé Đần"]
            new_name = random.choice(funny_names)
            # try:
            #     await target.edit(nick=new_name, reason=f"Bị {ctx.author} dùng thẻ đổi tên")
            # except Exception:
            #     pass
            await ctx.send(f"🤡 Đã đổi tên {target.mention} thành **{new_name}**!")
            
        elif db_key == "shield_card":
            # Ghi nhận trạng thái có khiên vào DB hoặc memory
            # await execute_db(...)
            await ctx.send(f"🛡️ {ctx.author.mention} đã trang bị thẻ miễn nhiễm! Sẽ chặn 1 lần hiệu ứng xấu.")
            
        elif db_key == "free_card":
            if target:
                assert isinstance(target, discord.Member)
                target_mention = target.mention
            else:
                target_mention = ctx.author.mention
            # jail_cog = self.bot.get_cog("JailSystem")
            # Xử lý thả tù...
            await ctx.send(f"🕊️ {ctx.author.mention} đã dùng thẻ đặc xá để giải cứu {target_mention} khỏi nhà giam!")'''

# Replace from 'if db_key == "timeout_1m":' to 'elif db_key == "nickname_change":\n... await ctx.send(...)'
# We will just do a regex replace
pattern = r'if db_key == "timeout_1m":.*await ctx\.send\(f"🤡 Đã đổi tên \{target\.mention\} thành \*\*\{new_name\}\*\*\!"\)'
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
