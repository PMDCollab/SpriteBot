from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
from Constants import PHASES

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetRessourceCompletion(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", ressource_type: str, completion: int):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
        #TODO: completion should eventually be replaced by a class or enum once better in-memory ressource typing is implemented.
        self.completion = completion
    
    def getRequiredPermission(self):
        return PermissionLevel.STAFF
    
    def getCompletionName(self) -> str:
        if self.completion == TrackerUtils.PHASE_INCOMPLETE:
            return "Incomplete"
        elif self.completion == TrackerUtils.PHASE_EXISTS:
            return "Available"
        elif self.completion == TrackerUtils.PHASE_FULL:
            return "Fully Featured"
        else:
            raise NotImplementedError()
    
    def getCompletionEmoji(self) -> str:
        if self.completion == TrackerUtils.PHASE_INCOMPLETE:
            return "\u26AA"
        elif self.completion == TrackerUtils.PHASE_EXISTS:
            return "\u2705"
        elif self.completion == TrackerUtils.PHASE_FULL:
            return "\u2B50"
        else:
            raise NotImplementedError()
    
    def getCompletionCommandCode(self) -> str:
        if self.completion == TrackerUtils.PHASE_INCOMPLETE:
            return "wip"
        elif self.completion == TrackerUtils.PHASE_EXISTS:
            return "exists"
        elif self.completion == TrackerUtils.PHASE_FULL:
            return "filled"
        else:
            raise NotImplementedError()
    
    def getCommand(self) -> str:
        return self.ressource_type + self.getCompletionCommandCode()
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Set the {self.ressource_type} status to {self.getCompletionName()}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()} <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
            f"Manually sets the {self.ressource_type} status as {self.getCompletionEmoji()} {self.getCompletionName()}.\n" \
            "`Pokemon Name` - Name of the Pokemon\n" \
            "`Form Name` - [Optional] Form name of the Pokemon\n" \
            f"`Shiny` - [Optional] Specifies if you want the shiny {self.ressource_type} or not\n" \
            "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
            + self.generateMultiLineExample(
                server_config.prefix,
                [
                    "Pikachu",
                    "Pikachu Shiny",
                    "Pikachu Female",
                    "Pikachu Shiny Female",
                    "Shaymin Sky",
                    "Shaymin Sky Shiny"
                ]
            )

    async def executeCommand(self, msg: discord.Message, args: List[str]):
        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        phase_str = PHASES[self.completion]

        # if the node has no credit, fail
        if chosen_node.__dict__[self.ressource_type + "_credit"].primary == "" and self.completion > TrackerUtils.PHASE_INCOMPLETE:
            status = TrackerUtils.getStatusEmoji(chosen_node, self.ressource_type)
            await msg.channel.send(msg.author.mention +
                                   " {0} #{1:03d}: {2} has no data and cannot be marked {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))
            return

        # set to complete
        chosen_node.__dict__[self.ressource_type + "_complete"] = self.completion

        status = TrackerUtils.getStatusEmoji(chosen_node, self.ressource_type)
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} marked as {3}.".format(status, int(full_idx[0]), " ".join(name_seq), phase_str))

        self.spritebot.saveTracker()
        self.spritebot.changed = True