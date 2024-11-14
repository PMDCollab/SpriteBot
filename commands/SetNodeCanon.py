from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetNodeCanon(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", canon: bool):
        super().__init__(spritebot)
        self.canon = canon
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        if self.canon:
            return "canon"
        else:
            return "uncanon"
    
    def getCanonOrUncanon(self) -> str:
        if self.canon:
            return "canon"
        else:
            return "uncanon"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Mark a Pokémon as {self.getCanonOrUncanon()}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()} <Pokemon Name> [Pokemon Form] [Shiny] [Gender]`\n" \
            f"{self.getSingleLineHelp(server_config)}\n" \
            + self.generateMultiLineExample(
                server_config.prefix,
                [
                    "Pikachu"
                ]
            )
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        TrackerUtils.setCanon(chosen_node, self.canon)

        # set to complete
        await msg.channel.send(msg.author.mention + " {0} is now {1}.".format(" ".join(name_seq), self.getCanonOrUncanon()))

        self.spritebot.saveTracker()
        self.spritebot.changed = True