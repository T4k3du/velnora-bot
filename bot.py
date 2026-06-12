import discord
import asyncio
import os

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
pending_applications = {}

@client.event
async def on_ready():
    print(f"✅ Бот запущен: {client.user}")
    print(f"🏠 Сервер: {client.guilds[0].name}")
    print(f"🤖 Жду анкеты (!анкета)...")

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
    if message.content.strip().lower() != "!анкета":
        return
    verify_ch = discord.utils.get(message.guild.text_channels, name="📋・верификация")
    if message.channel != verify_ch:
        return

    # Удаляем сообщение !анкета чтобы не засорять канал
    try:
        await message.delete()
    except:
        pass

    # Отправляем вопросы в личку
    try:
        await message.author.send("📋 **Анкета VELNORA**\n\nОтвечай на вопросы здесь в личке.\n\n**1/5** — Как тебя зовут?")
        dm_channel = message.author.dm_channel
    except discord.Forbidden:
        await verify_ch.send(
            f"{message.author.mention} ❌ Не могу написать тебе в личку. Открой личные сообщения и попробуй снова.",
            delete_after=10)
        return

    await verify_ch.send(
        f"{message.author.mention} Анкета отправлена тебе в **личку** — ответь там! 📩",
        delete_after=10)

    def check(m):
        return m.author == message.author and isinstance(m.channel, discord.DMChannel)

    try:
        answers = {}
        r = await client.wait_for("message", check=check, timeout=180)
        answers["name"] = r.content
        await message.author.send("**2/5** — Сколько лет?")
        r = await client.wait_for("message", check=check, timeout=180)
        answers["age"] = r.content
        await message.author.send("**3/5** — Ссылка на FACEIT:")
        r = await client.wait_for("message", check=check, timeout=180)
        answers["faceit"] = r.content
        await message.author.send("**4/5** — Позиция (entry / AWP / IGL / support / lurker):")
        r = await client.wait_for("message", check=check, timeout=180)
        answers["position"] = r.content
        await message.author.send("**5/5** — Расскажи о себе:")
        r = await client.wait_for("message", check=check, timeout=180)
        answers["about"] = r.content
    except asyncio.TimeoutError:
        await message.author.send("⏰ Время вышло. Зайди на сервер и напиши `!анкета` снова.")
        return

    embed = discord.Embed(title="📋 Новая заявка", color=discord.Color.blue())
    embed.add_field(name="👤 Имя",     value=answers["name"],     inline=False)
    embed.add_field(name="🎂 Возраст", value=answers["age"],      inline=True)
    embed.add_field(name="🎮 FACEIT",  value=answers["faceit"],   inline=True)
    embed.add_field(name="🎯 Позиция", value=answers["position"], inline=True)
    embed.add_field(name="📝 О себе",  value=answers["about"],    inline=False)
    embed.set_footer(text=f"{message.author} | ID: {message.author.id}")
    embed.set_thumbnail(url=message.author.display_avatar.url)

    apps_ch = discord.utils.get(message.guild.text_channels, name="📬・заявки")
    if apps_ch:
        app_msg = await apps_ch.send(
            f"🔔 Новая заявка от {message.author.mention}!\n✅ принять / ❌ отклонить",
            embed=embed)
        await app_msg.add_reaction("✅")
        await app_msg.add_reaction("❌")
        pending_applications[message.author.id] = {"msg_id": app_msg.id}

    await message.author.send("✅ Анкета отправлена! Ожидай решения капитана.")

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
                await member.send("✅ Твоя заявка в **VELNORA** одобрена! Добро пожаловать в команду 💪")
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
