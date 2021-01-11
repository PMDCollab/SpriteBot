import sys
import os
import re
import shutil
import math
import struct
import glob
import time
import urllib
import urllib.request
from PIL import Image, ImageDraw, ImageFont
import datetime
import json
from io import BytesIO
import zipfile
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import utils as exUtils

RETRIEVE_HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'}
PORTRAIT_SIZE = 40
PORTRAIT_TILE_X = 5
PORTRAIT_TILE_Y = 8
EMOTIONS = [ "Normal",
            "Happy",
            "Pain",
            "Angry",
            "Worried",
            "Sad",
            "Crying",
            "Shouting",
            "Teary-Eyed",
            "Determined",
            "Joyous",
            "Inspired",
            "Surprised",
            "Dizzy",
            "Special0",
            "Special1",
            "Sigh",
            "Stunned",
            "Special2",
            "Special3" ]

DIRECTIONS = [ "Down",
               "DownRight",
               "Right",
               "UpRight",
               "Up",
               "UpLeft",
               "Left",
               "DownLeft"]

ACTION_MAP = { 0: "Walk",
               1: "Attack",
               5: "Sleep",
               6: "Hurt",
               7: "Idle",
               8: "Swing",
               9: "Double",
               10: "Hop",
               11: "Charge",
               12: "Rotate"
               }

ACTIONS = [ "Idle",
            "Walk",
            "Sleep",
            "Hurt",
            "Attack",
            "Charge",
            "Shoot",
            "Strike",
            "Chop",
            "Scratch",
            "Punch",
            "Slap",
            "Slice",
            "MultiScratch",
            "MultiStrike",
            "Uppercut",
            "Ricochet",
            "Bite",
            "Shake",
            "Jab",
            "Kick",
            "Lick",
            "Slam",
            "Stomp",
            "Appeal",
            "Dance",
            "Twirl",
            "TailWhip",
            "Sing",
            "Sound",
            "Rumble",
            "FlapAround",
            "Gas",
            "Shock",
            "Emit",
            "SpAttack",
            "Withdraw",
            "RearUp",
            "Swell",
            "Swing",
            "Double",
            "Rotate",
            "Hop",
            "Hover",
            "QuickStrike",
            "EventSleep",
            "Wake",
            "Eat",
            "Tumble",
            "Pose",
            "Pull",
            "Pain",
            "Float",
            "DeepBreath",
            "Nod",
            "Sit",
            "LookUp",
            "Sink",
            "Trip",
            "Laying",
            "LeapForth",
            "Head",
            "Cringe",
            "LostBalance",
            "TumbleBack",
            "HitGround",
            "Faint",
            "Fainted",
            "StandingUp",
            "DigIn",
            "DigOut",
            "Wiggle",
            "Yawn",
            "RaiseArms",
            "CarefulWalk",
            "Injured",
            "Jump",
            "Roar",
            "Wave",
            "Cry",
            "Bow",
            "Special0",
            "Special1",
            "Special2",
            "Special3",
            "Special4",
            "Special5",
            "Special6",
            "Special7",
            "Special8",
            "Special9",
            "Special10",
            "Special11",
            "Special12",
            "Special13",
            "Special14",
            "Special15",
            "Special16",
            "Special17",
            "Special18",
            "Special19",
            "Special20",
            "Special21",
            "Special22",
            "Special23",
            "Special24",
            "Special25",
            "Special26",
            "Special27",
            "Special28",
            "Special29",
            "Special30",
            "Special31" ]

ZIP_SIZE_LIMIT = 5000000
DRAW_CENTER_X = 0
DRAW_CENTER_Y = -4


class SpriteVerifyError(Exception):
    def __init__(self, message, preview_img=None):
        self.message = message
        self.preview_img = preview_img
        super().__init__(self.message)


class AnimStat:

    def __init__(self, index, name, size, backref):
        self.index = index
        self.name = name
        self.size = size
        self.backref = backref
        self.durations = []
        self.rushFrame = -1
        self.hitFrame = -1
        self.returnFrame = -1


class FrameOffset:

    def __init__(self, head, lhand, rhand, center):
        self.head = head
        self.lhand = lhand
        self.rhand = rhand
        self.center = center

    def AddLoc(self, loc):
        self.head = exUtils.addLoc(self.head, loc)
        self.lhand = exUtils.addLoc(self.lhand, loc)
        self.rhand = exUtils.addLoc(self.rhand, loc)
        self.center = exUtils.addLoc(self.center, loc)

    def GetBounds(self):
        maxBounds = (10000, 10000, -10000, -10000)
        maxBounds = exUtils.combineExtents(maxBounds, self.getBounds(self.head))
        maxBounds = exUtils.combineExtents(maxBounds, self.getBounds(self.lhand))
        maxBounds = exUtils.combineExtents(maxBounds, self.getBounds(self.rhand))
        maxBounds = exUtils.combineExtents(maxBounds, self.getBounds(self.center))
        return maxBounds

    def getBounds(self, start):
        return (start[0], start[1], start[0] + 1, start[1] + 1)



def isBlank(inImg):
    inData = inImg.getdata()
    for data in inData:
        if data[3] > 0:
            return False
    return True

def comparePalette(img1, img2):
    palette1 = getPalette(img1)
    palette2 = getPalette(img2)

    return len(palette2) - len(palette1)

def comparePixels(img1, img2):
    inData1 = img1.getdata()
    inData2 = img2.getdata()
    diffs = []
    for ii in range(len(inData1)):
        data1 = inData1[ii]
        data2 = inData2[ii]
        if (data1[3] > 0) != (data2[3] > 0):
            diffs.append((ii % img1.size[0], ii // img1.size[0]))

    return diffs

def combineImgs(imgDict):
    max_width = 0
    max_height = 0
    for imgName in ACTIONS:
        if imgName in imgDict:
            img = imgDict[imgName]
            max_width = max_width + img.size[0] + 1
            max_height = max(max_height, img.size[1])
        else:
            max_width = max_width + 1
    max_width = max_width - 1

    outImg = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 255))

    current_width = 0
    for imgName in ACTIONS:
        if imgName in imgDict:
            img = imgDict[imgName]
            outImg.paste(img, (current_width, 0))
            current_width = current_width + img.size[0] + 1
        else:
            current_width = current_width + 1

    return outImg

def combineImgsInDir(path):
    imgDict = {}
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        if ext == '.png':
            inImg = Image.open(os.path.join(path, file)).convert("RGBA")
            imgDict[filename] = inImg

    combinedImg = combineImgs(imgDict)
    outImg = insertPalette(combinedImg)
    outImg.save(os.path.join(path, "Total.png"))

