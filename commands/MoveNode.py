from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import SpriteUtils
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer


class MoveNode(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "move"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Swaps the sprites, portraits, and names for two Pokemon/formes"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}move <Pokemon Name> [Pokemon Form] -> <Pokemon Name 2> [Pokemon Form 2]`\n" \
        "Swaps the name, sprites, and portraits of one slot with another.  " \
        "This can only be done with Pokemon or formes, and the swap is recursive to shiny/genders.  " \
        "Good for promoting alternate forms to base form, temp Pokemon to newly revealed dex numbers, " \
        "or just fixing mistakes.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Escavalier -> Accelgor",
            "Zoroark Alternate -> Zoroark",
            "Missingno_ Kleavor -> Kleavor",
            "Minior Blue -> Minior Indigo"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        try:
            delim_idx = args.index("->")
        except:
            await msg.channel.send(msg.author.mention + " Command needs to separate the source and destination with `->`.")
            return

        name_args_from = args[:delim_idx]
        name_args_to = args[delim_idx+1:]

        name_seq_from = [TrackerUtils.sanitizeName(i) for i in name_args_from]
        full_idx_from = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq_from, 0)
        if full_idx_from is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as source.")
            return
        if len(full_idx_from) > 2:
            await msg.channel.send(msg.author.mention + " Can move only species or form. Source specified more than that.")
            return

        name_seq_to = [TrackerUtils.sanitizeName(i) for i in name_args_to]
        full_idx_to = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq_to, 0)
        if full_idx_to is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as destination.")
            return
        if len(full_idx_to) > 2:
            await msg.channel.send(msg.author.mention + " Can move only species or form. Destination specified more than that.")
            return

        chosen_node_from = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_from, 0)
        chosen_node_to = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_to, 0)

        if chosen_node_from == chosen_node_to:
            await msg.channel.send(msg.author.mention + " Cannot move to the same location.")
            return

        explicit_idx_from = full_idx_from.copy()
        if len(explicit_idx_from) < 2:
            explicit_idx_from.append("0000")
        explicit_idx_to = full_idx_to.copy()
        if len(explicit_idx_to) < 2:
            explicit_idx_to.append("0000")

        explicit_node_from = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_from, 0)
        explicit_node_to = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_to, 0)

        # check the main nodes
        try:
            await self.spritebot.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, "sprite")
            await self.spritebot.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, "portrait")
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        try:
            await self.spritebot.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, "sprite")
            await self.spritebot.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, "portrait")
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
        TrackerUtils.swapFolderPaths(self.spritebot.config.path, self.spritebot.tracker, "sprite", full_idx_from, full_idx_to)
        TrackerUtils.swapFolderPaths(self.spritebot.config.path, self.spritebot.tracker, "portrait", full_idx_from, full_idx_to)
        TrackerUtils.swapNodeMiscFeatures(chosen_node_from, chosen_node_to)

        # then, swap the subnodes
        TrackerUtils.swapAllSubNodes(self.spritebot.config.path, self.spritebot.tracker, explicit_idx_from, explicit_idx_to)

        await msg.channel.send(msg.author.mention + " Swapped {0} with {1}.".format(" ".join(name_seq_from), " ".join(name_seq_to)))
        # if the source is empty in sprite and portrait, and its subunits are empty in sprite and portrait
        # remind to delete
        if not TrackerUtils.isDataPopulated(chosen_node_from):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_to)))
        if not TrackerUtils.isDataPopulated(chosen_node_to):
            await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_from)))

        self.spritebot.saveTracker()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Swapped {0} with {1} recursively".format(" ".join(name_seq_from), " ".join(name_seq_to)))