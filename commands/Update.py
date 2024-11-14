from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import os
import git

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class Update(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        return "update"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Update the SpriteBot using Git"
    
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
        resp = await resp_ch.send("Pulling from repo...")
        # update self
        bot_repo = git.Repo(self.spritebot.path)
        origin = bot_repo.remotes.origin
        origin.pull()
        await resp.edit(content="Update complete! Bot will restart.")
        self.spritebot.need_restart = True
        self.spritebot.config.update_ch = resp_ch.id
        self.spritebot.config.update_msg = resp.id
        self.spritebot.saveConfig()
        await self.spritebot.client.close()