import io
import time

import requests
from requests_oauthlib import OAuth1
import tweepy
import os

from PIL import Image

TOKEN_FILE_PATH = 'twitter_token.txt'

scdir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(scdir, TOKEN_FILE_PATH)) as token_file:
    token = token_file.read().split('\n')
    consumer_key = token[0]
    consumer_secret = token[1]
    access_token = token[2]
    access_token_secret = token[3]

def init_twitter():
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    return api
    #try:
    #    api.verify_credentials()
    #    print("Authentication Successful")
    #    return api
    #except Exception as ex:
    #    print("Authentication Error: " + str(ex))
    #    return None

def post_image(api, text, img_name, img):
    try:
        fileData = io.BytesIO()
        img.save(fileData, format='PNG')
        fileData.seek(0)
        media = api.media_upload(filename=img_name, file=fileData)
        status = api.update_status(status=text, media_ids=[media.media_id])
        print(str(status))
    except Exception as ex:
        print("Failed to post image: " + str(ex))

def reply_mentions(api, since_id):
    new_since_id = since_id
    for tweet in tweepy.Cursor(api.mentions_timeline, since_id=since_id).items():
        new_since_id = max(tweet.id, new_since_id)

        name_args = tweet.text.lower().split()
        img = Image.open(os.path.join(scdir, "Test.png")).convert("RGBA")#get_requested_img(name_args)
        img_name = "portrait_test" # node.Name

        fileData = io.BytesIO()
        img.save(fileData, format='PNG')
        fileData.seek(0)
        media = api.media_upload(filename=img_name, file=fileData)
        status = api.update_status(
            status="@" + tweet.user.screen_name + " Test: Pikachu, Chunsoft",
            media_ids=[media.media_id],
            in_reply_to_status_id=tweet.id,
        )
        print(str(status))
    return new_since_id

tw_api = init_twitter()

#test_img = Image.open(os.path.join(scdir, "Test.png")).convert("RGBA")
#post_image(tw_api, "Automated test with image 3", "test_alcremie", test_img)

since_id = 1
while True:
    since_id = reply_mentions(tw_api, since_id)
    time.sleep(60)



def test_request(text, img, consumer_key, consumer_secret, access_token, access_token_secret):
    payload = { "text": text }
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    request = requests.post(
        auth=auth, url=url, json=payload, headers={"Content-Type": "application/json"}
    )
    return request

#test_request("Automated Image Test", test_img, consumer_key, consumer_secret, access_token, access_token_secret)