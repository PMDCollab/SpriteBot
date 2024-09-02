import io
import time

import requests
from requests_oauthlib import OAuth1
import mastodon
import os
import SpriteUtils
import TrackerUtils

TOKEN_FILE_PATH = 'mastodon_token.txt'

def init_mastodon(scdir):
    with open(os.path.join(scdir, "tokens", TOKEN_FILE_PATH)) as token_file:
        lines = token_file.read().split('\n')
        token = lines[0]
        endpoint = lines[1]

    # Authenticate to Mastodon
    api = mastodon.Mastodon(access_token=token, api_base_url=endpoint)

    return api

def post_image(api, text, chosen_link):
    asset_type = "portrait"
    base_file, base_name = SpriteUtils.getLinkFile(chosen_link, asset_type)
    base_file = SpriteUtils.thumbnailFileImg(base_file)
    media = api.media_post(file_name=base_name, mime_type="image/png", media_file=base_file)
    status = api.status_post(status=text, media_ids=media)
    print(str(status))

def post_text(api, orig_post, msg, media_ids):
    if orig_post:
        status = api.status_reply(
            status="@" + orig_post.user.screen_name + " " + msg,
            media_ids=media_ids,
            in_reply_to_id=orig_post.id,
        )
    else:
        status = api.status_post(
            status=msg,
            media_ids=media_ids,
        )

    print(str(status))

async def query_text(sprite_bot, api, tracker, text, name_args):
    asset_type = "portrait"

    if len(name_args) == 0:
        post_text(api, text, "Specify a Pokemon.", [])
        return

    name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
    full_idx = TrackerUtils.findFullTrackerIdx(tracker, name_seq, 0)
    if full_idx is None:
        post_text(api, text, "No such Pokemon.", [])
        return

    chosen_node = TrackerUtils.getNodeFromIdx(tracker, full_idx, 0)
    # post the statuses
    response = ""
    status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
    response += "{0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

    if chosen_node.__dict__[asset_type + "_required"]:
        file_exists = chosen_node.__dict__[asset_type + "_credit"].primary != ""
        if not file_exists:
            post_text(api, text, "This Pokemon doesn't have a {0}.".format(asset_type), [])
            return
        else:
            credit = chosen_node.__dict__[asset_type + "_credit"]
            base_credit = None
            response += "\n" + sprite_bot.createCreditBlock(credit, base_credit, True)

        chosen_link = await sprite_bot.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)
        base_file, base_name = SpriteUtils.getLinkFile(chosen_link, asset_type)
        base_file = SpriteUtils.thumbnailFileImg(base_file)
        media = api.media_upload(filename=base_name, file=base_file)

        post_text(api, text, response, [media.media_id])
    else:
        response += " does not need a {0}.".format(asset_type)
        post_text(api, text, response, [])


async def reply_mentions(sprite_bot, api, since_id):
    # TODO: remove reference to spritebot
    new_since_id = since_id
    for text in tweepy.Cursor(api.mentions_timeline, since_id=since_id).items():
        new_since_id = max(text.id, new_since_id)

        name_args = text.text.split()
        for ii in range(len(name_args)):
            if "@" in name_args[-ii]:
                del name_args[-ii]

        await query_text(sprite_bot, api, sprite_bot.tracker, text, name_args)

    return new_since_id