def getPalette(inImg):
    inData = inImg.getdata()
    palette = {}
    for data in inData:
        if data[3] > 0:
            if data not in palette:
                palette[data] = 0
            palette[data] = palette[data]+1
    return palette

def insertPalette(inImg):
    outImg = Image.new('RGBA', (inImg.size[0], inImg.size[1]+1), (0,0,0,0))
    inData = outImg.getdata()
    datas = [(0,0,0,0)] * (outImg.size[0] * outImg.size[1])
    palette = getPalette(inImg)
    paletteNum = 0
    for key in palette:
        datas[paletteNum] = key
        paletteNum = paletteNum + 1
    outImg.putdata(datas)
    outImg.paste(inImg, (0,1))
    return outImg


def xyPlusOne(loc):
    return (loc[0], loc[1]+1)

def removePalette(inImg):
    imgCrop = inImg.crop((0,1,inImg.size[0], inImg.size[1]))
    return imgCrop.convert("RGBA")

def getLinkImg(url):
    full_path, ext = os.path.splitext(url)
    unzip = ext == ".zip"
    _, file = os.path.split(full_path)
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    with urllib.request.urlopen(req) as response:
        if unzip:
            zip_data = BytesIO()
            zip_data.write(response.read())
            zip_data.seek(0)
            with zipfile.ZipFile(zip_data, 'r') as zip:
                img = readZipImg(zip, file + ".png")
        else:
            img = Image.open(response).convert("RGBA")

    return img

def verifyZipFile(zip, file_name):
    info = zip.getinfo(file_name)
    if info.file_size > ZIP_SIZE_LIMIT:
        raise SpriteVerifyError("Zipped file {0} is too large, at {1} bytes.".format(file_name, info.file_size))

def readZipImg(zip, file_name):
    verifyZipFile(zip, file_name)

    file_data = BytesIO()
    file_data.write(zip.read(file_name))
    file_data.seek(0)
    return Image.open(file_data).convert("RGBA")

def getLinkZipGroup(url):
    full_path, ext = os.path.splitext(url)
    _, file = os.path.split(full_path)
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    zip_data = BytesIO()
    with urllib.request.urlopen(req) as response:
        zip_data.write(response.read())
    zip_data.seek(0)

    return zip_data

def getLinkFile(url, asset_type):
    full_path, ext = os.path.splitext(url)
    unzip = ext == ".zip" and asset_type == "portrait"
    _, file = os.path.split(full_path)
    output_file = file + ext

    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    file_data = BytesIO()
    with urllib.request.urlopen(req) as response:
        if unzip:
            zip_data = BytesIO()
            zip_data.write(response.read())
            zip_data.seek(0)
            with zipfile.ZipFile(zip_data, 'r') as zip:
                file_data.write(zip.read(file + ".png"))
                output_file = file + ".png"
        else:
            file_data.write(response.read())

    file_data.seek(0)
    return file_data, output_file

def placeSpriteRecolors(path, outPath, shiny):
    #print(path + " -> " + outPath)
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        if ext == '.png':
            inImg = Image.open(os.path.join(path, file)).convert("RGBA")
            outImg = removePalette(inImg)
            pathParts = filename[:-5].split('-')[1:]
            #print(str(pathParts))
            origPath = os.path.join(outPath, "/".join(pathParts), "animations.xml")
            if shiny:
                if len(pathParts) < 2:
                    pathParts.append('form0')
                if len(pathParts) < 3:
                    pathParts.append('shiny1')
                else:
                    pathParts[2] = 'shiny1'
            destPath = os.path.join(outPath, "/".join(pathParts))
            print(os.path.join(path, file) + " -> " + os.path.join(destPath, "sheet.png"))
            os.makedirs(destPath, exist_ok=True)
            outImg.save(os.path.join(destPath, "sheet.png"))
            if origPath != os.path.join(destPath, "animations.xml"):
                shutil.copyfile(origPath, os.path.join(destPath, "animations.xml"))


def downloadFromUrl(path, sprite_link):
    if sprite_link == '':
        return
    file_name = os.path.join(path, sprite_link.split('/')[-1])
    print("Downloading from " + sprite_link)
    request = urllib.request.Request(sprite_link, None, RETRIEVE_HEADERS)
    with urllib.request.urlopen(request) as response:
        print("Saving to " + file_name)
        with open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    time.sleep(0.5)


"""
File verification
"""

def verifySpriteRecolor(msg_args, orig_zip, wan_zip, recolor):
    raise SpriteVerifyError("Recolor verification not yet implemented.")

def verifyPortraitRecolor(msg_args, orig_img, img, recolor):
    if orig_img.size != img.size:
        raise SpriteVerifyError("Recolor has dimensions {0} instead of {1}.".format(str(img.size), str(orig_img.size)))
    else:
        if recolor:
            orig_img = removePalette(orig_img)
            img = removePalette(img)

        pixDiff = comparePixels(orig_img, img)
        if recolor:
            correctedDiff = [xyPlusOne(x) for x in pixDiff]
        else:
            correctedDiff = pixDiff

        if len(correctedDiff) > 0:
            raise SpriteVerifyError("Recolor has differing pixel opacity at:\n {0}".format(str(correctedDiff)[:1000]))
        else:
            paletteDiff = comparePalette(orig_img, img)
            if paletteDiff != 0:
                if paletteDiff > 0:
                    diff_str = "+" + str(paletteDiff)
                else:
                    diff_str = str(paletteDiff)
                if len(msg_args) == 0 or not msg_args[0] == diff_str:
                    base_str = "Recolor has `{0}` colors compared to the original.\nIf this was intended, resubmit and specify `{0}` in the message."
                    raise SpriteVerifyError(base_str.format(diff_str))
                else:
                    msg_args.pop(0)

def getEmotionFromTilePos(tile_pos):
    rogue_idx = tile_pos[1] * PORTRAIT_TILE_X + tile_pos[0]
    rogue_str = EMOTIONS[rogue_idx % len(EMOTIONS)]
    if rogue_idx // len(EMOTIONS) > 0:
        rogue_str += " Flipped"
    return rogue_str


