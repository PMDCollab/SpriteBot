from typing import TYPE_CHECKING, List
from .BaseCommand import BaseCommand
from Constants import PermissionLevel
import TrackerUtils
import discord
import json
from Constants import PHASES

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class AddResourceBounty(BaseCommand):
    def __init__(self, spritebot: "SpriteBot", resource_type: str):
        super().__init__(spritebot)
        self.resource_type = resource_type
    
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.EVERYONE
    
    def getCommand(self) -> str:
        return f"{self.resource_type}bounty"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return f"Place a bounty on a {self.resource_type}"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        sprite_example = ["Meowstic 1", "Meowstic 5", "Meowstic Shiny 1", "Meowstic Female 1", "Meowstic Shiny Female 1", "Diancie Mega 1", "Diancie Mega Shiny 1"]
        portrait_example = ["Meowstic 1", "Meowstic 5", "Meowstic Shiny 1", "Meowstic Female 1", "Meowstic Shiny Female 1", "Diancie Mega 1", "Diancie Mega Shiny 1"]
        if self.resource_type == "sprite":
            return f"`{server_config.prefix}spritebounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                "Places a bounty on a missing or incomplete sprite, using your Guild Points.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                "`Points` - The number of guild points you wish to donate\n" \
                + self.generateMultiLineExample(server_config.prefix, sprite_example)
        elif self.resource_type == "portrait":
            return f"`{server_config.prefix}portraitbounty <Pokemon Name> [Form Name] [Shiny] [Gender] <Points>`\n" \
                "Places a bounty on a missing or incomplete portrait, using your Guild Points.\n" \
                "`Pokemon Name` - Name of the Pokemon\n" \
                "`Form Name` - [Optional] Form name of the Pokemon\n" \
                "`Shiny` - [Optional] Specifies if you want the shiny sprite or not\n" \
                "`Gender` - [Optional] Specifies the gender of the Pokemon, for those with gender differences\n" \
                "`Points` - The number of guild points you wish to donate\n" \
                + self.generateMultiLineExample(server_config.prefix, portrait_example)
        else:
            raise NotImplementedError()
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        try:
            amt = int(args[-1])
        except Exception as e:
            await msg.channel.send(msg.author.mention + " Specify a Pokemon and an amount.")
            return

        if amt <= 0:
            await msg.channel.send(msg.author.mention + " Specify an amount above 0.")
            return

        name_seq = [TrackerUtils.sanitizeName(i) for i in args[:-1]]
        full_idx = TrackerUtils.findFullTrackerIdx(self.spritebot.tracker, name_seq, 0)
        if full_idx is None:
            await msg.channel.send(msg.author.mention + " No such Pokemon.")
            return
        chosen_node = TrackerUtils.getNodeFromIdx(self.spritebot.tracker, full_idx, 0)

        status = TrackerUtils.getStatusEmoji(chosen_node, self.resource_type)
        if chosen_node.__dict__[self.resource_type + "_complete"] >= TrackerUtils.PHASE_FULL:
            await msg.channel.send(msg.author.mention + " {0} #{1:03d} {2} is fully featured and cannot have a bounty.".format(status, int(full_idx[0]), " ".join(name_seq)))
            return

        if self.spritebot.config.points == 0:
            user_perms = await self.spritebot.getUserPermission(msg.author, msg.guild)
            if not user_perms.canPerformAction(PermissionLevel.STAFF):
                await msg.channel.send(msg.author.mention + " Not authorized.")
                return
        else:
            channel = self.spritebot.client.get_channel(self.spritebot.config.points_ch)
            resp = await channel.send("<@{0}> !checkr {1}".format(self.spritebot.config.points, msg.author.id))

            # check for enough points
            def check(m):
                return m.channel == resp.channel and m.author.id == self.spritebot.config.points

            cur_amt = 0
            try:
                wait_msg = await self.spritebot.client.wait_for('message', check=check, timeout=10.0)
                result_json = json.loads(wait_msg.content)
                cur_amt = int(result_json["result"])
            except Exception as e:
                await msg.channel.send(msg.author.mention + " Error retrieving guild points.")
                return

            if cur_amt < amt:
                await msg.channel.send(msg.author.mention + " Not enough guild points! You currently have **{0}GP**.".format(cur_amt))
                return
            resp = await channel.send("<@{0}> !tr {0} {1} {2}".format(self.spritebot.config.points, msg.author.id, amt, msg.channel.id))

            try:
                wait_msg = await self.spritebot.client.wait_for('message', check=check, timeout=10.0)
                result_json = json.loads(wait_msg.content)
                if result_json["status"] != "success":
                    raise Exception() # TODO: what exception is this?
            except Exception as e:
                await msg.channel.send(msg.author.mention + " Error taking guild points.")
                return

        cur_val = 0
        result_phase = chosen_node.__dict__[self.resource_type + "_complete"] + 1
        if str(result_phase) in chosen_node.__dict__[self.resource_type + "_bounty"]:
            cur_val = chosen_node.__dict__[self.resource_type + "_bounty"][str(result_phase)]

        chosen_node.__dict__[self.resource_type + "_bounty"][str(result_phase)] = cur_val + amt

        # set to complete
        await msg.channel.send(msg.author.mention + " {0} #{1:03d}: {2} now has a bounty of **{3}GP**, paid out when the {4} becomes {5}.".format(status, int(full_idx[0]), " ".join(name_seq), cur_val + amt, self.resource_type, PHASES[result_phase].title()))

        self.spritebot.saveTracker()
        self.spritebot.changed = True
