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

SPRITE_WORTH = 10
PORTRAIT_WORTH = 1
SPRITE_SHINY_WORTH = 2
PORTRAIT_SHINY_WORTH = 1

PHASES = [ "\u26AA incomplete", "\u2705 available", "\u2B50 fully featured" ]

# Command prefix.
COMMAND_PREFIX = '!'

scdir = os.path.dirname(os.path.abspath(__file__))

# The Discord client.
client = discord.Client()

class BotServer:

    def __init__(self, main_dict=None):
        if main_dict is None:
            self.info = 0
            self.chat = 0
            self.submit = 0
            self.approval = 0
            self.info_posts = []
            return
        self.__dict__ = main_dict

    def getDict(self):
        return self.__dict__

class BotConfig:

    def __init__(self, main_dict=None):
        if main_dict is None:
            self.path = ""
            self.root = 0
            self.push = False
            self.points = 0
            self.points_ch = 0
            self.update_ch = 0
            self.update_msg = 0
            self.servers = {}
            return

        self.__dict__ = main_dict

        sub_dict = {}
        for key in self.servers:
            sub_dict[key] = BotServer(self.servers[key])
        self.servers = sub_dict

    def getDict(self):
        node_dict = { }
        for k in self.__dict__:
            node_dict[k] = self.__dict__[k]
        sub_dict = { }
        for sub_idx in self.servers:
            sub_dict[sub_idx] = self.servers[sub_idx].getDict()
        node_dict["servers"] = sub_dict
        return node_dict

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
            self.config = BotConfig(json.load(f))

        # init repo
        self.repo = git.Repo(self.config.path)
        self.commits = 0
        # tracking data from the content folder
        with open(os.path.join(self.config.path, TRACKER_FILE_PATH)) as f:
            new_tracker = json.load(f)
            self.tracker = { }
            for species_idx in new_tracker:
                self.tracker[species_idx] = SpriteUtils.TrackerNode(new_tracker[species_idx])
        self.names = SpriteUtils.loadNameFile(os.path.join(self.path, NAME_FILE_PATH))
        confirmed_names = SpriteUtils.loadNameFile(os.path.join(self.config.path, NAME_FILE_PATH))
        self.client = client
        self.changed = False

        # update tracker based on last-modify
        over_dict = SpriteUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker
        SpriteUtils.fileSystemToJson(over_dict, os.path.join(self.config.path, "sprite"), "sprite", 0)
        SpriteUtils.fileSystemToJson(over_dict, os.path.join(self.config.path, "portrait"), "portrait", 0)

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
        SpriteUtils.updateNameFile(os.path.join(self.config.path, NAME_FILE_PATH), self.names, False)

    def saveConfig(self):
        with open(os.path.join(self.path, CONFIG_FILE_PATH), 'w', encoding='utf-8') as txt:
            config = self.config.getDict()
            json.dump(config, txt, indent=2)

    def saveTracker(self):
        new_tracker = { }
        for species_idx in self.tracker:
            new_tracker[species_idx] = self.tracker[species_idx].getDict()
        with open(os.path.join(self.config.path, TRACKER_FILE_PATH), 'w', encoding='utf-8') as txt:
            json.dump(new_tracker, txt, indent=2)

    async def gitCommit(self, msg):
        if self.config.push:
            index = self.repo.index
            diff = index.diff(None)
            if len(diff) > 0:
                try:
                    self.repo.git.add(".")
                    self.repo.git.commit(m=msg)
                except Exception as e:
                    user = await client.fetch_user(self.config.root)
                    trace = traceback.format_exc()
                    print(trace)
                    await user.send("```" + trace + "```")
            self.commits += 1


    async def gitPush(self):
        if self.config.push and self.commits > 0:
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
        self.config.update_ch = resp_ch.id
        self.config.update_msg = resp.id
        self.saveConfig()
        await self.client.logout()

    async def checkRestarted(self):
        if self.config.update_ch != 0 and self.config.update_msg != 0:
            msg = await self.client.get_channel(self.config.update_ch).fetch_message(self.config.update_msg)
            await msg.edit(content="Bot updated and restarted.")
            self.config.update_ch = 0
            self.config.update_msg = 0
            self.saveConfig()

    def getChatChannel(self, guild_id):
        chat_id = self.config.servers[str(guild_id)].chat
        return self.client.get_channel(chat_id)

    def getStatusEmoji(self, chosen_node, asset_type):
        pending = chosen_node.__dict__[asset_type+"_pending"]
        added = chosen_node.__dict__[asset_type + "_credit"] != ""
        complete = chosen_node.__dict__[asset_type+"_complete"]
        required = chosen_node.__dict__[asset_type+"_required"]
        if complete > SpriteUtils.PHASE_EXISTS: # star
            return "\u2B50"
        elif len(pending) > 0:
            if complete > SpriteUtils.PHASE_INCOMPLETE:  # interrobang
                return "\u2049"
            else:  # question
                return "\u2754"
        elif added:
            if len(pending) > 0:  # interrobang
                return "\u2049"
            else:
                if complete > SpriteUtils.PHASE_INCOMPLETE:  # checkmark
                    return "\u2705"
                else:  # white circle
                    return "\u26AA"
        else:
            if required:  # X mark
                return "\u274C"
            else:  # black circle
                return "\u26AB"

    def getAuthorCol(self, author):
        return str(author.id) + "#" + author.name.replace("\t", "") + "#" + author.discriminator

    def getPostCredit(self, mention):
        if mention == "":
            return "-"
        if len(mention) < 4:
            return mention
        if mention[:3] != "<@!" or mention[-1] != ">":
            return mention

        try:
            user_id = int(mention[2:-1])
            user = self.client.get_user(user_id)
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

    def getPostsFromDict(self, include_sprite, include_portrait, include_credit, tracker_dict, posts, indices):
        if tracker_dict.name != "":
            new_titles = SpriteUtils.getIdxName(self.tracker, indices)
            dexnum = int(indices[0])
            name_str = " ".join(new_titles)
            post = ""

            # status
            if include_sprite:
                post += self.getStatusEmoji(tracker_dict, "sprite")
            if include_portrait:
                post += self.getStatusEmoji(tracker_dict, "portrait")
            # name
            post += " `#" + "{:03d}".format(dexnum) + "`: `" + name_str + "` "

            # credits
            if include_credit:
                if include_sprite:
                    post += self.getPostCredit(tracker_dict.sprite_credit)
                    if include_portrait:
                        post += "/"
                if include_portrait:
                    post += self.getPostCredit(tracker_dict.portrait_credit)
            posts.append(post)

        for sub_dict in tracker_dict.subgroups:
            self.getPostsFromDict(include_sprite, include_portrait, include_credit, tracker_dict.subgroups[sub_dict], posts, indices + [sub_dict])



    def getBountiesFromDict(self, asset_type, tracker_dict, entries, indices):
        if tracker_dict.name != "":
            new_titles = SpriteUtils.getIdxName(self.tracker, indices)
            dexnum = int(indices[0])
            name_str = " ".join(new_titles)
            post = asset_type.title() + " of "

            # status
            post += self.getStatusEmoji(tracker_dict, asset_type)
            # name
            post += " `#" + "{:03d}".format(dexnum) + "`: `" + name_str + "` "

            bounty_dict = tracker_dict.__dict__[asset_type + "_bounty"]
            next_phase = tracker_dict.__dict__[asset_type + "_complete"] + 1

            if str(next_phase) in bounty_dict:
                bounty = bounty_dict[str(next_phase)]
                if bounty > 0:
                    entries.append((bounty, post, asset_type, next_phase))

        for sub_dict in tracker_dict.subgroups:
            self.getBountiesFromDict(asset_type, tracker_dict.subgroups[sub_dict], entries, indices + [sub_dict])


    async def isAuthorized(self, user, guild):

        if user.id == self.client.user.id:
            return False
        if user.id == self.config.root:
            return True
        guild_id_str = str(guild.id)
        approve_role = guild.get_role(self.config.servers[guild_id_str].approval)

        try:
            user_member = await guild.fetch_member(user.id)
        except discord.NotFound as e:
            user_member = None

        if user_member is None:
            return False
        if approve_role in user_member.roles:
            return True
        return False

    async def generateLink(self, file_data, filename):
        # file_data is a file-like object to post with
        # post the file to the admin under a specific filename
        user = await client.fetch_user(self.config.root)
        resp = await user.send("", file=discord.File(file_data, filename))
        result_url = resp.attachments[0].url
        return result_url

    async def verifySubmission(self, msg, full_idx, asset_type, recolor, msg_args):
        decline_msg = None
        quant_img = None
        diffs = None

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        full_arr = [self.config.path, asset_type] + full_idx
        chosen_path = os.path.join(*full_arr)

        if asset_type == "sprite":
            # get the sprite zip and verify its contents
            try:
                if recolor:
                    wan_zip = SpriteUtils.getLinkImg(msg.attachments[0].url)
                else:
                    wan_zip = SpriteUtils.getLinkZipGroup(msg.attachments[0].url)
            except SpriteUtils.SpriteVerifyError as e:
                await self.returnMsgFile(msg, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
            except Exception as e:
                await self.returnMsgFile(msg, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                raise e

            orig_zip = None
            # if it's a shiny, get the original image
            if SpriteUtils.isShinyIdx(full_idx):
                orig_idx = SpriteUtils.createShinyIdx(full_idx, False)
                orig_node = SpriteUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                if orig_node.__dict__[asset_type + "_credit"] == "":
                    # this means there's no original portrait to base the recolor off of
                    await self.returnMsgFile(msg, msg.author.mention + " Cannot submit a shiny when the original isn't finished.", asset_type)
                    return False, None

                orig_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, recolor)
                try:
                    if recolor:
                        orig_zip = SpriteUtils.getLinkImg(orig_link)
                    else:
                        orig_zip = SpriteUtils.getLinkZipGroup(orig_link)
                except SpriteUtils.SpriteVerifyError as e:
                    await self.returnMsgFile(msg, msg.author.mention + " A problem occurred reading original sprite.", asset_type)
                except Exception as e:
                    await self.returnMsgFile(msg, msg.author.mention + " A problem occurred reading original sprite.", asset_type)
                    raise e

            # if the file needs to be compared to an original, verify it as a recolor. Otherwise, by itself.
            try:
                diffs = SpriteUtils.verifySpriteLock(chosen_node, chosen_path, wan_zip, recolor)
                if SpriteUtils.isShinyIdx(full_idx):
                    SpriteUtils.verifySpriteRecolor(msg_args, orig_zip, wan_zip, recolor)
                else:
                    SpriteUtils.verifySprite(msg_args, wan_zip)
            except SpriteUtils.SpriteVerifyError as e:
                decline_msg = e.message
                quant_img = e.preview_img
        elif asset_type == "portrait":
            # get the portrait image and verify its contents
            try:
                img = SpriteUtils.getLinkImg(msg.attachments[0].url)
            except SpriteUtils.SpriteVerifyError as e:
                await self.returnMsgFile(msg, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                return False, None
            except Exception as e:
                await self.returnMsgFile(msg, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                raise e

            orig_img = None
            # if it's a shiny, get the original image
            if SpriteUtils.isShinyIdx(full_idx):
                orig_idx = SpriteUtils.createShinyIdx(full_idx, False)
                orig_node = SpriteUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                if orig_node.__dict__[asset_type + "_credit"] == "":
                    # this means there's no original portrait to base the recolor off of
                    await self.returnMsgFile(msg, msg.author.mention + " Cannot submit a shiny when the original isn't finished.", asset_type)
                    return False, None

                orig_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, recolor)

                try:
                    orig_img = SpriteUtils.getLinkImg(orig_link)
                except SpriteUtils.SpriteVerifyError as e:
                    await self.returnMsgFile(msg, msg.author.mention + " A problem occurred reading original portrait.",
                                             asset_type)
                    return False, None
                except Exception as e:
                    await self.returnMsgFile(msg, msg.author.mention + " A problem occurred reading original portrait.",
                                             asset_type)
                    raise e

            # if the file needs to be compared to an original, verify it as a recolor. Otherwise, by itself.
            try:
                diffs = SpriteUtils.verifyPortraitLock(chosen_node, chosen_path, img, recolor)
                if SpriteUtils.isShinyIdx(full_idx):
                    SpriteUtils.verifyPortraitRecolor(msg_args, orig_img, img, recolor)
                else:
                    SpriteUtils.verifyPortrait(msg_args, img)
            except SpriteUtils.SpriteVerifyError as e:
                decline_msg = e.message
                quant_img = e.preview_img

        if decline_msg is not None:
            await self.returnMsgFile(msg, msg.author.mention + " " + decline_msg, asset_type, quant_img)
            return False, None

        return True, diffs

    async def returnMsgFile(self, msg, msg_body, asset_type, quant_img=None):
        try:
            return_file, return_name = SpriteUtils.getLinkFile(msg.attachments[0].url, asset_type)
            await self.getChatChannel(msg.guild.id).send(msg_body, file=discord.File(return_file, return_name))

            if quant_img is not None:
                fileData = io.BytesIO()
                quant_img.save(fileData, format='PNG')
                fileData.seek(0)
                await self.getChatChannel(msg.guild.id).send("Color-reduced preview:",
                    file=discord.File(fileData, return_name.replace('.zip', '.png')))
        except SpriteUtils.SpriteVerifyError as e:
            await self.getChatChannel(msg.guild.id).send(msg_body + "\n(An error occurred with the file)")
        except Exception as e:
            await self.getChatChannel(msg.guild.id).send(msg_body + "\n(An error occurred with the file)")
            trace = traceback.format_exc()
            user = await self.client.fetch_user(self.config.root)
            await user.send("```" + trace[:1950] + "```")
        await msg.delete()



    async def stageSubmission(self, msg, full_idx, chosen_node, asset_type, author, recolor, diffs, overcolor):

        try:
            return_file, return_name = SpriteUtils.getLinkFile(msg.attachments[0].url, asset_type)
        except SpriteUtils.SpriteVerifyError as e:
            await self.getChatChannel(msg.guild.id).send("An error occurred with the file {0}.\n{1}".format(msg.attachments[0].filename, str(e)))
            await msg.delete()
            return
        except Exception as e:
            await self.getChatChannel(msg.guild.id).send("An error occurred with the file {0}.\n{1}".format(msg.attachments[0].filename, str(e)))
            await msg.delete()
            raise e

        overcolor_img = None
        if overcolor:
            overcolor_img = SpriteUtils.getLinkImg(msg.attachments[0].url)
            if recolor:
                overcolor_img = SpriteUtils.removePalette(overcolor_img)

        await self.postStagedSubmission(msg.channel, msg.content, full_idx, chosen_node, asset_type, author, recolor,
                                        diffs, return_file, return_name, overcolor_img)

        await msg.delete()

    async def postStagedSubmission(self, channel, content, full_idx, chosen_node, asset_type, author, recolor,
                                   diffs, return_file, return_name, overcolor_img):

        title = SpriteUtils.getIdxName(self.tracker, full_idx)

        send_files = [discord.File(return_file, return_name)]
        add_msg = ""
        if overcolor_img is not None:
            if asset_type == "sprite":
                reduced_img = SpriteUtils.simple_quant(overcolor_img)
            elif asset_type == "portrait":
                reduced_img = SpriteUtils.simple_quant_portraits(overcolor_img)

            reduced_file = io.BytesIO()
            reduced_img.save(reduced_file, format='PNG')
            reduced_file.seek(0)
            send_files.append(discord.File(reduced_file, return_name.replace('.png', '_reduced.png')))
            add_msg += "\nReduced Color Preview included."
        if chosen_node.__dict__[asset_type + "_credit"] != "":
            if not recolor:
                if diffs is not None and len(diffs) > 0:
                    add_msg += "\nChanges: {0}".format(", ".join(diffs))
                else:
                    add_msg += "\nNo Changes."
            if recolor or asset_type == "portrait":
                orig_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, recolor)
                add_msg += "\nCurrent Version: {0}".format(orig_link)
        new_msg = await channel.send("{0} {1}\n{2}".format(author, " ".join(title), content + add_msg),
                                     files=send_files)

        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 0
        pending_dict[str(new_msg.id)] = new_msg.channel.id

        # react to the message
        await new_msg.add_reaction('\U00002705')
        await new_msg.add_reaction('\U0000274C')

        self.changed |= change_status

    async def submissionApproved(self, msg, orig_sender, orig_author, approvals):
        sender_info = orig_sender
        if orig_author != orig_sender:
            sender_info = "{0}/{1}".format(orig_sender, orig_author)

        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(orig_sender + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        is_base = not SpriteUtils.isShinyIdx(full_idx)
        shiny_idx = None
        shiny_node = None
        base_recolor_img = None
        if is_base:
            shiny_idx = SpriteUtils.createShinyIdx(full_idx, True)
            shiny_node = SpriteUtils.getNodeFromIdx(self.tracker, shiny_idx, 0)

            if shiny_node.__dict__[asset_type + "_complete"] > SpriteUtils.PHASE_INCOMPLETE:
                # get recolor data
                base_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, True)
                base_recolor_img = SpriteUtils.getLinkImg(base_link)

        # get the name of the slot that it was written to
        new_name = SpriteUtils.getIdxName(self.tracker, full_idx)
        new_name_str = " ".join(new_name)

        # change the status of the sprite
        new_revise = "New"
        if chosen_node.__dict__[asset_type+"_credit"] != "":
            new_revise = "Revised"

        # save and set the new sprite or portrait
        full_arr = [self.config.path, asset_type] + full_idx
        gen_path = os.path.join(*full_arr)
        if asset_type == "sprite":
            if recolor:
                orig_idx = SpriteUtils.createShinyIdx(full_idx, False)
                orig_arr = [self.config.path, asset_type] + orig_idx
                orig_path = os.path.join(*orig_arr)
                # no need to check if the original sprite has changed between this recolor's submission and acceptance
                # because when the original sprite is approved, all submissions for shinies are purged
                try:
                    recolor_img = SpriteUtils.getLinkImg(msg.attachments[0].url)
                except Exception as e:
                    await self.getChatChannel(msg.guild.id).send(
                        orig_sender + " " + "Removed unknown file: {0}".format(file_name))
                    await msg.delete()
                    raise e
                SpriteUtils.placeSpriteRecolorToPath(orig_path, recolor_img, gen_path)
            else:
                wan_file = SpriteUtils.getLinkZipGroup(msg.attachments[0].url)
                SpriteUtils.placeSpriteZipToPath(wan_file, gen_path)
        elif asset_type == "portrait":
            try:
                portrait_img = SpriteUtils.getLinkImg(msg.attachments[0].url)
            except Exception as e:
                await self.getChatChannel(msg.guild.id).send(orig_sender + " " + "Removed unknown file: {0}".format(file_name))
                await msg.delete()
                raise e

            if recolor:
                portrait_img = SpriteUtils.removePalette(portrait_img)
            SpriteUtils.placePortraitToPath(portrait_img, gen_path)

        prev_completion_file = SpriteUtils.getCurrentCompletion(chosen_node, asset_type)

        new_credit = True
        cur_credits = SpriteUtils.getFileCredits(gen_path)
        for credit in cur_credits:
            if credit[1] == orig_author:
                new_credit = False
                break

        SpriteUtils.appendCredits(gen_path, orig_author)
        # add to universal names list and save if changed
        if orig_author not in self.names:
            self.names[orig_author] = SpriteUtils.CreditEntry("", "")
        self.names[orig_author].sprites = True
        self.names[orig_author].portraits = True
        self.saveNames()

        # update the credits and timestamp in the chosen node
        chosen_node.__dict__[asset_type + "_modified"] = str(datetime.datetime.utcnow())
        chosen_node.__dict__[asset_type + "_credit"] = orig_author
        # update the file cache
        SpriteUtils.updateFiles(chosen_node, gen_path, asset_type)

        current_completion_file = SpriteUtils.getCurrentCompletion(chosen_node, asset_type)

        give_points = current_completion_file - prev_completion_file
        if give_points < 1 and new_credit:
            give_points = 1

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

        mentions = ["<@!"+str(ii)+">" for ii in approvals]
        approve_msg = "{0} {1} approved by {2}: #{3:03d}: {4}".format(new_revise, asset_type, str(mentions), int(full_idx[0]), new_name_str)

        # update completion to correct value
        chosen_node.__dict__[asset_type + "_complete"] = current_completion_file
        if current_completion_file != prev_completion_file:
            approve_msg += "\n{0} is now {1}.".format(asset_type.title(), PHASES[current_completion_file])

        # if this was non-shiny, set the complete flag to false for the shiny
        if is_base:
            if shiny_node.__dict__[asset_type+"_credit"] != "":
                shiny_node.__dict__[asset_type+"_complete"] = SpriteUtils.PHASE_INCOMPLETE
                approve_msg += "\nNote: Shiny form now marked as {0} due to this change.".format(PHASES[SpriteUtils.PHASE_INCOMPLETE])


        if SpriteUtils.isShinyIdx(full_idx):
            if asset_type == "sprite":
                give_points *= SPRITE_SHINY_WORTH
            elif asset_type == "portrait":
                give_points *= PORTRAIT_SHINY_WORTH
        else:
            if asset_type == "sprite":
                give_points *= SPRITE_WORTH
            elif asset_type == "portrait":
                give_points *= PORTRAIT_WORTH

        if chosen_node.modreward:
            give_points = 0
            approve_msg += "\nThe non-bounty GP Reward for this {0} will be handled by the approvers.".format(asset_type)

        # save the tracker
        self.saveTracker()

        update_msg = "{0} {1} #{2:03d}: {3}".format(new_revise, asset_type, int(full_idx[0]), new_name_str)
        # commit the changes
        await self.gitCommit("{0} by {1} {2}".format(update_msg, orig_author, self.names[orig_author].name))

        # post about it
        for server_id in self.config.servers:
            if server_id == str(msg.guild.id):
                await self.getChatChannel(msg.guild.id).send(sender_info + " " + approve_msg + "\n" + new_link)
            else:
                await self.getChatChannel(int(server_id)).send("{1}: {0}".format(update_msg, msg.guild.name))

        # delete post
        await msg.delete()


        # add bounty
        result_phase = current_completion_file
        while result_phase > 0:
            if str(result_phase) in chosen_node.__dict__[asset_type + "_bounty"]:
                give_points += chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)]
                del chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)]
            result_phase -= 1

        if give_points > 0 and orig_author.startswith("<@!") and self.config.points_ch != 0:
            orig_author_id = orig_author[3:-1]
            await self.client.get_channel(self.config.points_ch).send("!gr {0} {1} {2}".format(orig_author_id, give_points, self.config.servers[str(msg.guild.id)].chat))

        self.changed = True

        if is_base:
            pending = {}
            for pending_id in shiny_node.__dict__[asset_type+"_pending"]:
                pending[pending_id] = shiny_node.__dict__[asset_type+"_pending"][pending_id]

            for pending_id in pending:
                try:
                    shiny_ch = self.client.get_channel(pending[pending_id])
                    shiny_msg = await shiny_ch.fetch_message(pending_id)
                    shiny_lines = msg.content.split()
                    shiny_data = shiny_lines[0].split()
                    shiny_sender_data = shiny_data[0].split("/")
                    shiny_sender = shiny_sender_data[0]
                    await self.submissionDeclined(shiny_msg, shiny_sender, [])
                except Exception as e:
                    trace = traceback.format_exc()
                    user = await self.client.fetch_user(sprite_bot.config.root)
                    await user.send("```" + trace + "```")

            if base_recolor_img is not None:
                # auto-generate recolor link
                base_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, True)
                cur_recolor_img = SpriteUtils.getLinkImg(base_link)
                # auto-generate the shiny recolor image, in file form
                shiny_arr = [self.config.path, asset_type] + shiny_idx
                shiny_path = os.path.join(*shiny_arr)
                auto_recolor_img, content = SpriteUtils.autoRecolor(base_recolor_img, cur_recolor_img, shiny_path, asset_type)
                # post it as a staged submission
                return_name = "{0}-{1}{2}".format(asset_type + "_recolor", "-".join(shiny_idx), ".png")

                auto_recolor_file = io.BytesIO()
                auto_recolor_img.save(auto_recolor_file, format='PNG')
                auto_recolor_file.seek(0)

                msg_args = content.split()
                overcolor = ('overcolor' in msg_args)
                overcolor_img = None
                if overcolor:
                    overcolor_img = SpriteUtils.removePalette(auto_recolor_img)

                await self.postStagedSubmission(msg.channel, content, shiny_idx, shiny_node, asset_type, orig_sender,
                                                True, None, auto_recolor_file, return_name, overcolor_img)



    async def submissionDeclined(self, msg, orig_sender, declines):

        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(orig_sender + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        # change the status of the sprite
        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 1
        if str(msg.id) in pending_dict:
            del pending_dict[str(msg.id)]

        if len(declines) > 0:
            mentions = ["<@!" + str(ii) + ">" for ii in declines]
            await self.returnMsgFile(msg, orig_sender + " " + "{0} declined by {1}:".format(asset_type, ', '.join(mentions)), asset_type)
        else:
            await self.returnMsgFile(msg,
                                     orig_sender + " " + "{0} declined due to another change."
                                                         "  Please resubmit.".format(asset_type), asset_type)
        self.changed |= change_status

    async def checkAllSubmissions(self):
        # clear all pending submissions; we don't know if they were deleted or not between startups
        for node_idx in self.tracker:
            SpriteUtils.clearSubmissions(self.tracker[node_idx])

        # make sure they are re-added
        for server in self.config.servers:
            ch_id = self.config.servers[server].submit
            msgs = []
            channel = self.client.get_channel(ch_id)
            async for message in channel.history(limit=None):
                msgs.append(message)
            for msg in msgs:
                try:
                    await self.pollSubmission(msg)
                except Exception as e:
                    trace = traceback.format_exc()
                    user = await self.client.fetch_user(self.config.root)
                    await user.send("```" + trace + "```")
            self.saveTracker()
            self.changed = True

    """
    Returns true if anything changed that would require a tracker save
    """
    async def pollSubmission(self, msg):
        # check for messages in #submissions

        if msg.author.id == self.client.user.id:
            cks = None
            xs = None
            ss = None
            remove_users = []
            for reaction in msg.reactions:
                if reaction.emoji == '\u2705':
                    cks = reaction
                elif reaction.emoji == '\u274C':
                    xs = reaction
                elif reaction.emoji == '\u2B50':
                    ss = reaction
                else:
                    async for user in reaction.users():
                        remove_users.append((reaction, user))

            msg_lines = msg.content.split()
            main_data = msg_lines[0].split()
            sender_data = main_data[0].split("/")
            orig_sender = sender_data[0]
            orig_author = sender_data[-1]
            orig_sender_id = int(orig_sender[3:-1])

            auto = False
            approve = []
            decline = []

            if ss:
                async for user in ss.users():
                    if user.id == self.config.root:
                        auto = True
                        approve.append(user.id)
                    else:
                        remove_users.append((ss, user))

            async for user in cks.users():
                if await self.isAuthorized(user, msg.guild):
                    approve.append(user.id)
                elif user.id != self.client.user.id:
                    remove_users.append((cks, user))

            async for user in xs.users():
                if await self.isAuthorized(user, msg.guild) or user.id == orig_sender_id:
                    decline.append(user.id)
                elif user.id != self.client.user.id:
                    remove_users.append((xs, user))

            file_name = msg.attachments[0].filename
            name_valid, full_idx, asset_type, recolor = SpriteUtils.getStatsFromFilename(file_name)

            if len(decline) > 0:
                await self.submissionDeclined(msg, orig_sender, decline)
                return True
            elif auto or (asset_type == "sprite" and len(approve) >= 3) or (asset_type == "portrait" and len(approve) >= 2):
                await self.submissionApproved(msg, orig_sender, orig_author, approve)
                return False
            else:
                chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)
                pending_dict = chosen_node.__dict__[asset_type + "_pending"]
                pending_dict[str(msg.id)] = msg.channel.id

                for reaction, user in remove_users:
                    await reaction.remove(user)
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
            elif not chosen_node.__dict__[asset_type + "_required"]:
                # if the node can be found, but it's not required, it's also invalid
                name_valid = False

            if not name_valid:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid filename {0}. Do not change the filename from the original.".format(file_name))
                return False

            msg_args = msg.content.split()
            overcolor = ('overcolor' in msg_args)
            # at this point, we confirm the file name is valid, now check the contents
            verified, diffs = await self.verifySubmission(msg, full_idx, asset_type, recolor, msg_args)
            if not verified:
                return False

            # after other args have been consumed, check for one more arg: if the submission was made in someone else's stead
            author = "<@!{0}>".format(msg.author.id)
            if len(msg_args) > 0:
                decline_msg = None
                if msg_args[0] not in self.names:
                    decline_msg = "{0} does not have a profile.".format(msg_args[0])

                if decline_msg is not None:
                    await self.returnMsgFile(msg, msg.author.mention + " " + decline_msg, asset_type)
                    return False

                author = "{0}/{1}".format(author, msg_args[0])

            await self.stageSubmission(msg, full_idx, chosen_node, asset_type, author, recolor, diffs, overcolor)
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
                    msg = await channel.fetch_message(msg_ids[msg_idx])
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
                msg_ids.append(msg.id)
                changed = True
            line_idx += line_len
            msg_idx += 1

        return msg_idx, changed

    async def updatePost(self, server):
        # update status in #info
        msg_ids = server.info_posts
        changed_list = False

        channel = self.client.get_channel(int(server.info))

        posts = []
        over_dict = SpriteUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker
        self.getPostsFromDict(True, True, True, over_dict, posts, [])

        msgs_used = 0
        msgs_used, changed = await self.sendInfoPosts(channel, posts, msg_ids, msgs_used)
        changed_list |= changed
        msgs_used, changed = await self.sendInfoPosts(channel, self.info_post, msg_ids, msgs_used)
        changed_list |= changed

        while msgs_used < len(msg_ids):
            msg = await channel.fetch_message(msg_ids[-1])
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
        gen_path = os.path.join(self.config.path, asset_type, "0000")
        # otherwise, use the provided path
        if chosen_node.__dict__[asset_type + "_credit"] != "":
            full_arr = [self.config.path, asset_type] + full_idx
            gen_path = os.path.join(*full_arr)

        if recolor:
            target_idx = SpriteUtils.createShinyIdx(full_idx, True)
        else:
            target_idx = full_idx
        file_data, ext = SpriteUtils.generateFileData(gen_path, asset_type, recolor)
        file_data.seek(0)
        file_name = "{0}-{1}{2}".format(req_base, "-".join(target_idx), ext)

        new_link = await self.generateLink(file_data, file_name)
        chosen_node.__dict__[req_link] = new_link
        self.saveTracker()
        return new_link

    def retrieveCreditFile(self, full_idx, chosen_node, asset_type):
        # otherwise, use the provided path
        if chosen_node.__dict__[asset_type + "_credit"] == "":
            return None
        full_arr = [self.config.path, asset_type] + full_idx
        gen_path = os.path.join(*full_arr)

        credits = SpriteUtils.getFileCredits(gen_path)

        credit_strings = []
        for credit in credits:
            credit_id = credit[1]
            entry = self.names[credit_id]
            if entry.name != '':
                credit_id = entry.name
            credit_strings.append("{0}\t{1}".format(credit_id, entry.contact))

        return credit_strings

    async def completeSlot(self, msg, name_args, asset_type, phase):
        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        phase_str = PHASES[phase]

        # if the node has no credit, fail
        if chosen_node.__dict__[asset_type + "_credit"] == "" and phase > SpriteUtils.PHASE_INCOMPLETE:
            status = self.getStatusEmoji(chosen_node, asset_type)
            await msg.channel.send(msg.author.mention +
                                   " {0} #{1:03d}: {2} has no data and cannot be marked {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))
            return

        # set to complete
        chosen_node.__dict__[asset_type + "_complete"] = phase

        status = self.getStatusEmoji(chosen_node, asset_type)
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} marked as {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))

        self.saveTracker()
        self.changed = True

    async def placeBounty(self, msg, name_args, asset_type):
        try:
            amt = int(name_args[-1])
        except Exception as e:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon and an amount.")
            return

        if amt <= 0:
            await msg.channel.send(msg.author.mention + " Specify an amount above 0.")
            return

        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args[:-1]]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        status = self.getStatusEmoji(chosen_node, asset_type)
        if chosen_node.__dict__[asset_type + "_complete"] >= SpriteUtils.PHASE_FULL:
            await msg.channel.send(msg.author.mention + " {0} #{1:03d} {2} is fully featured and cannot have a bounty.".format(status, int(full_idx[0]), " ".join(name_seq)))
            return

        if self.config.points == 0:
            if not await self.isAuthorized(msg.author, msg.guild):
                await msg.channel.send(msg.author.mention + " Not authorized.")
                return
        else:
            channel = self.client.get_channel(self.config.points_ch)
            resp = await channel.send("!checkr {0}".format(msg.author.id))

            # check for enough points
            def check(m):
                return m.channel == resp.channel and m.author.id == self.config.points

            cur_amt = 0
            try:
                wait_msg = await client.wait_for('message', check=check, timeout=10.0)
                result_json = json.loads(wait_msg.content)
                cur_amt = int(result_json["result"])
            except Exception as e:
                await msg.channel.send(msg.author.mention + " Error retrieving guild points.")
                return

            if cur_amt < amt:
                await msg.channel.send(msg.author.mention + " Not enough guild points! You currently have **{0}GP**.".format(cur_amt))
                return
            resp = await channel.send("!tr {0} {1} {2}".format(msg.author.id, amt, msg.channel.id))

            try:
                wait_msg = await client.wait_for('message', check=check, timeout=10.0)
                result_json = json.loads(wait_msg.content)
                if result_json["status"] != "success":
                    raise Exception() # TODO: what exception is this?
            except Exception as e:
                await msg.channel.send(msg.author.mention + " Error taking guild points.")
                return

        cur_val = 0
        result_phase = chosen_node.__dict__[asset_type + "_complete"] + 1
        if str(result_phase) in chosen_node.__dict__[asset_type + "_bounty"]:
            cur_val = chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)]

        chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)] = cur_val + amt

        # set to complete
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} now has a bounty of **{3}GP**, paid out when the {4} becomes {5}.".format(status, int(full_idx[0]), " ".join(name_seq), cur_val + amt, asset_type, PHASES[result_phase].title()))

        self.saveTracker()
        self.changed = True


    async def setLock(self, msg, name_args, asset_type, lock_state):

        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args[:-1]]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        file_name = name_args[-1]
        for k in chosen_node.__dict__[asset_type + "_files"]:
            if file_name.lower() == k.lower():
                file_name = k
                break

        if file_name not in chosen_node.__dict__[asset_type + "_files"]:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon and an existing emotion/animation.")
            return
        chosen_node.__dict__[asset_type + "_files"][file_name] = lock_state

        status = self.getStatusEmoji(chosen_node, asset_type)

        lock_str = "unlocked"
        if lock_state:
            lock_str = "locked"
        # set to complete
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} {3} is now {4}.".format(status, int(full_idx[0]), " ".join(name_seq), file_name, lock_str))

        self.saveTracker()
        self.changed = True

    async def listBounties(self, msg, name_args):
        include_sprite = True
        include_portrait = True

        if len(name_args) > 0:
            if name_args[0].lower() == "sprite":
                include_portrait = False
            elif name_args[0].lower() == "portrait":
                include_sprite = False
            else:
                await msg.channel.send(msg.author.mention + " Use 'sprite' or 'portrait' as argument.")
                return

        entries = []
        over_dict = SpriteUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker

        if include_sprite:
            self.getBountiesFromDict("sprite", over_dict, entries, [])
        if include_portrait:
            self.getBountiesFromDict("portrait", over_dict, entries, [])

        entries = sorted(entries, reverse=True)
        entries = entries[:10]

        posts = []
        if include_sprite and include_portrait:
            posts.append("**Top Bounties**")
        elif include_sprite:
            posts.append("**Top Bounties for Sprites**")
        else:
            posts.append("**Top Bounties for Portraits**")
        for entry in entries:
            posts.append("#{0:02d}. {2} for **{1}GP**, paid when the {3} becomes {4}.".format(len(posts), entry[0], entry[1], entry[2], PHASES[entry[3]].title()))

        if len(posts) == 1:
            posts.append("[None]")

        msgs_used, changed = await self.sendInfoPosts(msg.channel, posts, [], 0)

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

    async def listForms(self, msg, name_args, asset_type):
        # compute answer from current status
        if len(name_args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [SpriteUtils.sanitizeName(name_args[0])]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        posts = []
        over_dict = SpriteUtils.initSubNode("", True)
        over_dict.subgroups = { full_idx[0] : chosen_node }
        self.getPostsFromDict(asset_type == 'sprite', asset_type == 'portrait', False, over_dict, posts, [])
        msgs_used, changed = await self.sendInfoPosts(msg.channel, posts, [], 0)

    async def tryAutoRecolor(self, msg, name_args, asset_type):
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
        if "Shiny" in name_seq:
            await msg.channel.send(msg.author.mention + " Can't recolor a shiny Pokemon.")
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        if chosen_node.__dict__[asset_type + "_credit"] == "":
            await msg.channel.send(msg.author.mention + " Can't recolor a Pokemon that doesn't have a {0}.".format(asset_type))
            return

        shiny_idx = SpriteUtils.createShinyIdx(full_idx, True)
        shiny_node = SpriteUtils.getNodeFromIdx(self.tracker, shiny_idx, 0)

        if shiny_node.__dict__[asset_type + "_credit"] == "":
            await msg.channel.send(msg.author.mention + " Can't recolor a Pokemon that doesn't have a shiny {0}.".format(asset_type))
            return

        base_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, True)
        cur_recolor_img = SpriteUtils.getLinkImg(base_link)
        # auto-generate the shiny recolor image, in file form
        shiny_arr = [self.config.path, asset_type] + shiny_idx
        shiny_path = os.path.join(*shiny_arr)
        auto_recolor_img, content = SpriteUtils.autoRecolor(cur_recolor_img, cur_recolor_img, shiny_path, asset_type)
        # post it as a staged submission
        return_name = "{0}-{1}{2}".format(asset_type + "_recolor", "-".join(shiny_idx), ".png")

        auto_recolor_file = io.BytesIO()
        auto_recolor_img.save(auto_recolor_file, format='PNG')
        auto_recolor_file.seek(0)

        title = SpriteUtils.getIdxName(self.tracker, full_idx)

        send_files = [discord.File(auto_recolor_file, return_name)]
        await msg.channel.send("{0} {1}\n{2}".format(msg.author.mention, " ".join(title), content),
                                     files=send_files)


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
                elif not recolor:
                    mention = chosen_node.__dict__[asset_type + "_credit"]
                    if mention in self.names:
                        response += "\nLatest Author: {0} `{1}` `{2}`".format(self.names[mention].name, mention, self.names[mention].contact)
                    else:
                        response += "\nLatest Author: `{0}`".format(mention)
                if recolor:
                    response += "\n [Recolor this {0} to its shiny palette and submit it.]".format(asset_type)
                chosen_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, recolor)
                response += "\n" + chosen_link

            next_phase = chosen_node.__dict__[asset_type + "_complete"] + 1
            if str(next_phase) in chosen_node.__dict__[asset_type + "_bounty"]:
                bounty = chosen_node.__dict__[asset_type + "_bounty"][str(next_phase)]
                if bounty > 0:
                    response += "\n This {0} has a bounty of **{1}GP**, paid out when it becomes {2}".format(asset_type, bounty, PHASES[next_phase].title())
            if chosen_node.modreward and chosen_node.__dict__[asset_type + "_complete"] == SpriteUtils.PHASE_INCOMPLETE:
                response += "\n The reward for this {0} will be decided by approvers.".format(asset_type)
        else:
            response += " does not need a {0}.".format(asset_type)

        await msg.channel.send(response)


    async def getCredit(self, msg, name_args, asset_type):
        # compute answer from current status
        if len(name_args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [SpriteUtils.sanitizeName(i) for i in name_args]
        full_idx = SpriteUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = SpriteUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        credit_lines = self.retrieveCreditFile(full_idx, chosen_node, asset_type)
        if credit_lines is None:
            await msg.channel.send(msg.author.mention + " No credit found.")

        response = msg.author.mention + " "
        status = self.getStatusEmoji(chosen_node, asset_type)
        response += "Full credit for {0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

        credit_str = "```"
        too_long = False
        for credit_line in credit_lines:
            if len(credit_str) + len(credit_line) < 1950:
                credit_str += '\n' + credit_line
            else:
                too_long = True
                break
        credit_str += "```"

        if too_long:
            file_data = io.StringIO()
            file_data.write(credit_str)
            await msg.channel.send(response, file=discord.File(file_data, 'credits.txt'))
        else:
            await msg.channel.send(response + credit_str)


    async def getProfile(self, msg):
        msg_mention = "<@!{0}>".format(msg.author.id)
        if msg_mention in self.names:
            await msg.channel.send(msg_mention + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[msg_mention].name, self.names[msg_mention].contact))
            return
        await msg.channel.send(msg_mention + " No profile. Set it with `!register <Name> <Contact>`!")

    async def getAbsentProfiles(self, msg):
        total_names = ["Absentee profiles:"]
        msg_ids = []
        for name in self.names:
            if not name.startswith("<@!"):
                total_names.append(name + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[name].name, self.names[name].contact))
        await self.sendInfoPosts(msg.channel, total_names, msg_ids, 0)

    async def setProfile(self, msg, args):
        msg_mention = "<@!{0}>".format(msg.author.id)

        if len(args) == 1:
            new_credit = SpriteUtils.CreditEntry(args[0], "")
        elif len(args) == 2:
            new_credit = SpriteUtils.CreditEntry(args[0], args[1])
        elif len(args) == 3:
            if not await self.isAuthorized(msg.author, msg.guild):
                await msg.channel.send(msg.author.mention + " Not authorized to create absent registration.")
                return
            msg_mention = args[0].upper()
            new_credit = SpriteUtils.CreditEntry(args[1], args[2])
        else:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        if msg_mention in self.names:
            new_credit.sprites = self.names[msg_mention].sprites
            new_credit.portraits = self.names[msg_mention].portraits
        self.names[msg_mention] = new_credit
        self.saveNames()

        await msg.channel.send(msg_mention + " registered profile:\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[msg_mention].name, self.names[msg_mention].contact))

    async def deleteProfile(self, msg, args):
        msg_mention = "<@!{0}>".format(msg.author.id)

        if len(args) == 0:
            pass
        elif len(args) == 1:
            if not await self.isAuthorized(msg.author, msg.guild):
                await msg.channel.send(msg.author.mention + " Not authorized to delete absent registration.")
                return
            msg_mention = args[0].upper()
        else:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        if msg_mention not in self.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(msg_mention))
            return



        if self.names[msg_mention].sprites or self.names[msg_mention].portraits:
            await msg.channel.send(msg.author.mention + " {0} was not deleted because it was credited. Details have been wiped instead.".format(msg_mention))
            new_credit = SpriteUtils.CreditEntry("", "")
            new_credit.sprites = self.names[msg_mention].sprites
            new_credit.portraits = self.names[msg_mention].portraits
            self.names[msg_mention] = new_credit
        else:
            del self.names[msg_mention]
            await msg.channel.send(msg.author.mention + " {0} was deleted.".format(msg_mention))
        self.saveNames()


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


        user = await client.fetch_user(self.config.root)
        if msg.author == user:
            with open(TRACKER_FILE_PATH, 'rb') as file_data:
                await user.send(file=discord.File(file_data, TRACKER_FILE_PATH))

        credits = "Credit:"
        for sender in users:
            if sender != "":
                credits += "\n<@!" + sender + "> : " + str(users[sender])
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

        new_server = BotServer()
        new_server.info = info_ch.id
        new_server.chat = bot_ch.id
        new_server.submit = submit_ch.id
        new_server.approval = reviewer_role.id
        self.config.servers[str(init_guild.id)] = new_server

        self.saveConfig()
        await msg.channel.send(msg.author.mention + " Initialized bot to this server!")

    async def rescan(self, msg):
        #SpriteUtils.iterateTracker(self.tracker, self.markPortraitFull, [])
        #self.changed = True
        #self.saveTracker()
        await msg.channel.send(msg.author.mention + " Rescan complete.")

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

            canon = True
            if form_name.startswith("Alternate"):
                canon = False
            if form_name.startswith("Altcolor"):
                canon = False
            if form_name.startswith("Beta"):
                canon = False
            if species_name == "Missingno_":
                canon = False

            count = len(species_dict.subgroups)
            new_count = "{:04d}".format(count)
            species_dict.subgroups[new_count] = SpriteUtils.createFormNode(form_name, canon)

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


    async def modSpeciesForm(self, msg, args):
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
            species_dict.modreward = not species_dict.modreward

            if species_dict.modreward:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1}'s rewards will be decided by approvers.".format(int(species_idx), species_name))
            else:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1}'s rewards will be given automatically.".format(int(species_idx), species_name))
        else:

            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            form_dict = species_dict.subgroups[form_idx]
            form_dict.modreward = not form_dict.modreward

            if form_dict.modreward:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} {2}'s rewards will be decided by approvers.".format(int(species_idx), species_name, form_name))
            else:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} {2}'s rewards will be given automatically.".format(int(species_idx), species_name, form_name))

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
            # check against count
            if int(species_idx) != len(self.tracker) - 1:
                await msg.channel.send(msg.author.mention + " Can only delete the last species!")
                return

            # check against data population
            if SpriteUtils.isDataPopulated(species_dict) and msg.author.id != self.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return


            del self.tracker[species_idx]
            SpriteUtils.deleteData(os.path.join(self.config.path, 'sprite', species_idx))
            SpriteUtils.deleteData(os.path.join(self.config.path, 'portrait', species_idx))
            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1}!".format(int(species_idx), species_name))
        else:

            form_name = SpriteUtils.sanitizeName(args[1])
            form_idx = SpriteUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against count
            if int(form_idx) != len(species_dict.subgroups) - 1:
                await msg.channel.send(msg.author.mention + " Can only delete the last form!")
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if SpriteUtils.isDataPopulated(form_dict) and msg.author.id != self.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            del species_dict.subgroups[form_idx]
            SpriteUtils.deleteData(os.path.join(self.config.path, 'sprite', species_idx, form_idx))
            SpriteUtils.deleteData(os.path.join(self.config.path, 'portrait', species_idx, form_idx))
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

    async def help(self, msg, args):
        if len(args) == 0:
            return_msg = "**Commands**\n" \
                  "`!sprite` - Get the Pokemon's sprite sheet\n" \
                  "`!portrait` - Get the Pokemon's portrait sheet\n" \
                  "`!recolorsprite` - Get the Pokemon's sprite sheet in a form for easy recoloring\n" \
                  "`!recolorportrait` - Get the Pokemon's portrait sheet in a form for easy recoloring\n" \
                  "`!autocolor` - Generates an automatic recolor of the Pokemon's portrait sheet\n" \
                  "`!listsprite` - List all sprites related to a Pokemon\n" \
                  "`!listportrait` - List all portraits related to a Pokemon\n" \
                  "`!spritebounty` - Place a bounty on a sprite\n" \
                  "`!portraitbounty` - Place a bounty on a portrait\n" \
                  "`!bounties` - View top bounties\n" \
                  "`!register` - Register your profile\n" \
                  "`!profile` - View your profile\n" \
                  "Type `!help` with the name of a command to learn more about it."

        else:
            base_arg = args[0]
            if base_arg == "listsprite":
                return_msg = "**Command Help**\n" \
                             "`!listsprite <Pokemon Name>`\n" \
                             "List all sprites related to a Pokemon.  This includes all forms, gender, and shiny variants.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "**Examples**\n" \
                             "`!listsprite Pikachu`"
            elif base_arg == "sprite":
                return_msg = "**Command Help**\n" \
                             "`!sprite <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Gets the sprite sheet for a Pokemon.  If there is none, it will return a blank template.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!sprite Pikachu`\n" \
                             "`!sprite Pikachu Shiny`\n" \
                             "`!sprite Pikachu Female`\n" \
                             "`!sprite Pikachu Shiny Female`\n" \
                             "`!sprite Shaymin Sky`\n" \
                             "`!sprite Shaymin Sky Shiny`"
            elif base_arg == "recolorsprite":
                return_msg = "**Command Help**\n" \
                             "`!recolorsprite <Pokemon Name> [Form Name] [Gender]`\n" \
                             "Gets the sprite sheet for a Pokemon in a form that is easy to recolor.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!recolorsprite Pikachu`\n" \
                             "`!recolorsprite Pikachu Female`\n" \
                             "`!recolorsprite Shaymin Sky`"
            elif base_arg == "listportrait":
                return_msg = "**Command Help**\n" \
                             "`!listportrait <Pokemon Name>`\n" \
                             "List all portraits related to a Pokemon.  This includes all forms, gender, and shiny variants.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "**Examples**\n" \
                             "`!listportrait Pikachu`"
            elif base_arg == "portrait":
                return_msg = "**Command Help**\n" \
                             "`!portrait <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Gets the portrait sheet for a Pokemon.  If there is none, it will return a blank template.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!portrait Wooper`\n" \
                             "`!portrait Wooper Shiny`\n" \
                             "`!portrait Wooper Female`\n" \
                             "`!portrait Wooper Shiny Female`\n" \
                             "`!portrait Shaymin Sky`\n" \
                             "`!portrait Shaymin Sky Shiny`"
            elif base_arg == "recolorportrait":
                return_msg = "**Command Help**\n" \
                             "`!recolorportrait <Pokemon Name> [Form Name] [Gender]`\n" \
                             "Gets the portrait sheet for a Pokemon in a form that is easy to recolor.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!recolorportrait Pikachu`\n" \
                             "`!recolorportrait Pikachu Female`\n" \
                             "`!recolorportrait Shaymin Sky`"
            elif base_arg == "autocolor":
                return_msg = "**Command Help**\n" \
                             "`!autocolor <Pokemon Name> [Form Name] [Gender]`\n" \
                             "Generates an automatic shiny of a Pokemon's portrait sheet, in recolor form. " \
                             "Meant to be used as a starting point to assist in manual recoloring. " \
                             "Works best on portraits with multiple emotions, where the shiny has only one.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!recolorportrait Pikachu`\n" \
                             "`!recolorportrait Pikachu Female`\n" \
                             "`!recolorportrait Shaymin Sky`"
            elif base_arg == "spritecredit":
                return_msg = "**Command Help**\n" \
                             "`!spritecredit <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Gets the full credits for a Pokemon's sprite sheet.  Credit them all in your romhacks.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!spritecredit Pikachu`\n" \
                             "`!spritecredit Pikachu Shiny`\n" \
                             "`!spritecredit Pikachu Female`\n" \
                             "`!spritecredit Pikachu Shiny Female`\n" \
                             "`!spritecredit Shaymin Sky`\n" \
                             "`!spritecredit Shaymin Sky Shiny`"
            elif base_arg == "portraitcredit":
                return_msg = "**Command Help**\n" \
                             "`!portraitcredit <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Gets the full credits for a Pokemon's portraits.  Credit them all in your romhacks.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "**Examples**\n" \
                             "`!portraitcredit Wooper`\n" \
                             "`!portraitcredit Wooper Shiny`\n" \
                             "`!portraitcredit Wooper Female`\n" \
                             "`!portraitcredit Wooper Shiny Female`\n" \
                             "`!portraitcredit Shaymin Sky`\n" \
                             "`!portraitcredit Shaymin Sky Shiny`"
            elif base_arg == "spritebounty":
                return_msg = "**Command Help**\n" \
                             "`!spritebounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                             "Places a bounty on a missing or incomplete sprite, using your Guild Points.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "`Points` - The number of guild points you wish to donate\n" \
                             "**Examples**\n" \
                             "`!spritebounty Meowstic 1`\n" \
                             "`!spritebounty Meowstic 5`\n" \
                             "`!spritebounty Meowstic Shiny 1`\n" \
                             "`!spritebounty Meowstic Female 1`\n" \
                             "`!spritebounty Meowstic Shiny Female 1`\n" \
                             "`!spritebounty Diancie Mega 1`\n" \
                             "`!spritebounty Diancie Mega Shiny 1`"
            elif base_arg == "portraitbounty":
                return_msg = "**Command Help**\n" \
                             "`!portraitbounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                             "Places a bounty on a missing or incomplete portrait, using your Guild Points.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                             "`Points` - The number of guild points you wish to donate\n" \
                             "**Examples**\n" \
                             "`!portraitbounty Meowstic 1`\n" \
                             "`!portraitbounty Meowstic 5`\n" \
                             "`!portraitbounty Meowstic Shiny 1`\n" \
                             "`!portraitbounty Meowstic Female 1`\n" \
                             "`!portraitbounty Meowstic Shiny Female 1`\n" \
                             "`!portraitbounty Diancie Mega 1`\n" \
                             "`!portraitbounty Diancie Mega Shiny 1`"
            elif base_arg == "bounties":
                return_msg = "**Command Help**\n" \
                             "`!bounties [Type]`\n" \
                             "View the top sprites/portraits that have bounties placed on them.  " \
                             "You will claim a bounty when you successfully submit that sprite/portrait.\n" \
                             "`Type` - [Optional] Can be `sprite` or `portrait`\n" \
                             "**Examples**\n" \
                             "`!bounties`\n" \
                             "`!bounties sprite`"
            elif base_arg == "profile":
                return_msg = "**Command Help**\n" \
                             "`!profile`\n" \
                             "View your profile, containing your current name and contact info."
            elif base_arg == "register":
                return_msg = "**Command Help**\n" \
                             "`!register <Name> <Contact>`\n" \
                             "Registers your name and contact info for crediting purposes.  " \
                             "If you do not register, credits will be given to your discord ID instead.\n" \
                             "`Name` - Your preferred name\n" \
                             "`Contact` - Your preferred contact info; can be email, url, etc.\n" \
                             "**Examples**\n" \
                             "`!register Audino https://github.com/audinowho`"
        await msg.channel.send(msg.author.mention + " {0}".format(return_msg))

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
            args = content[len(COMMAND_PREFIX):].split(' ')
            await sprite_bot.initServer(msg, args[1:])
            return

        # only respond to the proper guilds
        guild_id_str = str(msg.guild.id)
        if guild_id_str not in sprite_bot.config.servers:
            return

        if msg.channel.id == sprite_bot.config.servers[guild_id_str].chat:
            if not content.startswith(COMMAND_PREFIX):
                return
            args = content[len(COMMAND_PREFIX):].split(' ')

            authorized = await sprite_bot.isAuthorized(msg.author, msg.guild)
            base_arg = args[0].lower()
            if base_arg == "help":
                await sprite_bot.help(msg, args[1:])
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
                # authorized commands
            elif base_arg == "autocolor":
                await sprite_bot.tryAutoRecolor(msg, args[1:], "portrait")
            elif base_arg == "add" and authorized:
                await sprite_bot.addSpeciesForm(msg, args[1:])
            elif base_arg == "modreward" and authorized:
                await sprite_bot.modSpeciesForm(msg, args[1:])
            elif base_arg == "rename" and authorized:
                await sprite_bot.renameSpeciesForm(msg, args[1:])
            elif base_arg == "delete" and authorized:
                await sprite_bot.removeSpeciesForm(msg, args[1:])
            elif base_arg == "addgender" and authorized:
                await sprite_bot.addGender(msg, args[1:])
            elif base_arg == "deletegender" and authorized:
                await sprite_bot.removeGender(msg, args[1:])
            elif base_arg == "spritewip" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", SpriteUtils.PHASE_INCOMPLETE)
            elif base_arg == "portraitwip" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", SpriteUtils.PHASE_INCOMPLETE)
            elif base_arg == "spriteexists" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", SpriteUtils.PHASE_EXISTS)
            elif base_arg == "portraitexists" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", SpriteUtils.PHASE_EXISTS)
            elif base_arg == "spritefilled" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "sprite", SpriteUtils.PHASE_FULL)
            elif base_arg == "portraitfilled" and authorized:
                await sprite_bot.completeSlot(msg, args[1:], "portrait", SpriteUtils.PHASE_FULL)
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
            elif base_arg == "update" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.updateBot(msg)
            elif base_arg == "forcepush" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.gitCommit("Tracker update from forced push.")
                await sprite_bot.gitPush()
                msg.channel.send(msg.author.mention + " Changes pushed.")
            elif base_arg in ["gr", "tr"]:
                pass
            else:
                await msg.channel.send(msg.author.mention + " Unknown Command.")

        elif msg.channel.id == sprite_bot.config.servers[guild_id_str].submit:
            changed_tracker = await sprite_bot.pollSubmission(msg)
            if changed_tracker:
                sprite_bot.saveTracker()

    except Exception as e:
        trace = traceback.format_exc()
        user = await client.fetch_user(sprite_bot.config.root)
        await user.send("```"+trace+"```")

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
        trace = traceback.format_exc()
        user = await client.fetch_user(sprite_bot.config.root)
        await user.send("```"+trace+"```")


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
            trace = traceback.format_exc()
            user = await client.fetch_user(sprite_bot.config.root)
            print(trace)
            await user.send("```"+trace+"```")
        await asyncio.sleep(10)

sprite_bot = SpriteBot(scdir, client)

client.loop.create_task(periodic_update_status())

with open(os.path.join(scdir, TOKEN_FILE_PATH)) as token_file:
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
