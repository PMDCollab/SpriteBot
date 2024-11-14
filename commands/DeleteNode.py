from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import os

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class DeleteNode(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "delete"

    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Deletes an empty Pokemon or forme"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}delete <Pokemon Name> [Form Name]`\n" \
        "Deletes a Pokemon or form of an existing Pokemon.  " \
        "Only works if the slot + its children are empty.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Pikablu",
            "Arceus Mega"
        ])
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if len(args) < 1 or len(args) > 2:
            await msg.channel.send(msg.author.mention + " Invalid number of args!")
            return

        species_name = TrackerUtils.sanitizeName(args[0])
        species_idx = TrackerUtils.findSlotIdx(self.spritebot.tracker, species_name)
        if species_idx is None:
            await msg.channel.send(msg.author.mention + " {0} does not exist!".format(species_name))
            return

        species_dict = self.spritebot.tracker[species_idx]
        if len(args) == 1:

            # check against data population
            if TrackerUtils.isDataPopulated(species_dict) and msg.author.id != self.spritebot.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            TrackerUtils.deleteData(self.spritebot.tracker, os.path.join(self.spritebot.config.path, 'sprite'),
                                       os.path.join(self.spritebot.config.path, 'portrait'), species_idx)

            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1}!".format(int(species_idx), species_name))
        else:

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            # check against data population
            form_dict = species_dict.subgroups[form_idx]
            if TrackerUtils.isDataPopulated(form_dict) and msg.author.id != self.spritebot.config.root:
                await msg.channel.send(msg.author.mention + " Can only delete empty slots!")
                return

            TrackerUtils.deleteData(species_dict.subgroups, os.path.join(self.spritebot.config.path, 'sprite', species_idx),
                                       os.path.join(self.spritebot.config.path, 'portrait', species_idx), form_idx)

            await msg.channel.send(msg.author.mention + " Deleted #{0:03d}: {1} {2}!".format(int(species_idx), species_name, form_name))

        self.spritebot.saveTracker()
        self.spritebot.changed = True

        await self.spritebot.gitCommit("Removed {0}".format(" ".join(args)))