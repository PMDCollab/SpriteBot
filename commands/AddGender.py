from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import SpriteUtils
import TrackerUtils
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class AddGender(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "addgender"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Adds the female sprite/portrait to the Pokemon"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}addgender <Asset Type> <Pokemon Name> [Pokemon Form] <Male or Female>`\n" \
            "Adds a slot for the male/female version of the species, or form of the species.\n" \
            "`Asset Type` - \"sprite\" or \"portrait\"\n" \
            "`Pokemon Name` - Name of the Pokemon\n" \
            "`Form Name` - [Optional] Form name of the Pokemon\n" \
            + self.generateMultiLineExample(server_config.prefix, [
                "Sprite Venusaur Female",
                "Portrait Steelix Female",
                "Sprite Raichu Alola Male"
            ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 3 or len(args) > 4:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        asset_type = args[0].lower()
        if asset_type != "sprite" and asset_type != "portrait":
            await msg.channel.send(msg.author.mention + " Must specify sprite or portrait!")
            return

        gender_name = args[-1].title()
        if gender_name != "Male" and gender_name != "Female":
            await msg.channel.send(msg.author.mention + " Must specify male or female!")
            return
        other_gender = "Male"
        if gender_name == "Male":
            other_gender = "Female"

        species_name = TrackerUtils.sanitizeName(args[1])
        species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.spritebot.tracker[species_idx]
        if len(args) == 3:
            # check against already existing
            if TrackerUtils.genderDiffExists(species_dict.subgroups["0000"], asset_type, gender_name):
                await msg.channel.send(msg.author.mention + " Gender difference already exists for #{0:03d}: {1}!".format(int(species_idx), species_name))
                return

            TrackerUtils.createGenderDiff(species_dict.subgroups["0000"], asset_type, gender_name)
            await msg.channel.send(msg.author.mention + " Added gender difference to #{0:03d}: {1}! ({2})".format(int(species_idx), species_name, asset_type))
        else:

            form_name = TrackerUtils.sanitizeName(args[2])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if TrackerUtils.genderDiffExists(form_dict, asset_type, gender_name):
                await msg.channel.send(msg.author.mention +
                    " Gender difference already exists for #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))
                return

            TrackerUtils.createGenderDiff(form_dict, asset_type, gender_name)
            await msg.channel.send(msg.author.mention +
                " Added gender difference to #{0:03d}: {1} {2}! ({3})".format(int(species_idx), species_name, form_name, asset_type))

        self.spritebot.saveTracker()
        self.spritebot.changed = True