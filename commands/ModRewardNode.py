from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import os

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ModRewardNode(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.STAFF
    
    def getCommand(self) -> str:
        return "modreward"

    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "Toggles whether a Pokemon or forme will have a custom reward"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        return f"`{server_config.prefix}modreward <Pokemon Name> [Form Name]`\n" \
        "Toggles whether a Pokemon/form will have a custom reward.  " \
        "Instead of the bot automatically handing out GP, the approver must do so instead.\n" \
        "`Pokemon Name` - Name of the Pokemon\n" \
        "`Form Name` - [Optional] Form name of the Pokemon\n" \
        + self.generateMultiLineExample(server_config.prefix, [
            "Unown",
            "Minior Red"
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
            new_modreward = not species_dict.modreward
            species_dict.modreward = new_modreward

            form_dict = species_dict.subgroups['0000']
            TrackerUtils.setNodeModReward(form_dict, new_modreward, True)

            if species_dict.modreward:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1}'s rewards will be decided by approvers. (Including shiny and gender slots)".format(int(species_idx), species_name))
            else:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1}'s rewards will be given automatically. (Including shiny and gender slots)".format(int(species_idx), species_name))
        else:

            form_name = TrackerUtils.sanitizeName(args[1])
            form_idx = TrackerUtils.findSlotIdx(species_dict.subgroups, form_name)
            if form_idx is None:
                await msg.channel.send(msg.author.mention + " {2} doesn't exist within #{0:03d}: {1}!".format(int(species_idx), species_name, form_name))
                return

            form_dict = species_dict.subgroups[form_idx]
            new_modreward = not form_dict.modreward
            TrackerUtils.setNodeModReward(form_dict, new_modreward, True)

            if form_dict.modreward:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} {2}'s rewards will be decided by approvers. (Including shiny and gender slots)".format(int(species_idx), species_name, form_name))
            else:
                await msg.channel.send(msg.author.mention + " #{0:03d}: {1} {2}'s rewards will be given automatically. (Including shiny and gender slots)".format(int(species_idx), species_name, form_name))

        self.spritebot.saveTracker()
        self.spritebot.changed = True