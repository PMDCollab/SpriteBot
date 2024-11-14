from typing import TYPE_CHECKING, List, Tuple
from .BaseCommand import BaseCommand
import TrackerUtils
from Constants import PermissionLevel, MESSAGE_BOUNTIES_DISABLED, PHASES
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class ListBounties(BaseCommand):
    def getRequiredPermission(self) -> PermissionLevel:
        return PermissionLevel.EVERYONE
    
    def getCommand(self) -> str:
        return "bounties"
    
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        return "View top bounties"
    
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        if self.spritebot.config.use_bounties:
            return f"`{server_config.prefix}{self.getCommand()} [Type]`\n" \
                    "View the top sprites/portraits that have bounties placed on them.  " \
                    "You will claim a bounty when you successfully submit that sprite/portrait.\n" \
                    "`Type` - [Optional] Can be `sprite` or `portrait`\n" \
                    + self.generateMultiLineExample(
                        server_config.prefix,
                        [
                            "",
                            "sprite"
                        ]
                    )
        else:
            return MESSAGE_BOUNTIES_DISABLED
    
    def shouldListInHelp(self) -> bool:
        return self.spritebot.config.use_bounties
    
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        if not self.spritebot.config.use_bounties:
            await msg.channel.send(msg.author.mention + " " + MESSAGE_BOUNTIES_DISABLED)
            return
        
        include_sprite = True
        include_portrait = True

        if len(args) > 0:
            if args[0].lower() == "sprite":
                include_portrait = False
            elif args[0].lower() == "portrait":
                include_sprite = False
            else:
                await msg.channel.send(msg.author.mention + " Use 'sprite' or 'portrait' as argument.")
                return

        entries: List[Tuple[int, str, str, int]] = []
        over_dict = TrackerUtils.initSubNode("", True)
        over_dict.subgroups = self.spritebot.tracker

        if include_sprite:
            self.spritebot.getBountiesFromDict("sprite", over_dict, entries, [])
        if include_portrait:
            self.spritebot.getBountiesFromDict("portrait", over_dict, entries, [])

        entries = sorted(entries, reverse=True)
        entries = entries[:10]

        posts = []
        if include_sprite and include_portrait:
            posts.append("**Top Bounties**")
        elif include_sprite:
            posts.append("**Top Bounties for Sprites**")
        else:
            posts.append("**Top Bounties for Portraits**")
        for entry in entries:
            posts.append("#{0:02d}. {2} for **{1}GP**, paid when the {3} becomes {4}.".format(len(posts), entry[0], entry[1], entry[2], PHASES[entry[3]].title()))

        if len(posts) == 1:
            posts.append("[None]")

        msgs_used, changed = await self.spritebot.sendInfoPosts(msg.channel, posts, [], 0)