
import traceback
from html.parser import HTMLParser
import mastodon
import os
import SpriteUtils
import TrackerUtils
import asyncio

TOKEN_FILE_PATH = 'mastodon_token.txt'

def init_mastodon(scdir):
    with open(os.path.join(scdir, "tokens", TOKEN_FILE_PATH)) as token_file:
        lines = token_file.read().split('\n')
        token = lines[0]
        endpoint = lines[1]

    # Authenticate to Mastodon
    api = mastodon.Mastodon(access_token=token, api_base_url=endpoint)

    return api

async def post_image(api, text, img_title, img_file, asset_type):
    if asset_type == "sprite":
        media = api.media_post(file_name=img_title, mime_type="image/gif", media_file=img_file)
    elif asset_type == "portrait":
        media = api.media_post(file_name=img_title, mime_type="image/png", media_file=img_file)
    await asyncio.sleep(20)
    status = api.status_post(status=text, media_ids=media)
    return status["url"]

def post_text(api, orig_post, msg, media):

    if not media and orig_post.status.in_reply_to_id:
        return

    status = api.status_reply(
        status=msg,
        media_ids=media,
        to_status=orig_post.status,
        in_reply_to_id=orig_post.id,
    )


async def query_text(sprite_bot, api, tracker, orig_post, name_args):
    asset_type = "portrait"

    if len(name_args) == 0:
        post_text(api, orig_post, "Specify a Pokemon.", None)
        return

    name_seq = [TrackerUtils.sanitizeName(i) for i in name_args]
    full_idx = TrackerUtils.findFullTrackerIdx(tracker, name_seq, 0)
    if full_idx is None:
        post_text(api, orig_post, "No such Pokemon.", None)
        return

    chosen_node = TrackerUtils.getNodeFromIdx(tracker, full_idx, 0)
    # post the statuses
    response = ""
    status = TrackerUtils.getStatusEmoji(chosen_node, asset_type)
    response += "{0} #{1:03d}: {2}".format(status, int(full_idx[0]), " ".join(name_seq))

    if chosen_node.__dict__[asset_type + "_required"]:
        file_exists = chosen_node.__dict__[asset_type + "_credit"].primary != ""
        if not file_exists:
            post_text(api, orig_post, "This Pokemon doesn't have a {0}.".format(asset_type), None)
            return
        else:
            credit = chosen_node.__dict__[asset_type + "_credit"]
            base_credit = None
            response += "\n" + sprite_bot.createCreditBlock(credit, base_credit, True)

        chosen_link = await sprite_bot.retrieveLinkMsg(full_idx, chosen_node, asset_type, False)
        base_file, base_name = SpriteUtils.getLinkFile(chosen_link, asset_type)
        base_file = SpriteUtils.thumbnailFileImg(base_file)
        media = api.media_post(file_name=base_name, mime_type="image/png", media_file=base_file)

        post_text(api, orig_post, response, media)
    else:
        response += " does not need a {0}.".format(asset_type)
        post_text(api, orig_post, response, None)


async def reply_mentions(sprite_bot, api, since_id):
    # TODO: remove reference to spritebot
    new_since_id = since_id
    notes = api.notifications(since_id=since_id, types=["mention"])
    notes = reversed(notes)
    for post in notes:
        new_since_id = max(post.id, new_since_id)

        try:
            parser = PostParser()
            parser.feed(post.status.content)
            name_args = parser.raw.split()
            for ii in range(len(name_args)):
                if "@" in name_args[-ii]:
                    del name_args[-ii]

            await query_text(sprite_bot, api, sprite_bot.tracker, post, name_args)
        except:
            await sprite_bot.sendError(traceback.format_exc())

    return new_since_id

class PostParser(HTMLParser):

    raw = ""

    def handle_starttag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        self.raw = self.raw + data

    def handle_comment(self, data):
        pass

    def handle_entityref(self, name):
        pass

    def handle_charref(self, name):
        pass

    def handle_decl(self, data):
        pass