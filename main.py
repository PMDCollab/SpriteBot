from spritebot.SpriteBot import SpriteBot
import spritebot.TrackerUtils as TrackerUtils
from spritebot.Constants import TOKEN_FILE_PATH
import discord
import os
import datetime
import asyncio
import traceback
import sys

# The Discord client.
client = discord.Client()

# for bot updating
spritebot_code_folder = os.path.dirname(os.path.abspath(__file__))


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    global sprite_bot
    await sprite_bot.checkAllSubmissions()
    await sprite_bot.checkRestarted()
    print('------')


@client.event
async def on_message(msg: discord.Message):
    await client.wait_until_ready()
    try:
        if msg.guild is None:
            return
        # exclude self posts
        if msg.author.id == sprite_bot.client.user.id:
            return

        content = msg.content
        # only respond to the proper author
        if msg.author.id == sprite_bot.config.root and content.startswith("!init"):
            args = content[len("!"):].split(' ')
            await sprite_bot.initServer(msg, args[1:])
            return

        # only respond to the proper guilds
        guild_id_str = str(msg.guild.id)
        if guild_id_str not in sprite_bot.config.servers:
            return

        server = sprite_bot.config.servers[guild_id_str]
        prefix = server.prefix

        if msg.channel.id == server.chat:
            if not content.startswith(prefix):
                return
            args = content[len(prefix):].split(' ')

            authorized = await sprite_bot.isAuthorized(msg.author, msg.guild)
            base_arg = args[0].lower()
            if base_arg == "help":
                await sprite_bot.help(msg, args[1:])
            elif base_arg == "staffhelp":
                await sprite_bot.staffhelp(msg, args[1:])
                # primary commands
            elif base_arg == "listsprite":
                await sprite_bot.listForms(msg, args[1:], "sprite")
            elif base_arg == "sprite":
                await sprite_bot.queryStatus(msg, args[1:], "sprite", False)
            elif base_arg == "recolorsprite":
                await sprite_bot.queryStatus(msg, args[1:], "sprite", True)
            elif base_arg == "listportrait":
                await sprite_bot.listForms(msg, args[1:], "portrait")
            elif base_arg == "portrait":
                await sprite_bot.queryStatus(msg, args[1:], "portrait", False)
            elif base_arg == "recolorportrait":
                await sprite_bot.queryStatus(msg, args[1:], "portrait", True)
            elif base_arg == "spritecredit":
                await sprite_bot.getCredit(msg, args[1:], "sprite")
            elif base_arg == "portraitcredit":
                await sprite_bot.getCredit(msg, args[1:], "portrait")
            elif base_arg == "spritebounty":
                await sprite_bot.placeBounty(msg, args[1:], "sprite")
            elif base_arg == "portraitbounty":
                await sprite_bot.placeBounty(msg, args[1:], "portrait")
            elif base_arg == "bounties":
                await sprite_bot.listBounties(msg, args[1:])
            elif base_arg == "profile":
                await sprite_bot.getProfile(msg)
            elif base_arg == "register":
                await sprite_bot.setProfile(msg, args[1:])
            elif base_arg == "absentprofiles":
                await sprite_bot.getAbsentProfiles(msg)
            elif base_arg == "unregister":
                await sprite_bot.deleteProfile(msg, args[1:])
            elif base_arg == "autocolor":
                await sprite_bot.tryAutoRecolor(msg, args[1:], "portrait")
                # authorized commands
            elif base_arg == "add" and authorized:
                await sprite_bot.addSpeciesForm(msg, args[1:])
            elif base_arg == "delete" and authorized:
                await sprite_bot.removeSpeciesForm(msg, args[1:])
            elif base_arg == "rename" and authorized:
                await sprite_bot.renameSpeciesForm(msg, args[1:])
            elif base_arg == "addgender" and authorized:
                await sprite_bot.addGender(msg, args[1:])
            elif base_arg == "deletegender" and authorized:
                await sprite_bot.removeGender(msg, args[1:])
            elif base_arg == "need" and authorized:
                await sprite_bot.setNeed(msg, args[1:], True)
            elif base_arg == "dontneed" and authorized:
                await sprite_bot.setNeed(msg, args[1:], False)
            elif base_arg == "movesprite" and authorized:
                await sprite_bot.moveSlot(msg, args[1:], "sprite")
            elif base_arg == "moveportrait" and authorized:
                await sprite_bot.moveSlot(msg, args[1:], "portrait")
            elif base_arg == "spritewip" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", TrackerUtils.PHASE_INCOMPLETE)
            elif base_arg == "portraitwip" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", TrackerUtils.PHASE_INCOMPLETE)
            elif base_arg == "spriteexists" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", TrackerUtils.PHASE_EXISTS)
            elif base_arg == "portraitexists" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", TrackerUtils.PHASE_EXISTS)
            elif base_arg == "spritefilled" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", TrackerUtils.PHASE_FULL)
            elif base_arg == "portraitfilled" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", TrackerUtils.PHASE_FULL)
            elif base_arg == "setspritecredit" and authorized:
                await sprite_bot.resetCredit(msg, args[1:], "sprite")
            elif base_arg == "setportraitcredit" and authorized:
                await sprite_bot.resetCredit(msg, args[1:], "portrait")
            elif base_arg == "addspritecredit" and authorized:
                await sprite_bot.addCredit(msg, args[1:], "sprite")
            elif base_arg == "addportraitcredit" and authorized:
                await sprite_bot.addCredit(msg, args[1:], "portrait")
            elif base_arg == "modreward" and authorized:
                await sprite_bot.modSpeciesForm(msg, args[1:])
            elif base_arg == "transferprofile" and authorized:
                await sprite_bot.transferProfile(msg, args[1:])
            elif base_arg == "clearcache" and authorized:
                await sprite_bot.clearCache(msg, args[1:])
                # root commands
            elif base_arg == "rescan" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.rescan(msg)
            elif base_arg == "unlockportrait" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setLock(msg, args[1:], "portrait", False)
            elif base_arg == "unlocksprite" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setLock(msg, args[1:], "sprite", False)
            elif base_arg == "lockportrait" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setLock(msg, args[1:], "portrait", True)
            elif base_arg == "locksprite" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setLock(msg, args[1:], "sprite", True)
            elif base_arg == "canon" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setCanon(msg, args[1:], True)
            elif base_arg == "noncanon" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.setCanon(msg, args[1:], False)
            elif base_arg == "update" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.updateBot(msg)
            elif base_arg == "forcepush" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.gitCommit("Tracker update from forced push.")
                await sprite_bot.gitPush()
                msg.channel.send(msg.author.mention + " Changes pushed.")
            elif base_arg in ["gr", "tr", "checkr"]:
                pass
            else:
                await msg.channel.send(msg.author.mention + " Unknown Command.")

        elif msg.channel.id == sprite_bot.config.servers[guild_id_str].submit:
            changed_tracker = await sprite_bot.pollSubmission(msg)
            if changed_tracker:
                sprite_bot.saveTracker()

    except Exception as e:
        await sprite_bot.sendError(traceback.format_exc())

