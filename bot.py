import discord
import asyncio
import os
import re
from datetime import datetime

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
pending_applications = {}
# Хранилище FACEIT ссылок: {user_id: faceit_url}
faceit_links = {}

@client.event
async def on_ready():
    print(f"✅ Бот запущен: {client.user}")
    print(f"🏠 Сервер: {client.guilds[0].name}")
    print(f"🤖 Жду команды...")

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

# ── Обработка сообщений ───────────────────────────────────────────────
@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild = message.guild
    content = message.content.strip()

    # ── !анкета ───────────────────────────────────────────────────────
    if content.lower() == "!анкета":
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
            await verify_ch.send(
                f"{message.author.mention} ❌ Открой личные сообщения и попробуй снова.",
                delete_after=10)
            return

        await verify_ch.send(
            f"{message.author.mention} Анкета отправлена в **личку** 📩",
            delete_after=10)

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

        # Сохраняем FACEIT ссылку
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
            app_msg = await apps_ch.send(
                f"🔔 Новая заявка от {message.author.mention}!\n✅ принять / ❌ отклонить",
                embed=embed)
            await app_msg.add_reaction("✅")
            await app_msg.add_reaction("❌")
            pending_applications[message.author.id] = {"msg_id": app_msg.id}

        await message.author.send("✅ Анкета отправлена! Ожидай решения капитана.")
        return

    # ── !состав ───────────────────────────────────────────────────────
    if content.lower() == "!состав":
        await guild.chunk()

        role_order = ["🏆 капитан", "основной состав", "основа", "секонд состав", "замена", "стратег"]
        role_emojis = {
            "🏆 капитан": "🏆",
            "основной состав": "⭐",
            "основа": "⭐",
            "секонд состав": "🎯",
            "замена": "🔄",
            "стратег": "🗺️",
        }

        embed = discord.Embed(
            title="👥 СОСТАВ VELNORA",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

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

        embed.set_footer(text=f"Всего участников: {len(added)}")
        await message.channel.send(embed=embed)
        return

    # ── !статс @игрок ─────────────────────────────────────────────────
    if content.lower().startswith("!статс"):
        target = message.mentions[0] if message.mentions else message.author
        faceit_url = faceit_links.get(target.id)

        embed = discord.Embed(
            title=f"🎮 Статистика {target.display_name}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if faceit_url:
            embed.add_field(name="🔗 FACEIT профиль", value=faceit_url, inline=False)
            embed.add_field(name="ℹ️ Инфо", value="Перейди по ссылке чтобы посмотреть полную статистику", inline=False)
        else:
            embed.add_field(name="❌ Нет данных", value="Игрок не заполнял анкету или данные не сохранены", inline=False)

        embed.set_footer(text=f"Запросил: {message.author.display_name}")
        await message.channel.send(embed=embed)
        return

    # ── !практика <время> ─────────────────────────────────────────────
    if content.lower().startswith("!практика"):
        # Проверяем что это капитан
        captain_role = discord.utils.find(lambda r: "капитан" in r.name.lower(), guild.roles)
        if captain_role not in message.author.roles:
            await message.channel.send(
                f"{message.author.mention} ❌ Только капитан может объявлять практики.",
                delete_after=5)
            return

        parts = content.split()
        time_str = parts[1] if len(parts) > 1 else "время не указано"
        note = " ".join(parts[2:]) if len(parts) > 2 else ""

        # Пингуем все игровые роли
        ping_roles = []
        for rname in ["основной состав", "основа", "секонд состав", "замена", "стратег"]:
            r = discord.utils.find(lambda r: r.name.lower() == rname, guild.roles)
            if r:
                ping_roles.append(r.mention)

        embed = discord.Embed(
            title="⚔️ АНОНС ПРАКТИКИ",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🕐 Время", value=f"**{time_str}**", inline=True)
        embed.add_field(name="👤 Организатор", value=message.author.display_name, inline=True)
        if note:
            embed.add_field(name="📝 Заметка", value=note, inline=False)
        embed.add_field(name="✅ Готовность", value="Поставь ✅ если придёшь", inline=False)
        embed.set_footer(text="VELNORA CS2")

        sched_ch = discord.utils.get(guild.text_channels, name="📅・расписание")
        target_ch = sched_ch if sched_ch else message.channel

        ping_text = " ".join(ping_roles) if ping_roles else "@everyone"
        announce = await target_ch.send(content=f"🔔 {ping_text}", embed=embed)
        await announce.add_reaction("✅")
        await announce.add_reaction("❌")

        if target_ch != message.channel:
            await message.channel.send(f"✅ Анонс отправлен в {target_ch.mention}!", delete_after=5)
        try:
            await message.delete()
        except:
            pass
        return

# ── Реакции капитана (заявки) ─────────────────────────────────────────
@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id:
        return
    guild = client.get_guild(payload.guild_id)
    if not guild:
        return
    apps_ch = discord.utils.get(guild.text_channels, name="📬・заявки")
    if not apps_ch or payload.channel_id != apps_ch.id:
        return
    reactor = guild.get_member(payload.user_id)
    if not reactor:
        return
    captain_role = discord.utils.find(lambda r: "капитан" in r.name.lower(), guild.roles)
    if not captain_role or captain_role not in reactor.roles:
        return

    applicant_id = next((uid for uid, d in pending_applications.items()
                         if d["msg_id"] == payload.message_id), None)
    if not applicant_id:
        return

    member = guild.get_member(applicant_id)
    emoji = str(payload.emoji)

    if emoji == "✅":
        r_second = discord.utils.find(lambda r: r.name.lower() == "секонд состав", guild.roles)
        r_new = discord.utils.find(lambda r: "новичок" in r.name.lower(), guild.roles)
        if member and r_second:
            await member.add_roles(r_second)
            if r_new and r_new in member.roles:
                await member.remove_roles(r_new)
            welcome_ch = discord.utils.get(guild.text_channels, name="👋・приветствия")
            if welcome_ch:
                await welcome_ch.send(f"🎉 {member.mention} принят в **VELNORA**! Добро пожаловать! 💪")
            try:
                await member.send("✅ Твоя заявка в **VELNORA** одобрена! Добро пожаловать 💪")
            except:
                pass
        try:
            msg = await apps_ch.fetch_message(payload.message_id)
            await msg.edit(content="✅ **ПРИНЯТ**")
        except:
            pass
        del pending_applications[applicant_id]

    elif emoji == "❌":
        if member:
            try:
                await member.send("❌ Твоя заявка в **VELNORA** отклонена. Удачи!")
            except:
                pass
            await member.kick(reason="Заявка отклонена")
        try:
            msg = await apps_ch.fetch_message(payload.message_id)
            await msg.edit(content="❌ **ОТКЛОНЁН И КИКНУТ**")
        except:
            pass
        del pending_applications[applicant_id]

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN не задан!")
    client.run(token)
