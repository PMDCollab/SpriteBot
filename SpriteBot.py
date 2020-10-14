import os
import io
import discord
import urllib
import traceback
import asyncio
import json
import RecolorTool
import datetime
import git
import sys
from PIL import Image, ImageDraw, ImageFont


# Housekeeping for login information
TOKEN_FILE_PATH = 'token.txt'
NAME_FILE_PATH = 'credit_names.txt'
INFO_FILE_PATH = 'info.txt'
CONFIG_FILE_PATH = 'config.json'
TRACKER_FILE_PATH = 'tracker.json'


# Command prefix.
COMMAND_PREFIX = '!'

scdir = os.path.dirname(os.path.abspath(__file__))

print("Hello World!")

# wait for user input
input("Input anything")

# update self
repo = git.Repo(scdir)
origin = repo.remotes.origin
origin.pull()

# restart
args = sys.argv[:]
print('Re-spawning %s' % ' '.join(args))
args.insert(0, sys.executable)
if sys.platform == 'win32':
    args = ['"%s"' % arg for arg in args]

os.execv(sys.executable, args)
