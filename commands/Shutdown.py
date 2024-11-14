from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class Shutdown(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        return "shutdown"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Stop the bot"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()}`\n" \
            f"{self.getSingleLineHelp(server_config)}\n" \
            + self.generateMultiLineExample(
                server_config.prefix,
                []
            )
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        guild = msg.guild
        if guild is not None:
            resp_ch = self.spritebot.getChatChannel(guild.id)
            await resp_ch.send("Shutting down.")
        self.spritebot.saveConfig()
        await self.spritebot.client.close()