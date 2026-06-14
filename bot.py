import discord
import asyncio
import os
from datetime import datetime

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
pending_applications = {}
faceit_links = {}
warnings = {}  # {user_id: count}
# {message_id: {"embed": embed, "coming": [user_ids], "time": str, "note": str}}
practice_messages = {}

@client.event
async def on_ready():
    print(f"✅ Бот запущен: {client.user}")
    print(f"🏠 Сервер: {client.guilds[0].name}")

def is_captain(member, guild):
    captain_role = discord.utils.find(lambda r: "капитан" in r.name.lower(), guild.roles)
    return captain_role and captain_role in member.roles

# ── Авто-роль новичка ─────────────────────────────────────────────────
@client.event
async def on_member_join(member):
    guild = member.guild
    r_new = discord.utils.find(lambda r: "новичок" in r.name.lower(), guild.roles)
    if r_new:
        await member.add_roles(r_new)
    verify_ch = discord.utils.get(guild.text_channels, name="📋・верификация")
    if verify_ch:
        await verify_ch.send(
            f"👋 {member.mention}, добро пожаловать в **VELNORA**!\n"
            f"Напиши `!анкета` чтобы подать заявку.")

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild = message.guild
    content = message.content.strip()
    low = content.lower()

    # ── !анкета ───────────────────────────────────────────────────────
    if low == "!анкета":
        verify_ch = discord.utils.get(guild.text_channels, name="📋・верификация")
        if message.channel != verify_ch:
            return
        try:
            await message.delete()
        except:
            pass
        try:
            await message.author.send("📋 **Анкета VELNORA**\n\nОтвечай на вопросы здесь в личке.\n\n**1/5** — Как тебя зовут?")
        except discord.Forbidden:
            await verify_ch.send(f"{message.author.mention} ❌ Открой личные сообщения и попробуй снова.", delete_after=10)
            return
        await verify_ch.send(f"{message.author.mention} Анкета отправлена в **личку** 📩", delete_after=10)

        def check_dm(m):
            return m.author == message.author and isinstance(m.channel, discord.DMChannel)

        try:
            answers = {}
            r = await client.wait_for("message", check=check_dm, timeout=180)
            answers["name"] = r.content
            await message.author.send("**2/5** — Сколько лет?")
            r = await client.wait_for("message", check=check_dm, timeout=180)
            answers["age"] = r.content
            await message.author.send("**3/5** — Ссылка на FACEIT:")
            r = await client.wait_for("message", check=check_dm, timeout=180)
            answers["faceit"] = r.content
            await message.author.send("**4/5** — Позиция (entry/AWP/IGL/support/lurker):")
            r = await client.wait_for("message", check=check_dm, timeout=180)
            answers["position"] = r.content
            await message.author.send("**5/5** — Расскажи о себе:")
            r = await client.wait_for("message", check=check_dm, timeout=180)
            answers["about"] = r.content
        except asyncio.TimeoutError:
            await message.author.send("⏰ Время вышло. Зайди на сервер и напиши `!анкета` снова.")
            return

        faceit_links[message.author.id] = answers["faceit"]

        embed = discord.Embed(title="📋 Новая заявка", color=discord.Color.blue())
        embed.add_field(name="👤 Имя",     value=answers["name"],     inline=False)
        embed.add_field(name="🎂 Возраст", value=answers["age"],      inline=True)
        embed.add_field(name="🎮 FACEIT",  value=answers["faceit"],   inline=True)
        embed.add_field(name="🎯 Позиция", value=answers["position"], inline=True)
        embed.add_field(name="📝 О себе",  value=answers["about"],    inline=False)
        embed.set_footer(text=f"{message.author} | ID: {message.author.id}")
        embed.set_thumbnail(url=message.author.display_avatar.url)

        apps_ch = discord.utils.get(guild.text_channels, name="📬・заявки")
        if apps_ch:
            app_msg = await apps_ch.send(f"🔔 Новая заявка от {message.author.mention}!\n✅ принять / ❌ отклонить", embed=embed)
            await app_msg.add_reaction("✅")
            await app_msg.add_reaction("❌")
            pending_applications[message.author.id] = {"msg_id": app_msg.id}
        await message.author.send("✅ Анкета отправлена! Ожидай решения капитана.")
        return

    # ── !состав ───────────────────────────────────────────────────────
    if low == "!состав":
        await guild.chunk()
        role_order = ["🏆 капитан", "основной состав", "основа", "секонд состав", "замена", "стратег"]
        role_emojis = {"🏆 капитан": "🏆", "основной состав": "⭐", "основа": "⭐", "секонд состав": "🎯", "замена": "🔄", "стратег": "🗺️"}
        embed = discord.Embed(title="👥 СОСТАВ VELNORA", color=discord.Color.gold(), timestamp=datetime.utcnow())
        added = set()
        for role_name in role_order:
            role = discord.utils.find(lambda r: r.name.lower() == role_name, guild.roles)
            if not role:
                continue
            members_list = [m for m in role.members if not m.bot and m.id not in added]
            if not members_list:
                continue
            emoji = role_emojis.get(role_name, "👤")
            value = "\n".join([f"{emoji} {m.display_name}" for m in members_list])
            embed.add_field(name=f"{role.name} ({len(members_list)})", value=value, inline=False)
            for m in members_list:
                added.add(m.id)
        embed.set_footer(text=f"Всего: {len(added)}")
        await message.channel.send(embed=embed)
        return

    # ── !статс @игрок ─────────────────────────────────────────────────
    if low.startswith("!статс"):
        target = message.mentions[0] if message.mentions else message.author
        faceit_url = faceit_links.get(target.id)
        embed = discord.Embed(title=f"🎮 Статистика {target.display_name}", color=discord.Color.orange())
        embed.set_thumbnail(url=target.display_avatar.url)
        if faceit_url:
            embed.add_field(name="🔗 FACEIT", value=faceit_url, inline=False)
        else:
            embed.add_field(name="❌ Нет данных", value="Игрок не заполнял анкету", inline=False)
        embed.set_footer(text=f"Запросил: {message.author.display_name}")
        await message.channel.send(embed=embed)
        return

    # ── !инфо @игрок ──────────────────────────────────────────────────
    if low.startswith("!инфо"):
        target = message.mentions[0] if message.mentions else message.author
        roles_list = [r.name for r in target.roles if not r.is_default()]
        faceit_url = faceit_links.get(target.id, "Не указан")
        warns = warnings.get(target.id, 0)

        embed = discord.Embed(title=f"ℹ️ Информация об игроке", color=discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 Ник",        value=target.display_name,           inline=True)
        embed.add_field(name="🏷️ Тег",        value=str(target),                   inline=True)
        embed.add_field(name="📅 На сервере с", value=target.joined_at.strftime("%d.%m.%Y") if target.joined_at else "—", inline=True)
        embed.add_field(name="🎮 FACEIT",      value=faceit_url,                   inline=False)
        embed.add_field(name="🎭 Роли",        value=", ".join(roles_list) or "—", inline=False)
        embed.add_field(name="⚠️ Варны",       value=f"{warns}/3",                 inline=True)
        await message.channel.send(embed=embed)
        return

    # ── !варн @игрок причина ──────────────────────────────────────────
    if low.startswith("!варн"):
        if not is_captain(message.author, guild):
            await message.channel.send(f"{message.author.mention} ❌ Только капитан.", delete_after=5)
            return
        if not message.mentions:
            await message.channel.send("Использование: `!варн @игрок причина`", delete_after=5)
            return

        target = message.mentions[0]
        parts = content.split()
        reason = " ".join(parts[2:]) if len(parts) > 2 else "Причина не указана"

        warnings[target.id] = warnings.get(target.id, 0) + 1
        warn_count = warnings[target.id]

        embed = discord.Embed(title="⚠️ Предупреждение", color=discord.Color.yellow())
        embed.add_field(name="👤 Игрок",   value=target.mention,   inline=True)
        embed.add_field(name="⚠️ Варны",   value=f"{warn_count}/3", inline=True)
        embed.add_field(name="📝 Причина", value=reason,            inline=False)
        embed.set_footer(text=f"Выдал: {message.author.display_name}")
        await message.channel.send(embed=embed)

        try:
            await target.send(f"⚠️ Ты получил предупреждение в **VELNORA**\nПричина: {reason}\nВарны: {warn_count}/3")
        except:
            pass

        if warn_count >= 3:
            await message.channel.send(f"🔨 {target.mention} получил 3 варна и будет кикнут!")
            try:
                await target.send("❌ Ты получил 3 предупреждения и кикнут с сервера **VELNORA**.")
            except:
                pass
            await asyncio.sleep(2)
            await target.kick(reason="3 предупреждения")
            warnings.pop(target.id, None)
        return

    # ── !кик @игрок причина ───────────────────────────────────────────
    if low.startswith("!кик"):
        if not is_captain(message.author, guild):
            await message.channel.send(f"{message.author.mention} ❌ Только капитан.", delete_after=5)
            return
        if not message.mentions:
            await message.channel.send("Использование: `!кик @игрок причина`", delete_after=5)
            return

        target = message.mentions[0]
        parts = content.split()
        reason = " ".join(parts[2:]) if len(parts) > 2 else "Причина не указана"

        try:
            await target.send(f"❌ Ты кикнут с сервера **VELNORA**.\nПричина: {reason}")
        except:
            pass
        await target.kick(reason=reason)
        embed = discord.Embed(title="🔨 Игрок кикнут", color=discord.Color.red())
        embed.add_field(name="👤 Игрок",   value=target.display_name, inline=True)
        embed.add_field(name="📝 Причина", value=reason,               inline=True)
        embed.set_footer(text=f"Кикнул: {message.author.display_name}")
        await message.channel.send(embed=embed)
        return

    # ── !очистить N ───────────────────────────────────────────────────
    if low.startswith("!очистить"):
        if not is_captain(message.author, guild):
            await message.channel.send(f"{message.author.mention} ❌ Только капитан.", delete_after=5)
            return
        parts = content.split()
        try:
            amount = int(parts[1]) if len(parts) > 1 else 10
            amount = min(amount, 100)
        except:
            amount = 10
        await message.delete()
        deleted = await message.channel.purge(limit=amount)
        msg = await message.channel.send(f"🗑️ Удалено {len(deleted)} сообщений.", )
        await asyncio.sleep(3)
        await msg.delete()
        return

    # ── !помощь ───────────────────────────────────────────────────────
    if low == "!помощь":
        embed = discord.Embed(title="📖 Команды VELNORA", color=discord.Color.blue())
        embed.add_field(name="👥 Состав", value="`!состав` — список игроков по ролям\n`!инфо @игрок` — инфо об игроке\n`!статс @игрок` — FACEIT профиль", inline=False)
        embed.add_field(name="⚔️ Практики", value="`!практика 20:00 карта` — анонс практики с голосованием", inline=False)
        embed.add_field(name="🔨 Модерация (только капитан)", value="`!варн @игрок причина` — предупреждение (3 = кик)\n`!кик @игрок причина` — кик с сервера\n`!очистить 10` — удалить N сообщений", inline=False)
        embed.add_field(name="📋 Вступление", value="`!анкета` — подать заявку в команду", inline=False)
        embed.set_footer(text="VELNORA CS2 Bot")
        await message.channel.send(embed=embed)
        return

    # ── !практика <время> <заметка> ───────────────────────────────────
    if low.startswith("!практика"):
        if not is_captain(message.author, guild):
            await message.channel.send(f"{message.author.mention} ❌ Только капитан.", delete_after=5)
            return

        parts = content.split()
        time_str = parts[1] if len(parts) > 1 else "время не указано"
        note = " ".join(parts[2:]) if len(parts) > 2 else ""

        ping_roles = []
        for rname in ["основной состав", "основа", "секонд состав", "замена", "стратег"]:
            r = discord.utils.find(lambda r: r.name.lower() == rname, guild.roles)
            if r:
                ping_roles.append(r.mention)

        embed = discord.Embed(title="⚔️ АНОНС ПРАКТИКИ", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="🕐 Время",       value=f"**{time_str}**",              inline=True)
        embed.add_field(name="👤 Организатор", value=message.author.display_name,    inline=True)
        if note:
            embed.add_field(name="📝 Заметка", value=note, inline=False)
        embed.add_field(name="✅ Придут (0)", value="*Никто ещё не отметился*", inline=False)
        embed.set_footer(text="VELNORA CS2 • Поставь ✅ если придёшь")

        sched_ch = discord.utils.get(guild.text_channels, name="📅・расписание")
        target_ch = sched_ch if sched_ch else message.channel

        ping_text = " ".join(ping_roles) if ping_roles else ""
        announce = await target_ch.send(content=f"🔔 {ping_text}", embed=embed)
        await announce.add_reaction("✅")
        await announce.add_reaction("❌")

        practice_messages[announce.id] = {
            "time": time_str,
            "note": note,
            "organizer": message.author.display_name,
            "coming": [],
            "not_coming": []
        }

        if target_ch != message.channel:
            await message.channel.send(f"✅ Анонс отправлен в {target_ch.mention}!", delete_after=5)
        try:
            await message.delete()
        except:
            pass
        return

# ── Реакции ───────────────────────────────────────────────────────────
@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id:
        return
    guild = client.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    emoji = str(payload.emoji)

    # ── Практика — обновляем список ───────────────────────────────────
    if payload.message_id in practice_messages:
        data = practice_messages[payload.message_id]

        if emoji == "✅":
            if payload.user_id not in data["coming"]:
                data["coming"].append(payload.user_id)
            if payload.user_id in data["not_coming"]:
                data["not_coming"].remove(payload.user_id)
        elif emoji == "❌":
            if payload.user_id not in data["not_coming"]:
                data["not_coming"].append(payload.user_id)
            if payload.user_id in data["coming"]:
                data["coming"].remove(payload.user_id)
        else:
            return

        # Обновляем embed
        coming_names = []
        for uid in data["coming"]:
            m = guild.get_member(uid)
            if m:
                coming_names.append(f"✅ {m.display_name}")

        not_coming_names = []
        for uid in data["not_coming"]:
            m = guild.get_member(uid)
            if m:
                not_coming_names.append(f"❌ {m.display_name}")

        embed = discord.Embed(title="⚔️ АНОНС ПРАКТИКИ", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="🕐 Время",       value=f"**{data['time']}**",       inline=True)
        embed.add_field(name="👤 Организатор", value=data["organizer"],            inline=True)
        if data["note"]:
            embed.add_field(name="📝 Заметка", value=data["note"], inline=False)

        coming_text = "\n".join(coming_names) if coming_names else "*Никто ещё не отметился*"
        embed.add_field(name=f"✅ Придут ({len(coming_names)})", value=coming_text, inline=False)

        if not_coming_names:
            embed.add_field(name=f"❌ Не придут ({len(not_coming_names)})", value="\n".join(not_coming_names), inline=False)

        embed.set_footer(text="VELNORA CS2 • Поставь ✅ если придёшь")

        try:
            channel = guild.get_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
            await msg.edit(embed=embed)
        except:
            pass
        return

    # ── Заявки — капитан одобряет/отклоняет ──────────────────────────
    apps_ch = discord.utils.get(guild.text_channels, name="📬・заявки")
    if not apps_ch or payload.channel_id != apps_ch.id:
        return

    captain_role = discord.utils.find(lambda r: "капитан" in r.name.lower(), guild.roles)
    if not captain_role or captain_role not in member.roles:
        return

    applicant_id = next((uid for uid, d in pending_applications.items()
                         if d["msg_id"] == payload.message_id), None)
    if not applicant_id:
        return

    applicant = guild.get_member(applicant_id)

    if emoji == "✅":
        r_second = discord.utils.find(lambda r: r.name.lower() == "секонд состав", guild.roles)
        r_new = discord.utils.find(lambda r: "новичок" in r.name.lower(), guild.roles)
        if applicant and r_second:
            await applicant.add_roles(r_second)
            if r_new and r_new in applicant.roles:
                await applicant.remove_roles(r_new)
            welcome_ch = discord.utils.get(guild.text_channels, name="👋・приветствия")
            if welcome_ch:
                await welcome_ch.send(f"🎉 {applicant.mention} принят в **VELNORA**! Добро пожаловать! 💪")
            try:
                await applicant.send("✅ Твоя заявка в **VELNORA** одобрена! Добро пожаловать 💪")
            except:
                pass
        try:
            msg = await apps_ch.fetch_message(payload.message_id)
            await msg.edit(content="✅ **ПРИНЯТ**")
        except:
            pass
        del pending_applications[applicant_id]

    elif emoji == "❌":
        if applicant:
            try:
                await applicant.send("❌ Твоя заявка в **VELNORA** отклонена. Удачи!")
            except:
                pass
            await applicant.kick(reason="Заявка отклонена")
        try:
            msg = await apps_ch.fetch_message(payload.message_id)
            await msg.edit(content="❌ **ОТКЛОНЁН И КИКНУТ**")
        except:
            pass
        del pending_applications[applicant_id]

@client.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == client.user.id:
        return
    if payload.message_id not in practice_messages:
        return

    guild = client.get_guild(payload.guild_id)
    if not guild:
        return

    data = practice_messages[payload.message_id]
    emoji = str(payload.emoji)

    if emoji == "✅" and payload.user_id in data["coming"]:
        data["coming"].remove(payload.user_id)
    elif emoji == "❌" and payload.user_id in data["not_coming"]:
        data["not_coming"].remove(payload.user_id)
    else:
        return

    coming_names = []
    for uid in data["coming"]:
        m = guild.get_member(uid)
        if m:
            coming_names.append(f"✅ {m.display_name}")

    not_coming_names = []
    for uid in data["not_coming"]:
        m = guild.get_member(uid)
        if m:
            not_coming_names.append(f"❌ {m.display_name}")

    embed = discord.Embed(title="⚔️ АНОНС ПРАКТИКИ", color=discord.Color.red(), timestamp=datetime.utcnow())
    embed.add_field(name="🕐 Время",       value=f"**{data['time']}**",    inline=True)
    embed.add_field(name="👤 Организатор", value=data["organizer"],         inline=True)
    if data["note"]:
        embed.add_field(name="📝 Заметка", value=data["note"], inline=False)

    coming_text = "\n".join(coming_names) if coming_names else "*Никто ещё не отметился*"
    embed.add_field(name=f"✅ Придут ({len(coming_names)})", value=coming_text, inline=False)

    if not_coming_names:
        embed.add_field(name=f"❌ Не придут ({len(not_coming_names)})", value="\n".join(not_coming_names), inline=False)

    embed.set_footer(text="VELNORA CS2 • Поставь ✅ если придёшь")

    try:
        channel = guild.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)
        await msg.edit(embed=embed)
    except:
        pass

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN не задан!")
    client.run(token)
