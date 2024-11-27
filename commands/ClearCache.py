from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
import discord
import TrackerUtils
from Constants import PermissionLevel

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ClearCache(BaseCommand):
    def __init__(self, spritebot: "SpriteBot") -> None:
        self.spritebot = spritebot
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF

    def getCommand(self) -> str:
        return "clearcache"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Clears the image/zip links for a Pokemon/forme/shiny/gender"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}clearcache <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
            "Clears the all uploaded images related to a Pokemon, allowing them to be regenerated.  " \
            "This includes all portrait image and sprite zip links, " \
            "meant to be used whenever those links somehow become stale.\n" \
            "`Pokemon Name` - Name of the Pokemon\n" \
            "`Form Name` - [Optional] Form name of the Pokemon\n" \
            "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
            "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
            + self.generateMultiLineExample(server_config.prefix, ["Pikachu", "Pikachu Shiny", "Pikachu Female", "Pikachu Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        TrackerUtils.clearCache(chosen_node, True)

        self.spritebot.saveTracker()

        await msg.channel.send(msg.author.mention + " Cleared links for #{0:03d}: {1}.".format(int(full_idx[0]), " ".join(name_seq)))