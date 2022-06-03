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

test_img = Image.open(os.path.join(scdir, "Test.png")).convert("RGBA")

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

def post_image(api, text, img):
    try:
        media = api.media_upload(filename=os.path.join(scdir, "Test.png"))
        status = api.update_status(text, media_ids=[media.media_id])
        print(str(status))
    except Exception as ex:
        print("Failed to post image: " + str(ex))


#tw_api = init_twitter()

#post_image(tw_api, "Automated test with image", test_img)


def test_request(text, img, consumer_key, consumer_secret, access_token, access_token_secret):
    payload = { "text": text }
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    request = requests.post(
        auth=auth, url=url, json=payload, headers={"Content-Type": "application/json"}
    )
    return request

#test_request("Automated Image Test", test_img, consumer_key, consumer_secret, access_token, access_token_secret)