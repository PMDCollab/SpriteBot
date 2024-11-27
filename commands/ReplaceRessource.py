from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils
import SpriteUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ReplaceRessource(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", ressource_type: str):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return f"replace{self.ressource_type}"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Replace the content of one {self.ressource_type} with another"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()} <Pokemon Name> [Pokemon Form] [Shiny] [Gender] -> <Pokemon Name 2> [Pokemon Form 2] [Shiny 2] [Gender 2]`\n" \
        "Replaces the contents of one {self.ressource_type} with another.  " \
        "Good for promoting scratch-made alternates to main.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
        "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, ["Zoroark Alternate -> Zoroark"])
    
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
            await msg.channel.send(msg.author.mention + " Cannot move to the same location.")
            return

        if not chosen_node_from.__dict__[self.ressource_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when source {0} is unneeded.".format(self.ressource_type))
            return
        if not chosen_node_to.__dict__[self.ressource_type + "_required"]:
            await msg.channel.send(msg.author.mention + " Cannot move when destination {0} is unneeded.".format(self.ressource_type))
            return

        try:
            await self.spritebot.checkMoveLock(full_idx_from, chosen_node_from, full_idx_to, chosen_node_to, self.ressource_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot move out the locked Pokemon specified as source:\n{0}".format(e.message))
            return

        try:
            await self.spritebot.checkMoveLock(full_idx_to, chosen_node_to, full_idx_from, chosen_node_from, self.ressource_type)
        except SpriteUtils.SpriteVerifyError as e:
            await msg.channel.send(msg.author.mention + " Cannot replace the locked Pokemon specified as destination:\n{0}".format(e.message))
            return

        # clear caches
        TrackerUtils.clearCache(chosen_node_from, True)
        TrackerUtils.clearCache(chosen_node_to, True)

        TrackerUtils.replaceFolderPaths(self.spritebot.config.path, self.spritebot.tracker, self.ressource_type, full_idx_from, full_idx_to)

        await msg.channel.send(msg.author.mention + " Replaced {0} with {1}.".format(" ".join(name_seq_to), " ".join(name_seq_from)))
        # if the source is empty in sprite and portrait, and its subunits are empty in sprite and portrait
        # remind to delete
        await msg.channel.send(msg.author.mention + " {0} is now empty. Use `!delete` if it is no longer needed.".format(" ".join(name_seq_from)))

        self.spritebot.saveTracker()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Replaced {0} with {1}".format(" ".join(name_seq_to), " ".join(name_seq_from)))