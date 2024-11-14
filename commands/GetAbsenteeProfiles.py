from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class GetAbsenteeProfiles(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.EVERYONE

    def getCommand(self) -> str:
        return "absentprofiles"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "List the absentees profiles (those not linked to a Discord account)"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()}`\n" \
            f"{self.getSingleLineHelp(server_config)}\n" \
            + self.generateMultiLineExample(
                server_config.prefix,
                []
            )
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        total_names = ["Absentee profiles:"]
        msg_ids = [] # type: ignore
        for name in self.spritebot.names:
            if not name.startswith("<@!"):
                total_names.append(name + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.spritebot.names[name].name, self.spritebot.names[name].contact))
        await self.spritebot.sendInfoPosts(msg.channel, total_names, msg_ids, 0)