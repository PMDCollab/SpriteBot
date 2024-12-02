from typing import List


import os
import io

import discord
import traceback
import asyncio
import json
import SpriteUtils
import TrackerUtils
import datetime
import git
import sys
import re
import argparse
import Constants

import MastodonUtils
import BlueSkyUtils

from commands.QueryRessourceStatus import QueryRessourceStatus
from commands.AutoRecolorRessource import AutoRecolorRessource
from commands.ListRessource import ListRessource
from commands.QueryRessourceCredit import QueryRessourceCredit
from commands.DeleteRessourceCredit import DeleteRessourceCredit
from commands.GetProfile import GetProfile

from Constants import PHASES
import psutil

# Housekeeping for login information
TOKEN_FILE_PATH = 'discord_token.txt'
NAME_FILE_PATH = 'credit_names.txt'
CREDIT_FILE_PATH = 'spritebot_credits.txt'
INFO_FILE_PATH = 'README.md'
CONFIG_FILE_PATH = 'config.json'
SPRITE_CONFIG_FILE_PATH = 'sprite_config.json'
TRACKER_FILE_PATH = 'tracker.json'

MESSAGE_BOUNTIES_DISABLED = "Bounties are disabled for this instance of SpriteBot"

scdir = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('--overcolor', nargs='?', const=True, default=False)
parser.add_argument('--lineart', nargs='?', const=True, default=False)
parser.add_argument('--multioffset', nargs='?', const=True, default=False)
parser.add_argument('--noflip', nargs='?', const=True, default=False)
parser.add_argument('--base', nargs='+')
parser.add_argument('--colormod', type=int)
parser.add_argument('--colors', type=int)
parser.add_argument('--author')
parser.add_argument('--addauthor', nargs='?', const=True, default=False)
parser.add_argument('--deleteauthor', nargs='?', const=True, default=False)

class MyClient(discord.Client):
    async def setup_hook(self):
        asyncio.create_task(periodic_update_status())

# The Discord client.
intent = discord.Intents.default()
intent.message_content = True
client = MyClient(intents=intent)

class BotServer:

    def __init__(self, main_dict=None):
        self.info = 0
        self.chat = 0
        self.submit = 0
        self.approval = 0
        self.approval_chat = 0
        self.prefix = ""
        self.info_posts = []

        if main_dict is None:
            return

        for key in main_dict:
            self.__dict__[key] = main_dict[key]

    def getDict(self):
        return self.__dict__