@client.event
async def on_raw_reaction_add(payload):
    await client.wait_until_ready()
    try:
        if payload.user_id == client.user.id:
            return
        guild_id_str = str(payload.guild_id)
        if payload.channel_id == sprite_bot.config.servers[guild_id_str].submit:
            msg = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
            changed_tracker = await sprite_bot.pollSubmission(msg)
            if changed_tracker:
                sprite_bot.saveTracker()

    except Exception as e:
        await sprite_bot.sendError(traceback.format_exc())

async def periodic_update_status():
    await client.wait_until_ready()
    global sprite_bot
    last_date = ""
    while not client.is_closed():
        try:
            if sprite_bot.changed:
                sprite_bot.changed = False
                for server_id in sprite_bot.config.servers:
                    await sprite_bot.updatePost(sprite_bot.config.servers[server_id])

            # check for push
            cur_date = datetime.datetime.today().strftime('%Y-%m-%d')
            if last_date != cur_date:
                if last_date == "":
                    await sprite_bot.gitCommit("Tracker update from restart.")
                # update push
                await sprite_bot.gitPush()
                last_date = cur_date
        except Exception as e:
            await sprite_bot.sendError(traceback.format_exc())
        await asyncio.sleep(10)

sprite_bot = SpriteBot(spritebot_code_folder, client)

client.loop.create_task(periodic_update_status())

with open(os.path.join(spritebot_code_folder, TOKEN_FILE_PATH)) as token_file:
    token = token_file.read()

try:
    client.run(token)
except Exception as e:
    trace = traceback.format_exc()
    print(trace)


if sprite_bot.need_restart:
    # restart
    args = sys.argv[:]
    args.insert(0, sys.executable)
    if sys.platform == 'win32':
        args = ['"%s"' % arg for arg in args]

    os.execv(sys.executable, args)
