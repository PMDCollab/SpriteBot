
import os
from datetime import datetime, timezone
import urllib3
import json
import asyncio

TOKEN_FILE_PATH = 'bluesky_token.txt'

class BlueSkyApi:
    """
    A class for handling credit in credit history
    """
    def __init__(self, user, password):
        self.user = user
        self.password = password

def init_bluesky(scdir):
    with open(os.path.join(scdir, "tokens", TOKEN_FILE_PATH)) as token_file:
        lines = token_file.read().split('\n')
        user = lines[0]
        password = lines[1]

    api = BlueSkyApi(user, password)

    return api

def get_api_key(user, password):
    http = urllib3.PoolManager()
    post_data = {"identifier": user, "password": password}
    api_key = http.request(
        "POST", "https://bsky.social/xrpc/com.atproto.server.createSession",
        headers={"Content-Type": "application/json"},
        body=bytes(json.dumps(post_data), encoding="utf-8"),
    )
    api_key = json.loads(api_key.data)
    return api_key["accessJwt"]

def upload_blob(img_data, jwt, mime_type):
    http = urllib3.PoolManager()
    blob_request = http.request(
        "POST",
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        body=img_data,
        headers={"Content-Type": mime_type, "Authorization": f"Bearer {jwt}"},
    )
    blob_request = json.loads(blob_request.data)
    return blob_request["blob"]

def send_post(user, jwt, text, blob, image_alt):
    http = urllib3.PoolManager()
    post_record = {
        "collection": "app.bsky.feed.post",
        "repo": user,
        "record": {
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "embed": {
                "$type": "app.bsky.embed.images",
                "images": [ { "image": blob, "alt": image_alt } ],
            },
        },
    }
    post_request = http.request(
        "POST",
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        body=json.dumps(post_record),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
    )
    post_request = json.loads(post_request.data)
    return post_request

async def post_image(api, text, img_title, img_file, asset_type):
    jwt = get_api_key(api.user, api.password)
    if asset_type == "sprite":
        media = upload_blob(img_file, jwt, "image/gif")
    elif asset_type == "portrait":
        media = upload_blob(img_file, jwt, "image/png")
    status = send_post(api.user, jwt, text, media, img_title)
    await asyncio.sleep(20)
    return status["uri"]