class BotConfig:

    def __init__(self, main_dict=None):
        self.path = ""
        self.root = 0
        self.push = False
        self.bluesky = False
        self.mastodon = False
        self.last_tl_mention = 0
        self.points = 0
        self.error_ch = 0
        self.points_ch = 0
        self.update_ch = 0
        self.update_msg = 0
        self.use_bounties = False
        self.servers = {}

        if main_dict is None:
            return

        for key in main_dict:
            self.__dict__[key] = main_dict[key]

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

        self.writeLog("Pre-Startup Memory: {0}".format(psutil.Process().memory_info().rss))

        with open(os.path.join(self.path, CONFIG_FILE_PATH)) as f:
            self.config = BotConfig(json.load(f))

        if self.config.bluesky:
            self.bsky_api = BlueSkyUtils.init_bluesky(scdir)

        if self.config.mastodon:
            self.tl_api = MastodonUtils.init_mastodon(scdir)

        # init portrait constants
        with open(os.path.join(self.config.path, SPRITE_CONFIG_FILE_PATH)) as f:
            sprite_config = json.load(f)
            Constants.PORTRAIT_SIZE = sprite_config['portrait_size']
            Constants.PORTRAIT_TILE_X = sprite_config['portrait_tile_x']
            Constants.PORTRAIT_TILE_Y = sprite_config['portrait_tile_y']
            Constants.PORTRAIT_SHEET_WIDTH = Constants.PORTRAIT_SIZE * Constants.PORTRAIT_TILE_X
            Constants.PORTRAIT_SHEET_HEIGHT = Constants.PORTRAIT_SIZE * Constants.PORTRAIT_TILE_Y
            if 'portrait_sheet_width' in sprite_config:
                Constants.PORTRAIT_SHEET_WIDTH = sprite_config['portrait_sheet_width']
            if 'portrait_sheet_height' in sprite_config:
                Constants.PORTRAIT_SHEET_HEIGHT = sprite_config['portrait_sheet_height']
            if 'crop_portraits' in sprite_config:
                Constants.CROP_PORTRAITS = sprite_config['crop_portraits']
            Constants.COMPLETION_EMOTIONS = sprite_config['completion_emotions']
            Constants.EMOTIONS = sprite_config['emotions']
            Constants.COMPLETION_ACTIONS = sprite_config['completion_actions']
            Constants.ACTIONS = sprite_config['actions']
            Constants.DUNGEON_ACTIONS = sprite_config['dungeon_actions']
            Constants.STARTER_ACTIONS = sprite_config['starter_actions']
            for key in sprite_config['action_map']:
                Constants.ACTION_MAP[int(key)] = sprite_config['action_map'][key]

        with open(os.path.join(self.config.path, INFO_FILE_PATH)) as f:
            self.info_post = f.read().split("\n\n\n")

        # init repo
        self.repo = git.Repo(self.config.path)
        self.commits = 0
        # tracking data from the content folder
        with open(os.path.join(self.config.path, TRACKER_FILE_PATH)) as f:
            new_tracker = json.load(f)
            self.tracker = { }
            for species_idx in new_tracker:
                self.tracker[species_idx] = TrackerUtils.TrackerNode(new_tracker[species_idx])
        self.names = TrackerUtils.loadNameFile(os.path.join(self.path, NAME_FILE_PATH))
        confirmed_names = TrackerUtils.loadNameFile(os.path.join(self.config.path, NAME_FILE_PATH))
        self.client = client
        self.changed = False

        # update tracker based on last-modify
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker
        #TrackerUtils.fileSystemToJson(over_dict, os.path.join(self.config.path, "sprite"), "sprite", 0)
        #TrackerUtils.fileSystemToJson(over_dict, os.path.join(self.config.path, "portrait"), "portrait", 0)

        # update credits
        #for name in confirmed_names:
        #    if name not in self.names:
        #        self.names[name] = confirmed_names[name]
        #    self.names[name].sprites = True
        #    self.names[name].portraits = True
        #TrackerUtils.updateNameStats(self.names, over_dict)


        #TrackerUtils.printReadyMigrationDests(over_dict.subgroups, over_dict, self.config.path, [], [])
        TrackerUtils.MigrateNode(over_dict.subgroups, over_dict, self.config.path, [], [])

        # save updated tracker back to the file
        self.saveTracker()

        TrackerUtils.MigrateName(over_dict.subgroups, over_dict, self.config.path, [], [])


        # save updated tracker back to the file
        self.saveTracker()
        # save updated credits
        self.saveNames()

        # register commands
        self.commands = [
            QueryRessourceStatus(self, "portrait", False),
            QueryRessourceStatus(self, "portrait", True),
            QueryRessourceStatus(self, "sprite", False),
            QueryRessourceStatus(self, "sprite", True),
            AutoRecolorRessource(self, "portrait"),
            AutoRecolorRessource(self, "sprite"),
            ListRessource(self, "portrait"),
            ListRessource(self, "sprite"),
            QueryRessourceCredit(self, "portrait", False),
            QueryRessourceCredit(self, "sprite", False),
            QueryRessourceCredit(self, "portrait", True),
            QueryRessourceCredit(self, "sprite", True),
            DeleteRessourceCredit(self, "portrait"),
            DeleteRessourceCredit(self, "sprite"),
            GetProfile(self)
        ]
        
        self.writeLog("Startup Memory: {0}".format(psutil.Process().memory_info().rss))

        print("Info Initiated")

    def generateCreditCompilation(self):

        credit_dict = {}
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker
        TrackerUtils.updateCompilationStats(self.names, over_dict, os.path.join(self.config.path, "sprite"), "sprite", [], credit_dict)
        TrackerUtils.updateCompilationStats(self.names, over_dict, os.path.join(self.config.path, "portrait"), "portrait", [], credit_dict)

        TrackerUtils.updateCreditCompilation(os.path.join(self.config.path, CREDIT_FILE_PATH), credit_dict)


    def saveNames(self):
        TrackerUtils.updateNameFile(os.path.join(self.path, NAME_FILE_PATH), self.names, True)
        TrackerUtils.updateNameFile(os.path.join(self.config.path, NAME_FILE_PATH), self.names, False)

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
                    await self.sendError(traceback.format_exc())
            self.commits += 1


    async def gitPush(self):
        if self.config.push and self.commits > 0:
            origin = self.repo.remotes.origin
            origin.push()
            self.commits = 0

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
        await self.client.close()

    async def shutdown(self, msg):
        resp_ch = self.getChatChannel(msg.guild.id)
        await resp_ch.send("Shutting down.")
        self.saveConfig()
        await self.client.close()

    async def checkRestarted(self):
        if self.config.update_ch != 0 and self.config.update_msg != 0:
            msg = await self.client.get_channel(self.config.update_ch).fetch_message(self.config.update_msg)
            await msg.edit(content="Bot updated and restarted.")
            self.config.update_ch = 0
            self.config.update_msg = 0
            self.saveConfig()

    async def sendError(self, trace):
        self.writeLog(trace)
        to_send = await self.client.fetch_user(self.config.root)
        if self.config.error_ch != 0:
            to_send = self.client.get_channel(self.config.error_ch)

        await to_send.send("```" + trace[:1950] + "```")

    def writeLog(self, trace):
        try:
            with open(os.path.join(self.path, "out.log"), 'a+', encoding='utf-8') as txt:
                txt.write(trace+ "\n")
        except:
            pass

    def getChatChannel(self, guild_id):
        chat_id = self.config.servers[str(guild_id)].chat
        return self.client.get_channel(chat_id)

    def getAuthorCol(self, author):
        return str(author.id) + "#" + author.name.replace("\t", "") + "#" + author.discriminator

    def getFormattedCredit(self, name):
        # TODO: make this a regex
        if name.startswith("<@"):
            if name.startswith("<@!"):
                return name
            else:
                return "<@!{0}>".format(name[2:-1])
        return TrackerUtils.sanitizeName(name).upper()

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
            return TrackerUtils.sanitizeCredit(mention)

        return mention
        # if mention in self.names:
        #     return self.names[mention].Name

        # fall back on a quoted mention
        # return "`" + mention + "`"

    def getPostsFromDict(self, include_sprite, include_portrait, include_credit, tracker_dict, posts, indices):
        if tracker_dict.name != "":
            new_titles = TrackerUtils.getIdxName(self.tracker, indices)
            dexnum = int(indices[0])
            name_str = " ".join(new_titles)
            post = ""

            # status
            if include_sprite:
                post += TrackerUtils.getStatusEmoji(tracker_dict, "sprite")
            if include_portrait:
                post += TrackerUtils.getStatusEmoji(tracker_dict, "portrait")
            # name
            post += " `#" + "{:03d}".format(dexnum) + "`: `" + name_str + "` "

            # credits
            if include_credit:
                if include_sprite:
                    post += self.getPostCredit(tracker_dict.sprite_credit.primary)
                    if include_portrait:
                        post += "/"
                if include_portrait:
                    post += self.getPostCredit(tracker_dict.portrait_credit.primary)
            posts.append(post)

        for sub_dict in tracker_dict.subgroups:
            self.getPostsFromDict(include_sprite, include_portrait, include_credit, tracker_dict.subgroups[sub_dict], posts, indices + [sub_dict])



    def getBountiesFromDict(self, asset_type, tracker_dict, entries, indices):
        if tracker_dict.name != "":
            new_titles = TrackerUtils.getIdxName(self.tracker, indices)
            dexnum = int(indices[0])
            name_str = " ".join(new_titles)
            post = asset_type.title() + " of "

            # status
            post += TrackerUtils.getStatusEmoji(tracker_dict, asset_type)
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

        if self.config.servers[guild_id_str].approval == 0:
            return False

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
        to_send = await self.client.fetch_user(self.config.root)
        if self.config.error_ch != 0:
            to_send = self.client.get_channel(self.config.error_ch)

        resp = await to_send.send("", file=discord.File(file_data, filename))
        result_url = resp.attachments[0].url
        return result_url

    async def verifySubmission(self, msg, full_idx, base_idx, asset_type, recolor, msg_args):
        decline_msg = None
        quant_img = None
        diffs = None

        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        chosen_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx)

        if asset_type == "sprite":
            # get the sprite zip and verify its contents
            wan_zip = None
            try:
                if recolor:
                    wan_zip = SpriteUtils.getLinkImg(msg.attachments[0].url)
                else:
                    wan_zip = SpriteUtils.getLinkZipGroup(msg.attachments[0].url)
            except SpriteUtils.SpriteVerifyError as e:
                await self.returnMsgFile(msg, None, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
            except Exception as e:
                await self.returnMsgFile(msg, None, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                raise e

            orig_zip = None
            orig_zip_group = None

            orig_idx = None
            # if it's a shiny, get the original image
            if TrackerUtils.isShinyIdx(full_idx):
                orig_idx = TrackerUtils.createShinyIdx(full_idx, False)
            elif base_idx is not None:
                orig_idx = base_idx

            if orig_idx is not None:
                orig_node = TrackerUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                if orig_node.__dict__[asset_type + "_credit"].primary == "":
                    # this means there's no original portrait to base the recolor off of
                    await self.returnMsgFile(msg, None, msg.author.mention + " Cannot submit a shiny when the original isn't finished.", asset_type)
                    return False, None

                orig_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, recolor)
                try:
                    if recolor:
                        orig_zip = SpriteUtils.getLinkImg(orig_link)
                        orig_group_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, False)
                        orig_zip_group = SpriteUtils.getLinkZipGroup(orig_group_link)
                    else:
                        orig_zip = SpriteUtils.getLinkZipGroup(orig_link)
                except SpriteUtils.SpriteVerifyError as e:
                    await self.returnMsgFile(msg, None, msg.author.mention + " A problem occurred reading original sprite.", asset_type)
                except Exception as e:
                    await self.returnMsgFile(msg, None, msg.author.mention + " A problem occurred reading original sprite.", asset_type)
                    raise e

            # if the file needs to be compared to an original, verify it as a recolor. Otherwise, by itself.
            try:
                diffs = SpriteUtils.verifySpriteLock(chosen_node, chosen_path, orig_zip_group, wan_zip, recolor)
                if TrackerUtils.isShinyIdx(full_idx):
                    SpriteUtils.verifySpriteRecolor(msg_args, orig_zip, wan_zip, recolor, True)
                elif base_idx is not None:
                    SpriteUtils.verifySpriteRecolor(msg_args, orig_zip, wan_zip, recolor, False)
                else:
                    SpriteUtils.verifySprite(msg_args, wan_zip)
            except SpriteUtils.SpriteVerifyError as e:
                decline_msg = e.message
                quant_img = e.preview_img
            except Exception as e:
                await self.returnMsgFile(msg, None, msg.author.mention + " A problem occurred reading submitted sprite.\n{0}".format(str(e)), asset_type)
                raise e
        elif asset_type == "portrait":
            # get the portrait image and verify its contents
            try:
                img = SpriteUtils.getLinkImg(msg.attachments[0].url)
            except SpriteUtils.SpriteVerifyError as e:
                await self.returnMsgFile(msg, None, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                return False, None
            except Exception as e:
                await self.returnMsgFile(msg, None, msg.author.mention + " Submission was in the wrong format.\n{0}".format(str(e)), asset_type)
                raise e

            orig_img = None
            # if it's a shiny, get the original image
            if TrackerUtils.isShinyIdx(full_idx):
                orig_idx = TrackerUtils.createShinyIdx(full_idx, False)
                orig_node = TrackerUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                if orig_node.__dict__[asset_type + "_credit"].primary == "":
                    # this means there's no original portrait to base the recolor off of
                    await self.returnMsgFile(msg, None, msg.author.mention + " Cannot submit a shiny when the original isn't finished.", asset_type)
                    return False, None

                orig_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, recolor)

                try:
                    orig_img = SpriteUtils.getLinkImg(orig_link)
                except SpriteUtils.SpriteVerifyError as e:
                    await self.returnMsgFile(msg, None, msg.author.mention + " A problem occurred reading original portrait.",
                                             asset_type)
                    return False, None
                except Exception as e:
                    await self.returnMsgFile(msg, None, msg.author.mention + " A problem occurred reading original portrait.",
                                             asset_type)
                    raise e

            # if the file needs to be compared to an original, verify it as a recolor. Otherwise, by itself.
            try:
                diffs = SpriteUtils.verifyPortraitLock(chosen_node, chosen_path, img, recolor)
                if TrackerUtils.isShinyIdx(full_idx):
                    SpriteUtils.verifyPortraitRecolor(msg_args, orig_img, img, recolor)
                else:
                    SpriteUtils.verifyPortrait(msg_args, img)
            except SpriteUtils.SpriteVerifyError as e:
                decline_msg = e.message
                quant_img = e.preview_img

        if decline_msg is not None:
            await self.returnMsgFile(msg, None, msg.author.mention + " " + decline_msg, asset_type, quant_img)
            return False, None

        return True, diffs

    async def returnMsgFile(self, msg, thread, msg_body, asset_type, quant_img=None):
        try:
            return_file, return_name = SpriteUtils.getLinkFile(msg.attachments[0].url, asset_type)
            if thread:
                await self.getChatChannel(msg.guild.id).send(msg_body + "\n" + thread.mention, file=discord.File(return_file, return_name))
                return_file, return_name = SpriteUtils.getLinkFile(msg.attachments[0].url, asset_type)
                await thread.send(msg_body, file=discord.File(return_file, return_name))
            else:
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
            await self.sendError(traceback.format_exc())
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

        await self.postStagedSubmission(msg.channel, msg.content.replace('\n', ' '), "", full_idx, chosen_node, asset_type, author, recolor,
                                        diffs, return_file, return_name, overcolor_img)

        await msg.delete()

    async def postStagedSubmission(self, channel, cmd_str, formatted_content, full_idx, chosen_node, asset_type, author, recolor,
                                   diffs, return_file, return_name, overcolor_img):

        deleting = cmd_str == "--deleteauthor"
        title = TrackerUtils.getIdxName(self.tracker, full_idx)

        return_copy = io.BytesIO()
        return_copy.write(return_file.read())
        return_copy.seek(0)
        return_file.seek(0)
        send_files = [discord.File(return_copy, return_name)]

        if deleting:
            diff_str = "Approvers AND the author in question must approve this. Use \U00002705 to approve."
        elif diffs is not None and len(diffs) > 0:
            diff_str = "Changes: {0}".format(", ".join(diffs))
        else:
            diff_str = "No Changes."

        review_thread = await self.retrieveDiscussion(full_idx, chosen_node, asset_type, channel.guild.id)

        thread_link = ""
        if review_thread:
            thread_link = "\n{0}".format(review_thread.mention)


        add_msg = ""
        if not recolor and asset_type == "sprite":
            preview_img = SpriteUtils.getCombinedZipImg(return_file)
            preview_file = io.BytesIO()
            preview_img.save(preview_file, format='PNG')
            preview_file.seek(0)
            send_files.append(discord.File(preview_file, return_name.replace('.zip', '.png')))
            add_msg += "\nPreview included."

        if overcolor_img is not None:
            reduced_img = None
            if asset_type == "sprite":
                reduced_img = SpriteUtils.simple_quant(overcolor_img, 16)
            elif asset_type == "portrait":
                overpalette = SpriteUtils.getPortraitOverpalette(overcolor_img)
                reduced_img = SpriteUtils.simple_quant_portraits(overcolor_img, overpalette)

            reduced_file = io.BytesIO()
            reduced_img.save(reduced_file, format='PNG')
            reduced_file.seek(0)
            send_files.append(discord.File(reduced_file, return_name.replace('.png', '_reduced.png')))
            add_msg += "\nReduced Color Preview included."

        if chosen_node.__dict__[asset_type + "_credit"].primary != "":
            if recolor or asset_type == "portrait":
                orig_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, recolor)
                add_msg += "\nCurrent Version: {0}".format(orig_link)
        new_msg = await channel.send("{0} {1}\n{2}\n{3}{4}\n{5}".format(author, " ".join(title), cmd_str, diff_str,
                                                                        thread_link, formatted_content + add_msg), files=send_files)

        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 0
        pending_dict[str(new_msg.id)] = new_msg.channel.id

        # react to the message
        await new_msg.add_reaction('\U00002705')
        await new_msg.add_reaction('\U0000274C')

        if review_thread:
            await review_thread.send("New post by {0}: {1}".format(author, new_msg.jump_url))

        self.changed |= change_status


    async def submissionApproved(self, msg, orig_sender, orig_author, approvals):
        sender_info = orig_sender
        if orig_author != orig_sender:
            sender_info = "{0}/{1}".format(orig_sender, orig_author)

        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = TrackerUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(orig_sender + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        chosen_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx)
        review_thread = await self.retrieveDiscussion(full_idx, chosen_node, asset_type, msg.guild.id)


        msg_lines = msg.content.split('\n')
        base_idx = None
        add_author = False
        delete_author = False
        if len(msg_lines) > 1:
            try:
                msg_args = parser.parse_args(msg_lines[1].split())
            except SystemExit:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid arguments used in submission post.\n`{0}`".format(msg.content))
                return
            if msg_args.addauthor:
                add_author = True
            if msg_args.deleteauthor:
                delete_author = True
            if msg_args.base:
                name_seq = [TrackerUtils.sanitizeName(i) for i in msg_args.base]
                base_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
                if base_idx is None:
                    await self.getChatChannel(msg.guild.id).send(msg.author.mention + " No such Pokemon to base this sprite off.")
                    await msg.delete()
                    return

        diffs = []
        if not add_author and not delete_author and len(msg_lines) > 2:
            msg_changes = msg_lines[2]
            if msg_changes.startswith("Changes: "):
                diffs = msg_changes.replace("Changes: ", "").split(", ")
            elif msg_changes != "No Changes.":
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " This submission has invalid changes data. Contact staff.")
                await msg.delete()
                return

        is_shiny = TrackerUtils.isShinyIdx(full_idx)
        shiny_idx = None
        shiny_node = None
        base_recolor_file = None
        if not is_shiny:
            shiny_idx = TrackerUtils.createShinyIdx(full_idx, True)
            shiny_node = TrackerUtils.getNodeFromIdx(self.tracker, shiny_idx, 0)

            # the shiny may be marked as incomplete, so we should check for an author at all
            if shiny_node.__dict__[asset_type+"_credit"].primary != "":
                # get recolor data
                base_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)
                base_recolor_file, _ = SpriteUtils.getLinkFile(base_link, asset_type)

        # get the name of the slot that it was written to
        new_name = TrackerUtils.getIdxName(self.tracker, full_idx)
        new_name_str = " ".join(new_name)

        # change the status of the sprite
        new_revise = "New"
        if add_author:
            new_revise = "Revised Credit"
        elif delete_author:
            new_revise = "Deleted Credit"
        elif chosen_node.__dict__[asset_type+"_credit"].primary != "":
            new_revise = "Revised"

        # save and set the new sprite or portrait
        gen_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx)

        if not add_author and not delete_author:
            if asset_type == "sprite":
                orig_idx = None
                if is_shiny:
                    orig_idx = TrackerUtils.createShinyIdx(full_idx, False)
                elif base_idx is not None:
                    orig_idx = base_idx

                if orig_idx is not None and recolor:
                    orig_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, orig_idx)
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

        orig_node = chosen_node
        if is_shiny:
            orig_idx = TrackerUtils.createShinyIdx(full_idx, False)
            orig_node = TrackerUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

        prev_completion_file = TrackerUtils.getCurrentCompletion(orig_node, chosen_node, asset_type)

        new_credit = True
        cur_credits = []
        if delete_author:
            new_credit = False
            TrackerUtils.deleteCredits(gen_path, orig_author)

            # update the credits and timestamp in the chosen node
            chosen_node.__dict__[asset_type + "_modified"] = str(datetime.datetime.utcnow())

            credit_data = chosen_node.__dict__[asset_type + "_credit"]

            credit_entries = TrackerUtils.getCreditEntries(gen_path)
            if credit_data.primary == orig_author:
                # delete the primary and promote a secondary
                credit_data.primary = credit_entries[0]
            # reload secondary credits and amount
            TrackerUtils.updateCreditFromEntries(credit_data, credit_entries)
        else:
            cur_credits = TrackerUtils.getFileCredits(gen_path)
            for credit in cur_credits:
                if credit.name == orig_author:
                    new_credit = False
                    break

            TrackerUtils.appendCredits(gen_path, orig_author, ",".join(diffs))

            # add to universal names list and save if changed
            if orig_author not in self.names:
                self.names[orig_author] = TrackerUtils.CreditEntry("", "")

            self.names[orig_author].sprites = True
            self.names[orig_author].portraits = True
            self.saveNames()

            # update the credits and timestamp in the chosen node
            chosen_node.__dict__[asset_type + "_modified"] = str(datetime.datetime.utcnow())

            credit_data = chosen_node.__dict__[asset_type + "_credit"]
            if credit_data.primary != orig_author:
                # only update credit name if the new author is different from the primary
                credit_entries = TrackerUtils.getCreditEntries(gen_path)
                if credit_data.primary == "":
                    credit_data.total = len(credit_entries)
                    credit_data.primary = credit_entries[0]
                # reload secondary credits and amount
                TrackerUtils.updateCreditFromEntries(credit_data, credit_entries)

        # update the file cache
        TrackerUtils.updateFiles(chosen_node, gen_path, asset_type)

        current_completion_file = TrackerUtils.getCurrentCompletion(orig_node, chosen_node, asset_type)

        # remove from pending list
        pending_dict = chosen_node.__dict__[asset_type + "_pending"]
        if str(msg.id) in pending_dict:
            del pending_dict[str(msg.id)]

        new_link = ""
        if not add_author and not delete_author:
            # generate a new link
            file_data, ext = SpriteUtils.generateFileData(gen_path, asset_type, False)
            file_data.seek(0)
            file_name = "{0}-{1}{2}".format(asset_type, "-".join(full_idx), ext)

            new_link = await self.generateLink(file_data, file_name)
            chosen_node.__dict__[asset_type+"_link"] = new_link
            chosen_node.__dict__[asset_type+"_recolor_link"] = ""

        mentions = ["<@!"+str(ii)+">" for ii in approvals]
        approve_msg = "{0} {1} approved by {2}: #{3:03d}: {4}".format(new_revise, asset_type, str(mentions), int(full_idx[0]), new_name_str)

        reward_changes = []
        if not add_author and not delete_author:
            if len(diffs) > 0:
                approve_msg += "\nChanges: {0}".format(", ".join(diffs))
            else:
                approve_msg += "\nNo Changes."

            # update completion to correct value
            chosen_node.__dict__[asset_type + "_complete"] = current_completion_file
            if current_completion_file != prev_completion_file:
                approve_msg += "\n{0} is now {1}.".format(asset_type.title(), PHASES[current_completion_file])

            # if this was non-shiny, set the complete flag to false for the shiny
            if not is_shiny:
                if shiny_node.__dict__[asset_type+"_credit"].primary != "":
                    shiny_node.__dict__[asset_type+"_complete"] = TrackerUtils.PHASE_INCOMPLETE
                    approve_msg += "\nNote: Shiny form now marked as {0} due to this change.".format(PHASES[TrackerUtils.PHASE_INCOMPLETE])


            if TrackerUtils.isShinyIdx(full_idx):
                new_author = False
                for credit in cur_credits:
                    if credit.name == orig_author:
                        new_author = True
                        break
                if not new_author:
                    reward_changes.append("{0}sr".format(1))
            else:
                paid_diffs = []
                for diff in diffs:
                    if not TrackerUtils.hasExistingCredits(cur_credits, orig_author, diff) and not SpriteUtils.isCopyOf(gen_path, diff):
                        paid_diffs.append(diff)

                if asset_type == "sprite":
                    dungeon_anims = 0
                    starter_anims = 0
                    other_anims = 0
                    for diff in paid_diffs:
                        if diff in Constants.DUNGEON_ACTIONS:
                            dungeon_anims += 1
                        elif diff in Constants.STARTER_ACTIONS:
                            starter_anims += 1
                        else:
                            other_anims += 1

                    if dungeon_anims > 0:
                        reward_changes.append("{0}da".format(dungeon_anims))
                    if starter_anims > 0:
                        reward_changes.append("{0}sa".format(starter_anims))
                    if other_anims > 0:
                        reward_changes.append("{0}oa".format(other_anims))

                elif asset_type == "portrait":
                    sym_portraits = 0
                    asym_portraits = 0
                    for diff in paid_diffs:
                        if diff.endswith("^"):
                            asym_portraits += 1
                        else:
                            sym_portraits += 1
                    if sym_portraits > 0:
                        reward_changes.append("{0}p".format(sym_portraits))
                    if asym_portraits > 0:
                        reward_changes.append("{0}ap".format(asym_portraits))

            if chosen_node.modreward:
                reward_changes = []
                approve_msg += "\nThe non-bounty GP Reward for this {0} will be handled by the approvers.".format(asset_type)

        # save the tracker
        self.saveTracker()

        update_msg = "{0} {1} #{2:03d}: {3}".format(new_revise, asset_type, int(full_idx[0]), new_name_str)
        # commit the changes
        await self.gitCommit("{0} by {1} {2}".format(update_msg, orig_author, self.names[orig_author].name))

        # post about it
        for server_id in self.config.servers:
            if server_id == str(msg.guild.id):
                await self.getChatChannel(msg.guild.id).send(sender_info + " " + approve_msg + "\n" + review_thread.mention + "\n" + new_link)
                await review_thread.send(sender_info + " " + approve_msg + "\n" + new_link)
            else:
                await self.getChatChannel(int(server_id)).send("{1}: {0}".format(update_msg, msg.guild.name))

        # delete post
        await msg.delete()

        self.changed = True

        if not add_author and not delete_author:

            if self.names[orig_author].name == "" and self.names[orig_author].contact == "" and orig_author.startswith("<@!"):
                await self.getChatChannel(msg.guild.id).send("{0}\nPlease use `!register <your name> <contact info>` to register your name and contact info in the credits (use `!help register` for more info).\nWe recommended using an external contact in case you lose access to your Discord account.".format(orig_author))

            # add bounty
            bounty_points = 0
            result_phase = current_completion_file
            while result_phase > 0:
                if str(result_phase) in chosen_node.__dict__[asset_type + "_bounty"]:
                    bounty_points += chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)]
                    del chosen_node.__dict__[asset_type + "_bounty"][str(result_phase)]
                result_phase -= 1

            if bounty_points > 0:
                reward_changes.append(str(bounty_points))

            if len(reward_changes) > 0 and orig_author.startswith("<@!") and self.config.points_ch != 0:
                orig_author_id = orig_author[3:-1]
                await self.client.get_channel(self.config.points_ch).send("!gr {0} {1} {2}".format(orig_author_id, "+".join(reward_changes), self.config.servers[str(msg.guild.id)].chat))


            if not is_shiny:
                # remove all pending shinies
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
                        await self.sendError(traceback.format_exc())

                # autogenerate the shiny
                if base_recolor_file is not None:
                    # auto-generate the shiny recolor image, in file form
                    shiny_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, shiny_idx)
                    auto_recolor_img, cmd_str, content = SpriteUtils.autoRecolor(base_recolor_file, gen_path, shiny_path, asset_type)

                    # compute the diff
                    auto_diffs = []
                    try:
                        if asset_type == "sprite":
                            orig_idx = TrackerUtils.createShinyIdx(full_idx, False)
                            orig_node = TrackerUtils.getNodeFromIdx(self.tracker, orig_idx, 0)

                            orig_group_link = await self.retrieveLinkMsg(orig_idx, orig_node, asset_type, False)
                            orig_zip_group = SpriteUtils.getLinkZipGroup(orig_group_link)

                            auto_diffs = SpriteUtils.verifySpriteLock(shiny_node, shiny_path, orig_zip_group, auto_recolor_img, True)
                        elif asset_type == "portrait":
                            auto_diffs = SpriteUtils.verifyPortraitLock(shiny_node, shiny_path, auto_recolor_img, True)
                    except Exception as e:
                        return

                    # post it as a staged submission
                    return_name = "{0}-{1}{2}".format(asset_type + "_recolor", "-".join(shiny_idx), ".png")
                    auto_recolor_file = io.BytesIO()
                    auto_recolor_img.save(auto_recolor_file, format='PNG')
                    auto_recolor_file.seek(0)

                    try:
                        msg_args = parser.parse_args(cmd_str.split())
                    except SystemExit:
                        await self.sendError(traceback.format_exc())
                        return

                    overcolor = msg_args.overcolor
                    overcolor_img = None
                    if overcolor:
                        overcolor_img = SpriteUtils.removePalette(auto_recolor_img)

                    await self.postStagedSubmission(msg.channel, cmd_str, content, shiny_idx, shiny_node, asset_type, sender_info,
                                                    True, auto_diffs, auto_recolor_file, return_name, overcolor_img)

            if self.config.mastodon or self.config.bluesky:
                status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
                tl_msg = "{5} #{3:03d}: {4}\n{0} {1} by {2}".format(new_revise,
                                                                    asset_type,
                                                                    self.createCreditAttribution(orig_author, True),
                                                                    int(full_idx[0]), new_name_str, status)

                img_file = SpriteUtils.getSocialMediaImage(new_link, asset_type)
                if self.config.mastodon:
                    try:
                        await MastodonUtils.post_image(self.tl_api, tl_msg, new_name_str, img_file, asset_type)
                    except:
                        await self.sendError("Error sending post!\n{0}".format(traceback.format_exc()))
                if self.config.bluesky:
                    try:
                        await BlueSkyUtils.post_image(self.bsky_api, tl_msg, new_name_str, img_file, asset_type)
                    except:
                        await self.sendError("Error sending post!\n{0}".format(traceback.format_exc()))


    async def submissionDeclined(self, msg, orig_sender, declines):

        file_name = msg.attachments[0].filename
        file_valid, full_idx, asset_type, recolor = TrackerUtils.getStatsFromFilename(file_name)
        if not file_valid:
            await self.getChatChannel(msg.guild.id).send(orig_sender + " " + "Removed unknown file: {0}".format(file_name))
            await msg.delete()
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        review_thread = await self.retrieveDiscussion(full_idx, chosen_node, asset_type, msg.guild.id)

        # change the status of the sprite
        pending_dict = chosen_node.__dict__[asset_type+"_pending"]
        change_status = len(pending_dict) == 1
        if str(msg.id) in pending_dict:
            del pending_dict[str(msg.id)]

        if len(declines) > 0:
            mentions = ["<@!" + str(ii) + ">" for ii in declines]
            await self.returnMsgFile(msg, review_thread, orig_sender + " " + "{0} declined by {1}:".format(asset_type, ', '.join(mentions)), asset_type)
        else:
            await self.returnMsgFile(msg, None,
                                     orig_sender + " " + "{0} declined due to another change."
                                                         "  Please resubmit.".format(asset_type), asset_type)
        self.changed |= change_status

    async def checkAllSubmissions(self):
        # clear all pending submissions; we don't know if they were deleted or not between startups
        for node_idx in self.tracker:
            TrackerUtils.clearSubmissions(self.tracker[node_idx])

        # make sure they are re-added
        for server in self.config.servers:
            ch_id = self.config.servers[server].submit
            if ch_id == 0:
                continue
            msgs = []
            channel = self.client.get_channel(ch_id)
            async for message in channel.history(limit=None):
                msgs.append(message)
            for msg in msgs:
                try:
                    await self.pollSubmission(msg)
                except Exception as e:
                    await self.sendError(traceback.format_exc())
            self.saveTracker()
            self.changed = True

    """
    Returns true if anything changed that would require a tracker save
    """
    async def pollSubmission(self, msg):
        # check for messages in #submissions

        if msg.author.id == self.client.user.id:
            if msg.content == ".":
                return False

            cks = None
            xs = None
            ws = None
            ss = None
            remove_users = []
            for reaction in msg.reactions:
                if reaction.emoji == '\u2705':
                    cks = reaction
                elif reaction.emoji == '\u274C':
                    xs = reaction
                elif reaction.emoji == '\u26A0\uFE0F':
                    ws = reaction
                elif reaction.emoji == '\u2B50':
                    ss = reaction
                else:
                    async for user in reaction.users():
                        if await self.isAuthorized(user, msg.guild):
                            pass
                        else:
                            remove_users.append((reaction, user))

            msg_lines = msg.content.split('\n')
            main_data = msg_lines[0].split()
            sender_data = main_data[0].split("/")
            orig_sender = sender_data[0]
            orig_author = sender_data[-1]
            orig_sender_id = int(orig_sender[3:-1])
            args = msg_lines[1]
            deleting = args == "--deleteauthor"

            auto = False
            warn = False
            consent = False
            approve = []
            decline = []


            if ss:
                async for user in ss.users():
                    if user.id == self.config.root:
                        auto = True
                        approve.append(user.id)
                    else:
                        remove_users.append((ss, user))

            if cks:
                async for user in cks.users():
                    user_author_id = "<@!{0}>".format(user.id)
                    if deleting and user_author_id == orig_author:
                        approve.append(user.id)
                        consent = True
                    elif await self.isAuthorized(user, msg.guild):
                        approve.append(user.id)
                    elif user.id != self.client.user.id:
                        remove_users.append((cks, user))

            if ws:
                async for user in ws.users():
                    if await self.isAuthorized(user, msg.guild):
                        warn = True
                    else:
                        remove_users.append((ws, user))

            if xs:
                async for user in xs.users():
                    user_author_id = "<@!{0}>".format(user.id)
                    if await self.isAuthorized(user, msg.guild) or user.id == orig_sender_id:
                        decline.append(user.id)
                    elif deleting and user_author_id == orig_author:
                        decline.append(user.id)
                    elif user.id != self.client.user.id:
                        remove_users.append((xs, user))

            file_name = msg.attachments[0].filename
            name_valid, full_idx, asset_type, recolor = TrackerUtils.getStatsFromFilename(file_name)

            if len(decline) > 0:
                await self.submissionDeclined(msg, orig_sender, decline)
                return True
            elif auto:
                await self.submissionApproved(msg, orig_sender, orig_author, approve)
                return False
            elif not warn:
                if deleting:
                    if len(approve) >= 3 and consent:
                        await self.submissionApproved(msg, orig_sender, orig_author, approve)
                        return False
                elif asset_type == "sprite" and len(approve) >= 3:
                    await self.submissionApproved(msg, orig_sender, orig_author, approve)
                    return False
                elif asset_type == "portrait" and len(approve) >= 2:
                    await self.submissionApproved(msg, orig_sender, orig_author, approve)
                    return False

            chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
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
            name_valid, full_idx, asset_type, recolor = TrackerUtils.getStatsFromFilename(file_name)

            chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
            # if the node cant be found, the filepath is invalid
            if chosen_node is None:
                name_valid = False
            elif not chosen_node.__dict__[asset_type + "_required"]:
                # if the node can be found, but it's not required, it's also invalid
                name_valid = False

            if not name_valid:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid filename {0}. Do not change the filename from the original name given by !portrait or !sprite .".format(file_name))
                return False

            try:
                msg_args = parser.parse_args(msg.content.split())
            except SystemExit:
                await msg.delete()
                await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Invalid arguments used in submission post.\n`{0}`".format(msg.content))
                return False

            base_idx = None
            if msg_args.base:
                name_seq = [TrackerUtils.sanitizeName(i) for i in msg_args.base]
                base_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
                if base_idx is None:
                    await msg.delete()
                    await self.getChatChannel(msg.guild.id).send(msg.author.mention + " No such Pokemon to base this sprite off.")
                    return
                if TrackerUtils.isTrackerIdxEqual(base_idx, full_idx):
                    await msg.delete()
                    await self.getChatChannel(msg.guild.id).send(msg.author.mention + " Cannot base on the same Pokemon.")
                    return

            overcolor = msg_args.overcolor
            # at this point, we confirm the file name is valid, now check the contents
            verified, diffs = await self.verifySubmission(msg, full_idx, base_idx, asset_type, recolor, msg_args)
            if not verified:
                return False

            # after other args have been consumed, check for one more arg: if the submission was made in someone else's stead
            author = "<@!{0}>".format(msg.author.id)
            if msg_args.author is not None:
                sanitized_author = self.getFormattedCredit(msg_args.author)
                decline_msg = None
                if sanitized_author not in self.names:
                    decline_msg = "{0} does not have a profile.".format(sanitized_author)

                if decline_msg is not None:
                    await self.returnMsgFile(msg, None, msg.author.mention + " " + decline_msg, asset_type)
                    return False

                author = "{0}/{1}".format(author, sanitized_author)

            await self.stageSubmission(msg, full_idx, chosen_node, asset_type, author, recolor, diffs, overcolor)
            return True


    async def sendInfoPosts(self, channel, posts: List[str], msg_ids, msg_idx):
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

        posts: List[str] = []
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker
        self.getPostsFromDict(True, True, True, over_dict, posts, [])

        msgs_used = 0
        msgs_used, changed = await self.sendInfoPosts(channel, posts, msg_ids, msgs_used)
        changed_list |= changed
        msgs_used, changed = await self.sendInfoPosts(channel, self.info_post, msg_ids, msgs_used)
        changed_list |= changed

        # remove unneeded posts from the list
        while msgs_used < len(msg_ids):
            msg = await channel.fetch_message(msg_ids[-1])
            await msg.delete()
            msg_ids.pop()
            changed_list = True

        if changed_list:
            self.saveConfig()

        # remove unneeded posts from the channel
        prevMsg = None
        total = 0
        msgs = []
        while True:
            count = 0
            ended = False
            async for message in channel.history(limit=100, before=prevMsg):
                prevMsg = message
                count += 1
                if message.id in msg_ids:
                    continue
                if message.author.id != self.client.user.id:
                    continue
                msgs.append(message)

            total += count
            if count == 0:
                ended = True
            #print("Scanned " + str(total))
            if ended:
                #print("Scanned back to " + str(prevMsg.created_at))
                break
            #print("Continuing...")

        # deletion
        for ii in range(0, len(msgs)):
            message = msgs[ii]
            try:
                await message.delete()
            except:
                await self.sendError("Error deleting {0}!\n{1}".format(message.id, traceback.format_exc()))

    async def updateThreads(self, server_id):
        server = self.config.servers[server_id]
        if int(server.submit) == 0:
            return

        channel = self.client.get_channel(int(server.submit))
        if channel is None:
            raise Exception("No submission channel found for {0}!".format(server_id))

        for thread in channel.threads:
            if thread.archived:
                continue
            name_args = thread.name.split()
            asset_name = name_args[0].lower()
            name_seq = [TrackerUtils.sanitizeName(i) for i in name_args[1:]]
            full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
            if full_idx is None:
                # this thread should not exist!  But we'll just set it to archived?
                await thread.edit(archived=True)
                continue

            chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
            if chosen_node is None:
                await self.sendError("Could not get node when updating thread {0}!".format(thread.name))
                continue
            pending_dict = chosen_node.__dict__[asset_name+"_pending"]

            if len(pending_dict) > 0:
                # no need to archive, the submission is active
                continue

            # so this is an inactive submission.
            try:
                last_msg = await thread.fetch_message(thread.last_message_id)
                # subtract one day from current time and if the thread is older than one day, archive it
                time_before = datetime.datetime.now(last_msg.created_at.tzinfo) - datetime.timedelta(days=1)
                if last_msg.created_at < time_before:
                    await thread.edit(archived=True)
            except discord.errors.NotFound as err:
                pass
            except:
                await self.sendError("Error fetching message for thread {0}!\n{1}".format(thread.name, traceback.format_exc()))


    async def retrieveDiscussion(self, full_idx, chosen_node, asset_type, guild_id):

        guild_id_str = str(guild_id)

        req_base = asset_type
        req_link = req_base + "_talk"

        if guild_id_str in chosen_node.__dict__[req_link]:
            talk_id = chosen_node.__dict__[req_link][guild_id_str]
            guild = self.client.get_guild(guild_id)
            try:
                thread = await guild.fetch_channel(talk_id)

                if thread.parent_id != self.config.servers[str(guild_id_str)].submit:
                    # old thread, delete and fall to no thread
                    await thread.delete()
                else:
                    return thread
            except:
                # nonexistent thread, fall to no thread
                await self.sendError(traceback.format_exc())

        approval_id = self.config.servers[str(guild_id_str)].submit
        approval_ch = self.client.get_channel(approval_id)

        # no thread
        new_name = TrackerUtils.getIdxName(self.tracker, full_idx)
        new_name.insert(0, asset_type)
        new_name_str = " ".join(new_name)

        msg = await approval_ch.send(".")
        thread = await msg.create_thread(name=new_name_str)
        await thread.send("Discussion: {0}".format(new_name_str))
        await msg.delete()
        chosen_node.__dict__[req_link][guild_id_str] = thread.id
        return thread


    async def retrieveLinkMsg(self, full_idx, chosen_node, asset_type, recolor):
        # build the needed field
        req_base = asset_type
        if recolor:
            req_base += "_recolor"
        req_link = req_base + "_link"

        # if we already have a link, send that link
        if chosen_node.__dict__[req_link] != "":
            old_link = chosen_node.__dict__[req_link]
            # TODO: we might be able to get a new link by returning to the message used?
            if SpriteUtils.testLinkFile(old_link):
                return old_link

        # otherwise, generate that link
        # if there is no data in the folder (aka no credit)
        # create a dummy template using missingno
        gen_path = os.path.join(self.config.path, asset_type, "0000")
        # otherwise, use the provided path
        if chosen_node.__dict__[asset_type + "_credit"].primary != "":
            gen_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx)

        if recolor:
            target_idx = TrackerUtils.createShinyIdx(full_idx, True)
        else:
            target_idx = full_idx

        locked = []
        for part in chosen_node.__dict__[asset_type + "_files"]:
            if chosen_node.__dict__[asset_type + "_files"][part]:
                locked.append(part)
        file_data, ext = SpriteUtils.generateFileData(gen_path, asset_type, recolor, locked)
        file_data.seek(0)
        file_name = "{0}-{1}{2}".format(req_base, "-".join(target_idx), ext)

        new_link = await self.generateLink(file_data, file_name)
        chosen_node.__dict__[req_link] = new_link
        self.saveTracker()
        return new_link


    async def completeSlot(self, msg, name_args, asset_type, phase):
        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        phase_str = PHASES[phase]

        # if the node has no credit, fail
        if chosen_node.__dict__[asset_type + "_credit"].primary == "" and phase > TrackerUtils.PHASE_INCOMPLETE:
            status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
            await msg.channel.send(msg.author.mention +
                                   " {0} #{1:03d}: {2} has no data and cannot be marked {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))
            return

        # set to complete
        chosen_node.__dict__[asset_type + "_complete"] = phase

        status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} marked as {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))

        self.saveTracker()
        self.changed = True


    async def checkMoveLock(self, full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, asset_type):

        chosen_path_from = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx_from)
        chosen_img_to_link = await self.retrieveLinkMsg(full_idx_to, chosen_node_to, asset_type, False)
        if asset_type == "sprite":
            chosen_zip_to = SpriteUtils.getLinkZipGroup(chosen_img_to_link)
            SpriteUtils.verifySpriteLock(chosen_node_from, chosen_path_from, None, chosen_zip_to, False)
        elif asset_type == "portrait":
            chosen_img_to = SpriteUtils.getLinkImg(chosen_img_to_link)
            SpriteUtils.verifyPortraitLock(chosen_node_from, chosen_path_from, chosen_img_to, False)

    async def moveSlotRecursive(self, msg, name_args):
        try:
            delim_idx = name_args.index("->")
        except:
            await msg.channel.send(msg.author.mention + " Command needs to separate the source and destination with `->`.")
            return

        name_args_from = name_args[:delim_idx]
        name_args_to = name_args[delim_idx+1:]

        name_seq_from = [TrackerUtils.sanitizeName(i) for i in name_args_from]
        full_idx_from = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_from, 0)
        if full_idx_from is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as source.")
            return
        if len(full_idx_from) > 2:
            await msg.channel.send(msg.author.mention + " Can move only species or form. Source specified more than that.")
            return

        name_seq_to = [TrackerUtils.sanitizeName(i) for i in name_args_to]
        full_idx_to = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_to, 0)
        if full_idx_to is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as destination.")
            return
        if len(full_idx_to) > 2:
            await msg.channel.send(msg.author.mention + " Can move only species or form. Destination specified more than that.")
            return

        chosen_node_from = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_from, 0)
        chosen_node_to = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_to, 0)

        if chosen_node_from == chosen_node_to:
            await msg.channel.send(msg.author.mention + " Cannot move to the same location.")
            return

        explicit_idx_from = full_idx_from.copy()
        if len(explicit_idx_from) < 2:
            explicit_idx_from.append("0000")
        explicit_idx_to = full_idx_to.copy()
        if len(explicit_idx_to) < 2:
            explicit_idx_to.append("0000")

        explicit_node_from = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_from, 0)
        explicit_node_to = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_to, 0)

        # check the main nodes
        try:
            await self.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, "sprite")
            await self.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, "portrait")
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        try:
            await self.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, "sprite")
            await self.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, "portrait")
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move the locked Pokemon specified as destination:\n{0}".format(e.message))
            return

        # check the subnodes
        for sub_idx in explicit_node_from.subgroups:
            sub_node = explicit_node_from.subgroups[sub_idx]
            if TrackerUtils.hasLock(sub_node, "sprite", True) or TrackerUtils.hasLock(sub_node, "portrait", True):
                await msg.channel.send(msg.author.mention + " Cannot move the locked subgroup specified as source.")
                return
        for sub_idx in explicit_node_to.subgroups:
            sub_node = explicit_node_to.subgroups[sub_idx]
            if TrackerUtils.hasLock(sub_node, "sprite", True) or TrackerUtils.hasLock(sub_node, "portrait", True):
                await msg.channel.send(msg.author.mention + " Cannot move the locked subgroup specified as destination.")
                return

        # clear caches
        TrackerUtils.clearCache(chosen_node_from, True)
        TrackerUtils.clearCache(chosen_node_to, True)

        # perform the swap
        TrackerUtils.swapFolderPaths(self.config.path, self.tracker, "sprite", full_idx_from, full_idx_to)
        TrackerUtils.swapFolderPaths(self.config.path, self.tracker, "portrait", full_idx_from, full_idx_to)
        TrackerUtils.swapNodeMiscFeatures(chosen_node_from, chosen_node_to)

        # then, swap the subnodes
        TrackerUtils.swapAllSubNodes(self.config.path, self.tracker, explicit_idx_from, explicit_idx_to)

        await msg.channel.send(msg.author.mention + " Swapped {0} with {1}.".format(" ".join(name_seq_from), " ".join(name_seq_to)))
        # if the source is empty in sprite and portrait, and its subunits are empty in sprite and portrait
        # remind to delete
        if not TrackerUtils.isDataPopulated(chosen_node_from):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_to)))
        if not TrackerUtils.isDataPopulated(chosen_node_to):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_from)))

        self.saveTracker()
        self.changed = True

        await self.gitCommit("Swapped {0} with {1} recursively".format(" ".join(name_seq_from), " ".join(name_seq_to)))


    async def replaceSlot(self, msg, name_args, asset_type):
        try:
            delim_idx = name_args.index("->")
        except:
            await msg.channel.send(msg.author.mention + " Command needs to separate the source and destination with `->`.")
            return

        name_args_from = name_args[:delim_idx]
        name_args_to = name_args[delim_idx+1:]

        name_seq_from = [TrackerUtils.sanitizeName(i) for i in name_args_from]
        full_idx_from = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_from, 0)
        if full_idx_from is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as source.")
            return

        name_seq_to = [TrackerUtils.sanitizeName(i) for i in name_args_to]
        full_idx_to = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_to, 0)
        if full_idx_to is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as destination.")
            return

        chosen_node_from = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_from, 0)
        chosen_node_to = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_to, 0)

        if chosen_node_from == chosen_node_to:
            await msg.channel.send(msg.author.mention + " Cannot move to the same location.")
            return

        if not chosen_node_from.__dict__[asset_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when source {0} is unneeded.".format(asset_type))
            return
        if not chosen_node_to.__dict__[asset_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when destination {0} is unneeded.".format(asset_type))
            return

        try:
            await self.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, asset_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move out the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        try:
            await self.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, asset_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot replace the locked Pokemon specified as destination:\n{0}".format(e.message))
            return

        # clear caches
        TrackerUtils.clearCache(chosen_node_from, True)
        TrackerUtils.clearCache(chosen_node_to, True)

        TrackerUtils.replaceFolderPaths(self.config.path, self.tracker, asset_type, full_idx_from, full_idx_to)

        await msg.channel.send(msg.author.mention + " Replaced {0} with {1}.".format(" ".join(name_seq_to), " ".join(name_seq_from)))
        # if the source is empty in sprite and portrait, and its subunits are empty in sprite and portrait
        # remind to delete
        await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_from)))

        self.saveTracker()
        self.changed = True

        await self.gitCommit("Replaced {0} with {1}".format(" ".join(name_seq_to), " ".join(name_seq_from)))

    async def moveSlot(self, msg, name_args, asset_type):
        try:
            delim_idx = name_args.index("->")
        except:
            await msg.channel.send(msg.author.mention + " Command needs to separate the source and destination with `->`.")
            return

        name_args_from = name_args[:delim_idx]
        name_args_to = name_args[delim_idx+1:]

        name_seq_from = [TrackerUtils.sanitizeName(i) for i in name_args_from]
        full_idx_from = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_from, 0)
        if full_idx_from is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as source.")
            return

        name_seq_to = [TrackerUtils.sanitizeName(i) for i in name_args_to]
        full_idx_to = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq_to, 0)
        if full_idx_to is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as destination.")
            return

        chosen_node_from = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_from, 0)
        chosen_node_to = TrackerUtils.getNodeFromIdx(self.tracker, full_idx_to, 0)

        if chosen_node_from == chosen_node_to:
            await msg.channel.send(msg.author.mention + " Cannot move to the same location.")
            return

        if not chosen_node_from.__dict__[asset_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when source {0} is unneeded.".format(asset_type))
            return
        if not chosen_node_to.__dict__[asset_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when destination {0} is unneeded.".format(asset_type))
            return

        try:
            await self.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, asset_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        try:
            await self.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, asset_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move the locked Pokemon specified as destination:\n{0}".format(e.message))
            return

        # clear caches
        TrackerUtils.clearCache(chosen_node_from, True)
        TrackerUtils.clearCache(chosen_node_to, True)

        TrackerUtils.swapFolderPaths(self.config.path, self.tracker, asset_type, full_idx_from, full_idx_to)

        await msg.channel.send(msg.author.mention + " Swapped {0} with {1}.".format(" ".join(name_seq_from), " ".join(name_seq_to)))
        # if the source is empty in sprite and portrait, and its subunits are empty in sprite and portrait
        # remind to delete
        if not TrackerUtils.isDataPopulated(chosen_node_from):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_from)))
        if not TrackerUtils.isDataPopulated(chosen_node_to):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_to)))

        self.saveTracker()
        self.changed = True

        await self.gitCommit("Swapped {0} with {1}".format(" ".join(name_seq_from), " ".join(name_seq_to)))

    async def placeBounty(self, msg, name_args, asset_type):
        if not self.config.use_bounties:
            await msg.channel.send(msg.author.mention + " " + MESSAGE_BOUNTIES_DISABLED)
            return

        try:
            amt = int(name_args[-1])
        except Exception as e:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon and an amount.")
            return

        if amt <= 0:
            await msg.channel.send(msg.author.mention + " Specify an amount above 0.")
            return

        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args[:-1]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
        if chosen_node.__dict__[asset_type + "_complete"] >= TrackerUtils.PHASE_FULL:
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

    async def setCanon(self, msg, name_args, canon_state):

        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        TrackerUtils.setCanon(chosen_node, canon_state)

        lock_str = "non-"
        if canon_state:
            lock_str = ""
        # set to complete
        await msg.channel.send(msg.author.mention + " {0} is now {1}canon.".format(" ".join(name_seq), lock_str))

        self.saveTracker()
        self.changed = True


    async def promote(self, msg, name_args):

        if not self.config.mastodon and not self.config.bluesky:
            await msg.channel.send(msg.author.mention + " Social Media posting is disabled.")
            return

        asset_type = "sprite"

        file_name = name_args[-1]
        has_file_name = False
        for action in Constants.ACTIONS:
            if action.lower() == file_name.lower():
                has_file_name = True
                break

        if has_file_name:
            name_args = name_args[:-1]
        else:
            file_name = None
            asset_type = "portrait"

        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        if asset_type == "sprite":
            for k in chosen_node.__dict__[asset_type + "_files"]:
                if file_name.lower() == k.lower():
                    file_name = k
                    break

            if file_name not in chosen_node.__dict__[asset_type + "_files"]:
                await msg.channel.send(msg.author.mention + " Specify a Pokemon and an existing emotion/animation.")
                return

        credit_data = chosen_node.__dict__[asset_type + "_credit"]
        chosen_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)

        status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
        tl_msg = "{5} #{3:03d}: {4}\n{0} {1} by {2}".format("Showcased",
                                                            asset_type,
                                                            self.createCreditBlock(credit_data, None, True),
                                                            int(full_idx[0]), " ".join(name_seq), status)

        img_file = SpriteUtils.getSocialMediaImage(chosen_link, asset_type, file_name)

        urls = []
        if self.config.mastodon:
            try:
                url = await MastodonUtils.post_image(self.tl_api, tl_msg, " ".join(name_seq), img_file, asset_type)
                urls.append(url)
            except:
                await self.sendError("Error sending post!\n{0}".format(traceback.format_exc()))
        if self.config.bluesky:
            try:
                url = await BlueSkyUtils.post_image(self.bsky_api, tl_msg, " ".join(name_seq), img_file, asset_type)
                urls.append(url)
            except:
                await self.sendError("Error sending post!\n{0}".format(traceback.format_exc()))

        await msg.channel.send(msg.author.mention + " {0}".format("\n".join(urls)))


    async def setLock(self, msg, name_args, asset_type, lock_state):

        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args[:-1]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        file_name = name_args[-1]
        for k in chosen_node.__dict__[asset_type + "_files"]:
            if file_name.lower() == k.lower():
                file_name = k
                break

        if file_name not in chosen_node.__dict__[asset_type + "_files"]:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon and an existing emotion/animation.")
            return
        chosen_node.__dict__[asset_type + "_files"][file_name] = lock_state

        status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)

        lock_str = "unlocked"
        if lock_state:
            lock_str = "locked"
        # set to complete
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} {3} is now {4}.".format(status, int(full_idx[0]), " ".join(name_seq), file_name, lock_str))

        self.saveTracker()
        self.changed = True

    async def listBounties(self, msg, name_args):
        if not self.config.use_bounties:
            await msg.channel.send(msg.author.mention + " " + MESSAGE_BOUNTIES_DISABLED)
            return
        
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
        over_dict = TrackerUtils.initSubNode("", True)
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
        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        TrackerUtils.clearCache(chosen_node, True)

        self.saveTracker()

        await msg.channel.send(msg.author.mention + " Cleared links for #{0:03d}: {1}.".format(int(full_idx[0]), " ".join(name_seq)))

    def createCreditAttribution(self, mention, plainName=False):
        if plainName:
            # "plainName" actually refers to "social-media-ready name"
            # TODO: rename this variable or refactor it as a separate flag
            base_name = "{0}".format(mention)
            if mention in self.names:
                if self.names[mention].name != "":
                    base_name = self.names[mention].name
                if self.names[mention].contact != "":
                    return "{0}: {1}".format(base_name, self.names[mention].contact)
            return base_name
        else:
            base_name = "`{0}`".format(mention)
            if mention in self.names:
                if self.names[mention].name != "":
                    base_name = self.names[mention].name
                if self.names[mention].contact != "":
                    return "{0} `{1}`".format(base_name, self.names[mention].contact)
        return base_name

    """
    Base credit is used in the case of shinies.
    It is the credit of the base sprite that should be added to the shiny credit.
    """
    def createCreditBlock(self, credit, base_credit, plainName=False):
        author_arr = []
        author_arr.append(self.createCreditAttribution(credit.primary, plainName))
        for author in credit.secondary:
            author_arr.append(self.createCreditAttribution(author, plainName))
        if base_credit is not None:
            attr = self.createCreditAttribution(base_credit.primary, plainName)
            if attr not in author_arr:
                author_arr.append(attr)
            for author in credit.secondary:
                attr = self.createCreditAttribution(author, plainName)
                if attr not in author_arr:
                    author_arr.append(attr)

        block = "By: {0}".format(", ".join(author_arr))
        credit_diff = credit.total - len(author_arr)
        if credit_diff > 0:
            block += " +{0} more".format(credit_diff)
        return block

    async def resetCredit(self, msg, name_args, asset_type):
        # compute answer from current status
        if len(name_args) < 2:
            await msg.channel.send(msg.author.mention + " Specify a user ID and Pokemon.")
            return

        wanted_author = self.getFormattedCredit(name_args[0])
        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        if chosen_node.__dict__[asset_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " No credit found.")
            return
        gen_path = TrackerUtils.getDirFromIdx(self.config.path, asset_type, full_idx)

        credit_entries = TrackerUtils.getCreditEntries(gen_path)

        if wanted_author not in credit_entries:
            await msg.channel.send(msg.author.mention + " Could not find ID `{0}` in credits for {1}.".format(wanted_author, asset_type))
            return

        # make the credit array into the most current author by itself
        credit_data = chosen_node.__dict__[asset_type + "_credit"]
        if credit_data.primary == "CHUNSOFT":
            await msg.channel.send(msg.author.mention + " Cannot reset credit for a CHUNSOFT {0}.".format(asset_type))
            return

        credit_data.primary = wanted_author
        TrackerUtils.updateCreditFromEntries(credit_data, credit_entries)

        await msg.channel.send(msg.author.mention + " Credit display has been reset for {0} {1}:\n{2}".format(asset_type, " ".join(name_seq), self.createCreditBlock(credit_data, None)))

        self.saveTracker()
        self.changed = True

    async def addCredit(self, msg, name_args, asset_type):
        # compute answer from current status
        if len(name_args) < 2:
            await msg.channel.send(msg.author.mention + " Specify a user ID and Pokemon.")
            return

        wanted_author = self.getFormattedCredit(name_args[0])
        name_seq = [TrackerUtils.sanitizeName(i) for i in name_args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)

        if chosen_node.__dict__[asset_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " This command only works on filled {0}.".format(asset_type))
            return

        if wanted_author not in self.names:
            await msg.channel.send(msg.author.mention + " No such profile ID.")
            return

        chat_id = self.config.servers[str(msg.guild.id)].submit
        if chat_id == 0:
            await msg.channel.send(msg.author.mention + " This server does not support submissions.")
            return

        submit_channel = self.client.get_channel(chat_id)
        author = "<@!{0}>".format(msg.author.id)

        base_link = await self.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)
        base_file, base_name = SpriteUtils.getLinkData(base_link)

        # stage a post in submissions
        await self.postStagedSubmission(submit_channel, "--addauthor", "", full_idx, chosen_node, asset_type, author + "/" + wanted_author,
                                                False, None, base_file, base_name, None)

    async def getAbsentProfiles(self, msg):
        total_names = ["Absentee profiles:"]
        msg_ids = []
        for name in self.names:
            if not name.startswith("<@!"):
                total_names.append(name + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[name].name, self.names[name].contact))
        await self.sendInfoPosts(msg.channel, total_names, msg_ids, 0)

    async def setProfile(self, msg, args):
        msg_mention = "<@!{0}>".format(msg.author.id)

        if len(args) == 0:
            new_credit = TrackerUtils.CreditEntry("", "")
        elif len(args) == 1:
            new_credit = TrackerUtils.CreditEntry(args[0], "")
        elif len(args) == 2:
            new_credit = TrackerUtils.CreditEntry(args[0], args[1])
        elif len(args) == 3:
            if not await self.isAuthorized(msg.author, msg.guild):
                await msg.channel.send(msg.author.mention + " Not authorized to create absent registration.")
                return
            msg_mention = self.getFormattedCredit(args[0])
            new_credit = TrackerUtils.CreditEntry(args[1], args[2])
        else:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        if msg_mention in self.names:
            new_credit.sprites = self.names[msg_mention].sprites
            new_credit.portraits = self.names[msg_mention].portraits
        self.names[msg_mention] = new_credit
        self.saveNames()

        await msg.channel.send(msg_mention + " registered profile:\nName: \"{0}\"    Contact: \"{1}\"".format(self.names[msg_mention].name, self.names[msg_mention].contact))

    async def transferProfile(self, msg, args):
        if len(args) != 2:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        from_name = self.getFormattedCredit(args[0])
        to_name = self.getFormattedCredit(args[1])
        if from_name.startswith("<@!") or from_name == "CHUNSOFT":
            await msg.channel.send(msg.author.mention + " Only transfers from absent registrations are allowed.")
            return
        if from_name not in self.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(from_name))
            return
        if to_name not in self.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(to_name))
            return

        new_credit = TrackerUtils.CreditEntry(self.names[to_name].name, self.names[to_name].contact)
        new_credit.sprites = self.names[from_name].sprites or self.names[to_name].sprites
        new_credit.portraits = self.names[from_name].portraits or self.names[to_name].portraits
        del self.names[from_name]
        self.names[to_name] = new_credit

        # update tracker based on last-modify
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.tracker

        TrackerUtils.renameFileCredits(os.path.join(self.config.path, "sprite"), from_name, to_name)
        TrackerUtils.renameFileCredits(os.path.join(self.config.path, "portrait"), from_name, to_name)
        TrackerUtils.renameJsonCredits(over_dict, from_name, to_name)

        await msg.channel.send(msg.author.mention + " account {0} deleted and credits moved to {1}.".format(from_name, to_name))

        self.saveTracker()
        self.saveNames()
        self.changed = True

        await self.gitCommit("Moved account {0} to {1}".format(from_name, to_name))

    async def deleteProfile(self, msg, args):
        msg_mention = "<@!{0}>".format(msg.author.id)

        if len(args) == 0:
            await msg.channel.send(msg.author.mention + " WARNING: This command will move your credits into an anonymous profile and be separated from your account. This cannot be undone.\n" \
                                                        "If you wish to proceed, rerun the command with your discord ID and username (with discriminator) as arguments.")
            return
        elif len(args) == 1:
            if not await self.isAuthorized(msg.author, msg.guild):
                await msg.channel.send(msg.author.mention + " Not authorized to delete registration.")
                return
            msg_mention = self.getFormattedCredit(args[0])
        elif len(args) == 2:
            did = str(msg.author.id)
            dname = msg.author.name + "#" + msg.author.discriminator
            if args[0] != did or args[1] != dname:
                await msg.channel.send(msg.author.mention + " Discord ID/Username did not match.")
                return
        else:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        if msg_mention not in self.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(msg_mention))
            return



        if self.names[msg_mention].sprites or self.names[msg_mention].portraits:
            if msg_mention == "<@!{0}>".format(msg.author.id):
                # find a proper anonymous name to transfer to
                anon_num = 0
                new_name = None
                while True:
                    new_name = "ANONYMOUS_{:04d}".format(anon_num)
                    found_name = False
                    for name_credit in self.names:
                        if name_credit.lower() == new_name.lower():
                            found_name = True
                            break
                    if not found_name:
                        break
                    anon_num = anon_num + 1

                if not new_name:
                    raise Exception() # TODO: what is this exception?

                new_credit = TrackerUtils.CreditEntry("", "")
                new_credit.sprites = self.names[msg_mention].sprites
                new_credit.portraits = self.names[msg_mention].portraits
                del self.names[msg_mention]
                self.names[new_name] = new_credit

                # update tracker based on last-modify
                over_dict = TrackerUtils.initSubNode("", True)
                over_dict.subgroups = self.tracker

                TrackerUtils.renameFileCredits(os.path.join(self.config.path, "sprite"), msg_mention, new_name)
                TrackerUtils.renameFileCredits(os.path.join(self.config.path, "portrait"), msg_mention, new_name)
                TrackerUtils.renameJsonCredits(over_dict, msg_mention, new_name)

                await msg.channel.send(msg.author.mention + " account deleted and credits moved to anonymous.")
            else:
                await msg.channel.send(msg.author.mention + " {0} was not deleted because it was credited. Details have been wiped instead.".format(msg_mention))
                new_credit = TrackerUtils.CreditEntry("", "")
                new_credit.sprites = self.names[msg_mention].sprites
                new_credit.portraits = self.names[msg_mention].portraits
                self.names[msg_mention] = new_credit
        else:
            del self.names[msg_mention]
            await msg.channel.send(msg.author.mention + " {0} was deleted.".format(msg_mention))

        self.saveTracker()
        self.saveNames()
        self.changed = True

        await self.gitCommit("Deleted account {0}".format(msg_mention))



    async def initServer(self, msg, args):


        if len(args) == 3:
            if len(msg.channel_mentions) != 2:
                await msg.channel.send(msg.author.mention + " Bad channel args!")
                return

            info_ch = msg.channel_mentions[0]
            bot_ch = msg.channel_mentions[1]
            submit_ch = None
            reviewer_ch = None
            reviewer_role = None

        elif len(args) == 6:
            if msg.author.id != sprite_bot.config.root:
                await msg.channel.send(msg.author.mention + " Bad channel args!")
                return

            if len(msg.channel_mentions) != 4:
                await msg.channel.send(msg.author.mention + " Bad channel args!")
                return

            if len(msg.role_mentions) != 1:
                await msg.channel.send(msg.author.mention + " Bad role args!")
                return

            info_ch = msg.channel_mentions[0]
            bot_ch = msg.channel_mentions[1]
            submit_ch = msg.channel_mentions[2]
            reviewer_ch = msg.channel_mentions[3]
            reviewer_role = msg.role_mentions[0]
        else:
            await msg.channel.send(msg.author.mention + " Args not equal to 3 or 6!")
            return

        prefix = args[0]
        init_guild = msg.guild



        info_perms = info_ch.permissions_for(init_guild.me)
        if not info_perms.send_messages or not info_perms.read_messages:
            await msg.channel.send(msg.author.mention + " Bad channel perms for info!")
            return

        bot_perms = bot_ch.permissions_for(init_guild.me)
        if not bot_perms.send_messages or not bot_perms.read_messages:
            await msg.channel.send(msg.author.mention + " Bad channel perms for chat!")
            return

        if reviewer_ch is not None:
            review_perms = reviewer_ch.permissions_for(init_guild.me)
            if not review_perms.send_messages or not review_perms.read_messages or not review_perms.create_public_threads:
                await msg.channel.send(msg.author.mention + " Bad channel perms for review!")
                return

        if submit_ch is not None:
            submit_perms = submit_ch.permissions_for(init_guild.me)
            if not submit_perms.send_messages or not submit_perms.read_messages or not submit_perms.manage_messages:
                await msg.channel.send(msg.author.mention + " Bad channel perms for submit!")
                return

        new_server = BotServer()
        new_server.prefix = prefix
        new_server.info = info_ch.id
        new_server.chat = bot_ch.id
        if submit_ch is not None:
            new_server.submit = submit_ch.id
            new_server.approval_chat = reviewer_ch.id
            new_server.approval = reviewer_role.id
        else:
            new_server.submit = 0
            new_server.approval_chat = 0
            new_server.approval = 0
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

        species_name = TrackerUtils.sanitizeName(args[0])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
        if len(args) == 1:
            if species_idx is not None:
                await msg.channel.send(msg.author.mention + " {0} already exists!".format(species_name))
                return

            count = len(self.tracker)
            new_idx = "{:04d}".format(count)
            self.tracker[new_idx] = TrackerUtils.createSpeciesNode(species_name)

            await msg.channel.send(msg.author.mention + " Added #{0:03d}: {1}!".format(count, species_name))
        else:
            if species_idx is None:
                await msg.channel.send(msg.author.mention + " {0} doesn't exist! Create it first!".format(species_name))
                return

            form_name = TrackerUtils.sanitizeName(args[1])
            species_dict = self.tracker[species_idx]
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is not None:
                await msg.channel.send(msg.author.mention +
                                       " {2} already exists within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            if form_name == "Shiny" or form_name == "Male" or form_name == "Female":
                await msg.channel.send(msg.author.mention + " Invalid form name!")
                return

            canon = True
            if re.search(r"_?Alternate\d*$", form_name):
                canon = False
            if re.search(r"_?Starter\d*$", form_name):
                canon = False
            if re.search(r"_?Altcolor\d*$", form_name):
                canon = False
            if re.search(r"_?Beta\d*$", form_name):
                canon = False
            if species_name == "Missingno_":
                canon = False

            count = len(species_dict.subgroups)
            new_count = "{:04d}".format(count)
            species_dict.subgroups[new_count] = TrackerUtils.createFormNode(form_name, canon)

            await msg.channel.send(msg.author.mention +
                                   " Added #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.saveTracker()
        self.changed = True

    async def renameSpeciesForm(self, msg, args):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = TrackerUtils.sanitizeName(args[0])
        new_name = TrackerUtils.sanitizeName(args[-1])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]

        if len(args) == 2:
            new_species_idx = TrackerUtils.findSlotIdx(self.tracker, new_name)
            if new_species_idx is not None:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} already exists!".format(int(new_species_idx), new_name))
                return

            species_dict.name = new_name
            await msg.channel.send(msg.author.mention + " Changed #{0:03d}: {1} to {2}!".format(int(species_idx), species_name, new_name))
        else:

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            new_form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, new_name)
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

        species_name = TrackerUtils.sanitizeName(args[0])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
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

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
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

        species_name = TrackerUtils.sanitizeName(args[0])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 1:

            # check against data population
            if TrackerUtils.isDataPopulated(species_dict) and msg.author.id != self.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            TrackerUtils.deleteData(self.tracker, os.path.join(self.config.path, 'sprite'),
                                       os.path.join(self.config.path, 'portrait'), species_idx)

            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1}!".format(int(species_idx), species_name))
        else:

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if TrackerUtils.isDataPopulated(form_dict) and msg.author.id != self.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            TrackerUtils.deleteData(species_dict.subgroups, os.path.join(self.config.path, 'sprite', species_idx),
                                       os.path.join(self.config.path, 'portrait', species_idx), form_idx)

            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.saveTracker()
        self.changed = True

        await self.gitCommit("Removed {0}".format(" ".join(args)))

    async def setNeed(self, msg, args, needed):
        if len(args) < 2 or len(args) > 5:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        name_seq = [TrackerUtils.sanitizeName(i) for i in args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.tracker, full_idx, 0)
        chosen_node.__dict__[asset_type + "_required"] = needed

        if needed:
            await msg.channel.send(msg.author.mention + " {0} {1} is now needed.".format(asset_type, " ".join(name_seq)))
        else:
            await msg.channel.send(msg.author.mention + " {0} {1} is no longer needed.".format(asset_type, " ".join(name_seq)))

        self.saveTracker()
        self.changed = True

    async def addGender(self, msg, args):
        if len(args) < 3 or len(args) > 4:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        gender_name = args[-1].title()
        if gender_name != "Male" and gender_name != "Female":
            await msg.channel.send(msg.author.mention + " Must specify male or female!")
            return
        other_gender = "Male"
        if gender_name == "Male":
            other_gender = "Female"

        species_name = TrackerUtils.sanitizeName(args[1])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 3:
            # check against already existing
            if TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, gender_name):
                await msg.channel.send(msg.author.mention + " Gender difference already exists for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            TrackerUtils.createGenderDiff(species_dict.subgroups["0000"], asset_type, gender_name)
            await msg.channel.send(msg.author.mention + " Added gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:

            form_name = TrackerUtils.sanitizeName(args[2])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if TrackerUtils.genderDiffExists(form_dict, asset_type, gender_name):
                await msg.channel.send(msg.author.mention +
                    " Gender difference already exists for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            TrackerUtils.createGenderDiff(form_dict, asset_type, gender_name)
            await msg.channel.send(msg.author.mention +
                " Added gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.saveTracker()
        self.changed = True


    async def removeGender(self, msg, args):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        species_name = TrackerUtils.sanitizeName(args[1])
        species_idx = TrackerUtils.findSlotIdx(self.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.tracker[species_idx]
        if len(args) == 2:
            # check against not existing
            if not TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, "Male") and \
                    not TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, "Female"):
                await msg.channel.send(msg.author.mention + " Gender difference doesnt exist for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            # check against data population
            if TrackerUtils.genderDiffPopulated(species_dict.subgroups["0000"], asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            TrackerUtils.removeGenderDiff(species_dict.subgroups["0000"], asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:
            form_name = TrackerUtils.sanitizeName(args[2])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against not existing
            form_dict = species_dict.subgroups[form_idx]
            if not TrackerUtils.genderDiffExists(form_dict, asset_type, "Male") and \
                    not TrackerUtils.genderDiffExists(form_dict, asset_type, "Female"):
                await msg.channel.send(msg.author.mention +
                    " Gender difference doesn't exist for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            if TrackerUtils.genderDiffPopulated(form_dict, asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            TrackerUtils.removeGenderDiff(form_dict, asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.saveTracker()
        self.changed = True

    async def help(self, msg, args):
        server_config = self.config.servers[str(msg.guild.id)]
        prefix = server_config.prefix
        use_bounties = self.config.use_bounties
        if len(args) == 0:
            return_msg = "**Commands**\n"

            for command in self.commands:
                return_msg += f"`{prefix}{command.getCommand()}` - {command.getSingleLineHelp(server_config)}\n"
            if use_bounties:
                return_msg += f"`{prefix}spritebounty` - Place a bounty on a sprite\n" \
                              f"`{prefix}portraitbounty` - Place a bounty on a portrait\n" \
                              f"`{prefix}bounties` - View top bounties\n"
            return_msg += f"`{prefix}register` - Register your profile\n" \
                          f"Type `{prefix}help` with the name of a command to learn more about it."

        else:
            base_arg = args[0]
            return_msg = None
            for command in self.commands:
                if command.getCommand() == base_arg:
                    return_msg = "**Command Help**\n" \
                        + command.getMultiLineHelp(server_config)
            if return_msg != None:
                pass
            elif base_arg == "spritebounty":
                if use_bounties:
                    return_msg = "**Command Help**\n" \
                                f"`{prefix}spritebounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                                "Places a bounty on a missing or incomplete sprite, using your Guild Points.\n" \
                                "`Pokemon Name` - Name of the Pokemon\n" \
                                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                                "`Points` - The number of guild points you wish to donate\n" \
                                "**Examples**\n" \
                                f"`{prefix}spritebounty Meowstic 1`\n" \
                                f"`{prefix}spritebounty Meowstic 5`\n" \
                                f"`{prefix}spritebounty Meowstic Shiny 1`\n" \
                                f"`{prefix}spritebounty Meowstic Female 1`\n" \
                                f"`{prefix}spritebounty Meowstic Shiny Female 1`\n" \
                                f"`{prefix}spritebounty Diancie Mega 1`\n" \
                                f"`{prefix}spritebounty Diancie Mega Shiny 1`"
                else:
                    return_msg = MESSAGE_BOUNTIES_DISABLED
            elif base_arg == "portraitbounty":
                if use_bounties:
                    return_msg = "**Command Help**\n" \
                                f"`{prefix}portraitbounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                                "Places a bounty on a missing or incomplete portrait, using your Guild Points.\n" \
                                "`Pokemon Name` - Name of the Pokemon\n" \
                                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                                "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                                "`Points` - The number of guild points you wish to donate\n" \
                                "**Examples**\n" \
                                f"`{prefix}portraitbounty Meowstic 1`\n" \
                                f"`{prefix}portraitbounty Meowstic 5`\n" \
                                f"`{prefix}portraitbounty Meowstic Shiny 1`\n" \
                                f"`{prefix}portraitbounty Meowstic Female 1`\n" \
                                f"`{prefix}portraitbounty Meowstic Shiny Female 1`\n" \
                                f"`{prefix}portraitbounty Diancie Mega 1`\n" \
                                f"`{prefix}portraitbounty Diancie Mega Shiny 1`"
                else:
                    return_msg = MESSAGE_BOUNTIES_DISABLED
            elif base_arg == "bounties":
                if use_bounties:
                    return_msg = "**Command Help**\n" \
                                f"`{prefix}bounties [Type]`\n" \
                                "View the top sprites/portraits that have bounties placed on them.  " \
                                "You will claim a bounty when you successfully submit that sprite/portrait.\n" \
                                "`Type` - [Optional] Can be `sprite` or `portrait`\n" \
                                "**Examples**\n" \
                                f"`{prefix}bounties`\n" \
                                f"`{prefix}bounties sprite`"
                else:
                    return_msg = MESSAGE_BOUNTIES_DISABLED
            elif base_arg == "register":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}register <Name> <Contact>`\n" \
                             "Registers your name and contact info for crediting purposes.  " \
                             "If you do not register, credits will be given to your discord ID instead.\n" \
                             "`Name` - Your preferred name\n" \
                             "`Contact` - Your preferred contact info; can be email, url, etc.\n" \
                             "**Examples**\n" \
                             f"`{prefix}register Audino https://github.com/audinowho`"
            else:
                return_msg = "Unknown Command."
        await msg.channel.send(msg.author.mention + " {0}".format(return_msg))


    async def staffhelp(self, msg, args):
        prefix = self.config.servers[str(msg.guild.id)].prefix
        if len(args) == 0:
            return_msg = "**Approver Commands**\n" \
                  f"`{prefix}add` - Adds a Pokemon or forme to the current list\n" \
                  f"`{prefix}delete` - Deletes an empty Pokemon or forme\n" \
                  f"`{prefix}rename` - Renames a Pokemon or forme\n" \
                  f"`{prefix}addgender` - Adds the female sprite/portrait to the Pokemon\n" \
                  f"`{prefix}deletegender` - Removes the female sprite/portrait from the Pokemon\n" \
                  f"`{prefix}need` - Marks a sprite/portrait as needed\n" \
                  f"`{prefix}dontneed` - Marks a sprite/portrait as unneeded\n" \
                  f"`{prefix}movesprite` - Swaps the sprites for two Pokemon/formes\n" \
                  f"`{prefix}moveportrait` - Swaps the portraits for two Pokemon/formes\n" \
                  f"`{prefix}move` - Swaps the sprites, portraits, and names for two Pokemon/formes\n" \
                  f"`{prefix}spritewip` - Sets the sprite status as Incomplete\n" \
                  f"`{prefix}portraitwip` - Sets the portrait status as Incomplete\n" \
                  f"`{prefix}spriteexists` - Sets the sprite status as Exists\n" \
                  f"`{prefix}portraitexists` - Sets the portrait status as Exists\n" \
                  f"`{prefix}spritefilled` - Sets the sprite status as Fully Featured\n" \
                  f"`{prefix}portraitfilled` - Sets the portrait status as Fully Featured\n" \
                  f"`{prefix}setspritecredit` - Sets the primary author of the sprite\n" \
                  f"`{prefix}setportraitcredit` - Sets the primary author of the portrait\n" \
                  f"`{prefix}addspritecredit` - Adds a new author to the credits of the sprite\n" \
                  f"`{prefix}addportraitcredit` - Adds a new author to the credits of the portrait\n" \
                  f"`{prefix}modreward` - Toggles whether a sprite/portrait will have a custom reward\n" \
                  f"`{prefix}register` - Use with arguments to make absentee profiles\n" \
                  f"`{prefix}transferprofile` - Transfers the credit from absentee profile to a real one\n" \
                  f"`{prefix}clearcache` - Clears the image/zip links for a Pokemon/forme/shiny/gender\n" \
                  f"Type `{prefix}staffhelp` with the name of a command to learn more about it."

        else:
            base_arg = args[0]
            if base_arg == "add":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}add <Pokemon Name> [Form Name]`\n" \
                             "Adds a Pokemon to the dex, or a form to the existing Pokemon.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}add Calyrex`\n" \
                             f"`{prefix}add Mr_Mime Galar`\n" \
                             f"`{prefix}add Missingno_ Kotora`"
            elif base_arg == "delete":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}delete <Pokemon Name> [Form Name]`\n" \
                             "Deletes a Pokemon or form of an existing Pokemon.  " \
                             "Only works if the slot + its children are empty.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}delete Pikablu`\n" \
                             f"`{prefix}delete Arceus Mega`"
            elif base_arg == "rename":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}rename <Pokemon Name> [Form Name] <New Name>`\n" \
                             "Changes the existing species or form to the new name.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`New Name` - New Pokemon of Form name\n" \
                             "**Examples**\n" \
                             f"`{prefix}rename Calrex Calyrex`\n" \
                             f"`{prefix}rename Vulpix Aloha Alola`"
            elif base_arg == "addgender":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}addgender <Asset Type> <Pokemon Name> [Pokemon Form] <Male or Female>`\n" \
                             "Adds a slot for the male/female version of the species, or form of the species.\n" \
                             "`Asset Type` - \"sprite\" or \"portrait\"\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}addgender Sprite Venusaur Female`\n" \
                             f"`{prefix}addgender Portrait Steelix Female`\n" \
                             f"`{prefix}addgender Sprite Raichu Alola Male`"
            elif base_arg == "deletegender":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}deletegender <Asset Type> <Pokemon Name> [Pokemon Form]`\n" \
                             "Removes the slot for the male/female version of the species, or form of the species.  " \
                             "Only works if empty.\n" \
                             "`Asset Type` - \"sprite\" or \"portrait\"\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}deletegender Sprite Venusaur`\n" \
                             f"`{prefix}deletegender Portrait Steelix`\n" \
                             f"`{prefix}deletegender Sprite Raichu Alola`"
            elif base_arg == "need":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}need <Asset Type> <Pokemon Name> [Pokemon Form] [Shiny]`\n" \
                             "Marks a sprite/portrait as Needed.  This is the default for all sprites/portraits.\n" \
                             "`Asset Type` - \"sprite\" or \"portrait\"\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "**Examples**\n" \
                             f"`{prefix}need Sprite Venusaur`\n" \
                             f"`{prefix}need Portrait Steelix`\n" \
                             f"`{prefix}need Portrait Minior Red`\n" \
                             f"`{prefix}need Portrait Minior Shiny`\n" \
                             f"`{prefix}need Sprite Castform Sunny Shiny`"
            elif base_arg == "dontneed":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}dontneed <Asset Type> <Pokemon Name> [Pokemon Form] [Shiny]`\n" \
                             "Marks a sprite/portrait as Unneeded.  " \
                             "Unneeded sprites/portraits are marked with \u26AB and do not need submissions.\n" \
                             "`Asset Type` - \"sprite\" or \"portrait\"\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "**Examples**\n" \
                             f"`{prefix}dontneed Sprite Venusaur`\n" \
                             f"`{prefix}dontneed Portrait Steelix`\n" \
                             f"`{prefix}dontneed Portrait Minior Red`\n" \
                             f"`{prefix}dontneed Portrait Minior Shiny`\n" \
                             f"`{prefix}dontneed Sprite Alcremie Shiny`"
            elif base_arg == "movesprite":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}movesprite <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
                             "Swaps the contents of one sprite with another.  " \
                             "Good for promoting alternates to main, temp Pokemon to newly revealed dex numbers, " \
                             "or just fixing mistakes.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}movesprite Escavalier -> Accelgor`\n" \
                             f"`{prefix}movesprite Zoroark Alternate -> Zoroark`\n" \
                             f"`{prefix}movesprite Missingno_ Kleavor -> Kleavor`\n" \
                             f"`{prefix}movesprite Minior Blue -> Minior Indigo`"
            elif base_arg == "moveportrait":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}moveportrait <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
                             "Swaps the contents of one portrait with another.  " \
                             "Good for promoting alternates to main, temp Pokemon to newly revealed dex numbers, " \
                             "or just fixing mistakes.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}moveportrait Escavalier -> Accelgor`\n" \
                             f"`{prefix}moveportrait Zoroark Alternate -> Zoroark`\n" \
                             f"`{prefix}moveportrait Missingno_ Kleavor -> Kleavor`\n" \
                             f"`{prefix}moveportrait Minior Blue -> Minior Indigo`"
            elif base_arg == "move":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}move <Pokemon Name> [Pokemon Form] -> <Pokemon Name 2> [Pokemon Form 2]`\n" \
                             "Swaps the name, sprites, and portraits of one slot with another.  " \
                             "This can only be done with Pokemon or formes, and the swap is recursive to shiny/genders.  " \
                             "Good for promoting alternate forms to base form, temp Pokemon to newly revealed dex numbers, " \
                             "or just fixing mistakes.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}move Escavalier -> Accelgor`\n" \
                             f"`{prefix}move Zoroark Alternate -> Zoroark`\n" \
                             f"`{prefix}move Missingno_ Kleavor -> Kleavor`\n" \
                             f"`{prefix}move Minior Blue -> Minior Indigo`"
            elif base_arg == "replacesprite":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}replacesprite <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
                             "Replaces the contents of one sprite with another.  " \
                             "Good for promoting scratch-made alternates to main.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}replacesprite Zoroark Alternate -> Zoroark`"
            elif base_arg == "replaceportrait":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}replaceportrait <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
                             "Replaces the contents of one portrait with another.  " \
                             "Good for promoting scratch-made alternates to main.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}replaceportrait Zoroark Alternate -> Zoroark`"
            elif base_arg == "spritewip":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}spritewip <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the sprite status as \u26AA Incomplete.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}spritewip Pikachu`\n" \
                             f"`{prefix}spritewip Pikachu Shiny`\n" \
                             f"`{prefix}spritewip Pikachu Female`\n" \
                             f"`{prefix}spritewip Pikachu Shiny Female`\n" \
                             f"`{prefix}spritewip Shaymin Sky`\n" \
                             f"`{prefix}spritewip Shaymin Sky Shiny`"
            elif base_arg == "portraitwip":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}portraitwip <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the portrait status as \u26AA Incomplete.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}portraitwip Pikachu`\n" \
                             f"`{prefix}portraitwip Pikachu Shiny`\n" \
                             f"`{prefix}portraitwip Pikachu Female`\n" \
                             f"`{prefix}portraitwip Pikachu Shiny Female`\n" \
                             f"`{prefix}portraitwip Shaymin Sky`\n" \
                             f"`{prefix}portraitwip Shaymin Sky Shiny`"
            elif base_arg == "spriteexists":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}spriteexists <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the sprite status as \u2705 Available.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}spriteexists Pikachu`\n" \
                             f"`{prefix}spriteexists Pikachu Shiny`\n" \
                             f"`{prefix}spriteexists Pikachu Female`\n" \
                             f"`{prefix}spriteexists Pikachu Shiny Female`\n" \
                             f"`{prefix}spriteexists Shaymin Sky`\n" \
                             f"`{prefix}spriteexists Shaymin Sky Shiny`"
            elif base_arg == "portraitexists":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}portraitexists <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the portrait status as \u2705 Available.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}portraitexists Pikachu`\n" \
                             f"`{prefix}portraitexists Pikachu Shiny`\n" \
                             f"`{prefix}portraitexists Pikachu Female`\n" \
                             f"`{prefix}portraitexists Pikachu Shiny Female`\n" \
                             f"`{prefix}portraitexists Shaymin Sky`\n" \
                             f"`{prefix}portraitexists Shaymin Sky Shiny`"
            elif base_arg == "spritefilled":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}spritefilled <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the sprite status as \u2B50 Fully Featured.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}spritefilled Pikachu`\n" \
                             f"`{prefix}spritefilled Pikachu Shiny`\n" \
                             f"`{prefix}spritefilled Pikachu Female`\n" \
                             f"`{prefix}spritefilled Pikachu Shiny Female`\n" \
                             f"`{prefix}spritefilled Shaymin Sky`\n" \
                             f"`{prefix}spritefilled Shaymin Sky Shiny`"
            elif base_arg == "portraitfilled":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}portraitfilled <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the portrait status as \u2B50 Fully Featured.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}portraitfilled Pikachu`\n" \
                             f"`{prefix}portraitfilled Pikachu Shiny`\n" \
                             f"`{prefix}portraitfilled Pikachu Female`\n" \
                             f"`{prefix}portraitfilled Pikachu Shiny Female`\n" \
                             f"`{prefix}portraitfilled Shaymin Sky`\n" \
                             f"`{prefix}portraitfilled Shaymin Sky Shiny`"
            elif base_arg == "setspritecredit":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}setspritecredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the primary author of a sprite to the specified author.  " \
                             "The specified author must already exist in the credits for the sprite.\n" \
                             "`Author ID` - The discord ID of the author to set as primary\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}setspritecredit @Audino Unown Shiny`\n" \
                             f"`{prefix}setspritecredit <@!117780585635643396> Unown Shiny`\n" \
                             f"`{prefix}setspritecredit POWERCRISTAL Calyrex`\n" \
                             f"`{prefix}setspritecredit POWERCRISTAL Calyrex Shiny`\n" \
                             f"`{prefix}setspritecredit POWERCRISTAL Jellicent Shiny Female`"
            elif base_arg == "setportraitcredit":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}setportraitcredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Manually sets the primary author of a portrait to the specified author.  " \
                             "The specified author must already exist in the credits for the portrait.\n" \
                             "`Author ID` - The discord ID of the author to set as primary\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}setportraitcredit @Audino Unown Shiny`\n" \
                             f"`{prefix}setportraitcredit <@!117780585635643396> Unown Shiny`\n" \
                             f"`{prefix}setportraitcredit POWERCRISTAL Calyrex`\n" \
                             f"`{prefix}setportraitcredit POWERCRISTAL Calyrex Shiny`\n" \
                             f"`{prefix}setportraitcredit POWERCRISTAL Jellicent Shiny Female`"
            elif base_arg == "addspritecredit":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}addspritecredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Adds the specified author to the credits of the sprite.  " \
                             "This makes a post in the submissions channel, asking other approvers to sign off.\n" \
                             "`Author ID` - The discord ID of the author to set as primary\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}addspritecredit @Audino Unown Shiny`\n" \
                             f"`{prefix}addspritecredit <@!117780585635643396> Unown Shiny`\n" \
                             f"`{prefix}addspritecredit POWERCRISTAL Calyrex`\n" \
                             f"`{prefix}addspritecredit POWERCRISTAL Calyrex Shiny`\n" \
                             f"`{prefix}addspritecredit POWERCRISTAL Jellicent Shiny Female`"
            elif base_arg == "addportraitcredit":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}addportraitcredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Adds the specified author to the credits of the portrait.  " \
                             "This makes a post in the submissions channel, asking other approvers to sign off.\n" \
                             "`Author ID` - The discord ID of the author to set as primary\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}addportraitcredit @Audino Unown Shiny`\n" \
                             f"`{prefix}addportraitcredit <@!117780585635643396> Unown Shiny`\n" \
                             f"`{prefix}addportraitcredit POWERCRISTAL Calyrex`\n" \
                             f"`{prefix}addportraitcredit POWERCRISTAL Calyrex Shiny`\n" \
                             f"`{prefix}addportraitcredit POWERCRISTAL Jellicent Shiny Female`"
            elif base_arg == "modreward":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}modreward <Pokemon Name> [Form Name]`\n" \
                             "Toggles whether a Pokemon/form will have a custom reward.  " \
                             "Instead of the bot automatically handing out GP, the approver must do so instead.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}modreward Unown`\n" \
                             f"`{prefix}modreward Minior Red`"
            elif base_arg == "register":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}register <Author ID> <Name> <Contact>`\n" \
                             "Registers an absentee profile with name and contact info for crediting purposes.  " \
                             "If a discord ID is provided, the profile is force-edited " \
                             "(can be used to remove inappropriate content)." \
                             "This command is also available for self-registration.  " \
                             f"Check the `{prefix}help` version for more.\n" \
                             "`Author ID` - The desired ID of the absentee profile\n" \
                             "`Name` - The person's preferred name\n" \
                             "`Contact` - The person's preferred contact info\n" \
                             "**Examples**\n" \
                             f"`{prefix}register SUGIMORI Sugimori https://twitter.com/SUPER_32X`\n" \
                             f"`{prefix}register @Audino Audino https://github.com/audinowho`\n" \
                             f"`{prefix}register <@!117780585635643396> Audino https://github.com/audinowho`"
            elif base_arg == "transferprofile":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}transferprofile <Author ID> <New Author ID>`\n" \
                             "Transfers the credit from absentee profile to a real one.  " \
                             "Used for when an absentee's discord account is confirmed " \
                             "and credit needs te be moved to the new name." \
                             "This command is also available for self-registration.  " \
                             f"Check the `{prefix}help` version for more.\n" \
                             "`Author ID` - The desired ID of the absentee profile\n" \
                             "`New Author ID` - The real discord ID of the author\n" \
                             "**Examples**\n" \
                             f"`{prefix}transferprofile AUDINO_WHO <@!117780585635643396>`\n" \
                             f"`{prefix}transferprofile AUDINO_WHO @Audino`"
            elif base_arg == "clearcache":
                return_msg = "**Command Help**\n" \
                             f"`{prefix}clearcache <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                             "Clears the all uploaded images related to a Pokemon, allowing them to be regenerated.  " \
                             "This includes all portrait image and sprite zip links, " \
                             "meant to be used whenever those links somehow become stale.\n" \
                             "`Pokemon Name` - Name of the Pokemon\n" \
                             "`Form Name` - [Optional] Form name of the Pokemon\n" \
                             "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                             "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                             "**Examples**\n" \
                             f"`{prefix}clearcache Pikachu`\n" \
                             f"`{prefix}clearcache Pikachu Shiny`\n" \
                             f"`{prefix}clearcache Pikachu Female`\n" \
                             f"`{prefix}clearcache Pikachu Shiny Female`\n" \
                             f"`{prefix}clearcache Shaymin Sky`\n" \
                             f"`{prefix}clearcache Shaymin Sky Shiny`"
            else:
                return_msg = "Unknown Command."
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
            args = content[len(prefix):].split()

            authorized = await sprite_bot.isAuthorized(msg.author, msg.guild)
            base_arg = args[0].lower()

            for command in sprite_bot.commands:
                if base_arg == command.getCommand():
                    await command.executeCommand(msg, args[1:])
                    return

            if base_arg == "help":
                await sprite_bot.help(msg, args[1:])
            elif base_arg == "staffhelp":
                await sprite_bot.staffhelp(msg, args[1:])
                # primary commands
            elif base_arg == "spritebounty":
                await sprite_bot.placeBounty(msg, args[1:], "sprite")
            elif base_arg == "portraitbounty":
                await sprite_bot.placeBounty(msg, args[1:], "portrait")
            elif base_arg == "bounties":
                await sprite_bot.listBounties(msg, args[1:])
            elif base_arg == "register":
                await sprite_bot.setProfile(msg, args[1:])
            elif base_arg == "absentprofiles":
                await sprite_bot.getAbsentProfiles(msg)
            elif base_arg == "unregister":
                await sprite_bot.deleteProfile(msg, args[1:])
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
            elif base_arg == "move" and authorized:
                await sprite_bot.moveSlotRecursive(msg, args[1:])
            elif base_arg == "replacesprite" and authorized:
                await sprite_bot.replaceSlot(msg, args[1:], "sprite")
            elif base_arg == "replaceportrait" and authorized:
                await sprite_bot.replaceSlot(msg, args[1:], "portrait")
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
            elif base_arg == "promote" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.promote(msg, args[1:])
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
            elif base_arg == "shutdown" and msg.author.id == sprite_bot.config.root:
                await sprite_bot.shutdown(msg)
            elif base_arg == "forcepush" and msg.author.id == sprite_bot.config.root:
                sprite_bot.generateCreditCompilation()
                await sprite_bot.gitCommit("Tracker update from forced push.")
                await sprite_bot.gitPush()
                await msg.channel.send(msg.author.mention + " Changes pushed.")
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
    updates = 0
    while not client.is_closed():
        sprite_bot.writeLog("Update #{0}".format(updates))
        try:
            # check for push every 10 mins
            if updates % 60 == 0:
                if updates == 0:
                    await sprite_bot.gitCommit("Tracker update from restart.")
                # update push
                sprite_bot.writeLog("Performing Push")
                sprite_bot.generateCreditCompilation()
                await sprite_bot.gitCommit("Update credits.")
                await sprite_bot.gitPush()
                sprite_bot.writeLog("Push Complete")

        except Exception as e:
            await sprite_bot.sendError(traceback.format_exc())

        try:
            # thread updates every 1 hour
            if updates % 360 == 0:
                sprite_bot.writeLog("Performing Thread Update")
                for server_id in sprite_bot.config.servers:
                    await sprite_bot.updateThreads(server_id)
                sprite_bot.writeLog("Thread Update Complete")

        except Exception as e:
            await sprite_bot.sendError(traceback.format_exc())

        try:
            # twitter updates every minute
            if sprite_bot.config.mastodon:
                if updates % 6 == 0:
                    sprite_bot.writeLog("Performing Social Media Update")
                    # check for mentions
                    old_mention = max(1, sprite_bot.config.last_tl_mention)
                    sprite_bot.config.last_tl_mention = await MastodonUtils.reply_mentions(sprite_bot, sprite_bot.tl_api, old_mention)
                    if sprite_bot.config.last_tl_mention != old_mention:
                        sprite_bot.saveConfig()
                    sprite_bot.writeLog("Social Media Update Complete")
        except Exception as e:
            await sprite_bot.sendError(traceback.format_exc())

        try:
            # info updates every 1 hour
            if updates % 360 == 360:
                sprite_bot.writeLog("Performing Post Update")
                if sprite_bot.changed or updates == 0:
                    sprite_bot.changed = False
                    for server_id in sprite_bot.config.servers:
                        await sprite_bot.updatePost(sprite_bot.config.servers[server_id])
                sprite_bot.writeLog("Post Update Complete")

        except Exception as e:
            await sprite_bot.sendError(traceback.format_exc())

        await asyncio.sleep(10)
        updates += 1
        sprite_bot.writeLog("Client Closed Status: {0}".format(client.is_closed()))


sprite_bot = SpriteBot(scdir, client)

with open(os.path.join(scdir, "tokens", TOKEN_FILE_PATH)) as token_file:
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
