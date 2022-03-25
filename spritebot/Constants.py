from typing import List, Dict

PORTRAIT_SIZE = 0
PORTRAIT_TILE_X = 0
PORTRAIT_TILE_Y = 0

PORTRAIT_SHEET_WIDTH = PORTRAIT_SIZE * PORTRAIT_TILE_X
PORTRAIT_SHEET_HEIGHT = PORTRAIT_SIZE * PORTRAIT_TILE_Y

CROP_PORTRAITS = True

COMPLETION_EMOTIONS: List[List[int]] = []

EMOTIONS: List[str] = []


ACTION_MAP: Dict[str, str] = {}

COMPLETION_ACTIONS: List[List[int]] = []

ACTIONS: List[str] = []

DIRECTIONS = ["Down",
              "DownRight",
              "Right",
              "UpRight",
              "Up",
              "UpLeft",
              "Left",
              "DownLeft"]

MULTI_SHEET_XML = "AnimData.xml"

# Housekeeping for login information
TOKEN_FILE_PATH = 'token.txt'
NAME_FILE_PATH = 'credit_names.txt'
INFO_FILE_PATH = 'README.md'
CONFIG_FILE_PATH = 'config.json'
SPRITE_CONFIG_FILE_PATH = 'sprite_config.json'
TRACKER_FILE_PATH = 'tracker.json'
