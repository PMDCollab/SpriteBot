import io
import time

import traceback
import requests
from requests_oauthlib import OAuth1
from html.parser import HTMLParser
from atproto import Client
import os
import SpriteUtils
import TrackerUtils
import asyncio

TOKEN_FILE_PATH = 'bluesky_token.txt'

def init_bluesky(scdir):
    with open(os.path.join(scdir, "tokens", TOKEN_FILE_PATH)) as token_file:
        lines = token_file.read().split('\n')
        user = lines[0]
        password = lines[1]

    # Authenticate to Mastodon
    client = Client(base_url='https://bsky.social')
    client.login(user, password)

    return client

async def post_image(api, text, img_title, img_file, asset_type):
    status = api.send_image(text=text, image=img_file, image_alt=img_title)
    return status["uri"]
