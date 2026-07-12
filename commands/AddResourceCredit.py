from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils
import SpriteUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class AddResourceCredit(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str):
        super().__init__(spritebot)
        self.resource_type = resource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return f"add{self.resource_type}credit"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Adds a new author to the credits of the {self.resource_type}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}{self.getCommand()} <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender] <Files>`\n" \
            f"Adds the specified author to the credits of the {self.resource_type}.  " \
            "This makes a post in the submissions channel, asking other approvers to sign off.\n" \
            "`Author ID` - The discord ID of the author to set as primary\n" \
            "`Pokemon Name` - Name of the Pokemon\n" \
            "`Form Name` - [Optional] Form name of the Pokemon\n" \
            "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
            "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
            "`Files` - A comma-separated list of the files to change, or \" to represent the last applied credit\n" \
               + self.generateMultiLineExample(server_config.prefix, [
                "@Audino Unown Shiny \"",
                "<@!117780585635643396> Unown Shiny \"",
                "`{prefix}addspritecredit @Audino Unown Shiny Idle,Rotate,Sleep`",
                "POWERCRISTAL Calyrex \"",
                "POWERCRISTAL Calyrex Shiny \"",
                "POWERCRISTAL Jellicent Shiny Female \""
            ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        # compute answer from current status
        if len(args) < 3:
            await msg.channel.send(msg.author.mention + " Specify a user ID, file list, and Pokemon.")
            return

        wanted_author = self.spritebot.getFormattedCredit(args[0])
        name_seq = [TrackerUtils.sanitizeName(i) for i in args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if chosen_node.__dict__[self.resource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " This command only works on filled {0}.".format(self.resource_type))
            return

        if wanted_author not in self.spritebot.names:
            await msg.channel.send(msg.author.mention + " No such profile ID.")
            return

        assert(msg.guild is not None)

        submit_args = "--addauthor"
        file_names = args[-1]

        if file_names != "\"":
            final_file_names, failed_file_names = self.spritebot.parseFileNames(chosen_node, self.resource_type, file_names)
            if len(failed_file_names) > 0:
                await msg.channel.send(msg.author.mention + " Could not find the emotion/animations:\n{0}.".format(",".join(failed_file_names)))
                return False

            submit_args = submit_args + " --files " + ",".join(final_file_names)

        chat_id = self.spritebot.config.servers[str(msg.guild.id)].submit
        if chat_id == 0:
            await msg.channel.send(msg.author.mention + " This server does not support submissions.")
            return

        submit_channel = self.spritebot.client.get_channel(chat_id)
        author = "<@!{0}>".format(msg.author.id)

        base_link = await self.spritebot.retrieveLinkMsg(full_idx, chosen_node, self.resource_type, False)
        base_file, base_name = SpriteUtils.getLinkData(base_link)

        # stage a post in submissions
        await self.spritebot.postStagedSubmission(submit_channel, submit_args, "", full_idx, chosen_node, self.resource_type, author + "/" + wanted_author,
                                                False, None, base_file, base_name, None)