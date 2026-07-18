from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import os
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class DeleteProfile(BaseCommand):
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
            return "forceunregister"
        else:
            return "unregister"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.isStaffCommand:
            return "Delete someone's profile"
        else:
            return "Delete your profile"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.isStaffCommand:
            admin_examples = [
                "SUGIMORI",
                "@Audino",
                "<@!117780585635643396>"
            ]
            return f"`{server_config.prefix}forceunregister <Author ID> <Name> <Contact>`\n" \
            "Removes a profile with the specified ID and sets credits to anonymous.\n" \
            "`Author ID` - The desired ID of the profile\n" \
            + self.generateMultiLineExample(server_config.prefix, admin_examples)
        else:
            return f"`{server_config.prefix}unregister <Name> <Contact>`\n" \
            "Removes your name and contact info from credits and sets to anonymous. " \
            "If you do not register, credits will be given to your discord ID instead."
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        msg_mention = "<@!{0}>".format(msg.author.id)

        if len(args) == 0:
            await msg.channel.send(msg.author.mention + " WARNING: This command will move your credits into an anonymous profile and be separated from your account. This cannot be undone.\n" \
                                                        "If you wish to proceed, rerun the command with your discord ID and username (with discriminator) as arguments.")
            return
        elif len(args) == 1:
            user_perms = await self.spritebot.getUserPermission(msg.author, msg.guild)
            if not user_perms.canPerformAction(PermissionLevel.STAFF):
                await msg.channel.send(msg.author.mention + " Not authorized to delete registration.")
                return
            msg_mention = self.spritebot.getFormattedCredit(args[0])
        else:
            await msg.channel.send(msg.author.mention + " Invalid args")
            return

        if msg_mention not in self.spritebot.names:
            await msg.channel.send(msg.author.mention + " Entry {0} doesn't exist!".format(msg_mention))
            return

        if self.spritebot.names[msg_mention].sprites or self.spritebot.names[msg_mention].portraits:
            if msg_mention == "<@!{0}>".format(msg.author.id):
                # find a proper anonymous name to transfer to
                anon_num = 0
                new_name = None
                while True:
                    new_name = "ANONYMOUS_{:04d}".format(anon_num)
                    found_name = False
                    for name_credit in self.spritebot.names:
                        if name_credit.lower() == new_name.lower():
                            found_name = True
                            break
                    if not found_name:
                        break
                    anon_num = anon_num + 1

                if not new_name:
                    raise Exception() # TODO: what is this exception?

                new_credit = TrackerUtils.CreditEntry("", "")
                new_credit.sprites = self.spritebot.names[msg_mention].sprites
                new_credit.portraits = self.spritebot.names[msg_mention].portraits
                del self.spritebot.names[msg_mention]
                self.spritebot.names[new_name] = new_credit

                # update tracker based on last-modify
                over_dict = TrackerUtils.initSubNode("", True)
                over_dict.subgroups = self.spritebot.tracker

                TrackerUtils.renameFileCredits(os.path.join(self.spritebot.config.path, "sprite"), msg_mention, new_name)
                TrackerUtils.renameFileCredits(os.path.join(self.spritebot.config.path, "portrait"), msg_mention, new_name)
                TrackerUtils.renameJsonCredits(over_dict, msg_mention, new_name)

                await msg.channel.send(msg.author.mention + " account deleted and credits moved to anonymous.")
            else:
                await msg.channel.send(msg.author.mention + " {0} was not deleted because it was credited. Details have been wiped instead.".format(msg_mention))
                new_credit = TrackerUtils.CreditEntry("", "")
                new_credit.sprites = self.spritebot.names[msg_mention].sprites
                new_credit.portraits = self.spritebot.names[msg_mention].portraits
                self.spritebot.names[msg_mention] = new_credit
        else:
            del self.spritebot.names[msg_mention]
            await msg.channel.send(msg.author.mention + " {0} was deleted.".format(msg_mention))

        self.spritebot.saveTracker()
        self.spritebot.saveNames()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Deleted account {0}".format(msg_mention))