from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetResourceLock(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str, lock: bool):
        super().__init__(spritebot)
        self.resource_type = resource_type
        self.lock = lock
    
    def getRequiredPermission(self):
        return PermissionLevel.ADMIN
    
    def getCommand(self) -> str:
        if self.lock:
            return "lock" + self.resource_type
        else:
            return "unlock" + self.resource_type
    
    def getEmotionOrActionText(self) -> str:
        if self.resource_type == "sprite":
            return "action"
        else:
            return "emotion"

    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        
        if self.lock:
            return f"Mark a {self.resource_type} {self.getEmotionOrActionText()}as locked"
        else:
            return f"Mark a {self.resource_type} {self.getEmotionOrActionText()} as unlocked"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.lock:
            action = "lock"
            description = "Set a so it cannot be modified"
        else:
            action = "unlock"
            description = "so it can be modified again"

        if self.resource_type == "sprite":
            example = [
                "Pikachu pose",
                "Pikachu Female wake"
            ]
        else:
            example = [
                "Pikachu happy",
                "Pikachu Female normal"
            ]

        return f"`{server_config.prefix}{self.getCommand()} <Pokemon Name> [Pokemon Form] [Shiny] [Gender] <action/emotion>`\n" \
        f"Set a {self.resource_type} {self.getEmotionOrActionText()} {description}. \n" \
        + self.generateMultiLineExample(server_config.prefix, example)
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        name_seq = [TrackerUtils.sanitizeName(i) for i in args[:-1]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        final_file_names, failed_file_names = self.spritebot.parseFileNames(chosen_node, self.resource_type, args[-1])

        if len(failed_file_names) > 0:
            await msg.channel.send(msg.author.mention + " Could not find the emotion/animations:\n{0}.".format(",".join(failed_file_names)))
            return

        for file_name in final_file_names:
            chosen_node.__dict__[self.resource_type + "_files"][file_name] = self.lock

        status = TrackerUtils.getStatusEmoji(chosen_node, self.resource_type)

        lock_str = "unlocked"
        if self.lock:
            lock_str = "locked"
        # set to complete
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} {3} is now {4}.".format(status, int(full_idx[0]), " ".join(name_seq), ",".join(final_file_names), lock_str))

        self.spritebot.saveTracker()
        self.spritebot.changed = True