from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import re

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class AddNode(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "add"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Adds a Pokemon or forme to the current list"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}add <Pokemon Name> [Pokemon Form]`\n" \
        "Adds a Pokemon to the dex, or a form to the existing Pokemon.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Calyrex",
            "Mr_Mime Galar",
            "Missingno_ Kotora"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 1 or len(args) > 2:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = TrackerUtils.sanitizeName(args[0])
        species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, species_name)
        if len(args) == 1:
            if species_idx is not None:
                await msg.channel.send(msg.author.mention + " {0} already exists!".format(species_name))
                return

            count = len(self.spritebot.tracker)
            new_idx = "{:04d}".format(count)
            self.spritebot.tracker[new_idx] = TrackerUtils.createSpeciesNode(species_name)

            await msg.channel.send(msg.author.mention + " Added #{0:03d}: {1}!".format(count, species_name))
        else:
            if species_idx is None:
                await msg.channel.send(msg.author.mention + " {0} doesn't exist! Create it first!".format(species_name))
                return

            form_name = TrackerUtils.sanitizeName(args[1])
            species_dict = self.spritebot.tracker[species_idx]
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is not None:
                await msg.channel.send(msg.author.mention +
                                       " {2} already exists within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            if form_name == "Shiny" or form_name == "Male" or form_name == "Female":
                await msg.channel.send(msg.author.mention + " Invalid form name!")
                return

            canon = True
            if re.search(r"_?Alternate\d*$", form_name):
                canon = False
            if re.search(r"_?Starter\d*$", form_name):
                canon = False
            if re.search(r"_?Altcolor\d*$", form_name):
                canon = False
            if re.search(r"_?Beta\d*$", form_name):
                canon = False
            if species_name == "Missingno_":
                canon = False

            count = len(species_dict.subgroups)
            new_count = "{:04d}".format(count)
            species_dict.subgroups[new_count] = TrackerUtils.createFormNode(form_name, canon)

            await msg.channel.send(msg.author.mention +
                                   " Added #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.spritebot.saveTracker()
        self.spritebot.changed = True