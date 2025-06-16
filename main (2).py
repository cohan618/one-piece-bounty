from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import asyncio

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# משתנים קבועים
BOUNTY_ROLE = 1383049285897158666
MANAGE_BOUNTY_ROLE = 1383049400313712794
APPROVER_ROLE = 1383076270207799336

COMMAND_CHANNEL = 1383050256182280222
BOUNTY_CHECK_CHANNEL = 1383056881043378207
APPROVAL_CHANNEL = 1383077073266016276
BOUNTY_NOTIFY_CHANNEL = 1383050102347927552

BOUNTY_IMAGE_URL = "https://cdn.discordapp.com/attachments/1164551685688021052/1383054613778923581/One_piece.jpg?ex=684d657b&is=684c13fb&hm=82f1ff6a4f591de454f460e56d7c07f9fb16e77f30178cd7563f8ad2237c0875&"

bounty_data = {}
pending_requests = {}

def has_role(member, role_id):
    return discord.utils.get(member.roles, id=role_id) is not None

def mention_role(role_id):
    return f"<@&{role_id}>"

async def send_bounty_request_embed(channel, target_member, amount, action, reason, requester):
    embed = discord.Embed(title="בקשת באונטי", color=0xffcc00)
    embed.set_image(url=BOUNTY_IMAGE_URL)
    embed.add_field(name="שם", value=target_member.display_name, inline=True)
    embed.add_field(name="כמות", value=str(amount), inline=True)
    embed.add_field(name="סיבה", value=reason, inline=False)
    embed.add_field(name="פעולה", value=action, inline=True)
    embed.set_footer(text=f"מבקש: {requester.display_name}")
    msg = await channel.send(f"{mention_role(APPROVER_ROLE)} יש בקשה לבצע {action} ל{target_member.mention}:", embed=embed)
    return msg

async def update_bounty_notify_channel(member, amount, action):
    channel = bot.get_channel(BOUNTY_NOTIFY_CHANNEL)
    if channel is None:
        print(f"ERROR: לא נמצא ערוץ הבאונטי {BOUNTY_NOTIFY_CHANNEL}")
        return

    text = (
        f"ל{member.mention} יש באונטי של {amount} מטבעות.\n"
        "הוא נחשב לאיום ממשי על הצוות שלנו.\n"
        "על ראשו הוצע סכום גבוה במיוחד."
    )
    embed = discord.Embed(description=text, color=0xffcc00)
    embed.set_image(url=BOUNTY_IMAGE_URL)
    embed.set_footer(text=f"פעולה שבוצעה: {action}")

    await channel.send(embed=embed)

async def handle_bounty_request(ctx, member: discord.Member, amount: int = 0, action: str = "", reason: str = ""):
    if ctx.channel.id != COMMAND_CHANNEL:
        await ctx.message.delete()
        return

    if not has_role(ctx.author, MANAGE_BOUNTY_ROLE):
        await ctx.message.delete()
        return

    if not reason.strip():
        await ctx.send("עליך לציין סיבה לבקשה.", delete_after=7)
        return

    approval_channel = bot.get_channel(APPROVAL_CHANNEL)
    if approval_channel is None:
        await ctx.send("לא ניתן למצוא את ערוץ האישור.", delete_after=7)
        return

    msg = await send_bounty_request_embed(approval_channel, member, amount, action, reason, ctx.author)
    pending_requests[member.id] = {
        "member": member,
        "amount": amount,
        "action": action,
        "reason": reason,
        "requester": ctx.author,
        "approval_msg": msg
    }
    await ctx.message.delete()

@bot.command()
async def addbounty(ctx, member: discord.Member, amount: int, *, reason: str):
    await handle_bounty_request(ctx, member, amount, "הוספה", reason)

@bot.command()
async def rvbounty(ctx, member: discord.Member, amount: int, *, reason: str):
    await handle_bounty_request(ctx, member, amount, "הורדה", reason)

@bot.command()
async def rebounty(ctx, member: discord.Member, *, reason: str):
    await handle_bounty_request(ctx, member, 0, "איפוס", reason)

@bot.command()
@commands.has_role(APPROVER_ROLE)
async def acceptb(ctx, member: discord.Member):
    if member.id not in pending_requests:
        await ctx.send("לא קיימת בקשה עם שם זה.", delete_after=7)
        return

    data = pending_requests.pop(member.id)
    approval_msg = data.get("approval_msg")
    if approval_msg:
        try:
            await approval_msg.delete()
        except:
            pass

    current_amount = bounty_data.get(member.id, 0)
    action = data["action"]

    if action == "הוספה":
        new_amount = current_amount + data["amount"]
    elif action == "הורדה":
        new_amount = max(0, current_amount - data["amount"])
    elif action == "איפוס":
        new_amount = 0
    else:
        new_amount = current_amount

    bounty_data[member.id] = new_amount

    await ctx.send(f"{mention_role(APPROVER_ROLE)} בוצעה {action} ל{member.mention} בהצלחה.", delete_after=7)

    # שליחת עדכון לערוץ עם הפורמט שביקשת
    await update_bounty_notify_channel(member, new_amount, action)

    await asyncio.sleep(7)
    await ctx.message.delete()

@bot.command()
@commands.has_role(APPROVER_ROLE)
async def noacceptb(ctx, member: discord.Member, *, reject_reason: str):
    if member.id not in pending_requests:
        await ctx.send("לא קיימת בקשה עם שם זה.", delete_after=7)
        return

    data = pending_requests.pop(member.id)
    requester = data["requester"]
    try:
        await requester.send(
            f"הבקשה שלך {data['action']} ל{data['member'].display_name} לא התקבלה על ידי {ctx.author.display_name}.\nסיבה: {reject_reason}"
        )
    except:
        pass

    await ctx.send(f"הבקשה נדחתה בהצלחה.", delete_after=7)
    await asyncio.sleep(7)
    await ctx.message.delete()

@bot.command()
@commands.has_role(BOUNTY_ROLE)
async def bounty(ctx, member: discord.Member = None):
    if ctx.channel.id != BOUNTY_CHECK_CHANNEL:
        await ctx.message.delete()
        return

    target = member or ctx.author
    amount = bounty_data.get(target.id, 0)
    try:
        await ctx.author.send(f"{target.display_name} יש לו/לה באונטי של: {amount} שקלים")
    except:
        pass
    await ctx.message.delete(delay=3)

@bot.command()
@commands.has_role(BOUNTY_ROLE)
async def topbounty(ctx):
    if ctx.channel.id != BOUNTY_CHECK_CHANNEL:
        await ctx.message.delete()
        return

    if not bounty_data:
        await ctx.author.send("כרגע אין באונטי רשום.")
        await ctx.message.delete(delay=3)
        return

    sorted_bounty = sorted(bounty_data.items(), key=lambda x: x[1], reverse=True)
    description = ""
    for uid, amount in sorted_bounty[:10]:
        user = ctx.guild.get_member(uid)
        if user:
            description += f"{user.display_name}: {amount} שקלים\n"

    embed = discord.Embed(title="טבלת הבאונטי - 10 הגדולים", description=description, color=0xffaa00)
    try:
        await ctx.author.send(embed=embed)
    except:
        pass
    await ctx.message.delete(delay=3)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.delete()
    elif isinstance(error, commands.MissingAnyRole):
        await ctx.message.delete()
    elif isinstance(error, commands.CheckFailure):
        await ctx.message.delete()
    else:
        print(error)

from keep_alive import keep_alive

keep_alive()

load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
