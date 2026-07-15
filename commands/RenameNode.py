from typing import List, TYPE_CHECKING
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import discord
import TrackerUtils

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class RenameNode(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "rename"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Renames a Pokemon or forme"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}rename <Pokemon Name> [Form Name] <New Name>`\n" \
        "Changes the existing species or form to the new name.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        "`New Name` - New Pokemon of Form name\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Calrex Calyrex",
            "Vulpix Aloha Alola"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = TrackerUtils.sanitizeName(args[0])
        new_name = TrackerUtils.sanitizeName(args[-1])
        species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.spritebot.tracker[species_idx]

        if len(args) == 2:
            new_species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, new_name)
            if new_species_idx is not None:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} already exists!".format(int(new_species_idx), new_name))
                return

            species_dict.name = new_name
            await msg.channel.send(msg.author.mention + " Changed #{0:03d}: {1} to {2}!".format(int(species_idx), species_name, new_name))
        else:

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            new_form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, new_name)
            if new_form_idx is not None:
                await msg.channel.send(msg.author.mention + " {2} already exists within #{0:03d}: {1}!".format(int(species_idx), species_name, new_name))
                return

            form_dict = species_dict.subgroups[form_idx]
            form_dict.name = new_name

            await msg.channel.send(msg.author.mention + " Changed {2} to {3} in #{0:03d}: {1}!".format(int(species_idx), species_name, form_name, new_name))

        self.spritebot.saveTracker()
        self.spritebot.changed = True