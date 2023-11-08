from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
import TrackerUtils
import discord
import SpriteUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class DeleteRessourceCredit(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", ressource_type: str):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
    
    def getCommand(self) -> str:
        return f"delete{self.ressource_type}credit"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Removes an author to the credits of the {self.ressource_type}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        example_args = [
            "@Audino Unonw Shiny",
            "<@!117780585635643396> Unown Shiny",
            "@Audino Calyrex",
            "@Audino Calyrex Shiny",
            "@Audino Jellicent Shiny Female"
        ]
        if self.ressource_type == "portrait":
            return f"`{server_config.prefix}deleteportraitcredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Deletes the specified author from the credits of the portrait.  " \
                "This makes a post in the submissions channel, asking other approvers to sign off." \
                "The post must be approved by the author being removed.\n" \
                "`Author ID` - The discord ID of the author to set as primary\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                + self.generateMultiLineExample(server_config.prefix, example_args)
        elif self.ressource_type == "sprite":
            return f"`{server_config.prefix}deletespritecredit <Author ID> <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Deletes the specified author from the credits of the sprite.  " \
                "This makes a post in the submissions channel, asking other approvers to sign off." \
                "The post must be approved by the author being removed.\n" \
                "`Author ID` - The discord ID of the author to set as primary\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
                + self.generateMultiLineExample(server_config.prefix, example_args)
        else:
            raise NotImplementedError()
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        # compute answer from current status
        if len(args) < 2:
            await msg.channel.send(msg.author.mention + " Specify a user ID and Pokemon.")
            return

        wanted_author = self.spritebot.getFormattedCredit(args[0])
        if wanted_author not in self.spritebot.names:
            await msg.channel.send(msg.author.mention + " No such profile ID.")
            return

        authorized = await self.spritebot.isAuthorized(msg.author, msg.guild)
        author = "<@!{0}>".format(msg.author.id)
        if not authorized and author != wanted_author:
            await msg.channel.send(msg.author.mention + " You must specify your own user ID.")
            return

        name_seq = [TrackerUtils.sanitizeName(i) for i in args[1:]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if chosen_node.__dict__[self.ressource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " This command only works on filled {0}.".format(self.ressource_type))
            return

        gen_path = TrackerUtils.getDirFromIdx(self.spritebot.config.path, self.ressource_type, full_idx)
        credit_entries = TrackerUtils.getFileCredits(gen_path)
        has_credit = False
        latest_credit = False
        for credit_entry in credit_entries:
            credit_id = credit_entry[1]
            if credit_entry[2] == "OLD":
                continue
            if credit_id == wanted_author:
                has_credit = True
                latest_credit = True
            else:
                latest_credit = False

        if not has_credit:
            await msg.channel.send(msg.author.mention + " The author must be in the credits list for this {0}.".format(self.ressource_type))
            return

        if latest_credit:
            await msg.channel.send(msg.author.mention + " The author cannot be the latest contributor.")
            return

        if msg.guild == None:
            raise BaseException("The message has not been posted to a guild!")

        chat_id = self.spritebot.config.servers[str(msg.guild.id)].submit
        if chat_id == 0:
            await msg.channel.send(msg.author.mention + " This server does not support submissions.")
            return

        submit_channel = self.spritebot.client.get_channel(chat_id)
        author = "<@!{0}>".format(msg.author.id)

        base_link = await self.spritebot.retrieveLinkMsg(full_idx, chosen_node, self.ressource_type, False)
        base_file, base_name = SpriteUtils.getLinkData(base_link)

        # stage a post in submissions
        await self.spritebot.postStagedSubmission(submit_channel, "--deleteauthor", "", full_idx, chosen_node, self.ressource_type, author + "/" + wanted_author,
                                        False, None, base_file, base_name, None)