def mapDuplicateImportImgs(imgs, final_imgs, img_map, offset_diffs):
    map_back = {}
    for idx, img in enumerate(imgs):
        dupe = False
        flip = -1
        for final_idx, final_img in enumerate(final_imgs):
            imgs_equal = exUtils.imgsEqual(final_img[0], img[0])
            # if offsets are not synchronized, they are counted as different
            if imgs_equal:
                imgs_equal = exUtils.offsetsEqual(final_img[1], img[1], img[0].size[0])
                if not imgs_equal:
                    earlier_idx = map_back[final_idx]
                    if earlier_idx not in offset_diffs:
                        offset_diffs[earlier_idx] = []
                    offset_diffs[earlier_idx].append(idx)
            if imgs_equal:
                img_map[idx] = (final_idx, (0, 0))
                dupe = True
                break
            imgs_flip = exUtils.imgsEqual(final_img[0], img[0], True)
            if imgs_flip:
                imgs_flip = exUtils.offsetsEqual(final_img[1], img[1], img[0].size[0], True)
                if not imgs_flip:
                    earlier_idx = map_back[final_idx]
                    if earlier_idx not in offset_diffs:
                        offset_diffs[earlier_idx] = []
                    offset_diffs[earlier_idx].append(idx)
            if imgs_flip:
                flip = final_idx

        if not dupe:
            img_map[idx] = (len(final_imgs), (0, 0))
            map_back[len(final_imgs)] = idx
            final_imgs.append((img[0], img[1], img[2], flip))


