from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
import TrackerUtils
import discord
import io

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class QueryResourceCredit(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str, display_history: bool):
        super().__init__(spritebot)
        self.resource_type = resource_type
        self.display_history = display_history
    
    def getCommand(self) -> str:
        if self.display_history:
            return f"{self.resource_type}history"
        else:
            return f"{self.resource_type}credit"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        if self.display_history:
            return f"Gets the credit history of the {self.resource_type}"
        else:
            return f"Gets the credits of the {self.resource_type}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        sprite_example = ["Pikachu", "Pikachu Shiny", "Pikachu Female", "Pikachu Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"]
        portrait_example = ["Wooper", "Wooper Shiny", "Wooper Female", "Wooper Shiny Female", "Shaymin Sky", "Shaymin Sky Shiny"]
        if self.display_history and self.resource_type == "sprite":
            return f"`{server_config.prefix}spritehistory <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the full credit history for a Pokemon's sprite sheet, including who changed what.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, sprite_example)
        elif self.display_history and self.resource_type == "portrait":
            return f"`{server_config.prefix}portraithistory <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the full credit history for a Pokemon's portraits, including who changed what.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, portrait_example)
        elif not self.display_history and self.resource_type == "sprite":
            return f"`{server_config.prefix}spritecredit <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the full credits for a Pokemon's sprite sheet.  Credit them all in your romhacks.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, sprite_example)
        elif not self.display_history and self.resource_type == "portrait":
            return f"`{server_config.prefix}portraitcredit <Pokemon Name> [Form Name] [Shiny] [Gender]`\n" \
                "Gets the full credits for a Pokemon's portraits.  Credit them all in your romhacks.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny portrait or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                + self.generateMultiLineExample(server_config.prefix, portrait_example)
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

        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        if chosen_node.__dict__[self.resource_type + "_credit"].primary == "":
            await msg.channel.send(msg.author.mention + " No credit found.")
            return

        gen_path = TrackerUtils.getDirFromIdx(self.spritebot.config.path, self.resource_type, full_idx)

        response = msg.author.mention + " "
        status = TrackerUtils.getStatusEmoji(chosen_node, self.resource_type)
        response += "Full credit for {0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

        credit_str = ""
        too_long = False
        if self.display_history:
            credit_entries = TrackerUtils.getFileCredits(gen_path)
            for credit_entry in credit_entries:
                credit_id = credit_entry.name
                entry = self.spritebot.names[credit_entry.name]
                if entry.name != '':
                    credit_id = entry.name
                credit_line = "{0}\t{1}\t{2}".format(credit_entry.datetime, credit_id, credit_entry.changed)
                credit_str += '\n' + credit_line
                if len(credit_str) >= 1900:
                    too_long = True
        else:
            credit_entries = TrackerUtils.getCreditEntries(gen_path)
            for credit_id in credit_entries:
                entry = self.spritebot.names[credit_id]
                if entry.name != '':
                    credit_id = entry.name
                credit_line = "{0}\t{1}".format(credit_id, entry.contact)
                credit_str += '\n' + credit_line
                if len(credit_str) >= 1900:
                    too_long = True
        if too_long:
            file_data = io.StringIO()
            file_data.write(credit_str)
            file_data.seek(0)
            await msg.channel.send(response, file=discord.File(file_data, 'credit_msg.txt'))
        else:
            await msg.channel.send(response + "```" + credit_str + "```")