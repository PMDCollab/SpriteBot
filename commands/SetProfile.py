from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class SetProfile(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", isStaffCommand: bool):
        super().__init__(spritebot)
        self.isStaffCommand = isStaffCommand
    
    def getRequiredPermission(self) -> PermissionLevel:
        if self.isStaffCommand:
            return PermissionLevel.STAFF
        else:
            return PermissionLevel.EVERYONE
    
    def getCommand(self) -> str:
        if self.isStaffCommand:
            return "forceregister"
        else:
            return "register"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.isStaffCommand:
            return "Set someone's profile"
        else:
            return "Set your profile"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.isStaffCommand:
            admin_examples = [
                "SUGIMORI Sugimori https://twitter.com/SUPER_32X",
                "@Audino Audino https://github.com/audinowho",
                "<@!117780585635643396> Audino https://github.com/audinowho"
            ]
            return f"`{server_config.prefix}forceregister <Author ID> <Name> <Contact>`\n" \
            "Registers an absentee profile with name and contact info for crediting purposes.  " \
            "If a discord ID is provided, the profile is force-edited " \
            "(can be used to remove inappropriate content)." \
            "This command is also available for self-registration.  " \
            f"Check the `{server_config.prefix}register` version for more.\n" \
            "`Author ID` - The desired ID of the absentee profile\n" \
            "`Name` - The person's preferred name\n" \
            "`Contact` - The person's preferred contact info\n" \
            + self.generateMultiLineExample(server_config.prefix, admin_examples)
        else:
            return f"`{server_config.prefix}register <Name> <Contact>`\n" \
            "Registers your name and contact info for crediting purposes. " \
            "If you do not register, credits will be given to your discord ID instead.\n" \
            "`Name` - Your preferred name\n" \
            "`Contact` - Your preferred contact info; can be email, url, etc.\n" \
            + self.generateMultiLineExample(server_config.prefix, ["Audino https://github.com/audinowho"])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        entry_key = "<@!{0}>".format(msg.author.id)

        if self.isStaffCommand:
            if len(args) != 3:
                await msg.channel.send(msg.author.mention + " Require 3 arguments")
                return
            entry_key = self.spritebot.getFormattedCredit(args[0])
            new_credit = TrackerUtils.CreditEntry(args[1], args[2])
        else:
            if len(args) == 0:
                new_credit = TrackerUtils.CreditEntry("", "")
            elif len(args) == 1:
                new_credit = TrackerUtils.CreditEntry(args[0], "")
            elif len(args) == 2:
                new_credit = TrackerUtils.CreditEntry(args[0], args[1])
            else:
                await msg.channel.send(msg.author.mention + " Invalid amounts of arguments")

        if entry_key in self.spritebot.names:
            new_credit.sprites = self.spritebot.names[entry_key].sprites
            new_credit.portraits = self.spritebot.names[entry_key].portraits
        self.spritebot.names[entry_key] = new_credit
        self.spritebot.saveNames()

        await msg.channel.send(entry_key + " registered profile:\nName: \"{0}\"    Contact: \"{1}\"".format(self.spritebot.names[entry_key].name, self.spritebot.names[entry_key].contact))