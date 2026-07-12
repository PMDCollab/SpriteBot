from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import SpriteUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class Rescan(BaseCommand):
    def getRequiredPermission(self):
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        return "rescan"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Rescan the data (if not commented out in the code)"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}rescan`\n" \
            f"{self.getSingleLineHelp(server_config)}\n" \
            + self.generateMultiLineExample(server_config.prefix, [""])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        #SpriteUtils.iterateTracker(self.spritebot.tracker, self.spritebot.markPortraitFull, [])
        #self.spritebot.changed = True
        #self.spritebot.saveTracker()
        #await msg.channel.send(msg.author.mention + " Rescan complete.")
        await msg.channel.send(msg.author.mention + " Rescan disabled in the code")