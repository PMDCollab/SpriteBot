from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetResourceCredit(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str):
        super().__init__(spritebot)
        self.resource_type = resource_type

    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "set{}credit".format(self.resource_type)
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Sets the primary author of the {}".format(self.resource_type)
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}set{self.resource_type}credit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
        f"Manually sets the primary author of a {self.resource_type} to the specified author.  " \
        f"The specified author must already exist in the credits for the {self.resource_type}.\n" \
        "`Author ID` - The discord ID of the author to set as primary\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        f"`Shiny` - [Optional] Specifies if you want the shiny {self.resource_type} or not\n" \
        "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "@Audino Unown Shiny",
            "<@!117780585635643396> Unown Shiny",
            "POWERCRISTAL Calyrex",
            "POWERCRISTAL Calyrex Shiny",
            "POWERCRISTAL Jellicent Shiny Female"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):

        # compute answer from current status
        if len(args) < 2:
            await msg.channel.send(msg.author.mention + " Specify a user ID and Pokemon.")
            return

        wanted_author = self.spritebot.getFormattedCredit(args[0])
        name_seq = [TrackerUtils.sanitizeName(i) for i in args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if chosen_node.__dict__[self.resource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " No credit found.")
            return
        gen_path = TrackerUtils.getDirFromIdx(self.spritebot.config.path, self.resource_type, full_idx)

        credit_entries = TrackerUtils.getCreditEntries(gen_path)

        if wanted_author not in credit_entries:
            await msg.channel.send(msg.author.mention + " Could not find ID `{0}` in credits for {1}.".format(wanted_author, self.resource_type))
            return

        # make the credit array into the most current author by itself
        credit_data = chosen_node.__dict__[self.resource_type + "_credit"]
        if credit_data.primary == "CHUNSOFT":
            await msg.channel.send(msg.author.mention + " Cannot reset credit for a CHUNSOFT {0}.".format(self.resource_type))
            return

        credit_data.primary = wanted_author
        TrackerUtils.updateCreditFromEntries(credit_data, credit_entries)

        await msg.channel.send(msg.author.mention + " Credit display has been reset for {0} {1}:\n{2}".format(self.resource_type, " ".join(name_seq), self.spritebot.createCreditBlock(credit_data, None)))

        self.spritebot.saveTracker()
        self.spritebot.changed = True