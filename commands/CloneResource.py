from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import SpriteUtils
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class CloneResource(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str):
        super().__init__(spritebot)
        self.resource_type = resource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return f"clone{self.resource_type}"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Copies the {self.resource_type}s from one Pokemon/forme to another"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}clone{self.resource_type} <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
        f"Clones the contents of one {self.resource_type} to another.  " \
        "Good for copying alternates.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        f"`Shiny` - [Optional] Specifies if you want the shiny {self.resource_type} or not\n" \
        "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
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

        name_seq_to = [TrackerUtils.sanitizeName(i) for i in name_args_to]
        full_idx_to = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq_to, 0)
        if full_idx_to is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon specified as destination.")
            return

        chosen_node_from = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_from, 0)
        chosen_node_to = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx_to, 0)

        if chosen_node_from == chosen_node_to:
            await msg.channel.send(msg.author.mention + " Cannot clone to the same location.")
            return

        if not chosen_node_to.__dict__[self.resource_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot clone when destination {0} is unneeded.".format(self.resource_type))
            return

        try:
            await self.spritebot.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, self.resource_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot clone the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        if TrackerUtils.isDataPopulated(chosen_node_to, self.resource_type == "sprite", self.resource_type == "portrait", False):
            await msg.channel.send(msg.author.mention + " Cannot clone to an occupied destination!")
            return

        # clear caches
        TrackerUtils.clearCache(chosen_node_from, True)
        TrackerUtils.clearCache(chosen_node_to, True)

        TrackerUtils.copyFolderPaths(self.spritebot.config.path, self.spritebot.tracker, self.resource_type, full_idx_from, full_idx_to)

        await msg.channel.send(msg.author.mention + " Copied {0} to {1}.".format(" ".join(name_seq_from), " ".join(name_seq_to)))
        self.spritebot.saveTracker()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Copied {0} to {1}".format(" ".join(name_seq_from), " ".join(name_seq_to)))
