from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
import discord
import TrackerUtils
from Constants import PHASES, PermissionLevel

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class QueryRessourceStatus(BaseCommand):
    DEFAULT_PERMISSION: PermissionLevel = PermissionLevel.EVERYONE
    
    def __init__(self, spritebot: "SpriteBot", ressource_type: str, is_derivation: bool):
        super().__init__(spritebot)
        self.ressource_type = ressource_type
        self.is_derivation = is_derivation
    
    def getCommand(self) -> str:
        if self.is_derivation:
            return f"recolor{self.ressource_type}"
        else:
            return self.ressource_type
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait" and self.is_derivation:
            return "Get the Pokemon's portrait sheet in a form for easy recoloring"
        elif self.ressource_type == "portrait" and not self.is_derivation:
            return "Get the Pokemon's portrait sheet"
        elif self.ressource_type == "sprite" and self.is_derivation:
            return "Get the Pokemon's sprite sheet in a form for easy recoloring"
        elif self.ressource_type == "sprite" and not self.is_derivation:
            return "Get the Pokemon's sprite sheet"
        else:
            raise NotImplementedError()
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.ressource_type == "portrait" and not self.is_derivation:
            return f"`{server_config.prefix}portrait <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the portrait sheet for a Pokemon.  If there is none, it will return a blank template.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Wooper", "Wooper Shiny", "Wooper Female", "Wooper Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"])
        elif self.ressource_type == "sprite" and not self.is_derivation:
            return f"`{server_config.prefix}sprite <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the sprite sheet for a Pokemon.  If there is none, it will return a blank template.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu", "Pikachu Shiny", "Pikachu Female", "Pikachu Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"])
        elif self.ressource_type == "portrait" and self.is_derivation:
            return f"`{server_config.prefix}recolorportrait <Pokemon Name> [Form Name] [Gender]`\n" \
                "Gets the portrait sheet for a Pokemon in a form that is easy to recolor.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, ["Pikachu", "Pikachu Female", "Shaymin Sky"])
        elif self.ressource_type == "sprite" and self.is_derivation:
            return f"`{server_config.prefix}recolorsprite <Pokemon Name> [Form Name] [Gender]`\n" \
                "Gets the sprite sheet for a Pokemon in a form that is easy to recolor.\n" \
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

        # special case recolor link for a shiny
        recolor_shiny = False
        if self.is_derivation and "Shiny" in name_seq:
            recolor_shiny = True

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)
        # post the statuses
        response = msg.author.mention + " "
        status = TrackerUtils.getStatusEmoji(chosen_node, self.ressource_type)
        response += "{0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

        if chosen_node.__dict__[self.ressource_type + "_required"]:
            file_exists = chosen_node.__dict__[self.ressource_type + "_credit"].primary != ""
            if not file_exists and self.is_derivation:
                if recolor_shiny:
                    response += " doesn't have a {0}. Submit it first.".format(self.ressource_type)
                else:
                    response += " doesn't have a {0} to recolor. Submit the original first.".format(self.ressource_type)
            else:
                if not file_exists:
                    response += "\n [This {0} is missing. If you want to submit, use this file as a template!]".format(self.ressource_type)
                else:
                    credit = chosen_node.__dict__[self.ressource_type + "_credit"]
                    base_credit = None
                    response += "\n" + self.spritebot.createCreditBlock(credit, base_credit)
                    if len(credit.secondary) + 1 < credit.total:
                        response += "\nRun `!{0}credit {1}` for full credit.".format(self.ressource_type, " ".join(name_seq))
                if self.is_derivation and not recolor_shiny:
                    response += "\n [Recolor this {0} to its shiny palette and submit it.]".format(self.ressource_type)
                chosen_link = await self.spritebot.retrieveLinkMsg(full_idx, chosen_node, self.ressource_type, self.is_derivation)
                response += "\n" + chosen_link

            next_phase = chosen_node.__dict__[self.ressource_type + "_complete"] + 1

            if str(next_phase) in chosen_node.__dict__[self.ressource_type + "_bounty"]:
                bounty = chosen_node.__dict__[self.ressource_type + "_bounty"][str(next_phase)]
                if bounty > 0:
                    response += "\n This {0} has a bounty of **{1}GP**, paid out when it becomes {2}".format(self.ressource_type, bounty, PHASES[next_phase].title())
            if chosen_node.modreward and chosen_node.__dict__[self.ressource_type + "_complete"] == TrackerUtils.PHASE_INCOMPLETE:
                response += "\n The reward for this {0} will be decided by approvers.".format(self.ressource_type)
        else:
            response += " does not need a {0}.".format(self.ressource_type)

        await msg.channel.send(response)