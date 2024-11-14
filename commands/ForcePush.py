from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ForcePush(BaseCommand):
    def getRequiredPermission(self):
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        return "forcepush"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Commit and push the underlying git repository"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()}`\n" \
            f"{self.getSingleLineHelp(server_config)}"
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        self.spritebot.generateCreditCompilation()
        await self.spritebot.gitCommit("Tracker update from forced push.")
        await self.spritebot.gitPush()
        await msg.channel.send(msg.author.mention + " Changes pushed.")
