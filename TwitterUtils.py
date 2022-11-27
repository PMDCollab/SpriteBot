import io
import time

import requests
from requests_oauthlib import OAuth1
import tweepy
import os
import SpriteUtils
import TrackerUtils

TOKEN_FILE_PATH = 'twitter_token.txt'
TWITTER_RE = 'https://twitter.com/'

def init_twitter(scdir):
    with open(os.path.join(scdir, TOKEN_FILE_PATH)) as token_file:
        token = token_file.read().split('\n')
        consumer_key = token[0]
        consumer_secret = token[1]
        access_token = token[2]
        access_token_secret = token[3]

    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    return api

def post_image(api, text, chosen_link):
    asset_type = "portrait"
    base_file, base_name = SpriteUtils.getLinkFile(chosen_link, asset_type)
    base_file = SpriteUtils.thumbnailFileImg(base_file)
    media = api.media_upload(filename=base_name, file=base_file)
    status = api.update_status(status=text, media_ids=[media.media_id])
    # print(str(status))

def post_tweet(api, orig_tweet, msg, media_ids):
    if orig_tweet:
        status = api.update_status(
            status="@" + orig_tweet.user.screen_name + " " + msg,
            media_ids=media_ids,
            in_reply_to_status_id=orig_tweet.id,
        )
    else:
        status = api.update_status(
            status=msg,
            media_ids=media_ids,
        )

    # print(str(status))

async def query_tweet(sprite_bot, api, tracker, tweet, name_args):
    asset_type = "portrait"

    if len(name_args) == 0:
        post_tweet(api, tweet, "Specify a Pokemon.", [])
        return

    name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
    full_idx = TrackerUtils.findFullTrackerIdx(tracker, name_seq, 0)
    if full_idx is None:
        post_tweet(api, tweet, "No such Pokemon.", [])
        return

    chosen_node = TrackerUtils.getNodeFromIdx(tracker, full_idx, 0)
    # post the statuses
    response = ""
    status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
    response += "{0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

    if chosen_node.__dict__[asset_type + "_required"]:
        file_exists = chosen_node.__dict__[asset_type + "_credit"].primary != ""
        if not file_exists:
            post_tweet(api, tweet, "This Pokemon doesn't have a {0}.".format(asset_type), [])
            return
        else:
            credit = chosen_node.__dict__[asset_type + "_credit"]
            base_credit = None
            response += "\n" + sprite_bot.createCreditBlock(credit, base_credit, True)

        chosen_link = await sprite_bot.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)
        base_file, base_name = SpriteUtils.getLinkFile(chosen_link, asset_type)
        base_file = SpriteUtils.thumbnailFileImg(base_file)
        media = api.media_upload(filename=base_name, file=base_file)

        post_tweet(api, tweet, response, [media.media_id])
    else:
        response += " does not need a {0}.".format(asset_type)
        post_tweet(api, tweet, response, [])


async def reply_mentions(sprite_bot, api, since_id):
    # TODO: remove reference to spritebot
    new_since_id = since_id
    for tweet in tweepy.Cursor(api.mentions_timeline, since_id=since_id).items():
        new_since_id = max(tweet.id, new_since_id)

        name_args = tweet.text.split()
        for ii in range(len(name_args)):
            if "@" in name_args[-ii]:
                del name_args[-ii]

        await query_tweet(sprite_bot, api, sprite_bot.tracker, tweet, name_args)

    return new_since_id
