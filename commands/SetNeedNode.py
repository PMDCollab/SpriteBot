from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetNeedNode(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", needed: bool) -> None:
        self.spritebot = spritebot
        self.needed = needed
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        if self.needed:
            return "need"
        else:
            return "dontneed"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.needed:
            return "Marks a sprite/portrait as needed"
        else:
            return "Marks a sprite/portrait as unneeded"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.needed:
            description = "Marks a sprite/portrait as Needed.  This is the default for all sprites/portraits."
        else:
            description = "Marks a sprite/portrait as Unneeded.  " \
                "Unneeded sprites/portraits are marked with \u26AB and do not need submissions."
        return f"`{server_config.prefix}{self.getCommand()}<Asset Type> <Pokemon Name> [Pokemon Form] [Shiny]`\n" \
            + description + "\n" \
            + "`Asset Type` - \"sprite\" or \"portrait\"\n" \
            "`Pokemon Name` - Name of the Pokemon\n" \
            "`Form Name` - [Optional] Form name of the Pokemon\n" \
            "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
            + self.generateMultiLineExample(server_config.prefix, [
                "Sprite Venusaur",
                "Portrait Steelix",
                "Portrait Minior Red",
                "Portrait Minior Shiny",
                "Sprite Alcremie Shiny"
            ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 2 or len(args) > 5:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        name_seq = [TrackerUtils.sanitizeName(i) for i in args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)
        chosen_node.__dict__[asset_type + "_required"] = self.needed

        if self.needed:
            await msg.channel.send(msg.author.mention + " {0} {1} is now needed.".format(asset_type, " ".join(name_seq)))
        else:
            await msg.channel.send(msg.author.mention + " {0} {1} is no longer needed.".format(asset_type, " ".join(name_seq)))

        self.spritebot.saveTracker()
        self.spritebot.changed = True