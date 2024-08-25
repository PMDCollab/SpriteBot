from abc import ABCMeta, abstractmethod
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
from typing import TYPE_CHECKING, List
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class GetProfile(BaseCommand):
    DEFAULT_PERMISSION: PermissionLevel = PermissionLevel.EVERYONE

    def getCommand(self) -> str:
        return "profile"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "View your profile"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}profile`\n" \
            "View your profile, containing your current name and contact info."
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        msg_mention = "<@!{0}>".format(msg.author.id)
        if msg_mention in self.spritebot.names:
            await msg.channel.send(msg_mention + "\nName: \"{0}\"    Contact: \"{1}\"".format(self.spritebot.names[msg_mention].name, self.spritebot.names[msg_mention].contact))
            return
        await msg.channel.send(msg_mention + " No profile. Set it with `!register <Name> <Contact>`!")