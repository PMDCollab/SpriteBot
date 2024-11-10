from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import os

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class TransferProfile(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "transferprofile"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Transfers the credit from absentee profile to a real one"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()} <Author ID> <New Author ID>`\n" \
            "Transfers the credit from absentee profile to a real one.  " \
            "Used for when an absentee's discord account is confirmed " \
            "and credit needs te be moved to the new name.\n" \
            "`Author ID` - The desired ID of the absentee profile\n" \
            "`New Author ID` - The real discord ID of the author\n" \
            + self.generateMultiLineExample(
                server_config.prefix,
                ["AUDINO_WHO <@!117780585635643396>", "AUDINO_WHO @Audino"]
            )
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) != 2:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        from_name = self.spritebot.getFormattedCredit(args[0])
        to_name = self.spritebot.getFormattedCredit(args[1])
        if from_name.startswith("<@!") or from_name == "CHUNSOFT":
            await msg.channel.send(msg.author.mention + " Only transfers from absent registrations are allowed.")
            return
        if from_name not in self.spritebot.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(from_name))
            return
        if to_name not in self.spritebot.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(to_name))
            return

        new_credit = TrackerUtils.CreditEntry(self.spritebot.names[to_name].name, self.spritebot.names[to_name].contact)
        new_credit.sprites = self.spritebot.names[from_name].sprites or self.spritebot.names[to_name].sprites
        new_credit.portraits = self.spritebot.names[from_name].portraits or self.spritebot.names[to_name].portraits
        del self.spritebot.names[from_name]
        self.spritebot.names[to_name] = new_credit

        # update tracker based on last-modify
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.spritebot.tracker

        TrackerUtils.renameFileCredits(os.path.join(self.spritebot.config.path, "sprite"), from_name, to_name)
        TrackerUtils.renameFileCredits(os.path.join(self.spritebot.config.path, "portrait"), from_name, to_name)
        TrackerUtils.renameJsonCredits(over_dict, from_name, to_name)

        await msg.channel.send(msg.author.mention + " account {0} deleted and credits moved to {1}.".format(from_name, to_name))

        self.spritebot.saveTracker()
        self.spritebot.saveNames()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Moved account {0} to {1}".format(from_name, to_name))