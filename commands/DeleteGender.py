from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class DeleteGender(BaseCommand):
    def getRequiredPermission(self):
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "deletegender"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Removes the female sprite/portrait from the Pokemon"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}deletegender <Asset Type> <Pokemon Name> [Pokemon Form]`\n" \
        "Removes the slot for the male/female version of the species, or form of the species.  " \
        "Only works if empty.\n" \
        "`Asset Type` - \"sprite\" or \"portrait\"\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Sprite Venusaur",
            "Portrait Steelix",
            "Sprite Raichu Alola"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 2 or len(args) > 3:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        species_name = TrackerUtils.sanitizeName(args[1])
        species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.spritebot.tracker[species_idx]
        if len(args) == 2:
            # check against not existing
            if not TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, "Male") and \
                    not TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, "Female"):
                await msg.channel.send(msg.author.mention + " Gender difference doesnt exist for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            # check against data population
            if TrackerUtils.genderDiffPopulated(species_dict.subgroups["0000"], asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            TrackerUtils.removeGenderDiff(species_dict.subgroups["0000"], asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:
            form_name = TrackerUtils.sanitizeName(args[2])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against not existing
            form_dict = species_dict.subgroups[form_idx]
            if not TrackerUtils.genderDiffExists(form_dict, asset_type, "Male") and \
                    not TrackerUtils.genderDiffExists(form_dict, asset_type, "Female"):
                await msg.channel.send(msg.author.mention +
                    " Gender difference doesn't exist for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            if TrackerUtils.genderDiffPopulated(form_dict, asset_type):
                await msg.channel.send(msg.author.mention + " Gender difference isn't empty for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            TrackerUtils.removeGenderDiff(form_dict, asset_type)
            await msg.channel.send(msg.author.mention +
                " Removed gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.spritebot.saveTracker()
        self.spritebot.changed = True