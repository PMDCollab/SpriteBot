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

ACTIONS = [ "None",
            "Idle",
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
            "Special",
            "Withdraw",
            "RearUp",
            "Swell",
            "Swing",
            "Double",
            "Rotate",
            "Spin",
            "Jump",
            "HighJump" ]


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
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    with urllib.request.urlopen(req) as response:
        img = Image.open(response).convert("RGBA")
    return img

def getLinkFile(url):
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    file_data = BytesIO()
    with urllib.request.urlopen(req) as response:
        file_data.write(response.read())
    file_data.seek(0)
    return file_data

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

def verifyRecolor(msg_args, orig_img, img, recolor):
    if orig_img.size != img.size:
        return "Recolor has dimensions {0} instead of {1}.".format(str(img.size), str(orig_img.size))
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
            return "Recolor has differing pixel opacity at:\n {0}".format(str(correctedDiff)[:1000])
        else:
            paletteDiff = comparePalette(orig_img, img)
            if paletteDiff != 0:
                if paletteDiff > 0:
                    diff_str = "+" + str(paletteDiff)
                else:
                    diff_str = str(paletteDiff)
                if len(msg_args) == 0 or not msg_args[0] == diff_str:
                    base_str = "Recolor has `{0}` colors compared to the original.\nIf this was intended, resubmit and specify `{0}` in the message."
                    return base_str.format(diff_str)
                else:
                    msg_args.pop(0)
    return None

def getEmotionFromTilePos(tile_pos):
    rogue_idx = tile_pos[1] * PORTRAIT_TILE_X + tile_pos[0]
    rogue_str = EMOTIONS[rogue_idx % len(EMOTIONS)]
    if rogue_idx // len(EMOTIONS) > 0:
        rogue_str += " Flipped"
    return rogue_str

def verifyPortrait(msg_args, img):
    # make sure the dimensions are sound
    if img.size[0] % PORTRAIT_SIZE != 0 or img.size[1] % PORTRAIT_SIZE != 0:
        return "Portrait has an invalid size of {0}, Not divisble by {1}x{1}".format(str(img.size), PORTRAIT_SIZE)

    img_tile_size = (img.size[0] // PORTRAIT_SIZE, img.size[1] // PORTRAIT_SIZE)
    max_size = (PORTRAIT_TILE_X * PORTRAIT_SIZE, PORTRAIT_TILE_Y * PORTRAIT_SIZE)
    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
        return "Portrait has an invalid size of {0}, exceeding max of {1}".format(str(img.size), str(max_size))

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
            emote_str = getEmotionFromTilePos((xx, yy))
            if is_rogue:
                rogue_tiles.append(emote_str)
            palette_counts[emote_str] = len(palette)


    if len(rogue_pixels) > 0:
        return "Semi-transparent pixels found at: {0}".format(str(rogue_pixels)[:1900])
    if len(rogue_tiles) > 0:
        return "The following emotions have transparent pixels: {0}".format(str(rogue_tiles)[:1900])

    overpalette = { }
    for emote_str in palette_counts:
        if palette_counts[emote_str] > 15:
            overpalette[emote_str] = palette_counts[emote_str]
    if len(overpalette) > 0:
        return "The following emotions have over 15 colors: {0}".format(str(overpalette)[:1900])

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
            return "File has a flipped emotion when the original is missing."
        if not escape_clause:
            return "File is missing some flipped emotions. If you want to submit incomplete, include `noflip` in the message."

    return None


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


def prepareSpriteImage(path):
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        full_file = os.path.join(path, file)
        if os.path.isdir(full_file):
            continue
        elif ext == '.png':
            return Image.open(full_file).convert("RGBA")

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


"""
Assumes that the data path is always valid.
Returns file handle and an extension for the file format
"""
def generateFileData(path, asset_type, recolor):

    if asset_type == "portrait":
        portraitImg = preparePortraitImage(path)
        if recolor:
            portraitImg = insertPalette(portraitImg)
        fileData = BytesIO()
        portraitImg.save(fileData, format='PNG')
        return fileData, ".png"
    elif asset_type == "sprite":
        if recolor:
            spriteImg = prepareSpriteImage(path)
            fileData = BytesIO()
            spriteImg.save(fileData, format='PNG')
            return fileData, ".png"
        else:
            spriteZip = prepareSpriteZip(path)
            return spriteZip, ".zip"

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
    sub_dict["portrait_modified"] = ""
    sub_dict["portrait_pending"] = {}
    sub_dict["portrait_recolor_link"] = ""
    sub_dict["portrait_required"] = False
    sub_dict["sprite_complete"] = 0
    sub_dict["sprite_credit"] = ""
    sub_dict["sprite_link"] = ""
    sub_dict["sprite_modified"] = ""
    sub_dict["sprite_pending"] = {}
    sub_dict["sprite_recolor_link"] = ""
    sub_dict["sprite_required"] = False
    sub_dict["subgroups"] = {}
    return TrackerNode(sub_dict)

def fileSystemToJson(dict, species_path, prefix, tier):
    # get last modify date of everything that isn't credits.txt or dirs
    last_modify = ""
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
