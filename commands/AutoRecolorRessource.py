from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils
import SpriteUtils
import io

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class AutoRecolorRessource(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", ressource_type: str):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.EVERYONE
    
    def getCommand(self) -> str:
        return f"autocolor{self.ressource_type}"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait":
            return "Generates an automatic recolor of the Pokemon's portrait sheet"
        elif self.ressource_type == "sprite":
            return "Generates an automatic recolor of the Pokemon's sprite sheet"
        else:
            raise NotImplementedError()
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait":
            return f"`{server_config.prefix}autocolor <Pokemon Name> [Form Name] [Gender]`\n" \
                "Generates an automatic shiny of a Pokemon's portrait sheet, in recolor form. " \
                "Meant to be used as a starting point to assist in manual recoloring. " \
                "Works best on portrait with multiple emotions, where the shiny has only a few.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu", "Pikachu Female", "Shaymin Sky"])
        elif self.ressource_type == "sprite":
            return f"`{server_config.prefix}autocolor <Pokemon Name> [Form Name] [Gender]`\n" \
                "Generates an automatic shiny of a Pokemon's sprite sheet, in recolor form. " \
                "Meant to be used as a starting point to assist in manual recoloring. " \
                "Works best on sprite with multiple animations, where the shiny has only a few.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu", "Pikachu Female", "Shaymin Sky"])
        else:
            raise NotImplementedError()
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        # compute answer from current status
        if len(args) == 0:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon.")
            return
        name_seq = [TrackerUtils.sanitizeName(i) for i in args]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return

        # can't get recolor link for a shiny
        if "Shiny" in name_seq:
            await msg.channel.send(msg.author.mention + " Can't recolor a shiny Pokemon.")
            return

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if chosen_node.__dict__[self.ressource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " Can't recolor a Pokemon that doesn't have a {0}.".format(self.ressource_type))
            return

        shiny_idx = TrackerUtils.createShinyIdx(full_idx, True)
        shiny_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, shiny_idx, 0)

        if shiny_node.__dict__[self.ressource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " Can't recolor a Pokemon that doesn't have a shiny {0}.".format(self.ressource_type))
            return

        base_link = await self.spritebot.retrieveLinkMsg(full_idx, chosen_node, self.ressource_type, False)
        cur_recolor_file, _ = SpriteUtils.getLinkFile(base_link, self.ressource_type)
        base_recolor_link = await self.spritebot.retrieveLinkMsg(full_idx, chosen_node, self.ressource_type, True)
        cur_recolor_img = SpriteUtils.getLinkImg(base_recolor_link)
        base_path = TrackerUtils.getDirFromIdx(self.spritebot.config.path, self.ressource_type, full_idx)
        # auto-generate the shiny recolor image, in file form
        shiny_path = TrackerUtils.getDirFromIdx(self.spritebot.config.path, self.ressource_type, shiny_idx)
        auto_recolor_img, cmd_str, content = SpriteUtils.autoRecolor(cur_recolor_file, base_path, shiny_path, self.ressource_type)
        # post it as a staged submission
        return_name = "{0}-{1}{2}".format(self.ressource_type + "_recolor", "-".join(shiny_idx), ".png")

        auto_recolor_file = io.BytesIO()
        auto_recolor_img.save(auto_recolor_file, format='PNG')
        auto_recolor_file.seek(0)

        title = TrackerUtils.getIdxName(self.spritebot.tracker, full_idx)

        send_files = [discord.File(auto_recolor_file, return_name)]
        await msg.channel.send("{0} {1}\n{2}\n{3}".format(msg.author.mention, " ".join(title), cmd_str, content),
                                     files=send_files)