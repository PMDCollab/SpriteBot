from enum import Enum
from typing import Dict, List

PORTRAIT_SIZE = 0
PORTRAIT_TILE_X = 0
PORTRAIT_TILE_Y = 0

PORTRAIT_SHEET_WIDTH = PORTRAIT_SIZE * PORTRAIT_TILE_X
PORTRAIT_SHEET_HEIGHT = PORTRAIT_SIZE * PORTRAIT_TILE_Y

CROP_PORTRAITS = True

COMPLETION_EMOTIONS: List[List[int]] = []

EMOTIONS: List[str] = []


ACTION_MAP: Dict[int, str] = { }

COMPLETION_ACTIONS: List[List[int]] = []

ACTIONS: List[str] = []
DUNGEON_ACTIONS: List[str] = []
STARTER_ACTIONS: List[str] = []

DIRECTIONS = [ "Down",
               "DownRight",
               "Right",
               "UpRight",
               "Up",
               "UpLeft",
               "Left",
               "DownLeft"]

MULTI_SHEET_XML = "AnimData.xml"
CREDIT_TXT = "credits.txt"

PHASES = [ "\u26AA incomplete", "\u2705 available", "\u2B50 fully featured" ]

MESSAGE_BOUNTIES_DISABLED = "Bounties are disabled for this instance of SpriteBot"

class PermissionLevel(Enum):
    EVERYONE = 0
    STAFF = 1
    ADMIN = 2

    def canPerformAction(self, required_level) -> bool:
        return required_level.value <= self.value
    
    def displayname(self) -> str:
        if self == self.EVERYONE:
            return "everyone"
        elif self == self.STAFF:
            return "staff"
        elif self == self.ADMIN:
            return "admin"
        else:
            return "unknown"