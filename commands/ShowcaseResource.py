from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils
import Constants

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ShowcaseResource(BaseCommand):
    def __init__(self, spritebot: "SpriteBot"):
        super().__init__(spritebot)

    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "showcase"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Showcases a sprite or portrait to social media channels"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}showcase <Pokemon Name> [Form Name] [Shiny] [Gender] <Anim>`\n" \
        "Showcases the sprite or portrait to social media.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
        "`Gender` - [Optional] Specifies the gender of the Pokemon\n" \
        "`Anim` - The animation to showcase. This will cause the sprite to be shown instead of the portrait.\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Lucario Mega",
            "Calyrex Sleep"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):

        if not self.spritebot.config.mastodon and not self.spritebot.config.bluesky:
            await msg.channel.send(msg.author.mention + " Social Media posting is disabled.")
            return

        asset_type = "sprite"

        file_name = args[-1]
        has_file_name = False
        for action in Constants.ACTIONS:
            if action.lower() == file_name.lower():
                has_file_name = True
                break

        if has_file_name:
            args = args[:-1]
        else:
            file_name = None
            asset_type = "portrait"

        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if asset_type == "sprite":
            for k in chosen_node.__dict__[asset_type + "_files"]:
                if file_name.lower() == k.lower():
                    file_name = k
                    break

            if file_name not in chosen_node.__dict__[asset_type + "_files"]:
                await msg.channel.send(msg.author.mention + " Specify a Pokemon and an existing emotion/animation.")
                return

        credit_data = chosen_node.__dict__[asset_type + "_credit"]

        urls = await self.spritebot.postSocialMedia(full_idx, asset_type, "Showcased",
                                          self.spritebot.createCreditBlock(credit_data, None, True), file_name)

        await msg.channel.send(msg.author.mention + " {0}".format("\n".join(urls)))