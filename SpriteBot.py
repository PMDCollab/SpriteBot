import os
import io
import discord
import urllib
import traceback
import asyncio
import json
import SpriteUtils
import datetime
import git
import sys


# Housekeeping for login information
TOKEN_FILE_PATH = 'token.txt'
NAME_FILE_PATH = 'credit_names.txt'
INFO_FILE_PATH = 'info.txt'
CONFIG_FILE_PATH = 'config.json'
TRACKER_FILE_PATH = 'tracker.json'


# Command prefix.
COMMAND_PREFIX = '!'

scdir = os.path.dirname(os.path.abspath(__file__))

# The Discord client.
client = discord.Client()




class SpriteBot:
    """
    A class for handling recolors
    """
    def __init__(self, in_path, client):
        # init data
        self.path = in_path
        self.need_restart = False
        with open(os.path.join(self.path, INFO_FILE_PATH)) as f:
            self.info_post = f.read().split("\n\n\n")
        with open(os.path.join(self.path, CONFIG_FILE_PATH)) as f:
            config = json.load(f)
            self.can_push = config["push"]
            self.content_path = config["path"]
            self.owner_id = config["root"]
            self.servers = config["servers"]

        # init repo
        self.repo = git.Repo(self.content_path)
        self.commits = 0
        # tracking data from the content folder
        with open(os.path.join(self.content_path, TRACKER_FILE_PATH)) as f:
            new_tracker = json.load(f)
            self.tracker = { }
            for species_idx in new_tracker:
                self.tracker[species_idx] = SpriteUtils.TrackerNode(new_tracker[species_idx])
        self.names = SpriteUtils.loadNameFile(os.path.join(self.path, NAME_FILE_PATH))
        confirmed_names = SpriteUtils.loadNameFile(os.path.join(self.content_path, NAME_FILE_PATH))
        self.client = client
        self.changed = False

        # update tracker based on last-modify
        over_dict = SpriteUtils.initSubNode("")
        over_dict.subgroups = self.tracker
        SpriteUtils.fileSystemToJson(over_dict, os.path.join(self.content_path, "sprite"), "sprite", 0)
        SpriteUtils.fileSystemToJson(over_dict, os.path.join(self.content_path, "portrait"), "portrait", 0)

        # update credits
        for name in confirmed_names:
            if name not in self.names:
                self.names[name] = confirmed_names[name]
            self.names[name].sprites = True
            self.names[name].portraits = True
        SpriteUtils.updateNameStats(self.names, over_dict)

        # save updated tracker back to the file
        self.saveTracker()
        # save updated credits
        self.saveNames()

        print("Info Initiated")

    def saveNames(self):
        SpriteUtils.updateNameFile(os.path.join(self.path, NAME_FILE_PATH), self.names, True)
        SpriteUtils.updateNameFile(os.path.join(self.content_path, NAME_FILE_PATH), self.names, False)

    def saveConfig(self):
        with open(os.path.join(self.path, CONFIG_FILE_PATH), 'w', encoding='utf-8') as txt:
            config = { }
            config["path"] = self.content_path
            config["root"] = self.owner_id
            config["servers"] = self.servers
            json.dump(config, txt, indent=2)

    def saveTracker(self):
        new_tracker = { }
        for species_idx in self.tracker:
            new_tracker[species_idx] = self.tracker[species_idx].getDict()
        with open(os.path.join(self.content_path, TRACKER_FILE_PATH), 'w', encoding='utf-8') as txt:
            json.dump(new_tracker, txt, indent=2)

    def gitCommit(self, msg):
        self.repo.git.add(".")
        self.repo.git.commit(m=msg)
        self.commits += 1

    def gitPush(self):
        origin = self.repo.remotes.origin
        origin.push()

    async def updateBot(self, msg):
        resp_ch = self.getChatChannel(msg.guild.id)
        resp = await resp_ch.send("Pulling from repo...")
        # update self
        bot_repo = git.Repo(scdir)
        origin = bot_repo.remotes.origin
        origin.pull()
        await resp.edit(content="Update complete! Bot will restart.")
        self.need_restart = True
        await self.client.logout()

    def getChatChannel(self, guild_id):
        chat_id = self.servers[str(guild_id)]["chat"]
        return self.client.get_channel(chat_id)

    def getStatusEmoji(self, chosen_node, asset_type):
        pending = chosen_node.__dict__[asset_type+"_pending"]
        added = chosen_node.__dict__[asset_type + "_credit"] != ""
        complete = chosen_node.__dict__[asset_type+"_complete"]
        required = chosen_node.__dict__[asset_type+"_required"]
        if len(pending) > 0:
            if complete:# interrobang
                return "\u2049"
            else:# question
                return "\u2754"
        elif added:
            if len(pending) > 0:# interrobang
                return "\u2049"
            else:
                if complete:# checkmark
                    return "\u2705"
                else:# white circle
                    return "\u26AA"
        else:
            if required:# X mark
                return "\u274C"
            else:# black circle
                return "\u26AB"

    def getAuthorCol(self, author):
        return str(author.id) + "#" + author.name.replace("\t", "") + "#" + author.discriminator

    def getPostCredit(self, mention):
        if mention == "":
            return "-"
        if len(mention) < 4:
            return mention
        if mention[:2] != "<@" or mention[-1] != ">":
            return mention

        try:
            id = int(mention[2:-1])
            user = self.client.get_user(id)
        except Exception as e:
            user = None

        if user is not None:
            # this is where we check against illegal characters such as emoji and zalgo
            # but getting users doesnt seem to work for the bot (probably needs perms of some sort)
            # maybe intents
            # for now we skip
            return SpriteUtils.sanitizeCredit(mention)

        return mention
        # if mention in self.names:
        #     return self.names[mention].Name

        # fall back on a quoted mention
        # return "`" + mention + "`"

    def getPostsFromDict(self, tracker_dict, posts, indices):
        if tracker_dict.name != "":
            new_titles = SpriteUtils.getIdxName(self.tracker, indices)
            dexnum = int(indices[0])
            name_str = " ".join(new_titles)
            post = ""

            # status
            post += self.getStatusEmoji(tracker_dict, "sprite")
            post += self.getStatusEmoji(tracker_dict, "portrait")
            # name
            post += " `#" + "{:03d}".format(dexnum) + "`: `" + name_str + "` "

            # credits
            post += self.getPostCredit(tracker_dict.sprite_credit)
            post += "/"
            post += self.getPostCredit(tracker_dict.portrait_credit)
            posts.append(post)

        for sub_dict in tracker_dict.subgroups:
            self.getPostsFromDict(tracker_dict.subgroups[sub_dict], posts, indices + [sub_dict])


    async def isAuthorized(self, user, guild):
        if user.id == self.client.user.id:
            return False
        if user.id == self.owner_id:
            return True
        guild_id_str = str(guild.id)
        approve_role = guild.get_role(self.servers[guild_id_str]["approval"])

        user_member = await guild.fetch_member(user.id)
        if user_member is None:
            return False
        if approve_role in user_member.roles:
            return True
        return False

    async def generateLink(self, file_data, filename):
        # file_data is a file-like object to post with
        # post the file to the admin under a specific filename
        user = await client.fetch_user(self.owner_id)
        resp = await user.send("", file=discord.File(file_data, filename))
        result_url = resp.attachments[0].url
        return result_url

    async def stageSubmission(self, msg, chosen_node, asset_type):
        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 0
        pending_dict[str(msg.id)] = True

        # react to the message
        await msg.add_reaction('\U00002705')
        await msg.add_reaction('\U0000274C')

        self.changed |= change_status

    async def submissionApproved(self, msg, approvals):
        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(msg.author.mention + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        # get the name of the slot that it was written to
        new_name = SpriteUtils.getIdxName(self.tracker, full_idx)
        new_name_str = " ".join(new_name)

        # change the status of the sprite
        new_revise = "New"
        if chosen_node.__dict__[asset_type+"_credit"] != "":
            new_revise = "Revised"

        # save and set the new sprite or portrait
        full_arr = [self.content_path, asset_type] + full_idx
        gen_path = os.path.join(*full_arr)
        if asset_type == "sprite":
            pass
        elif asset_type == "portrait":
            portrait_img = SpriteUtils.getLinkImg(msg.attachments[0].url)
            if recolor:
                portrait_img = SpriteUtils.removePalette(portrait_img)
            SpriteUtils.placePortraitToPath(portrait_img, gen_path)

        # update the credits in that path
        SpriteUtils.appendCredits(gen_path, msg.author.mention)
        # add to universal names list and save if changed
        if msg.author.mention not in self.names:
            self.names[msg.author.mention] = SpriteUtils.CreditEntry("", "")
        self.names[msg.author.mention].sprites = True
        self.names[msg.author.mention].portraits = True
        self.saveNames()

        # update the credits and timestamp in the chosen node
        chosen_node.__dict__[asset_type + "_modified"] = str(datetime.datetime.utcnow())
        chosen_node.__dict__[asset_type + "_credit"] = msg.author.mention

        # remove from pending list
        pending_dict = chosen_node.__dict__[asset_type + "_pending"]
        if str(msg.id) in pending_dict:
            del pending_dict[str(msg.id)]

        # generate a new link
        file_data, ext = SpriteUtils.generateFileData(gen_path, asset_type, False)
        file_data.seek(0)
        file_name = "{0}-{1}{2}".format(asset_type, "-".join(full_idx), ext)

        new_link = await self.generateLink(file_data, file_name)
        chosen_node.__dict__[asset_type+"_link"] = new_link
        chosen_node.__dict__[asset_type+"_recolor_link"] = ""

        mentions = ["<@"+str(ii)+">" for ii in approvals]
        approve_msg = "{0} {1} approved by {2}: #{3:03d}: {4}".format(new_revise, asset_type, str(mentions), int(full_idx[0]), new_name_str)

        # if this was non-shiny, set the complete flag to false for the shiny
        if not SpriteUtils.isShinyIdx(full_idx):
            shiny_idx = SpriteUtils.createShinyIdx(full_idx, True)
            shiny_node = SpriteUtils.getNodeFromIdx(self.tracker, shiny_idx, 0)
            if shiny_node.__dict__[asset_type+"_credit"] != "":
                shiny_node.__dict__[asset_type+"_complete"] = False
                approve_msg += "\nNote: Shiny form now marked as incomplete due to this change."

        # save the tracker
        self.saveTracker()
        # commit the changes
        self.gitCommit("{0} {1} #{2:03d}: {3} by {4} {5}".format(new_revise, asset_type, int(full_idx[0]), new_name_str,
                                                      msg.author.mention, self.names[msg.author.mention].name))

        # post about it
        await self.getChatChannel(msg.guild.id).send(msg.author.mention + " " + approve_msg + "\n" + new_link)
        # delete post
        await msg.delete()
        self.changed = True

    async def submissionDeclined(self, msg):
        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(msg.author.mention + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        # change the status of the sprite
        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 1
        if str(msg.id) in pending_dict:
            del pending_dict[str(msg.id)]

        return_file = SpriteUtils.getLinkFile(msg.attachments[0].url)
        await self.getChatChannel(msg.guild.id).send(msg.author.mention + " " + "Declined {0}:".format(asset_type),
                                                     file=discord.File(return_file, msg.attachments[0].filename))
        # delete post
        await msg.delete()
        self.changed |= change_status

    async def checkAllSubmissions(self):
        # clear all pending submissions; we don't know if they were deleted or not between startups
        for node_idx in self.tracker:
            SpriteUtils.clearSubmissions(self.tracker[node_idx])

        # make sure they are re-added
        for server in self.servers:
            ch_id = self.servers[server]["submit"]
            msgs = []
            channel = self.client.get_channel(ch_id)
            async for message in channel.history(limit=None):
                msgs.append(message)
            for msg in msgs:
                await self.pollSubmission(msg)
            sprite_bot.saveTracker()
            sprite_bot.changed = True

    """
    Returns true if anything changed that would require a tracker save
    """
    async def pollSubmission(self, msg):
        # check for messages in #submissions
        cks = None
        xs = None
        ss = None
        for reaction in msg.reactions:
            if reaction.emoji == '\u2705':
                cks = reaction
            if reaction.emoji == '\u274C':
                xs = reaction
            if reaction.emoji == '\u2B50':
                ss = reaction

        if cks and xs and cks.me and xs.me:
            auto = False
            approve = []
            decline = 0

            if ss:
                async for user in ss.users():
                    if user.id == self.owner_id:
                        auto = True
                        approve.append(user.id)

            async for user in cks.users():
                if await self.isAuthorized(user, msg.guild):
                    approve.append(user.id)

            async for user in xs.users():
                if await self.isAuthorized(user, msg.guild):
                    decline += 1

            if decline > 0:
                await self.submissionDeclined(msg)
                return True
            elif auto or len(approve) >= 3:
                await self.submissionApproved(msg, approve)
                return False
            else:
                file_name = msg.attachments[0].filename
                name_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)
                chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
                pending_dict = chosen_node.__dict__[asset_type + "_pending"]
                pending_dict[str(msg.id)] = True
                return False
        else:
            if len(msg.attachments) != 1:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid submission. Attach one and only one file!")
                return False

            file_name = msg.attachments[0].filename
            name_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)

            chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
            # if the node cant be found, the filepath is invalid
            if chosen_node is None:
                name_valid = False

            # if the node can be found, but it's not required, it's also invalid
            if not chosen_node.__dict__[asset_type + "_required"]:
                name_valid = False

            if not name_valid:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid filename. Do not change the filename from the original.")
                return False

            # at this point, we confirm the file name is valid, now check the contents
            decline_msg = None
            if asset_type == "sprite":
                decline_msg = "Sprites currently not accepted."
            elif asset_type == "portrait":
                # get the portrait image and verify its contents
                img = SpriteUtils.getLinkImg(msg.attachments[0].url)
                orig_img = None
                # if it's a shiny, get the original image
                if SpriteUtils.isShinyIdx(full_idx):
                    orig_idx = SpriteUtils.createShinyIdx(full_idx, False)
                    orig_node = SpriteUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                    if orig_node.__dict__[asset_type+"_credit"] == "":
                        # this means there's no original portrait to base the recolor off of
                        await msg.delete()
                        await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Cannot submit a shiny when the original isn't finished.")
                        return False

                    orig_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, recolor)
                    orig_img = SpriteUtils.getLinkImg(orig_link)

                # if the file needs to be compared to an original, verify it as a recolor. Otherwise, by itself.
                if orig_img is None:
                    decline_msg = SpriteUtils.verifyPortrait(msg.content, img)
                else:
                    decline_msg = SpriteUtils.verifyRecolor(msg.content, orig_img, img, recolor)

            if decline_msg is not None:
                return_file = SpriteUtils.getLinkFile(msg.attachments[0].url)
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " " + decline_msg,
                                                             file=discord.File(return_file, file_name))
                await msg.delete()
                return False

            await self.stageSubmission(msg, chosen_node, asset_type)
            return True


    async def sendInfoPosts(self, channel, posts, msg_ids, msg_idx):
        changed = False
        line_idx = 0
        while line_idx < len(posts):
            cur_len = 0
            line_len = 0
            while line_idx + line_len < len(posts):
                new_len = len(posts[line_idx + line_len])
                if cur_len + new_len < 1950 and line_len < 25:
                    cur_len += new_len
                    line_len += 1
                else:
                    break

            post_range = posts[line_idx:(line_idx+line_len)]
            post = "\n".join(post_range)
            if msg_idx < len(msg_ids):
                try:
                    msg = await channel.fetch_message(int(msg_ids[msg_idx]))
                except Exception as e:
                    msg = None

                if msg is None:
                    msg_ids.pop(msg_idx)
                    changed = True
                    continue

                if msg.content != post:
                    await msg.edit(content=post)
            else:
                msg = await channel.send(content=post)
                msg_ids.append(str(msg.id))
                changed = True
            line_idx += line_len
            msg_idx += 1

        return msg_idx, changed

    async def updatePost(self, server):
        # update status in #info
        msg_ids = server["info_posts"]
        changed_list = False

        channel = self.client.get_channel(int(server["info"]))

        posts = []
        over_dict = SpriteUtils.initSubNode("")
        over_dict.subgroups = self.tracker
        self.getPostsFromDict(over_dict, posts, [])

        msgs_used = 0
        msgs_used, changed = await self.sendInfoPosts(channel, posts, msg_ids, msgs_used)
        changed_list |= changed
        msgs_used, changed = await self.sendInfoPosts(channel, self.info_post, msg_ids, msgs_used)
        changed_list |= changed

        while msgs_used < len(msg_ids):
            msg = await channel.fetch_message(int(msg_ids[-1]))
            await msg.delete()
            msg_ids.pop()
            changed_list = True

        if changed_list:
            self.saveConfig()

    async def retrieveLinkMsg(self, full_idx, chosen_node, asset_type, recolor):
        # build the needed field
        req_base = asset_type
        if recolor:
            req_base += "_recolor"
        req_link = req_base + "_link"

        # if we already have a link, send that link
        if chosen_node.__dict__[req_link] != "":
            return chosen_node.__dict__[req_link]

        # otherwise, generate that link
        # if there is no data in the folder (aka no credit)
        # create a dummy template using missingno
        gen_path = os.path.join(self.content_path, asset_type, "0000")
        # otherwise, use the provided path
        if chosen_node.__dict__[asset_type + "_credit"] != "":
            full_arr = [self.content_path, asset_type] + full_idx
            gen_path = os.path.join(*full_arr)

        target_idx = SpriteUtils.createShinyIdx(full_idx, recolor)
        file_data, ext = SpriteUtils.generateFileData(gen_path, asset_type, recolor)
        file_data.seek(0)
        file_name = "{0}-{1}{2}".format(req_base, "-".join(target_idx), ext)

        new_link = await self.generateLink(file_data, file_name)
        chosen_node.__dict__[req_link] = new_link
        self.saveTracker()
        return new_link

    async def completeSlot(self, msg, name_args, asset_type):
        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        # if the node has no credit, fail
        if chosen_node.__dict__[asset_type + "_credit"] == "":
            status = self.getStatusEmoji(chosen_node, asset_type)
            await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} has no data and cannot be marked complete.".format(status, int(full_idx[0]), " ".join(name_seq)))
            return

        # set to complete
        chosen_node.__dict__[asset_type + "_complete"] = True

        status = self.getStatusEmoji(chosen_node, asset_type)
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} marked as complete.".format(status, int(full_idx[0]), " ".join(name_seq)))

        self.saveTracker()
        self.changed = True

    async def clearCache(self, msg, name_args):
        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        # set to complete
        chosen_node.sprite_link = ""
        chosen_node.portrait_link = ""
        chosen_node.sprite_recolor_link = ""
        chosen_node.portrait_recolor_link = ""

        await msg.channel.send(msg.author.mention + " Cleared links for #{0:03d}: {1}.".format(int(full_idx[0]), " ".join(name_seq)))


    async def queryStatus(self, msg, name_args, asset_type, recolor):
        # compute answer from current status
        if len(name_args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        # can't get recolor link for a shiny
        if recolor and "Shiny" in name_seq:
            await msg.channel.send(msg.author.mention + " Can't get recolor for a shiny Pokemon.")
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        # post the statuses
        response = msg.author.mention + " "
        status = self.getStatusEmoji(chosen_node, asset_type)
        response += "{0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

        if chosen_node.__dict__[asset_type + "_required"]:
            file_exists = chosen_node.__dict__[asset_type + "_credit"] != ""
            if not file_exists and recolor:
                response += " doesn't have a {0} to recolor. Submit the original first.".format(asset_type)
            else:
                if not file_exists:
                    response += "\n [This {0} is missing. If you want to submit, use this file as a template!]".format(asset_type)
                if recolor:
                    response += "\n [Recolor this {0} to its shiny palette and submit it.]".format(asset_type)
                chosen_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, recolor)
                response += "\n" + chosen_link
        else:
            response += " does not need a {0}.".format(asset_type)

        await msg.channel.send(response)

    async def getProfile(self, msg):
        msg_mention = msg.author.mention
        if msg_mention in self.names:
            await msg.channel.send(msg_mention + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[msg_mention].name, self.names[msg_mention].contact))
            return
        await msg.channel.send(msg_mention + " No profile. Set it with `!register <Name> <Contact>`!")

    async def setProfile(self, msg, args):
        msg_mention = msg.author.mention
        if msg_mention in self.names:
            new_credit = self.names[msg_mention]
        else:
            new_credit = SpriteUtils.CreditEntry("", "")

        if len(args) > 0:
            new_credit.name = args[0]
        if len(args) > 1:
            new_credit.contact = args[1]
        self.names[msg_mention] = new_credit

        self.saveNames()

        await msg.channel.send(msg_mention + " Registered profile.\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[msg_mention].name, self.names[msg_mention].contact))

    async def printStatus(self, msg):
        sprites = 0
        total_sprites = 0
        portraits = 0
        total_portraits = 0

        users = {}

        for status in self.tracker:
            if status.sprite_link != "":
                total_sprites += 1
            if status.sprite_recolor_link != "":
                sprites += 1
            if status.portrait_link != "":
                total_portraits += 1
            if status.portrait_recolor_link != "":
                portraits += 1
            if status.portrait_credit not in users:
                users[status.portrait_credit] = 0
            users[status.portrait_credit] = users[status.portrait_credit]+1
            if status.sprite_credit not in users:
                users[status.sprite_credit] = 0
            users[status.sprite_credit] = users[status.sprite_credit] + 1

        await msg.channel.send(str(sprites)+"/"+ str(total_sprites)+ " Sprites.\n"+ \
                                             str(portraits)+"/"+str(total_portraits) + " Portraits.")


        user = await client.fetch_user(self.owner_id)
        if msg.author == user:
            with open(TRACKER_FILE_PATH, 'rb') as file_data:
                await user.send(file=discord.File(file_data, TRACKER_FILE_PATH))

        credits = "Credit:"
        for sender in users:
            if sender != "":
                credits += "\n<@" + sender + "> : " + str(users[sender])
        await user.send(credits)


    async def initServer(self, msg, args):

        if len(args) != 4:
            await msg.channel.send(msg.author.mention + " Args not equal to 4!")
            return

        if len(msg.channel_mentions) != 3:
            await msg.channel.send(msg.author.mention + " Bad channel args!")
            return

        if len(msg.role_mentions) != 1:
            await msg.channel.send(msg.author.mention + " Bad role args!")
            return

        info_ch = msg.channel_mentions[0]
        bot_ch = msg.channel_mentions[1]
        submit_ch = msg.channel_mentions[2]
        reviewer_role = msg.role_mentions[0]

        init_guild = msg.guild

        info_perms = info_ch.permissions_for(init_guild.me)
        bot_perms = bot_ch.permissions_for(init_guild.me)
        submit_perms = submit_ch.permissions_for(init_guild.me)

        if not info_perms.send_messages or not info_perms.read_messages:
            await msg.channel.send(msg.author.mention + " Bad channel perms for info!")
            return

        if not bot_perms.send_messages or not bot_perms.read_messages:
            await msg.channel.send(msg.author.mention + " Bad channel perms for chat!")
            return

        if not submit_perms.send_messages or not submit_perms.read_messages or not submit_perms.manage_messages:
            await msg.channel.send(msg.author.mention + " Bad channel perms for submit!")
            return

        self.servers[str(init_guild.id)] = { "info" : info_ch.id,
                                            "chat": bot_ch.id,
                                            "submit": submit_ch.id,
                                            "approval": reviewer_role.id,
                                            "info_posts": [ ]
                                            }

        self.saveConfig()
        await msg.channel.send(msg.author.mention + " Initialized bot to this server!")

    async def addSpeciesForm(self, msg, args):
        if len(args) < 1 or len(args) > 2:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = SpriteUtils.sanitizeName(args[0])
        species_idx = SpriteUtils.findSlotIdx(self.tracker, species_name)
        if len(args) == 1:
            if species_idx is not None:
                await msg.channel.send(msg.author.mention + " {0} already exists!".format(species_name))
                return

            count = len(self.tracker)
            new_idx = "{:04d}".format(count)
            self.tracker[new_idx] = SpriteUtils.createSpeciesNode(species_name)

            await msg.channel.send(msg.author.mention + " Added #{0:03d}: {1}!".format(count, species_name))
        else:
            if species_idx is None:
                await msg.channel.send(msg.author.mention + " {0} doesn't exist! Create it first!".format(species_name))
                return

            form_name = SpriteUtils.sanitizeName(args[1])
            species_dict = self.tracker[species_idx]
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is not None:
                await msg.channel.send(msg.author.mention +
                                       " {2} already exists within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            count = len(species_dict.subgroups)
            new_count = "{:04d}".format(count)
            species_dict.subgroups[new_count] = SpriteUtils.createFormNode(form_name)

            await msg.channel.send(msg.author.mention +
                                   " Added #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.saveTracker()
        self.changed = True

    async def renameSpeciesForm(self, msg, args):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = SpriteUtils.sanitizeName(args[0])
        new_name = SpriteUtils.sanitizeName(args[-1])
        species_idx = SpriteUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]

        if len(args) == 2:
            new_species_idx = SpriteUtils.findSlotIdx(self.tracker, new_name)
            if new_species_idx is not None:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} already exists!".format(int(new_species_idx), new_name))
                return

            species_dict.name = new_name
            await msg.channel.send(msg.author.mention + " Changed #{0:03d}: {1} to {2}!".format(int(species_idx), species_name, new_name))
        else:

            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            new_form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, new_name)
            if new_form_idx is not None:
                await msg.channel.send(msg.author.mention + " {2} already exists within #{0:03d}: {1}!".format(int(species_idx), species_name, new_name))
                return

            form_dict = species_dict.subgroups[form_idx]
            form_dict.name = new_name

            await msg.channel.send(msg.author.mention + " Changed {2} to {3} in #{0:03d}: {1}!".format(int(species_idx), species_name, form_name, new_name))

        self.saveTracker()
        self.changed = True

    async def removeSpeciesForm(self, msg, args):
        if len(args) < 1 or len(args) > 2:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = SpriteUtils.sanitizeName(args[0])
        species_idx = SpriteUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 1:
            # check against data population
            if SpriteUtils.isDataPopulated(species_dict):
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            # check against count
            if int(species_idx) != len(self.tracker) - 1:
                await msg.channel.send(msg.author.mention + " Can only delete the last species!")
                return

            del self.tracker[species_idx]
            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1}!".format(int(species_idx), species_name))
        else:

            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if SpriteUtils.isDataPopulated(form_dict):
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            # check against count
            if int(form_idx) != len(species_dict.subgroups) - 1:
                await msg.channel.send(msg.author.mention + " Can only delete the last form!")
                return

            del species_dict.subgroups[form_idx]
            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.saveTracker()
        self.changed = True


    async def addGender(self, msg, args):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[-1].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        species_name = SpriteUtils.sanitizeName(args[0])
        species_idx = SpriteUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 2:
            # check against already existing
            if SpriteUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference already exists for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            SpriteUtils.createGenderDiff(species_dict.subgroups["0000"], asset_type)
            await msg.channel.send(msg.author.mention +
                " Added gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:

            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if SpriteUtils.genderDiffExists(form_dict, asset_type):
                await msg.channel.send(msg.author.mention +
                    " Gender difference already exists for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            SpriteUtils.createGenderDiff(form_dict, asset_type)
            await msg.channel.send(msg.author.mention +
                " Added gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.saveTracker()
        self.changed = True


    async def removeGender(self, msg, args):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[-1].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        species_name = SpriteUtils.sanitizeName(args[0])
        species_idx = SpriteUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 2:
            # check against not existing
            if not SpriteUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference doesnt exist for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            # check against data population
            if SpriteUtils.genderDiffPopulated(species_dict.subgroups["0000"], asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            SpriteUtils.removeGenderDiff(species_dict.subgroups["0000"], asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:
            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against not existing
            form_dict = species_dict.subgroups[form_idx]
            if not SpriteUtils.genderDiffExists(form_dict, asset_type):
                await msg.channel.send(msg.author.mention +
                    " Gender difference doesn't exist for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            if SpriteUtils.genderDiffPopulated(form_dict, asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            SpriteUtils.removeGenderDiff(form_dict, asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.saveTracker()
        self.changed = True


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    global sprite_bot
    await sprite_bot.checkAllSubmissions()
    print('------')


@client.event
async def on_message(msg: discord.Message):
    await client.wait_until_ready()
    try:
        # exclude self posts
        if msg.author.id == sprite_bot.client.user.id:
            return

        content = msg.content
        # only respond to the proper author
        if msg.author.id == sprite_bot.owner_id and content.startswith("!init"):
            args = content[len(COMMAND_PREFIX):].split(' ')
            await sprite_bot.initServer(msg, args[1:])
            return

        # only respond to the proper guilds
        guild_id_str = str(msg.guild.id)
        if guild_id_str not in sprite_bot.servers:
            return

        if msg.channel.id == sprite_bot.servers[guild_id_str]["chat"]:
            if not content.startswith(COMMAND_PREFIX):
                return
            args = content[len(COMMAND_PREFIX):].split(' ')

            authorized = await sprite_bot.isAuthorized(msg.author, msg.guild)
            if args[0] == "add" and authorized:
                await sprite_bot.addSpeciesForm(msg, args[1:])
            elif args[0] == "rename" and authorized:
                await sprite_bot.renameSpeciesForm(msg, args[1:])
            elif args[0] == "delete" and authorized:
                await sprite_bot.removeSpeciesForm(msg, args[1:])
            elif args[0] == "addgender" and authorized:
                await sprite_bot.addGender(msg, args[1:])
            elif args[0] == "deletegender" and authorized:
                await sprite_bot.removeGender(msg, args[1:])
            elif args[0] == "sprite":
                await sprite_bot.queryStatus(msg, args[1:], "sprite", False)
            elif args[0] == "recolorsprite":
                await sprite_bot.queryStatus(msg, args[1:], "sprite", True)
            elif args[0] == "portrait":
                await sprite_bot.queryStatus(msg, args[1:], "portrait", False)
            elif args[0] == "recolorportrait":
                await sprite_bot.queryStatus(msg, args[1:], "portrait", True)
            elif args[0] == "profile":
                await sprite_bot.getProfile(msg)
            elif args[0] == "register":
                await sprite_bot.setProfile(msg, args[1:])
            elif args[0] == "spritedone":
                await sprite_bot.completeSlot(msg, args[1:], "sprite")
            elif args[0] == "portraitdone":
                await sprite_bot.completeSlot(msg, args[1:], "portrait")
            elif args[0] == "clearcache" and msg.author.id == sprite_bot.owner_id:
                await sprite_bot.clearCache(msg, args[1:])
            elif args[0] == "update" and msg.author.id == sprite_bot.owner_id:
                await sprite_bot.updateBot(msg)
            else:
                await msg.channel.send(msg.author.mention + " Unknown Command.")

        elif msg.channel.id == sprite_bot.servers[guild_id_str]["submit"]:
            changed_tracker = await sprite_bot.pollSubmission(msg)
            if changed_tracker:
                sprite_bot.saveTracker()

    except Exception as e:
        trace = traceback.format_exc()
        user = await client.fetch_user(sprite_bot.owner_id)
        await user.send("```"+trace+"```")

@client.event
async def on_raw_reaction_add(payload):
    await client.wait_until_ready()
    try:
        if payload.user_id == client.user.id:
            return
        guild_id_str = str(payload.guild_id)
        if payload.channel_id == sprite_bot.servers[guild_id_str]["submit"]:
            msg = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
            changed_tracker = await sprite_bot.pollSubmission(msg)
            if changed_tracker:
                sprite_bot.saveTracker()

    except Exception as e:
        trace = traceback.format_exc()
        user = await client.fetch_user(sprite_bot.owner_id)
        await user.send("```"+trace+"```")


async def periodic_update_status():
    await client.wait_until_ready()
    global sprite_bot
    last_date = ""
    while not client.is_closed():
        try:
            if sprite_bot.changed:
                sprite_bot.changed = False
                for server_id in sprite_bot.servers:
                    await sprite_bot.updatePost(sprite_bot.servers[server_id])

            # check for push
            cur_date = datetime.datetime.today().strftime('%Y-%m-%d')
            if sprite_bot.can_push and last_date != cur_date:
                last_date = cur_date
                # update push
                if sprite_bot.commits > 0:
                    sprite_bot.gitPush()
        except Exception as e:
            trace = traceback.format_exc()
            user = await client.fetch_user(sprite_bot.owner_id)
            print(trace)
            await user.send("```"+trace+"```")
        await asyncio.sleep(10)

sprite_bot = SpriteBot(scdir, client)

client.loop.create_task(periodic_update_status())

with open(os.path.join(scdir, TOKEN_FILE_PATH)) as token_file:
    token = token_file.read()

client.run(token)


if sprite_bot.need_restart:
    # restart
    args = sys.argv[:]
    args.insert(0, sys.executable)
    if sys.platform == 'win32':
        args = ['"%s"' % arg for arg in args]

    os.execv(sys.executable, args)