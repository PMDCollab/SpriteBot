from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import SpriteUtils
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class PastWork(BaseCommand):
    def getRequiredPermission(self):
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        return "pastwork"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Rescan the data (if not commented out in the code)"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}pastwork <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
               "Gets the last post in which this Pokemon was worked on.\n" \
               "`Pokemon Name` - Name of the Pokemon\n" \
               "`Form Name` - [Optional] Form name of the Pokemon\n" \
               "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
               "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
               + self.generateMultiLineExample(server_config.prefix, ["Wooper", "Wooper Shiny", "Wooper Female", "Wooper Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        # compute answer from current status
        if len(args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        past_links = chosen_node.past_work

        await msg.channel.send(msg.author.mention + " Last work on this sprite:\n{0}".format("\n".join(past_links)))