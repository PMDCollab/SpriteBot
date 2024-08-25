from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ListRessource(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", ressource_type: str):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.EVERYONE
    
    def getCommand(self) -> str:
        return f"list{self.ressource_type}"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait":
            return "List all portraits related to a Pokemon"
        elif self.ressource_type == "sprite":
            return "List all sprites related to a Pokemon"
        else:
            raise NotImplementedError()
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait":
            return f"`{server_config.prefix}listportrait <Pokemon Name>`\n" \
                "List all portraits related to a Pokemon.  This includes all forms, gender, and shiny variants.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu"])
        elif self.ressource_type == "sprite":
            return f"`{server_config.prefix}listsprite <Pokemon Name>`\n" \
                "List all sprites related to a Pokemon.  This includes all forms, gender, and shiny variants.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu"])
        else:
            raise NotImplementedError()
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        # compute answer from current status
        if len(args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [TrackerUtils.sanitizeName(args[0])]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        posts: List[str] = []
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = { full_idx[0] : chosen_node }
        self.spritebot.getPostsFromDict(self.ressource_type == 'sprite', self.ressource_type == 'portrait', False, over_dict, posts, [])
        msgs_used, changed = await self.spritebot.sendInfoPosts(msg.channel, posts, [], 0)