def verifySprite(msg_args, wan_zip):
    anim_stats = {}
    anim_names = {}

    frames = []
    palette = {}
    frameToSequence = []
    rogue_pixels = []
    with zipfile.ZipFile(wan_zip, 'r') as zip:
        name_list = zip.namelist()
        if 'AnimData.xml' not in name_list:
            raise SpriteVerifyError("No AnimData.xml found.")
        verifyZipFile(zip, 'AnimData.xml')

        file_data = BytesIO()
        file_data.write(zip.read('AnimData.xml'))
        file_data.seek(0)

        tree = ET.parse(file_data)
        root = tree.getroot()
        sdwSize = int(root.find('ShadowSize').text)
        if sdwSize < 0 or sdwSize > 2:
            raise SpriteVerifyError("Invalid shadow size: {0}".format(sdwSize))
        anims_node = root.find('Anims')
        for anim_node in anims_node.iter('Anim'):
            name = anim_node.find('Name').text
            # verify all names are real
            if name not in ACTIONS:
                raise SpriteVerifyError("Invalid anim name '{0}' in XML.".format(name))
            index = -1
            index_node = anim_node.find('Index')
            if index_node is not None:
                index = int(index_node.text)
            backref_node = anim_node.find('CopyOf')
            if backref_node is not None:
                backref = backref_node.text
                anim_stat = AnimStat(index, name, None, backref)
            else:
                frame_width = anim_node.find('FrameWidth')
                frame_height = anim_node.find('FrameHeight')
                anim_stat = AnimStat(index, name, (int(frame_width.text), int(frame_height.text)), None)

                rush_frame = anim_node.find('RushFrame')
                if rush_frame is not None:
                    anim_stat.rushFrame = int(rush_frame.text)
                hit_frame = anim_node.find('HitFrame')
                if hit_frame is not None:
                    anim_stat.hitFrame = int(hit_frame.text)
                return_frame = anim_node.find('ReturnFrame')
                if return_frame is not None:
                    anim_stat.returnFrame = int(return_frame.text)

                durations_node = anim_node.find('Durations')
                for dur_node in durations_node.iter('Duration'):
                    duration = int(dur_node.text)
                    anim_stat.durations.append(duration)

                if name.lower() in anim_names:
                    raise SpriteVerifyError("Anim '{0}' is specified twice in XML!".format(name))
                anim_names[name.lower()] = index
                if index == -1:
                    raise SpriteVerifyError("{0} has its own sheet and does not have an index!".format(name))

            if index > -1:
                if index in anim_stats:
                    raise SpriteVerifyError(
                        "{0} and {1} both have the an index of {2}!".format(anim_stats[index].name, name, index))
                anim_stats[index] = anim_stat

        for name in name_list:
            if name.endswith('.png'):
                anim_name = name.split('-')[0].lower()
                if anim_name not in anim_names:
                    raise SpriteVerifyError("Unexpected Anim file: {0}".format(name))
            elif name.endswith('.xml'):
                pass
            else:
                raise SpriteVerifyError("Unexpected File {0}".format(name))

        # verify internal indices 1-13 exist?
        missing_anims = []
        for idx in range(2):
            if ACTIONS[idx].lower() not in anim_names:
                missing_anims.append(ACTIONS[idx])
        if len(missing_anims) > 0:
            raise SpriteVerifyError("Missing required anims:\n{0}".format(', '.join(missing_anims)))
        violated_idx = []
        for idx in ACTION_MAP:
            anim_stat = anim_stats[idx]
            if anim_stat.name != ACTION_MAP[idx]:
                violated_idx.append(ACTION_MAP[idx] + ' -> ' + str(idx))
        if len(violated_idx) > 0:
            raise SpriteVerifyError("Some anims are required to have specific indices:\n{0}".format('\n'.join(violated_idx)))

        for anim_idx in anim_stats:
            anim_stat = anim_stats[anim_idx]
            if anim_stat.backref is not None:
                continue
            anim_name = anim_stat.name
            anim_png_name = anim_name + "-Anim.png"
            offset_png_name = anim_name + "-Offsets.png"
            shadow_png_name = anim_name + "-Shadow.png"
            if anim_png_name not in name_list:
                raise SpriteVerifyError("Anim specified in XML has no Anim.png: {0}".format(anim_name))
            if offset_png_name not in name_list:
                raise SpriteVerifyError("Anim specified in XML has no Offsets.png: {0}".format(anim_name))
            if shadow_png_name not in name_list:
                raise SpriteVerifyError("Anim specified in XML has no Shadow.png: {0}".format(anim_name))

            anim_img = readZipImg(zip, anim_png_name)
            offset_img = readZipImg(zip, offset_png_name)
            shadow_img = readZipImg(zip, shadow_png_name)

            tileSize = anim_stat.size
            durations = anim_stat.durations

            # check against inconsistent sizing
            if anim_img.size != offset_img.size or anim_img.size != shadow_img.size:
                raise SpriteVerifyError("Anim, Offset, and Shadow sheets for {0} must be the same size!".format(anim_name))

            if anim_img.size[0] % tileSize[0] != 0 or anim_img.size[1] % tileSize[1] != 0:
                raise SpriteVerifyError("Sheet for {4} is {0}x{1} pixels and is not divisible by {2}x{3} in xml!".format(
                    anim_img.size[0], anim_img.size[1], tileSize[0], tileSize[1], anim_name))

            total_frames = anim_img.size[0] // tileSize[0]
            total_dirs = anim_img.size[1] // tileSize[1]
            if total_dirs != 1 and total_dirs != 8:
                raise SpriteVerifyError("Sheet for {0} must be one-directional or 8-directional!".format(anim_name))
            # check against inconsistent duration counts
            if total_frames != len(durations):
                raise SpriteVerifyError("Number of frames in {0} does not match count of durations ({1}) specified in xml!".format(anim_name, len(durations)))

            if anim_stat.rushFrame >= len(durations):
                raise SpriteVerifyError("RushFrame of {0} is greater than the number of frames ({1}) in {2}!".format(anim_stat.rushFrame, len(durations), anim_name))
            if anim_stat.hitFrame >= len(durations):
                raise SpriteVerifyError("HitFrame of {0} is greater than the number of frames ({1}) in {2}!".format(anim_stat.hitFrame, len(durations), anim_name))
            if anim_stat.returnFrame >= len(durations):
                raise SpriteVerifyError("ReturnFrame of {0} is greater than the number of frames ({1}) in {2}!".format(anim_stat.returnFrame, len(durations), anim_name))

            datas = anim_img.getdata()
            for xx in range(anim_img.size[0]):
                for yy in range(anim_img.size[1]):
                    cur_pixel = datas[yy * anim_img.size[0] + xx]
                    cur_occupied = (cur_pixel[3] > 0)
                    if cur_occupied and cur_pixel[3] < 255:
                        rogue_pixels.append((xx, yy))
                    else:
                        if cur_pixel not in palette:
                            palette[cur_pixel] = 0
                        palette[cur_pixel] += 1

            total_dirs = anim_img.size[1] // tileSize[1]
            for dir in range(8):
                if dir >= total_dirs:
                    break
                for jj in range(anim_img.size[0] // tileSize[0]):
                    rel_center = (tileSize[0] // 2 - DRAW_CENTER_X, tileSize[1] // 2 - DRAW_CENTER_Y)
                    tile_rect = (jj * tileSize[0], dir * tileSize[1], tileSize[0], tileSize[1])
                    tile_bounds = (tile_rect[0], tile_rect[1], tile_rect[0] + tile_rect[2], tile_rect[1] + tile_rect[3])
                    bounds = exUtils.getCoveredBounds(anim_img, tile_bounds)
                    emptyBounds = False
                    if bounds[0] >= bounds[2]:
                        bounds = (rel_center[0], rel_center[1], rel_center[0]+1, rel_center[1]+1)
                        emptyBounds = True
                    rect = (bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1])
                    abs_bounds = exUtils.addToBounds(bounds, (tile_rect[0], tile_rect[1]))
                    frame_tex = anim_img.crop(abs_bounds)

                    try:
                        shadow_offset = exUtils.getOffsetFromRGB(shadow_img, tile_bounds, False, False, False, False, True)
                        frame_offset = exUtils.getOffsetFromRGB(offset_img, tile_bounds, True, True, True, True, False)
                    except exUtils.MultipleOffsetError as e:
                        raise SpriteVerifyError(e.message + '\n' + str((anim_name, DIRECTIONS[dir], jj)))

                    if emptyBounds and shadow_offset[4] is None and frame_offset[2] is None:
                        continue

                    offsets = FrameOffset(None, None, None, None)
                    if frame_offset[2] is None:
                        # raise warning if there's missing shadow or offsets
                        raise SpriteVerifyError("No frame offset found in frame {0} for {1}".format((DIRECTIONS[dir], jj), anim_name))
                    else:
                        offsets.center = frame_offset[2]
                        if frame_offset[0] is None:
                            offsets.head = frame_offset[2]
                        else:
                            offsets.head = frame_offset[0]
                        offsets.lhand = frame_offset[1]
                        offsets.rhand = frame_offset[3]
                    offsets.AddLoc((-rect[0], -rect[1]))

                    shadow = rel_center
                    if shadow_offset[4] is not None:
                        shadow = shadow_offset[4]
                    else:
                        raise SpriteVerifyError("No shadow offset found in frame {0} for {1}".format((jj, dir), anim_name))
                    shadow_diff = exUtils.addLoc(shadow, rect, True)

                    frames.append((frame_tex, offsets, shadow_diff))
                    frameToSequence.append((anim_name, DIRECTIONS[dir], jj))

    # check for semitransparent pixels
    if len(rogue_pixels) > 0:
        raise SpriteVerifyError("Semi-transparent pixels found at: {0}".format(str(rogue_pixels)[:1900]))

    offset_diffs = {}
    frame_map = [None] * len(frames)
    final_frames = []
    mapDuplicateImportImgs(frames, final_frames, frame_map, offset_diffs)
    if len(offset_diffs) > 0:
        escape_clause = len(msg_args) > 0 and msg_args[0] == "multioffset"
        if escape_clause:
            msg_args.pop(0)
        else:
            offset_diff_names = []
            for orig_idx in offset_diffs:
                offset_group = [frameToSequence[orig_idx]]
                for idx in offset_diffs[orig_idx]:
                    offset_group.append(frameToSequence[idx])
                offset_diff_names.append(offset_group)

            raise SpriteVerifyError("Some frames have identical sprites but different offsets.\n"
                                    "If this is acceptable, include `multioffset` in the message."
                                    "  Otherwise make these frame offsets consistent:\n{0}".format(str(offset_diff_names)[:1900]))

    # then, check the colors
    if len(palette) > 15:
        escape_clause = len(msg_args) > 0 and msg_args[0] == "=" + str(len(palette))
        if escape_clause:
            msg_args.pop(0)
        else:
            max_size = 0
            for frame_info in final_frames:
                frame_tex = frame_info[0]
                max_size = max(max_size, frame_tex.size[0])
                max_size = max(max_size, frame_tex.size[1])

            max_size = exUtils.roundUpToMult(max_size, 2)

            total_tile_width = 8
            total_tile_height = (len(final_frames) - 1) // 8 + 1

            combinedImg = Image.new('RGBA', (max_size * total_tile_width, max_size * total_tile_height), (0, 0, 0, 0))

            for idx, frame_info in enumerate(final_frames):
                frame = frame_info[0]
                xx = idx % total_tile_width
                yy = idx // total_tile_width
                tilePos = (xx * max_size, yy * max_size)
                centerPos = ((max_size - frame.size[0]) // 2, (max_size - frame.size[1]) // 2)
                combinedImg.paste(frame, (tilePos[0] + centerPos[0], tilePos[1] + centerPos[1]), frame)

            reduced_img = simple_quant(combinedImg)
            raise SpriteVerifyError("The sprite has {0} non-transparent colors with only 15 allowed.\n"
                                    "If this is acceptable, include `={0}` in the message."
                                    "  Otherwise reduce colors for the sprite.".format(len(palette)), reduced_img)


def verifyPortrait(msg_args, img):
    # make sure the dimensions are sound
    if img.size[0] % PORTRAIT_SIZE != 0 or img.size[1] % PORTRAIT_SIZE != 0:
        raise SpriteVerifyError("Portrait has an invalid size of {0}, Not divisble by {1}x{1}".format(str(img.size), PORTRAIT_SIZE))

    img_tile_size = (img.size[0] // PORTRAIT_SIZE, img.size[1] // PORTRAIT_SIZE)
    max_size = (PORTRAIT_TILE_X * PORTRAIT_SIZE, PORTRAIT_TILE_Y * PORTRAIT_SIZE)
    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
        raise SpriteVerifyError("Portrait has an invalid size of {0}, exceeding max of {1}".format(str(img.size), str(max_size)))

    in_data = img.getdata()
    occupied = [[]] * PORTRAIT_TILE_X
    for ii in range(PORTRAIT_TILE_X):
        occupied[ii] = [False] * PORTRAIT_TILE_Y

    # iterate every portrait and ensure that all pixels in that portrait are either solid or transparent
    rogue_pixels = []
    rogue_tiles = []
    palette_counts = {}
    for xx in range(PORTRAIT_TILE_X):
        for yy in range(PORTRAIT_TILE_Y):
            if xx >= img_tile_size[0] or yy >= img_tile_size[1]:
                continue
            first_pos = (xx * PORTRAIT_SIZE, yy * PORTRAIT_SIZE)
            first_pixel = in_data[first_pos[1] * img.size[0] + first_pos[0]]
            occupied[xx][yy] = (first_pixel[3] > 0)

            palette = {}
            is_rogue = False
            for mx in range(PORTRAIT_SIZE):
                for my in range(PORTRAIT_SIZE):
                    cur_pos = (first_pos[0] + mx, first_pos[1] + my)
                    cur_pixel = in_data[cur_pos[1] * img.size[0] + cur_pos[0]]
                    palette[cur_pixel] = True
                    cur_occupied = (cur_pixel[3] > 0)
                    if cur_occupied and cur_pixel[3] < 255:
                        rogue_pixels.append(cur_pos)
                    if cur_occupied != occupied[xx][yy]:
                        is_rogue = True
                        break
                if is_rogue:
                    break
            if is_rogue:
                rogue_tiles.append((xx, yy))
            palette_counts[(xx, yy)] = len(palette)


    if len(rogue_pixels) > 0:
        raise SpriteVerifyError("Semi-transparent pixels found at: {0}".format(str(rogue_pixels)[:1900]))
    if len(rogue_tiles) > 0:
        rogue_emotes = [getEmotionFromTilePos(a) for a in rogue_tiles]
        raise SpriteVerifyError("The following emotions have transparent pixels: {0}".format(str(rogue_emotes)[:1900]))

    overpalette = { }
    for emote_loc in palette_counts:
        if palette_counts[emote_loc] > 15:
            overpalette[emote_loc] = palette_counts[emote_loc]

    if len(overpalette) > 0:
        escape_clause = len(msg_args) > 0 and msg_args[0] == "overcolor"
        if escape_clause:
            msg_args.pop(0)
        else:
            reduced_img = img.copy()
            for emote_loc in overpalette:
                crop_pos = (emote_loc[0] * PORTRAIT_SIZE, emote_loc[1] * PORTRAIT_SIZE,
                            (emote_loc[0] + 1) * PORTRAIT_SIZE, (emote_loc[1] + 1) * PORTRAIT_SIZE)
                portrait_img = reduced_img.crop(crop_pos)

                reduced_portrait = simple_quant(portrait_img)
                reduced_img.paste(reduced_portrait, crop_pos)

            rogue_emotes = [getEmotionFromTilePos(a) for a in overpalette]
            raise SpriteVerifyError("Some emotions have over 15 colors.\n" \
                   "If this is acceptable, include `overcolor` in the message.  Otherwise reduce colors for emotes:\n" \
                   "{0}".format(str(rogue_emotes)[:1900]), reduced_img)

    # make sure all mirrored emotions have their original emotions
    # make sure if there is one mirrored emotion, there is all mirrored emotions
    halfway = PORTRAIT_TILE_Y // 2
    flipped_tiles = []
    has_one_flip = False
    has_missing_original = False
    for xx in range(PORTRAIT_TILE_X):
        for yy in range(halfway, PORTRAIT_TILE_Y):
            if occupied[xx][yy]:
                has_one_flip = True
            if occupied[xx][yy] != occupied[xx][yy-halfway]:
                rogue_str = getEmotionFromTilePos((xx, yy))
                flipped_tiles.append(rogue_str)
                if not occupied[xx][yy-halfway]:
                    has_missing_original = True

    if has_one_flip and len(flipped_tiles) > 0:
        escape_clause = len(msg_args) > 0 and msg_args[0] == "noflip"
        if escape_clause:
            msg_args.pop(0)

        if has_missing_original:
            raise SpriteVerifyError("File has a flipped emotion when the original is missing.")
        if not escape_clause:
            raise SpriteVerifyError("File is missing some flipped emotions." \
                   "If you want to submit incomplete, include `noflip` in the message.")



def verifyPortraitFilled(species_path):
    for name in EMOTIONS:
        if name.startswith("Special"):
            continue
        full_path = os.path.join(species_path, name + ".png")
        if not os.path.exists(full_path):
            return False

    return True

"""
File data writeback
"""

def placeSpriteZipToPath(wan_file, dest_path):
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
    else:
        # delete existing files
        existing_files = os.listdir(dest_path)
        for file in existing_files:
            if file.endswith(".png") or file.endswith(".xml"):
                os.remove(os.path.join(dest_path, file))

    # extract all
    with zipfile.ZipFile(wan_file, 'r') as zip:
        zip.extractall(path=dest_path)

def placeSpriteRecolorToPath(origImg, orig_path, outImg, dest_path):
    # remove palette bar of both images
    origImg = origImg.crop((0, 1, origImg.size[0], origImg.size[1]))
    outImg = outImg.crop((0, 1, outImg.size[0], outImg.size[1]))
    # obtain a mapping from the color image of the shiny path
    shiny_frames = []
    total_tile_width = 8
    max_size = outImg.size[0] // total_tile_width
    for yy in range(0, outImg.size[1], max_size):
        for xx in range(0, outImg.size[0], max_size):
            tile_bounds = (xx, yy, xx + max_size, yy + max_size)
            bounds = exUtils.getCoveredBounds(outImg, tile_bounds)
            if bounds[0] >= bounds[2]:
                continue
            abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
            frame_tex = outImg.crop(abs_bounds)
            shiny_frames.append(frame_tex)

    frames, frame_mapping = getFramesAndMappings(orig_path)

    for anim_name in frame_mapping:
        img_path = os.path.join(dest_path, anim_name + '-Anim.png')
        prev_img = Image.open(img_path).convert("RGBA")
        img = Image.new('RGBA', prev_img.size, (0, 0, 0, 0))
        for abs_bounds in frame_mapping[anim_name]:
            frame_idx, flip = frame_mapping[anim_name][abs_bounds]
            imgPiece = shiny_frames[frame_idx]
            if flip:
                imgPiece = imgPiece.transpose(Image.FLIP_LEFT_RIGHT)
            img.paste(imgPiece, (abs_bounds[0], abs_bounds[1]), imgPiece)
        img.save(img_path)


def placePortraitToPath(outImg, dest_path):
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
    else:
        # delete existing files
        existing_files = os.listdir(dest_path)
        for file in existing_files:
            if file.endswith(".png"):
                os.remove(os.path.join(dest_path, file))

    # add new ones
    for idx in range(len(EMOTIONS)):
        placeX = PORTRAIT_SIZE * (idx % PORTRAIT_TILE_X)
        placeY = PORTRAIT_SIZE * (idx // PORTRAIT_TILE_X)
        if placeX < outImg.size[0] and placeY < outImg.size[1]:
            imgCrop = outImg.crop((placeX,placeY,placeX+PORTRAIT_SIZE,placeY+PORTRAIT_SIZE))
            if not isBlank(imgCrop):
                imgCrop.save(os.path.join(dest_path, EMOTIONS[idx]+".png"))
        # check flips
        placeY += 4 * PORTRAIT_SIZE
        if placeX < outImg.size[0] and placeY < outImg.size[1]:
            imgCrop = outImg.crop((placeX,placeY,placeX+PORTRAIT_SIZE,placeY+PORTRAIT_SIZE))
            if not isBlank(imgCrop):
                imgCrop.save(os.path.join(dest_path, EMOTIONS[idx]+"^.png"))

"""
File data generation
"""

"""
Returns file-like object
"""
def prepareSpriteZip(path):
    asset_files = []
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        full_file = os.path.join(path, file)
        if os.path.isdir(full_file):
            continue
        elif ext == '.png' or ext == '.xml':
            asset_files.append(file)

    fileData = BytesIO()
    with zipfile.ZipFile(fileData,'w') as zip:
        # writing each file one by one
        for file in asset_files:
            full_file = os.path.join(path, file)
            zip.write(full_file, arcname=file)
    return fileData

def getFramesAndMappings(path):
    anim_dims = {}
    tree = ET.parse(os.path.join(path, 'AnimData.xml'))
    root = tree.getroot()
    anims_node = root.find('Anims')
    for anim_node in anims_node.iter('Anim'):
        name = anim_node.find('Name').text
        backref_node = anim_node.find('CopyOf')
        if backref_node is None:
            frame_width = anim_node.find('FrameWidth')
            frame_height = anim_node.find('FrameHeight')
            anim_dims[name] = (int(frame_width.text), int(frame_height.text))

    frames = []
    frame_mapping = {}
    for anim_name in anim_dims:
        anim_map = {}
        frame_size = anim_dims[anim_name]
        img = Image.open(os.path.join(path, anim_name + '-Anim.png')).convert("RGBA")

        for yy in range(0, img.size[1], frame_size[1]):
            for xx in range(0, img.size[0], frame_size[0]):
                tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
                bounds = exUtils.getCoveredBounds(img, tile_bounds)
                if bounds[0] >= bounds[2]:
                    continue
                abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
                frame_tex = img.crop(abs_bounds)
                isDupe = False
                for idx, frame in enumerate(frames):
                    if exUtils.imgsEqual(frame, frame_tex):
                        anim_map[abs_bounds] = (idx, False)
                        isDupe = True
                        break
                    if exUtils.imgsEqual(frame, frame_tex, True):
                        anim_map[abs_bounds] = (idx, True)
                        isDupe = True
                        break
                if not isDupe:
                    anim_map[abs_bounds] = (len(frames), False)
                    frames.append(frame_tex)

        frame_mapping[anim_name] = anim_map
    return frames, frame_mapping

def prepareSpriteRecolor(path):

    max_size = 0
    frames, frame_mapping = getFramesAndMappings(path)
    for frame_tex in frames:
        max_size = max(max_size, frame_tex.size[0])
        max_size = max(max_size, frame_tex.size[1])

    max_size = exUtils.roundUpToMult(max_size, 2)

    total_tile_width = 8
    total_tile_height = (len(frames) - 1) // 8 + 1

    combinedImg = Image.new('RGBA', (max_size * total_tile_width, max_size * total_tile_height), (0, 0, 0, 0))

    for idx, frame in enumerate(frames):
        xx = idx % total_tile_width
        yy = idx // total_tile_width
        tilePos = (xx * max_size, yy * max_size)
        centerPos = ((max_size - frame.size[0]) // 2, (max_size - frame.size[1]) // 2)
        combinedImg.paste(frame, (tilePos[0] + centerPos[0], tilePos[1] + centerPos[1]), frame)

    combinedImg = insertPalette(combinedImg)
    return combinedImg

"""
Returns Image
"""
def preparePortraitImage(path):
    printImg = Image.new('RGBA', (PORTRAIT_SIZE * 5, PORTRAIT_SIZE * 8), (0, 0, 0, 0))
    maxX = 0
    maxY = 0
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        if ext == '.png':
            for idx in range(len(EMOTIONS)):
                use = False
                flip = False
                if EMOTIONS[idx] == filename:
                    use = True
                elif EMOTIONS[idx] + "^" == filename:
                    use = True
                    flip = True

                if use:
                    inImg = Image.open(os.path.join(path, file)).convert("RGBA")
                    placeX = PORTRAIT_SIZE * (idx % 5)
                    placeY = PORTRAIT_SIZE * (idx // 5)
                    # handle flips
                    if flip:
                        placeY += 4 * PORTRAIT_SIZE
                    printImg.paste(inImg, (placeX, placeY))
                    maxX = max(maxX, placeX + PORTRAIT_SIZE)
                    maxY = max(maxY, placeY + PORTRAIT_SIZE)
                    break

    if maxX > 0 and maxY > 0:
        outImg = printImg.crop((0,0,maxX, maxY))
        return outImg
    return None

def preparePortraitRecolor(path):
    portraitImg = preparePortraitImage(path)
    portraitImg = insertPalette(portraitImg)
    return portraitImg

"""
Assumes that the data path is always valid.
Returns file handle and an extension for the file format
"""
def generateFileData(path, asset_type, recolor):
    if asset_type == "portrait":
        if recolor:
            portraitImg = preparePortraitRecolor(path)
        else:
            portraitImg = preparePortraitImage(path)
        fileData = BytesIO()
        portraitImg.save(fileData, format='PNG')
        return fileData, ".png"
    elif asset_type == "sprite":
        if recolor:
            spriteImg = prepareSpriteRecolor(path)
            fileData = BytesIO()
            spriteImg.save(fileData, format='PNG')
            return fileData, ".png"
        else:
            spriteZip = prepareSpriteZip(path)
            return spriteZip, ".zip"


def getFileCredits(path):
    id_list = []
    with open(os.path.join(path, "credits.txt"), 'r', encoding='utf-8') as txt:
        for line in txt:
            id_list.append(line.strip().split('\t'))
    return id_list

def appendCredits(path, id):
    with open(os.path.join(path, "credits.txt"), 'a+', encoding='utf-8') as txt:
        txt.write(str(datetime.datetime.utcnow()) + "\t" + id + "\n")

class CreditEntry:
    """
    A class for handling recolors
    """
    def __init__(self, name, contact):
        self.name = name
        self.sprites = False
        self.portraits = False
        self.contact = contact

class TrackerNode:

    def __init__(self, node_dict):
        temp_list = [i for i in node_dict]
        temp_list = sorted(temp_list)

        main_dict = { }
        for key in temp_list:
            main_dict[key] = node_dict[key]

        self.__dict__ = main_dict

        sub_dict = { }
        for key in self.subgroups:
            sub_dict[key] = TrackerNode(self.subgroups[key])
        self.subgroups = sub_dict

    def getDict(self):
        node_dict = { }
        for k in self.__dict__:
            node_dict[k] = self.__dict__[k]
        sub_dict = { }
        for sub_idx in self.subgroups:
            sub_dict[sub_idx] = self.subgroups[sub_idx].getDict()
        node_dict["subgroups"] = sub_dict
        return node_dict

def loadNameFile(name_path):
    name_dict = { }
    first = True
    with open(name_path, encoding='utf-8') as txt:
        for line in txt:
            if first:
                first = False
                continue
            cols = line[:-1].split('\t')
            name_dict[cols[1]] = CreditEntry(cols[0], cols[2])
    return name_dict

def initSubNode(name):
    sub_dict = { "name" : name }
    sub_dict["portrait_complete"] = 0
    sub_dict["portrait_credit"] = ""
    sub_dict["portrait_link"] = ""
    sub_dict["portrait_files"] = []
    sub_dict["portrait_modified"] = ""
    sub_dict["portrait_pending"] = {}
    sub_dict["portrait_recolor_link"] = ""
    sub_dict["portrait_required"] = False
    sub_dict["sprite_complete"] = 0
    sub_dict["sprite_credit"] = ""
    sub_dict["sprite_files"] = []
    sub_dict["sprite_link"] = ""
    sub_dict["sprite_modified"] = ""
    sub_dict["sprite_pending"] = {}
    sub_dict["sprite_recolor_link"] = ""
    sub_dict["sprite_required"] = False
    sub_dict["subgroups"] = {}
    return TrackerNode(sub_dict)


def getFiles(path):
    full_list = []
    for inFile in os.listdir(path):
        fullPath = os.path.join(path, inFile)
        if os.path.isdir(fullPath):
            pass
        elif inFile == "credits.txt":
            pass
        else:
            full_list.append(inFile)
    return full_list

def fileSystemToJson(dict, species_path, prefix, tier):
    # get last modify date of everything that isn't credits.txt or dirs
    last_modify = ""
    dict.__dict__[prefix + "_files"] = []
    for inFile in os.listdir(species_path):
        fullPath = os.path.join(species_path, inFile)
        if os.path.isdir(fullPath):
            if inFile not in dict.subgroups:
                # init name if applicable
                if tier == 1:
                    if inFile == "0000":
                        dict.subgroups[inFile] = initSubNode("")
                    else:
                        dict.subgroups[inFile] = initSubNode("Form" + inFile)
                elif tier == 2:
                    if inFile == "0001":
                        dict.subgroups[inFile] = initSubNode("Shiny")
                    else:
                        dict.subgroups[inFile] = initSubNode("")
                elif tier == 3:
                    if inFile == "0001":
                        dict.subgroups[inFile] = initSubNode("Male")
                    elif inFile == "0002":
                        dict.subgroups[inFile] = initSubNode("Female")
                    else:
                        dict.subgroups[inFile] = initSubNode("")

            fileSystemToJson(dict.subgroups[inFile], fullPath, prefix, tier + 1)
        elif inFile == "credits.txt":
            last_line = ""
            with open(fullPath, encoding='utf-8') as txt:
                for line in txt:
                    last_line = line
            last_credit = last_line[:-1].split('\t')
            dict.__dict__[prefix + "_credit"] = last_credit[1]
        else:
            modify_datetime = datetime.datetime.utcfromtimestamp(os.path.getmtime(fullPath))
            if str(modify_datetime) > last_modify:
                last_modify = str(modify_datetime)
            dict.__dict__[prefix + "_files"].append(inFile)

    updated = False
    if dict.__dict__[prefix + "_modified"] < last_modify:
        dict.__dict__[prefix + "_modified"] = last_modify
        updated = True

    # the link always starts off blank, or is set to blank when last-modified is updated
    if updated:
        dict.__dict__[prefix + "_link"] = ""

def isDataPopulated(sub_dict):
    if sub_dict.sprite_credit != "":
        return True
    if sub_dict.portrait_credit != "":
        return True

    for sub_idx in sub_dict.subgroups:
        if isDataPopulated(sub_dict.subgroups[sub_idx]):
            return True
    return False

def getIdxName(tracker_dict, full_idx):
    if len(full_idx) == 0:
        return []
    if full_idx[0] not in tracker_dict:
        return []
    node = tracker_dict[full_idx[0]]
    if node.name == "":
        return getIdxName(node.subgroups, full_idx[1:])
    else:
        return [node.name] + getIdxName(node.subgroups, full_idx[1:])


def findSlotIdx(sub_dict, name):
    for idx in sub_dict:
        if sub_dict[idx].name.lower() == name.lower():
            return idx
    return None

def iterateTracker(tracker_dict, func, full_idx):
    for idx in tracker_dict:
        node = tracker_dict[idx]

        full_idx.append(idx)
        func(full_idx)
        sub_dict = node.subgroups
        iterateTracker(sub_dict, func, full_idx)
        full_idx.pop()

def findFullTrackerIdx(tracker_dict, name_args, depth):
    # base case
    if depth >= len(name_args):
        return []

    # recursive case
    blank_idx = None
    for idx in tracker_dict:
        if tracker_dict[idx].name.lower() == name_args[depth].lower():
            sub_dict = tracker_dict[idx].subgroups
            full_idx = findFullTrackerIdx(sub_dict, name_args, depth+1)
            if full_idx is None:
                return None
            else:
                return [idx] + full_idx
        elif tracker_dict[idx].name == "":
            blank_idx = idx
    # didn't find any name matches, check if the base name is blank
    if blank_idx is not None:
        full_idx = findFullTrackerIdx(tracker_dict[blank_idx].subgroups, name_args, depth)
        if full_idx is None:
            return None
        else:
            return [blank_idx] + full_idx
    # otherwise, it means we just can't find it
    return None

def isShinyIdx(full_idx):
    if len(full_idx) < 3:
        return False
    return full_idx[2] == "0001"

def createShinyIdx(full_idx, shiny):
    new_idx = [i for i in full_idx]
    if len(new_idx) < 3 and not shiny:
        return new_idx

    while len(new_idx) < 3:
        new_idx.append("0000")

    if shiny:
        new_idx[2] = "0001"
    else:
        new_idx[2] = "0000"

    while len(new_idx) > 1 and new_idx[-1] == "0000":
        new_idx.pop()
    return new_idx

def getNodeFromIdx(tracker_dict, full_idx, depth):
    if full_idx is None:
        return None
    if len(full_idx) == 0:
        return None
    if full_idx[depth] not in tracker_dict:
        return None

    # base case
    node = tracker_dict[full_idx[depth]]
    if depth == len(full_idx) - 1:
        return node

    # recursive case, kind of weird
    return getNodeFromIdx(node.subgroups, full_idx, depth+1)

def getStatsFromFilename(filename):
    # attempt to parse the filename to a destination
    file, ext = os.path.splitext(filename)
    name_idx = file.split("-")
    prefix = name_idx[0].split("_")

    asset_type = prefix[0]
    recolor = "_".join(prefix[1:])

    if asset_type != "sprite" and asset_type != "portrait":
        return False, None, None, None
    if recolor != "" and recolor != "recolor":
        return False, None, None, None

    if len(name_idx) < 2:
        return False, None, None, None

    full_idx = name_idx[1:]
    return True, full_idx, asset_type, recolor == "recolor"

def genderDiffExists(form_dict, asset_type):
    if "0000" not in form_dict.subgroups:
        return False
    normal_dict = form_dict.subgroups["0000"].subgroups
    female_idx = findSlotIdx(normal_dict, "Female")
    if female_idx is None:
        return False
    female_dict = normal_dict[female_idx]

    return female_dict.__dict__[asset_type + "_required"]

def genderDiffPopulated(form_dict, asset_type):
    if "0000" not in form_dict.subgroups:
        return False
    normal_dict = form_dict.subgroups["0000"].subgroups
    female_idx = findSlotIdx(normal_dict, "Female")
    if female_idx is None:
        return False
    female_dict = normal_dict[female_idx]

    return female_dict.__dict__[asset_type + "_credit"] != ""

def createGenderDiff(form_dict, asset_type):
    if "0000" not in form_dict.subgroups:
        form_dict.subgroups["0000"] = initSubNode("")
    normal_dict = form_dict.subgroups["0000"].subgroups
    createColorGenderDiff(normal_dict, asset_type)

    shiny_dict = form_dict.subgroups["0001"].subgroups
    createColorGenderDiff(shiny_dict, asset_type)

def createColorGenderDiff(color_dict, asset_type):
    female_idx = findSlotIdx(color_dict, "Female")
    if female_idx is None:
        female_dict = initSubNode("Female")
        color_dict["0002"] = female_dict
    else:
        female_dict = color_dict[female_idx]
    female_dict.__dict__[asset_type + "_required"] = True


def removeGenderDiff(form_dict, asset_type):
    normal_dict = form_dict.subgroups["0000"].subgroups
    nothing_left = removeColorGenderDiff(normal_dict, asset_type)
    if nothing_left:
        del form_dict.subgroups["0000"]

    shiny_dict = form_dict.subgroups["0001"].subgroups
    removeColorGenderDiff(shiny_dict, asset_type)

def removeColorGenderDiff(color_dict, asset_type):
    # return whether or not the gender was fully deleted
    female_idx = findSlotIdx(color_dict, "Female")
    if female_idx is None:
        return True

    female_dict = color_dict[female_idx]
    female_dict.__dict__[asset_type + "_required"] = False
    if not female_dict.__dict__["sprite_required"] and not female_dict.__dict__["portrait_required"]:
        del color_dict[female_idx]
        return True

    return False

def createFormNode(name):
    forme_dict = initSubNode(name)
    forme_dict.sprite_required = True
    forme_dict.portrait_required = True
    shiny_dict = initSubNode("Shiny")
    forme_dict.subgroups["0001"] = shiny_dict
    shiny_dict.sprite_required = True
    shiny_dict.portrait_required = True
    return forme_dict

def createSpeciesNode(name):

    sub_dict = initSubNode(name)
    sub_dict.sprite_required = True
    sub_dict.portrait_required = True
    forme_dict = initSubNode("")
    sub_dict.subgroups["0000"] = forme_dict
    shiny_dict = initSubNode("Shiny")
    forme_dict.subgroups["0001"] = shiny_dict
    shiny_dict.sprite_required = True
    shiny_dict.portrait_required = True
    return sub_dict

def clearSubmissions(node):
    node.sprite_pending = { }
    node.portrait_pending = { }

    for sub_idx in node.subgroups:
        clearSubmissions(node.subgroups[sub_idx])

"""
Name operations
"""
def updateNameFile(name_path, name_dict, include_all):
    with open(name_path, 'w+', encoding='utf-8') as txt:
        txt.write("Name\tDiscord\tContact\n")
        for handle in name_dict:
            if include_all or name_dict[handle].sprites or name_dict[handle].portraits:
                txt.write("{0}\t{1}\t{2}\n".format(name_dict[handle].name, handle, name_dict[handle].contact))

def updateNameStats(name_dict, dict):
    if dict.sprite_credit != "" and dict.sprite_credit in name_dict:
        name_dict[dict.sprite_credit].sprites = True
    if dict.portrait_credit != "" and dict.portrait_credit in name_dict:
        name_dict[dict.portrait_credit].portraits = True

    for sub_dict in dict.subgroups:
        updateNameStats(name_dict, dict.subgroups[sub_dict])


"""
String operations
"""
def sanitizeName(str):
    return re.sub("\W+", "_", str).title()

def sanitizeCredit(str):
    return re.sub("\t\n", "", str)

def simple_quant(img: Image.Image) -> Image.Image:
    """
    Simple single-palette image quantization. Reduces to 15 colors and adds one transparent color at index 0.
    The transparent (alpha=0) pixels in the input image are converted to that color.
    If you need to do tiled multi-palette quantization, use Tilequant instead!
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    transparency_map = [px[3] == 0 for px in img.getdata()]
    qimg = img.quantize(15, dither=0).convert('RGBA')
    # Shift up all pixel values by 1 and add the transparent pixels
    pixels = qimg.load()
    k = 0
    for j in range(img.size[1]):
        for i in range(img.size[0]):
            if transparency_map[k]:
                pixels[i, j] = (0, 0, 0, 0)
            k += 1
    return qimg
