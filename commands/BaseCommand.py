from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, List
from Constants import PermissionLevel
import discord

if TYPE_CHECKING:
    from SpriteBot import SpriteBot, BotServer

class BaseCommand:
    def __init__(self, spritebot: "SpriteBot") -> None:
        self.spritebot = spritebot
    
    @abstractmethod
    def getRequiredPermission(self) -> PermissionLevel:
        """return the permission level required to execute this command"""
        raise NotImplementedError()
    
    @abstractmethod
    def getCommand(self) -> str:
        """return the command associated with this Class, like "recolorsprite" """
        raise NotImplementedError()
    
    @abstractmethod
    def getSingleLineHelp(self, server_config: "BotServer") -> str:
        """return a short description of the function in a single line"""
        raise NotImplementedError()
    
    @abstractmethod
    def getMultiLineHelp(self, server_config: "BotServer") -> str:
        """return a multi-line help for this command"""
        raise NotImplementedError()
    
    def shouldListInHelp(self) -> bool:
        return True
    
    @abstractmethod
    async def executeCommand(self, msg: discord.Message, args: List[str]):
        """perform the action of this command following a user’s command"""
        raise NotImplementedError()
    
    def generateMultiLineExample(self, prefix: str, examples_args: List[str]) -> str:
        """ Generate the Examples: section of the multi-line documentation, with each entry in examples_args as a command argument list"""
        result = "**Examples**\n"
        if len(examples_args) == 0:
            examples_args = [""]
        for example in examples_args:
            result += f"`{prefix}{self.getCommand()} {example}`\n"
        return result
