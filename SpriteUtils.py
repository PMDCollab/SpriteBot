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
import Constants
from typing import Dict, List, Tuple

RETRIEVE_HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'}


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
        if data1[3] != data2[3]:
            diffs.append((ii % img1.size[0], ii // img1.size[0]))

    return diffs

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

def thumbnailFileImg(inFile):
    # expand the image to fit a twitter preview
    # truncate the second half if there exists one
    img = Image.open(inFile).convert("RGBA")
    img = img.crop((0, 0, Constants.PORTRAIT_SIZE * Constants.PORTRAIT_TILE_X, Constants.PORTRAIT_SIZE * Constants.PORTRAIT_TILE_Y // 2))
    # crop out the whitespace
    img = img.crop(exUtils.getCoveredBounds(img))
    length = img.size[0]
    factor = 400 // length
    new_size = (img.size[0] * factor, img.size[1] * factor)
    # expand to 400px wide at most
    img = img.resize(new_size, resample=Image.NEAREST)

    file_data = BytesIO()
    img.save(file_data, format='PNG')
    file_data.seek(0)
    return file_data

def animateFileZip(inFile, anim):
    print("start animation")
    img_list = []
    factor = 8
    final_size = (800, 800)

    with zipfile.ZipFile(inFile, 'r') as zip:
        name_list = zip.namelist()

        file_data = BytesIO()
        file_data.write(zip.read(Constants.MULTI_SHEET_XML))
        file_data.seek(0)

        sdw_size, anim_names, anim_stats = getStatsFromTree(file_data)


        if anim + "-Anim.png" not in name_list:
            raise SpriteVerifyError("Missing Anim {0}".format(anim))

        anim_stat = anim_stats[anim_names[anim.lower()]]
        anim_name = anim_stat.name
        anim_png_name = anim_name + "-Anim.png"
        shadow_png_name = anim_name + "-Shadow.png"

        anim_img = readZipImg(zip, anim_png_name)
        shadow_img = readZipImg(zip, shadow_png_name)

        datas = shadow_img.getdata()
        shadow_datas = [(0,0,0,0)] * len(datas)
        for idx in range(len(datas)):
            color = datas[idx]
            if color[3] != 255:
                continue

            if color[1] == 255:
                shadow_datas[idx] = (0,0,0,255)
            elif color[0] == 255 and sdw_size > 0:
                shadow_datas[idx] = (0,0,0,255)
            elif color[2] == 255 and sdw_size > 1:
                shadow_datas[idx] = (0,0,0,255)

        shadow_img = Image.new('RGBA', shadow_img.size, (0, 0, 0, 0))
        shadow_img.putdata(shadow_datas)

        tileSize = anim_stat.size
        newTileSize = (tileSize[0] * factor, tileSize[1] * factor)
        paste_loc = ((final_size[0] - newTileSize[0]) // 2, (final_size[1] - newTileSize[1]) // 2 )
        durations = anim_stat.durations

        total_frames = anim_img.size[0] // tileSize[0]
        total_dirs = anim_img.size[1] // tileSize[1]

        for dir in range(total_dirs):
            for jj in range(total_frames):
                tile_rect = (jj * tileSize[0], dir * tileSize[1], tileSize[0], tileSize[1])
                tile_bounds = (tile_rect[0], tile_rect[1], tile_rect[0] + tile_rect[2], tile_rect[1] + tile_rect[3])
                tile_tex = anim_img.crop(tile_bounds)
                shadow_tex = shadow_img.crop(tile_bounds)

                new_tile_tex = tile_tex.resize(newTileSize, resample=Image.NEAREST)
                new_shadow_tex = shadow_tex.resize(newTileSize, resample=Image.NEAREST)
                frame_dur = durations[jj]
                print("add frames " + str(jj))
                for ii in range(frame_dur):
                    full_frame = Image.new('RGBA', final_size, (0, 128, 128, 0))
                    full_frame.paste(new_shadow_tex, (paste_loc[0], paste_loc[1]), new_shadow_tex)
                    full_frame.paste(new_tile_tex, (paste_loc[0], paste_loc[1]), new_tile_tex)
                    img_list.append(full_frame)

    print("saving animation")
    file_data = BytesIO()
    img_list[0].save(file_data, format='GIF', save_all=True, append_images=img_list[1:], duration=20, loop=0)
    file_data.seek(0)

    print("saved animation")
    #img_list[0].save("test.gif", format='GIF', save_all=True, append_images=img_list[1:], optimize=True, duration=20, loop=0)
    return file_data

def getLinkData(url):
    clean_url = sanitizeLink(url)
    _, file = os.path.split(clean_url)
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)

    with urllib.request.urlopen(req) as response:
        zip_data = BytesIO()
        zip_data.write(response.read())
        zip_data.seek(0)
        return zip_data, file

def getLinkImg(url):
    clean_url = sanitizeLink(url)
    full_path, ext = os.path.splitext(clean_url)
    unzip = ext == ".zip"
    _, file = os.path.split(full_path)
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    try:
        with urllib.request.urlopen(req) as response:
            if unzip:
                zip_data = BytesIO()
                zip_data.write(response.read())
                zip_data.seek(0)
                with zipfile.ZipFile(zip_data, 'r') as zip:
                    img = readZipImg(zip, file + ".png")
            else:
                img = Image.open(response).convert("RGBA")
    except zipfile.BadZipfile as e:
        raise SpriteVerifyError(str(e))

    return img

def getCombinedZipImg(zip_data):
    with zipfile.ZipFile(zip_data, 'r') as shiny_zip:
        combinedImg, _ = getCombinedImg(shiny_zip, True)
        return combinedImg

def verifyZipFile(zip, file_name):
    try:
        info = zip.getinfo(file_name)
    except KeyError as e:
        raise SpriteVerifyError(str(e))
    if info.file_size > ZIP_SIZE_LIMIT:
        raise SpriteVerifyError("Zipped file {0} is too large, at {1} bytes.".format(file_name, info.file_size))

def readZipImg(zip, file_name) -> Image.Image:
    verifyZipFile(zip, file_name)

    file_data = BytesIO()
    file_data.write(zip.read(file_name))
    file_data.seek(0)
    return Image.open(file_data).convert("RGBA")

def getLinkZipGroup(url):
    clean_url = sanitizeLink(url)
    full_path, ext = os.path.splitext(clean_url)
    _, file = os.path.split(full_path)
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    zip_data = BytesIO()
    with urllib.request.urlopen(req) as response:
        zip_data.write(response.read())
    zip_data.seek(0)

    return zip_data

def testLinkFile(url):
    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    try:
        with urllib.request.urlopen(req) as response:
            return True
    except:
        return False


def getLinkFile(url, asset_type):
    clean_url = sanitizeLink(url)
    full_path, ext = os.path.splitext(clean_url)
    unzip = ext == ".zip" and asset_type == "portrait"
    _, file = os.path.split(full_path)
    output_file = file + ext

    req = urllib.request.Request(url, None, RETRIEVE_HEADERS)
    file_data = BytesIO()
    try:
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
    except KeyError as e:
        raise SpriteVerifyError(str(e))
    except zipfile.BadZipfile as e:
        raise SpriteVerifyError(str(e))

    file_data.seek(0)
    return file_data, output_file

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



def getStatsFromTree(file_data):
    tree = ET.parse(file_data)
    root = tree.getroot()
    maybe_shadow_size = root.find('ShadowSize')
    if maybe_shadow_size is None or maybe_shadow_size.text is None:
        raise SpriteVerifyError("ShadowSize element missing or empty")
    sdw_size = int(maybe_shadow_size.text)
    if sdw_size < 0 or sdw_size > 2:
        raise SpriteVerifyError("Invalid shadow size: {0}".format(sdw_size))

    anim_names: Dict[str, int] = {}
    anim_stats: Dict[int, AnimStat] = {}
    anims_node = root.find('Anims')
    if anims_node is None:
        raise SpriteVerifyError("Anims tag missing")
    for anim_node in anims_node.iter('Anim'):
        maybe_name = anim_node.find('Name')
        if maybe_name is None or maybe_name.text is None:
            raise SpriteVerifyError("An Anim have a Name tag missing or empty")
        name = maybe_name.text
        # verify all names are real
        if name not in Constants.ACTIONS:
            raise SpriteVerifyError("Invalid anim name '{0}' in XML.".format(name))
        index = -1
        index_node = anim_node.find('Index')
        if index_node is not None and index_node.text is not None:
            index = int(index_node.text)
        backref_node = anim_node.find('CopyOf')
        if backref_node is not None and backref_node.text is not None:
            backref = backref_node.text
            anim_stat = AnimStat(index, name, None, backref)
        else:
            frame_width = anim_node.find('FrameWidth')
            frame_height = anim_node.find('FrameHeight')
            if frame_width is None or frame_width.text is None:
                raise SpriteVerifyError("FrameWidth empty or missing for {}".format(name))
            if frame_height is None or frame_height.text is None:
                raise SpriteVerifyError("FrameHeight empty or missing for {}".format(name))
            anim_stat = AnimStat(index, name, (int(frame_width.text), int(frame_height.text)), None)

            rush_frame = anim_node.find('RushFrame')
            if rush_frame is not None and rush_frame.text is not None:
                anim_stat.rushFrame = int(rush_frame.text)
            hit_frame = anim_node.find('HitFrame')
            if hit_frame is not None and hit_frame.text is not None:
                anim_stat.hitFrame = int(hit_frame.text)
            return_frame = anim_node.find('ReturnFrame')
            if return_frame is not None and return_frame.text is not None:
                anim_stat.returnFrame = int(return_frame.text)

            durations_node = anim_node.find('Durations')
            if durations_node is None:
                raise SpriteVerifyError("Durations missing in {}".format(name))
            for dur_node in durations_node.iter('Duration'):
                duration = int(dur_node.text)
                anim_stat.durations.append(duration)

            if index == -1:
                raise SpriteVerifyError("{0} has its own sheet and does not have an index!".format(name))

        if name.lower() in anim_names:
            raise SpriteVerifyError("Anim '{0}' is specified twice in XML!".format(name))
        anim_names[name.lower()] = index

        if index > -1:
            if index in anim_stats:
                raise SpriteVerifyError(
                    "{0} and {1} both have the an index of {2}!".format(anim_stats[index].name, name, index))
            anim_stats[index] = anim_stat

    return sdw_size, anim_names, anim_stats


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


"""
File verification
"""

def compareSpriteRecolorDiff(orig_anim_img, shiny_anim_img, anim_name,
                             trans_diff, black_diff, orig_palette, shiny_palette):
    orig_data = orig_anim_img.getdata()
    shiny_data = shiny_anim_img.getdata()
    for yy in range(orig_data.size[1]):
        for xx in range(orig_data.size[0]):
            orig_color = orig_data[yy * orig_data.size[0] + xx]
            shiny_color = shiny_data[yy * orig_data.size[0] + xx]
            # test against transparency, black pixel changes
            if orig_color[3] != shiny_color[3]:
                if anim_name not in trans_diff:
                    trans_diff[anim_name] = []
                trans_diff[anim_name].append((xx, yy))
            if (orig_color == (0, 0, 0, 255)) != (shiny_color == (0, 0, 0, 255)):
                if anim_name not in black_diff:
                    black_diff[anim_name] = []
                black_diff[anim_name].append((xx, yy))
            # compile palette
            if orig_color[3] == 255:
                if orig_color not in orig_palette:
                    orig_palette[orig_color] = 0
                orig_palette[orig_color] += 1
            if shiny_color[3] == 255:
                if shiny_color not in shiny_palette:
                    shiny_palette[shiny_color] = 0
                shiny_palette[shiny_color] += 1

def verifySpriteRecolor(msg_args, precolor_zip, wan_zip, recolor, checkSilhouette):
    orig_palette = {}
    shiny_palette = {}
    trans_diff = {}
    black_diff = {}

    if recolor:
        if precolor_zip.size != wan_zip.size:
            raise SpriteVerifyError(
                "Recolor has dimensions {0} instead of {1}.".format(str(wan_zip.size), str(precolor_zip.size)))

        precolor_zip = removePalette(precolor_zip)
        wan_zip = removePalette(wan_zip)
        compareSpriteRecolorDiff(precolor_zip, wan_zip, "sheet",
                                 trans_diff, black_diff, orig_palette, shiny_palette)
    else:
        try:
            with zipfile.ZipFile(precolor_zip, 'r') as zip:
                with zipfile.ZipFile(wan_zip, 'r') as shiny_zip:
                    name_list = zip.namelist()
                    shiny_name_list = shiny_zip.namelist()
                    if name_list != shiny_name_list:
                        name_set = set(name_list)
                        shiny_name_set = set(shiny_name_list)
                        missing_shiny = name_set - shiny_name_set
                        missing_orig = shiny_name_set - name_set
                        report = ""
                        if len(missing_shiny) > 0:
                            report += "\nFiles missing: {0}".format(missing_shiny)
                        if len(missing_orig) > 0:
                            report += "\nFiles extra: {0}".format(missing_orig)
                        if len(report) > 0:
                            raise SpriteVerifyError("File list of recolor does not match original.{0}".format(report))

                    bin_diff = []
                    for shiny_name in shiny_name_list:
                        if shiny_name == Constants.MULTI_SHEET_XML:
                            verifyZipFile(shiny_zip, shiny_name)
                            orig_anim_data = zip.read(shiny_name)
                            shiny_anim_data = shiny_zip.read(shiny_name)
                            if orig_anim_data != shiny_anim_data:
                                bin_diff.append(shiny_name)
                        elif not shiny_name.endswith("-Anim.png"):
                            orig_anim_data = readZipImg(zip, shiny_name)
                            shiny_anim_data = readZipImg(shiny_zip, shiny_name)
                            if not exUtils.imgsEqual(orig_anim_data, shiny_anim_data):
                                bin_diff.append(shiny_name)

                    if len(bin_diff) > 0:
                        raise SpriteVerifyError("The files below must remain identical to those of the original sprite."
                                                "  Please copy them from the original zip:\n{0}".format(", ".join(bin_diff)[:1900]))

                    for shiny_name in shiny_name_list:
                        if shiny_name.endswith("-Anim.png"):
                            anim_name = shiny_name.replace('-Anim.png', '')
                            verifyZipFile(shiny_zip, shiny_name)
                            orig_anim_img = readZipImg(zip, shiny_name)
                            shiny_anim_img = readZipImg(shiny_zip, shiny_name)
                            if orig_anim_img.size != shiny_anim_img.size:
                                raise SpriteVerifyError(
                                    "Anim {0} has a size {1}x{2} that is different"
                                    " from the original's size of {3}x{4}".format(shiny_name, shiny_anim_img.size[0],
                                                                                  shiny_anim_img.size[1],
                                                                                  orig_anim_img.size[0],
                                                                                  orig_anim_img.size[1]))
                            compareSpriteRecolorDiff(orig_anim_img, shiny_anim_img, anim_name,
                                                     trans_diff, black_diff, orig_palette, shiny_palette)

        except zipfile.BadZipfile as e:
            raise SpriteVerifyError(str(e))

    if checkSilhouette and len(trans_diff) > 0:
        px_strings = []
        for anim_name in trans_diff:
            px_strings.append(anim_name + ": " + ", ".join([str(a) for a in trans_diff[anim_name]]))
        raise SpriteVerifyError("Some pixels were found to have changed transparency:\n{0}".format(
            "\n".join(px_strings)[:1900]))

    if len(black_diff) > 0:
        if not msg_args.lineart:
            px_strings = []
            for anim_name in black_diff:
                px_strings.append(anim_name + ": " + ", ".join([str(a) for a in black_diff[anim_name]]))
            raise SpriteVerifyError("Some pixels were found to have changed from black to another color:\n{0}\nIf this was intended (very rare!), resubmit and include `--lineart` in the message.".format(
                "\n".join(px_strings)[:1800]))

    if len(orig_palette) != len(shiny_palette):
        palette_diff = len(shiny_palette) - len(orig_palette)
        if palette_diff != 0:
            if msg_args.colormod != palette_diff:
                base_str = "Recolor has {0} colors compared to the original.\nIf this was intended, resubmit and specify `--colormod {0}` in the message."
                raise SpriteVerifyError(base_str.format(palette_diff))

    # then, check the colors
    if len(shiny_palette) > 15:
        if msg_args.colors != len(shiny_palette):
            if recolor:
                combinedImg = wan_zip
            else:
                with zipfile.ZipFile(wan_zip, 'r') as shiny_zip:
                    combinedImg, _ = getCombinedImg(shiny_zip, True)
            reduced_img = simple_quant(combinedImg, 16)
            reduced_img = insertPalette(reduced_img)
            raise SpriteVerifyError("The sprite has {0} non-transparent colors with only 15 allowed.\n"
                                    "If this is acceptable, include `--colors {0}` in the message."
                                    "  Otherwise reduce colors for the sprite.".format(len(shiny_palette)), reduced_img)

def verifyPortraitRecolor(msg_args, orig_img, img, recolor):
    if orig_img.size != img.size:
        raise SpriteVerifyError("Recolor has dimensions {0} instead of {1}.".format(str(img.size), str(orig_img.size)))

    if recolor:
        orig_img = removePalette(orig_img)
        img = removePalette(img)

    tileDiff = []
    partialPixDiff = []
    for xt in range(Constants.PORTRAIT_TILE_X):
        for yt in range(Constants.PORTRAIT_TILE_Y):
            xx = xt * Constants.PORTRAIT_SIZE
            yy = yt * Constants.PORTRAIT_SIZE
            if xx < orig_img.size[0] and yy < orig_img.size[1]:
                orig_crop = orig_img.crop((xx, yy, xx + Constants.PORTRAIT_SIZE, yy + Constants.PORTRAIT_SIZE))
            else:
                orig_crop = Image.new('RGBA', (Constants.PORTRAIT_SIZE, Constants.PORTRAIT_SIZE), (0, 0, 0, 0))

            if xx < img.size[0] and yy < img.size[1]:
                img_crop = img.crop((xx, yy, xx + Constants.PORTRAIT_SIZE, yy + Constants.PORTRAIT_SIZE))
            else:
                img_crop = Image.new('RGBA', (Constants.PORTRAIT_SIZE, Constants.PORTRAIT_SIZE), (0, 0, 0, 0))

            pixDiff = comparePixels(orig_crop, img_crop)
            if len(pixDiff) == Constants.PORTRAIT_SIZE * Constants.PORTRAIT_SIZE:
                # full tile missing or added
                tileDiff.append((xt, yt))
            elif len(pixDiff) > 0:
                for px, py in pixDiff:
                    partialPixDiff.append((xx + px, yy + py))


    if recolor:
        partialPixDiff = [xyPlusOne(x) for x in partialPixDiff]

    if len(partialPixDiff) > 0:
        raise SpriteVerifyError("Recolor has differing opacity at pixels:\n {0}".format(str(partialPixDiff)[:1000]))
    if len(tileDiff) > 0:
        if not msg_args.lineart:
            raise SpriteVerifyError("Recolor has missing or added portrait at tiles:\n {0}\nIf this is intended (ex, incomplete recolors), resubmit and include `--lineart` in the message.".format(str(tileDiff)[:1000]))

    palette_diff = comparePalette(orig_img, img)
    if palette_diff != 0:
        if msg_args.colormod != palette_diff:
            base_str = "Recolor has `{0}` colors compared to the original.\nIf this was intended, resubmit and specify `--colormod {0}` in the message."
            raise SpriteVerifyError(base_str.format(palette_diff))

    overpalette = getPortraitOverpalette(img)

    if len(overpalette) > 0:
        if not msg_args.overcolor:
            reduced_img = simple_quant_portraits(img, overpalette)
            if recolor:
                reduced_img = insertPalette(reduced_img)
            rogue_emotes = [getEmotionFromTilePos(a) for a in overpalette]
            raise SpriteVerifyError("Some emotions have over 15 colors.\n" \
                   "If this is acceptable, include `--overcolor` in the message.  Otherwise reduce colors for emotes:\n" \
                   "{0}".format(str(rogue_emotes)[:1900]), reduced_img)

def getPortraitOverpalette(img):
    palette_counts = {}
    in_data = img.getdata()
    img_tile_size = (img.size[0] // Constants.PORTRAIT_SIZE, img.size[1] // Constants.PORTRAIT_SIZE)
    for xx in range(Constants.PORTRAIT_TILE_X):
        for yy in range(Constants.PORTRAIT_TILE_Y):
            if xx >= img_tile_size[0] or yy >= img_tile_size[1]:
                continue
            first_pos = (xx * Constants.PORTRAIT_SIZE, yy * Constants.PORTRAIT_SIZE)
            first_pixel = in_data[first_pos[1] * img.size[0] + first_pos[0]]
            if first_pixel[3] == 0:
                continue

            palette = {}
            for mx in range(Constants.PORTRAIT_SIZE):
                for my in range(Constants.PORTRAIT_SIZE):
                    cur_pos = (first_pos[0] + mx, first_pos[1] + my)
                    cur_pixel = in_data[cur_pos[1] * img.size[0] + cur_pos[0]]
                    palette[cur_pixel] = True
            palette_counts[(xx, yy)] = len(palette)

    overpalette = { }
    for emote_loc in palette_counts:
        if palette_counts[emote_loc] > 15:
            overpalette[emote_loc] = palette_counts[emote_loc]

    return overpalette


def getEmotionFromTilePos(tile_pos):
    rogue_idx = tile_pos[1] * Constants.PORTRAIT_TILE_X + tile_pos[0]
    rogue_str = Constants.EMOTIONS[rogue_idx % len(Constants.EMOTIONS)]
    if rogue_idx // len(Constants.EMOTIONS) > 0:
        rogue_str += "^"
    return rogue_str

def getLRSwappedOffset(offset):
    swapped_offset = FrameOffset(offset.head, offset.rhand, offset.lhand, offset.center)
    return swapped_offset

def mapDuplicateImportImgs(imgs, final_imgs, img_map, offset_diffs):
    map_back = {}
    for idx, img in enumerate(imgs):
        dupe = False
        flip = -1
        for final_idx, final_img in enumerate(final_imgs):
            imgs_equal = exUtils.imgsEqual(final_img[0], img[0])
            # if offsets are not synchronized, they are counted as different
            if imgs_equal:
                offsets_equal = exUtils.offsetsEqual(final_img[1], img[1], img[0].size[0])
                offsets_equal |= exUtils.offsetsEqual(final_img[1], getLRSwappedOffset(img[1]), img[0].size[0])
                if not offsets_equal:
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
                offsets_flip = exUtils.offsetsEqual(final_img[1], img[1], img[0].size[0], True)
                offsets_flip |= exUtils.offsetsEqual(final_img[1], getLRSwappedOffset(img[1]), img[0].size[0], True)
                if not offsets_flip:
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
    frames = []
    palette = {}
    frameToSequence = []
    rogue_pixels = []
    try:
        with zipfile.ZipFile(wan_zip, 'r') as zip:
            name_list = zip.namelist()
            if Constants.MULTI_SHEET_XML not in name_list:
                raise SpriteVerifyError("No {0} found.".format(Constants.MULTI_SHEET_XML))
            verifyZipFile(zip, Constants.MULTI_SHEET_XML)

            file_data = BytesIO()
            file_data.write(zip.read(Constants.MULTI_SHEET_XML))
            file_data.seek(0)

            sdw_size, anim_names, anim_stats = getStatsFromTree(file_data)

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
            for idx in Constants.COMPLETION_ACTIONS[0]:
                if Constants.ACTIONS[idx].lower() not in anim_names:
                    missing_anims.append(Constants.ACTIONS[idx])
            if len(missing_anims) > 0:
                raise SpriteVerifyError("Missing required anims:\n{0}".format(', '.join(missing_anims)))
            violated_idx = []
            for idx in Constants.ACTION_MAP:
                if idx in anim_stats:
                    anim_stat = anim_stats[idx]
                    if anim_stat.name != Constants.ACTION_MAP[idx]:
                        violated_idx.append(Constants.ACTION_MAP[idx] + ' -> ' + str(idx))
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
                        if cur_occupied:
                            if cur_pixel[3] < 255:
                                rogue_pixels.append((xx, yy))
                            else:
                                if cur_pixel not in palette:
                                    palette[cur_pixel] = 0
                                palette[cur_pixel] += 1

                for dir in range(total_dirs):
                    for jj in range(total_frames):
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
                            raise SpriteVerifyError(e.message + '\n' + str((anim_name, Constants.DIRECTIONS[dir], jj)))

                        if emptyBounds and shadow_offset[4] is None and frame_offset[2] is None:
                            continue

                        offsets = FrameOffset(None, None, None, None)
                        if frame_offset[2] is None:
                            # raise warning if there's missing shadow or offsets
                            raise SpriteVerifyError("No frame offset found in frame {0} for {1}".format((Constants.DIRECTIONS[dir], jj), anim_name))
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
                        frameToSequence.append((anim_name, Constants.DIRECTIONS[dir], jj))

        # check for semitransparent pixels
        if len(rogue_pixels) > 0:
            raise SpriteVerifyError("Semi-transparent pixels found at: {0}".format(str(rogue_pixels)[:1900]))

        offset_diffs = {}
        frame_map = [None] * len(frames)
        final_frames = []
        mapDuplicateImportImgs(frames, final_frames, frame_map, offset_diffs)
        if len(offset_diffs) > 0:
            if not msg_args.multioffset:
                offset_diff_names = []
                for orig_idx in offset_diffs:
                    offset_group = [frameToSequence[orig_idx]]
                    for idx in offset_diffs[orig_idx]:
                        offset_group.append(frameToSequence[idx])
                    offset_diff_names.append(offset_group)

                raise SpriteVerifyError("Some frames have identical sprites but different offsets.\n"
                                        "If intended, include `--multioffset` in the message (very rare!)."
                                        "  Otherwise make these frame offsets consistent (you can use Collapse Offsets):\n{0}".format(str(offset_diff_names)[:1700]))

        # then, check the colors
        if len(palette) > 15:
            if msg_args.colors != len(palette):
                with zipfile.ZipFile(wan_zip, 'r') as zip:
                    combinedImg, _ = getCombinedImg(zip, True)
                    reduced_img = simple_quant(combinedImg, 16)
                raise SpriteVerifyError("The sprite has {0} non-transparent colors with only 15 allowed.\n"
                                        "If this is acceptable, include `--colors {0}` in the message."
                                        "  Otherwise reduce colors for the sprite.".format(len(palette)), reduced_img)
    except zipfile.BadZipfile as e:
        raise SpriteVerifyError(str(e))

def verifySpriteLock(dict, chosen_path, precolor_zip, wan_zip, recolor):
    # make sure all locked sprites are the same as their original counterparts
    changed_files = []

    try:
        cmp_zip = wan_zip
        shiny_frames = None
        frame_mapping = None
        if recolor:
            cmp_zip = precolor_zip
            wan_zip = removePalette(wan_zip)

            with zipfile.ZipFile(precolor_zip, 'r') as opened_zip:
                frames, frame_mapping = getFramesAndMappings(opened_zip, True)
            frame_size = getFrameSizeFromFrames(frames)

            # obtain a mapping from the color image of the shiny path
            shiny_frames = []
            for yy in range(0, wan_zip.size[1], frame_size[1]):
                for xx in range(0, wan_zip.size[0], frame_size[0]):
                    tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
                    bounds = exUtils.getCoveredBounds(wan_zip, tile_bounds)
                    if bounds[0] >= bounds[2]:
                        bounds = (frame_size[0] // 2, frame_size[1] // 2, frame_size[0] // 2 + 1, frame_size[1] // 2 + 1)
                        # reached the end of actual frames
                        if len(shiny_frames) >= len(frames):
                            continue
                    abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
                    frame_tex = wan_zip.crop(abs_bounds)
                    shiny_frames.append(frame_tex)

        with zipfile.ZipFile(cmp_zip, 'r') as zip:
            name_list = zip.namelist()
            if Constants.MULTI_SHEET_XML not in name_list:
                raise SpriteVerifyError("No {0} found.".format(Constants.MULTI_SHEET_XML))
            verifyZipFile(zip, Constants.MULTI_SHEET_XML)

            file_data = BytesIO()
            file_data.write(zip.read(Constants.MULTI_SHEET_XML))
            file_data.seek(0)

            sdw_size, anim_names, anim_stats = getStatsFromTree(file_data)
            if os.path.exists(os.path.join(chosen_path, Constants.MULTI_SHEET_XML)):
                sdw_size_cur, anim_names_cur, anim_stats_cur = getStatsFromTree(
                    os.path.join(chosen_path, Constants.MULTI_SHEET_XML))
            else:
                sdw_size_cur = 0
                anim_names_cur = {}
                anim_stats_cur = {}

            has_lock = False
            for anim_name in Constants.ACTIONS:
                if anim_name in dict.sprite_files and dict.sprite_files[anim_name]:
                    has_lock = True

                exists_old = anim_name.lower() in anim_names_cur
                exists_new = anim_name.lower() in anim_names
                # anim has been added or removed
                if exists_old != exists_new:
                    changed_files.append(anim_name)
                    continue

                # anim does not exist in either
                if not exists_old:
                    continue

                # check to ensure the indices are the same
                anim_idx = anim_names[anim_name.lower()]
                anim_idx_cur = anim_names_cur[anim_name.lower()]
                if anim_idx != anim_idx_cur:
                    changed_files.append(anim_name)
                    continue

                # anim is a backreference in both situations
                if anim_idx == -1:
                    continue

                # check to make sure the stats are the same
                anim_stat = anim_stats[anim_idx]
                anim_stat_cur = anim_stats_cur[anim_idx_cur]

                stat_violated = False
                stat_violated |= anim_stat.index != anim_stat_cur.index
                stat_violated |= anim_stat.name != anim_stat_cur.name
                stat_violated |= anim_stat.size != anim_stat_cur.size
                stat_violated |= anim_stat.backref != anim_stat_cur.backref
                stat_violated |= anim_stat.rushFrame != anim_stat_cur.rushFrame
                stat_violated |= anim_stat.hitFrame != anim_stat_cur.hitFrame
                stat_violated |= anim_stat.returnFrame != anim_stat_cur.returnFrame
                stat_violated |= len(anim_stat.durations) != len(anim_stat_cur.durations)
                if not stat_violated:
                    for idx, dur in enumerate(anim_stat.durations):
                        stat_violated |= dur != anim_stat_cur.durations[idx]

                if stat_violated:
                    changed_files.append(anim_name)
                    continue

                if anim_stat.backref is not None:
                    continue

                # check to make sure the images are the same
                anim_png_name = anim_name + "-Anim.png"
                offset_png_name = anim_name + "-Offsets.png"
                shadow_png_name = anim_name + "-Shadow.png"
                if anim_png_name not in name_list:
                    raise SpriteVerifyError("Anim specified in XML has no Anim.png: {0}".format(anim_name))
                if offset_png_name not in name_list:
                    raise SpriteVerifyError("Anim specified in XML has no Offsets.png: {0}".format(anim_name))
                if shadow_png_name not in name_list:
                    raise SpriteVerifyError("Anim specified in XML has no Shadow.png: {0}".format(anim_name))

                # absent file is counted as changed
                if not os.path.exists(os.path.join(chosen_path, anim_png_name)):
                    changed_files.append(anim_name)
                    continue

                # check for actual change
                if recolor:
                    assert frame_mapping is not None
                    prev_img = readZipImg(zip, anim_png_name)
                    anim_img = createRecolorAnim(prev_img, frame_mapping[anim_name], shiny_frames)
                else:
                    anim_img = readZipImg(zip, anim_png_name)

                anim_img_cur = Image.open(os.path.join(chosen_path, anim_png_name)).convert("RGBA")
                if not exUtils.imgsEqual(anim_img, anim_img_cur):
                    changed_files.append(anim_name)
                    continue

                # absent file is counted as changed
                if not os.path.exists(os.path.join(chosen_path, offset_png_name)):
                    changed_files.append(anim_name)
                    continue

                # check for actual change
                offset_img = readZipImg(zip, offset_png_name)
                offset_img_cur = Image.open(os.path.join(chosen_path, offset_png_name)).convert("RGBA")
                if not exUtils.imgsEqual(offset_img, offset_img_cur):
                    changed_files.append(anim_name)
                    continue

                # absent file is counted as changed
                if not os.path.exists(os.path.join(chosen_path, shadow_png_name)):
                    changed_files.append(anim_name)
                    continue

                # check for actual change
                shadow_img = readZipImg(zip, shadow_png_name)
                shadow_img_cur = Image.open(os.path.join(chosen_path, shadow_png_name)).convert("RGBA")
                if not exUtils.imgsEqual(shadow_img, shadow_img_cur):
                    changed_files.append(anim_name)
                    continue

            if has_lock and sdw_size != sdw_size_cur:
                raise SpriteVerifyError("The shadow size for this sprite is locked and cannot be changed.")

    except zipfile.BadZipfile as e:
        raise SpriteVerifyError(str(e))

    violated_files = []
    for change in changed_files:
        if change in dict.sprite_files and dict.sprite_files[change]:
            violated_files.append(change)

    if len(violated_files) > 0:
        raise SpriteVerifyError(
            "The following actions are locked and cannot be changed: {0}".format(str(violated_files)[:1900]))

    return changed_files

def verifyPortrait(msg_args, img):
    # make sure the dimensions are sound
    if img.size[0] % Constants.PORTRAIT_SIZE != 0 or img.size[1] % Constants.PORTRAIT_SIZE != 0:
        raise SpriteVerifyError("Portrait has an invalid size of {0}, Not divisble by {1}x{1}".format(str(img.size), Constants.PORTRAIT_SIZE))

    img_tile_size = (img.size[0] // Constants.PORTRAIT_SIZE, img.size[1] // Constants.PORTRAIT_SIZE)
    max_size = (Constants.PORTRAIT_TILE_X * Constants.PORTRAIT_SIZE, Constants.PORTRAIT_TILE_Y * Constants.PORTRAIT_SIZE)
    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
        raise SpriteVerifyError("Portrait has an invalid size of {0}, exceeding max of {1}".format(str(img.size), str(max_size)))

    in_data = img.getdata()
    occupied = [[]] * Constants.PORTRAIT_TILE_X
    for ii in range(Constants.PORTRAIT_TILE_X):
        occupied[ii] = [False] * Constants.PORTRAIT_TILE_Y

    # iterate every portrait and ensure that all pixels in that portrait are either solid or transparent
    rogue_pixels = []
    rogue_tiles = []
    palette_counts = {}
    for xx in range(Constants.PORTRAIT_TILE_X):
        for yy in range(Constants.PORTRAIT_TILE_Y):
            if xx >= img_tile_size[0] or yy >= img_tile_size[1]:
                continue
            first_pos = (xx * Constants.PORTRAIT_SIZE, yy * Constants.PORTRAIT_SIZE)
            first_pixel = in_data[first_pos[1] * img.size[0] + first_pos[0]]
            occupied[xx][yy] = (first_pixel[3] > 0)

            palette = {}
            is_rogue = False
            for mx in range(Constants.PORTRAIT_SIZE):
                for my in range(Constants.PORTRAIT_SIZE):
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
        if not msg_args.overcolor:
            reduced_img = simple_quant_portraits(img, overpalette)

            rogue_emotes = [getEmotionFromTilePos(a) for a in overpalette]
            raise SpriteVerifyError("Some emotions have over 15 colors.\n" \
                   "If this is acceptable, include `--overcolor` in the message.  Otherwise reduce colors for emotes:\n" \
                   "{0}".format(str(rogue_emotes)[:1900]), reduced_img)

    # make sure all mirrored emotions have their original emotions
    # make sure if there is one mirrored emotion, there is all mirrored emotions
    halfway = Constants.PORTRAIT_TILE_Y // 2
    flipped_tiles = []
    has_one_flip = False
    has_missing_original = False
    for xx in range(Constants.PORTRAIT_TILE_X):
        for yy in range(halfway, Constants.PORTRAIT_TILE_Y):
            if occupied[xx][yy]:
                has_one_flip = True
            if occupied[xx][yy] != occupied[xx][yy-halfway]:
                rogue_str = getEmotionFromTilePos((xx, yy))
                flipped_tiles.append(rogue_str)
                if not occupied[xx][yy-halfway]:
                    has_missing_original = True

    if has_one_flip and len(flipped_tiles) > 0:
        if has_missing_original:
            raise SpriteVerifyError("File has a flipped emotion when the original is missing.")
        if not msg_args.noflip:
            raise SpriteVerifyError("File is missing some flipped emotions." \
                   "If you want to submit incomplete, include `--noflip` in the message.")

def verifyPortraitLock(dict, chosen_path, img, recolor):
    # make sure all locked portraits are the same as their original counterparts
    if recolor:
        img = removePalette(img)

    in_data = img.getdata()
    changed_files = []
    for xx in range(Constants.PORTRAIT_TILE_X):
        for yy in range(Constants.PORTRAIT_TILE_Y):
            emote_name = getEmotionFromTilePos((xx, yy))

            # check the current file against the new file
            first_pos = (xx * Constants.PORTRAIT_SIZE, yy * Constants.PORTRAIT_SIZE)
            png_name = os.path.join(chosen_path, emote_name + ".png")

            exists_old = os.path.exists(png_name)
            exists_new = False
            if first_pos[0] < img.size[0] and first_pos[1] < img.size[1]:
                for mx in range(Constants.PORTRAIT_SIZE):
                    for my in range(Constants.PORTRAIT_SIZE):
                        cur_pos = (first_pos[0] + mx, first_pos[1] + my)
                        cur_pixel = in_data[cur_pos[1] * img.size[0] + cur_pos[0]]
                        if cur_pixel[3] > 0:
                            exists_new = True
                            break
                    if exists_new:
                        break

            if exists_old != exists_new:
                violated = True
            elif not exists_old:
                violated = False
            else:
                chosen_img = Image.open(png_name).convert("RGBA")
                chosen_data = chosen_img.getdata()
                violated = False
                for mx in range(Constants.PORTRAIT_SIZE):
                    for my in range(Constants.PORTRAIT_SIZE):
                        cur_pos = (first_pos[0] + mx, first_pos[1] + my)
                        cur_pixel = in_data[cur_pos[1] * img.size[0] + cur_pos[0]]
                        chosen_pixel = chosen_data[my * chosen_img.size[0] + mx]
                        if cur_pixel != chosen_pixel:
                            violated = True
                            break
                    if violated:
                        break
            if violated:
                changed_files.append((xx, yy))

    violated_files = []
    for idx, change in enumerate(changed_files):
        emote_name = getEmotionFromTilePos(change)
        if emote_name in dict.portrait_files and dict.portrait_files[emote_name]:
            violated_files.append(change)
        changed_files[idx] = emote_name


    if len(violated_files) > 0:
        violated_names = [getEmotionFromTilePos(a) for a in violated_files]
        raise SpriteVerifyError("The following emotions are locked and cannot be changed: {0}".format(str(violated_names)[:1900]))

    return changed_files

def verifyPortraitFilled(species_path):
    for name in Constants.EMOTIONS:
        if name.startswith("Special"):
            continue
        full_path = os.path.join(species_path, name + ".png")
        if not os.path.exists(full_path):
            return False

    return True

def isCopyOf(species_path, anim):
    if os.path.exists(os.path.join(species_path, Constants.MULTI_SHEET_XML)):
        tree = ET.parse(os.path.join(species_path, Constants.MULTI_SHEET_XML))
        root = tree.getroot()
        anims_node = root.find('Anims')
        for anim_node in anims_node.iter('Anim'):
            name = anim_node.find('Name').text
            if name == anim:
                backref_node = anim_node.find('CopyOf')
                return backref_node is not None
    return False

"""
File data writeback
"""

def placeSpriteZipToPath(wan_file, dest_path):
    preparePlacement(dest_path)

    # extract all
    try:
        with zipfile.ZipFile(wan_file, 'r') as zip:
            zip.extractall(path=dest_path)
    except zipfile.BadZipfile as e:
        raise SpriteVerifyError(str(e))

def placeSpriteRecolorToPath(orig_path, outImg, dest_path):
    preparePlacement(dest_path)

    # remove palette bar of both images
    outImg = removePalette(outImg)

    frames, frame_mapping = getFramesAndMappings(orig_path, False)
    frame_size = getFrameSizeFromFrames(frames)

    # obtain a mapping from the color image of the shiny path
    shiny_frames = []
    for yy in range(0, outImg.size[1], frame_size[1]):
        for xx in range(0, outImg.size[0], frame_size[0]):
            tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
            bounds = exUtils.getCoveredBounds(outImg, tile_bounds)
            if bounds[0] >= bounds[2]:
                bounds = (frame_size[0] // 2, frame_size[1] // 2, frame_size[0] // 2 + 1, frame_size[1] // 2 + 1)
                # reached the end of actual frames
                if len(shiny_frames) >= len(frames):
                    continue
            abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
            frame_tex = outImg.crop(abs_bounds)
            shiny_frames.append(frame_tex)

    shutil.copyfile(os.path.join(orig_path, Constants.MULTI_SHEET_XML), os.path.join(dest_path, Constants.MULTI_SHEET_XML))

    for anim_name in frame_mapping:
        img_path = os.path.join(orig_path, anim_name + '-Anim.png')
        img_dest_path = os.path.join(dest_path, anim_name + '-Anim.png')
        prev_img = Image.open(img_path).convert("RGBA")
        img = createRecolorAnim(prev_img, frame_mapping[anim_name], shiny_frames)
        img.save(img_dest_path)

        shutil.copyfile(os.path.join(orig_path, anim_name + '-Offsets.png'), os.path.join(dest_path, anim_name + '-Offsets.png'))
        shutil.copyfile(os.path.join(orig_path, anim_name + '-Shadow.png'), os.path.join(dest_path, anim_name + '-Shadow.png'))

def createRecolorAnim(template_img, anim_map, shiny_frames):
    anim_img = Image.new('RGBA', template_img.size, (0, 0, 0, 0))
    for abs_bounds in anim_map:
        frame_idx, flip = anim_map[abs_bounds]
        imgPiece = shiny_frames[frame_idx]
        if flip:
            imgPiece = imgPiece.transpose(Image.FLIP_LEFT_RIGHT)
        anim_img.paste(imgPiece, (abs_bounds[0], abs_bounds[1]), imgPiece)
    return anim_img

def placePortraitToPath(outImg, dest_path):
    preparePlacement(dest_path)

    # add new ones
    for idx in range(len(Constants.EMOTIONS)):
        placeX = Constants.PORTRAIT_SIZE * (idx % Constants.PORTRAIT_TILE_X)
        placeY = Constants.PORTRAIT_SIZE * (idx // Constants.PORTRAIT_TILE_X)
        if placeX < outImg.size[0] and placeY < outImg.size[1]:
            imgCrop = outImg.crop((placeX,placeY,placeX+Constants.PORTRAIT_SIZE,placeY+Constants.PORTRAIT_SIZE))
            if not isBlank(imgCrop):
                imgCrop.save(os.path.join(dest_path, Constants.EMOTIONS[idx]+".png"))
        # check flips
        placeY += 4 * Constants.PORTRAIT_SIZE
        if placeX < outImg.size[0] and placeY < outImg.size[1]:
            imgCrop = outImg.crop((placeX,placeY,placeX+Constants.PORTRAIT_SIZE,placeY+Constants.PORTRAIT_SIZE))
            if not isBlank(imgCrop):
                imgCrop.save(os.path.join(dest_path, Constants.EMOTIONS[idx]+"^.png"))

def preparePlacement(dest_path):
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
    else:
        # delete existing files
        existing_files = os.listdir(dest_path)
        for file in existing_files:
            if file.endswith(".png") or file.endswith(".xml"):
                os.remove(os.path.join(dest_path, file))

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

def getFramesAndMappings(path, is_zip) -> Tuple[
    List[Tuple[Image.Image, FrameOffset]],
    Dict[str, Dict[Tuple[int, int, int, int], Tuple[int, bool]]]
]:
    anim_dims: Dict[str, Tuple[int, int]] = {}
    if is_zip:
        file_data = BytesIO()
        file_data.write(path.read(Constants.MULTI_SHEET_XML))
        file_data.seek(0)
        tree = ET.parse(file_data)
    else:
        tree = ET.parse(os.path.join(path, Constants.MULTI_SHEET_XML))
    root = tree.getroot()
    anims_node = root.find('Anims')
    if anims_node is None:
        raise ValueError("Anims tag not found")
    for anim_node in anims_node.iter('Anim'):
        maybe_name = anim_node.find('Name')
        if maybe_name is None or maybe_name.text is None:
            raise ValueError("Name missing in an Anim node of the XML")
        name = maybe_name.text
        backref_node = anim_node.find('CopyOf')
        if backref_node is None:
            frame_width = anim_node.find('FrameWidth')
            frame_height = anim_node.find('FrameHeight')
            if frame_width is None or frame_width.text is None or frame_height is None or frame_height.text is None:
                raise ValueError("FrameWidth or FrameHeight missing or empty")
            anim_dims[name] = (int(frame_width.text), int(frame_height.text))

    frames: List[Tuple[Image.Image, FrameOffset]] = []
    frame_mapping: Dict[str, Dict[Tuple[int, int, int, int], Tuple[int, bool]]] = {}
    for anim_name in anim_dims:
        anim_map: Dict[Tuple[int, int, int, int], Tuple[int, bool]] = {}
        frame_size = anim_dims[anim_name]
        if is_zip:
            img = readZipImg(path, anim_name + '-Anim.png')
            offset_img = readZipImg(path, anim_name + '-Offsets.png')
        else:
            img = Image.open(os.path.join(path, anim_name + '-Anim.png')).convert("RGBA")
            offset_img = Image.open(os.path.join(path, anim_name + '-Offsets.png')).convert("RGBA")
        
        for base_yy in range(0, img.size[1], frame_size[1]):
            # standardized to clockwise style
            yy = ((8 - base_yy // frame_size[1]) % 8) * frame_size[1]
            for xx in range(0, img.size[0], frame_size[0]):
                tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
                bounds = exUtils.getCoveredBounds(img, tile_bounds)

                missing_tex = True
                if bounds[0] >= bounds[2]:
                    bounds = (frame_size[0] // 2, frame_size[1] // 2, frame_size[0] // 2 + 1, frame_size[1] // 2 + 1)
                else:
                    missing_tex = False

                frame_offset = exUtils.getOffsetFromRGB(offset_img, tile_bounds, True, True, True, True, False)
                offsets = FrameOffset(None, None, None, None)
                offsets.center = frame_offset[2]
                if frame_offset[0] is None:
                    offsets.head = frame_offset[2]
                else:
                    offsets.head = frame_offset[0]
                    missing_tex = False

                # no texture OR offset means this frame is missing.  do not map it.  skip.
                if missing_tex:
                    continue

                offsets.lhand = frame_offset[1]
                offsets.rhand = frame_offset[3]
                offsets.AddLoc((-bounds[0], -bounds[1]))

                abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
                frame_tex = img.crop(abs_bounds)

                isDupe = False
                for idx, frame_pair in enumerate(frames):
                    final_frame, final_offset = frame_pair
                    if exUtils.imgsEqual(final_frame, frame_tex) and exUtils.offsetsEqual(final_offset, offsets, frame_tex.size[0]):
                        anim_map[abs_bounds] = (idx, False)
                        isDupe = True
                        break
                    if exUtils.imgsEqual(final_frame, frame_tex, True) and exUtils.offsetsEqual(final_offset, offsets, frame_tex.size[0], True):
                        anim_map[abs_bounds] = (idx, True)
                        isDupe = True
                        break
                if not isDupe:
                    anim_map[abs_bounds] = (len(frames), False)
                    frames.append((frame_tex, offsets))

        frame_mapping[anim_name] = anim_map
    return frames, frame_mapping

def getFrameSizeFromFrames(frames):

    max_width = 0
    max_height = 0
    for frame_tex, frame_offset in frames:
        max_width = max(max_width, frame_tex.size[0])
        max_height = max(max_height, frame_tex.size[1])
        offset_bounds = frame_offset.GetBounds()
        offset_bounds = exUtils.centerBounds(offset_bounds, (frame_tex.size[0] // 2, frame_tex.size[1] // 2))
        max_width = max(max_width, offset_bounds[2] - offset_bounds[0])
        max_height = max(max_height, offset_bounds[3] - offset_bounds[1])

    max_width = exUtils.roundUpToMult(max_width, 2)
    max_height = exUtils.roundUpToMult(max_height, 2)

    return max_width, max_height

def getCombinedImg(path, is_zip):
    frames, _ = getFramesAndMappings(path, is_zip)
    frame_size = getFrameSizeFromFrames(frames)

    max_size = int(math.ceil(math.sqrt(len(frames))))
    combinedImg = Image.new('RGBA', (frame_size[0] * max_size, frame_size[1] * max_size), (0, 0, 0, 0))

    for idx, frame_pair in enumerate(frames):
        frame = frame_pair[0]
        diffPos = (frame_size[0] // 2 - frame.size[0] // 2, frame_size[1] // 2 - frame.size[1] // 2)
        xx = idx % max_size
        yy = idx // max_size
        tilePos = (xx * frame_size[0], yy * frame_size[1])
        combinedImg.paste(frame, (tilePos[0] + diffPos[0], tilePos[1] + diffPos[1]), frame)

    return combinedImg, frame_size

def prepareSpriteRecolor(path):
    combinedImg, _ = getCombinedImg(path, False)
    return insertPalette(combinedImg)

def getSpriteRecolorMap(frames, shiny_frames):
    color_tbl = {}
    img_tbl = []

    for frame_tex in frames:
        for shiny_tex in shiny_frames:
            if exUtils.imgsLineartEqual(frame_tex, shiny_tex, False):
                img_tbl.append((frame_tex, shiny_tex))
                break

    color_lookup = {}

    # only do a color mapping for frames that have been known to fit
    for frame_tex, shiny_tex in img_tbl:
        datas = frame_tex.getdata()
        shinyDatas = shiny_tex.getdata()
        for idx in range(len(datas)):
            color = datas[idx]
            shinyColor = shinyDatas[idx]
            if color[3] != 255 or shinyColor[3] != 255:
                continue
            if color not in color_lookup:
                color_lookup[color] = {}
            if shinyColor not in color_lookup[color]:
                color_lookup[color][shinyColor] = 0
            color_lookup[color][shinyColor] += 1

    # sort by most common mapping
    for color in color_lookup:
        map_to = []
        for shinyColor in color_lookup[color]:
            map_to.append((shinyColor, color_lookup[color][shinyColor]))
        map_to = sorted(map_to, key=lambda stat: stat[1], reverse=True)
        color_tbl[color] = map_to

    return color_tbl, img_tbl

def getPortraitRecolorMap(img, shinyImg, frame_size):
    color_tbl = {}
    img_tbl = []

    for yy in range(0, img.size[1], frame_size[1]):
        for xx in range(0, img.size[0], frame_size[0]):
            tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
            bounds = exUtils.getCoveredBounds(img, tile_bounds)
            if bounds[0] >= bounds[2]:
                continue
            shiny_bounds = exUtils.getCoveredBounds(shinyImg, tile_bounds)
            if shiny_bounds[0] >= shiny_bounds[2]:
                continue
            abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
            frame_tex = img.crop(abs_bounds)
            shiny_tex = shinyImg.crop(abs_bounds)
            img_tbl.append((frame_tex, shiny_tex))

    color_lookup = {}
    datas = img.getdata()
    shinyDatas = shinyImg.getdata()
    for idx in range(len(datas)):
        color = datas[idx]
        shinyColor = shinyDatas[idx]
        if color[3] != 255 or shinyColor[3] != 255:
            continue
        if color not in color_lookup:
            color_lookup[color] = {}
        if shinyColor not in color_lookup[color]:
            color_lookup[color][shinyColor] = 0
        color_lookup[color][shinyColor] += 1
    # sort by most common mapping
    for color in color_lookup:
        map_to = []
        for shinyColor in color_lookup[color]:
            map_to.append((shinyColor, color_lookup[color][shinyColor]))
        map_to = sorted(map_to, key=lambda stat: stat[1], reverse=True)
        color_tbl[color] = map_to

    return color_tbl, img_tbl

def getRecoloredTex(color_tbl, img_tbl, frame_tex):
    # attempt to find an image in img_tbl that corresponds with this one
    for frame, shiny_frame in img_tbl:
        if exUtils.imgsEqual(frame, frame_tex):
            return shiny_frame, { }
        if exUtils.imgsEqual(frame, frame_tex, True):
            return shiny_frame.transpose(Image.FLIP_LEFT_RIGHT), { }
    # attempt to recolor the image
    datas = frame_tex.getdata()
    shiny_datas = [(0,0,0,0)] * len(datas)
    off_color_tbl = { }
    for idx in range(len(datas)):
        color = datas[idx]
        if color[3] != 255:
            continue
        # no color mapping at all?  we can't recolor it.  serious issue.
        if color not in color_tbl:
            off_color_tbl[color] = []
            shiny_colors = [(color, 0)]
        else:
            shiny_colors = color_tbl[color]
        if len(shiny_colors) > 1:
            off_color_tbl[color] = shiny_colors
        shiny_datas[idx] = shiny_colors[0][0]

    shiny_tex = Image.new('RGBA', frame_tex.size, (0, 0, 0, 0))
    shiny_tex.putdata(shiny_datas)
    return shiny_tex, off_color_tbl

def updateOffColorTable(total_off_color, off_color_tbl):
    for color in off_color_tbl:
        if color not in total_off_color:
            total_off_color[color] = {}
        sub_color = total_off_color[color]
        colors_to = off_color_tbl[color]
        for color_to, count in colors_to:
            if color_to not in sub_color:
                sub_color[color_to] = 0
            sub_color[color_to] += count

def autoRecolor(prev_base_file, cur_base_path, shiny_path, asset_type):
    cur_shiny_img = None
    total_off_color = {}
    if asset_type == "sprite":
        with zipfile.ZipFile(prev_base_file, 'r') as prev_base_zip:
            prev_frames, _ = getFramesAndMappings(prev_base_zip, True)
        prev_frames_only = [x[0] for x in prev_frames]
        frames, _ = getFramesAndMappings(cur_base_path, False)
        shiny_frames, _ = getFramesAndMappings(shiny_path, False)
        shiny_frames_only = [x[0] for x in shiny_frames]
        color_tbl, img_tbl = getSpriteRecolorMap(prev_frames_only, shiny_frames_only)

        frame_size = getFrameSizeFromFrames(frames)

        max_size = int(math.ceil(math.sqrt(len(frames))))
        cur_base_img = Image.new('RGBA', (frame_size[0] * max_size, frame_size[1] * max_size), (0, 0, 0, 0))
        cur_shiny_img = Image.new('RGBA', (frame_size[0] * max_size, frame_size[1] * max_size), (0, 0, 0, 0))

        for idx, frame_pair in enumerate(frames):
            frame = frame_pair[0]
            recolored_frame, off_color_tbl = getRecoloredTex(color_tbl, img_tbl, frame)
            updateOffColorTable(total_off_color, off_color_tbl)

            diffPos = (frame_size[0] // 2 - frame.size[0] // 2, frame_size[1] // 2 - frame.size[1] // 2)
            xx = idx % max_size
            yy = idx // max_size
            tilePos = (xx * frame_size[0], yy * frame_size[1])
            cur_base_img.paste(frame, (tilePos[0] + diffPos[0], tilePos[1] + diffPos[1]), frame)
            cur_shiny_img.paste(recolored_frame, (tilePos[0] + diffPos[0], tilePos[1] + diffPos[1]), recolored_frame)

    elif asset_type == "portrait":
        prev_base_img = Image.open(prev_base_file).convert("RGBA")
        prev_shiny_img = preparePortraitImage(shiny_path)

        cur_base_img = preparePortraitImage(cur_base_path)
        frame_size = (Constants.PORTRAIT_SIZE, Constants.PORTRAIT_SIZE)
        color_tbl, img_tbl = getPortraitRecolorMap(prev_base_img, prev_shiny_img, frame_size)

        cur_shiny_img = Image.new('RGBA', cur_base_img.size, (0, 0, 0, 0))
        for yy in range(0, cur_base_img.size[1], frame_size[1]):
            for xx in range(0, cur_base_img.size[0], frame_size[0]):
                tile_bounds = (xx, yy, xx + frame_size[0], yy + frame_size[1])
                bounds = exUtils.getCoveredBounds(cur_base_img, tile_bounds)
                if bounds[0] >= bounds[2]:
                    continue
                abs_bounds = exUtils.addToBounds(bounds, (xx, yy))
                frame_tex = cur_base_img.crop(abs_bounds)
                shiny_tex, off_color_tbl = getRecoloredTex(color_tbl, img_tbl, frame_tex)
                updateOffColorTable(total_off_color, off_color_tbl)

                cur_shiny_img.paste(shiny_tex, (abs_bounds[0], abs_bounds[1]), shiny_tex)
    else:
        raise ValueError("asset_type is neither sprite nor portrait")

    # check the shiny against needed tags
    # check against colors compared to original
    # check against total colors over 15
    args = []

    base_palette = getPalette(cur_base_img)
    shiny_palette = getPalette(cur_shiny_img)
    palette_diff = len(shiny_palette) - len(base_palette)
    if palette_diff != 0:
        args.append("--colormod " + str(palette_diff))

    if asset_type == "portrait":
        palette_counts = {}
        in_data = cur_shiny_img.getdata()
        img_tile_size = (cur_shiny_img.size[0] // Constants.PORTRAIT_SIZE, cur_shiny_img.size[1] // Constants.PORTRAIT_SIZE)
        for xx in range(Constants.PORTRAIT_TILE_X):
            for yy in range(Constants.PORTRAIT_TILE_Y):
                if xx >= img_tile_size[0] or yy >= img_tile_size[1]:
                    continue
                first_pos = (xx * Constants.PORTRAIT_SIZE, yy * Constants.PORTRAIT_SIZE)
                first_pixel = in_data[first_pos[1] * cur_shiny_img.size[0] + first_pos[0]]
                if first_pixel[3] == 0:
                    continue

                palette = {}
                for mx in range(Constants.PORTRAIT_SIZE):
                    for my in range(Constants.PORTRAIT_SIZE):
                        cur_pos = (first_pos[0] + mx, first_pos[1] + my)
                        cur_pixel = in_data[cur_pos[1] * cur_shiny_img.size[0] + cur_pos[0]]
                        palette[cur_pixel] = True
                palette_counts[(xx, yy)] = len(palette)

        overpalette = False
        for emote_loc in palette_counts:
            if palette_counts[emote_loc] > 15:
                overpalette = True

        if overpalette:
            args.append("--overcolor")
    elif asset_type == "sprite":
        if len(shiny_palette) > 15:
            args.append("=" + str(len(shiny_palette)))

    cmd_str = " ".join(args)

    # also add information about off-colors
    content = ""
    color_content = ""
    for idx, color in enumerate(total_off_color):
        if len(color_content) > 1000:
            color_content += "\n+{0} More".format(len(total_off_color) - idx)
            break
        sub_color = total_off_color[color]
        result_array = []
        for color_to in sub_color:
            result_array.append(colorToHex(color_to) + ":" + str(sub_color[color_to]))
        color_content += "\n{0}-> {1}".format(colorToHex(color), ", ".join(result_array))
    if len(color_content) > 0:
        content += "\n__This auto-generated recolor has ambiguous mappings below:__"
        content += color_content
    else:
        content += "\n__This is an auto-generated recolor.__"

    cur_shiny_img = insertPalette(cur_shiny_img)

    return cur_shiny_img, cmd_str, content.strip()


def colorToHex(color):
    return ('#%02x%02x%02x' % color[:3]).upper()

"""
Returns Image
"""
def preparePortraitImage(path):
    printImg = Image.new('RGBA', (Constants.PORTRAIT_SHEET_WIDTH, Constants.PORTRAIT_SHEET_HEIGHT), (0, 0, 0, 0))
    maxX = 0
    maxY = 0
    for file in os.listdir(path):
        filename, ext = os.path.splitext(file)
        if ext == '.png':
            for idx in range(len(Constants.EMOTIONS)):
                use = False
                flip = False
                if Constants.EMOTIONS[idx] == filename:
                    use = True
                elif Constants.EMOTIONS[idx] + "^" == filename:
                    use = True
                    flip = True

                if use:
                    inImg = Image.open(os.path.join(path, file)).convert("RGBA")
                    placeX = Constants.PORTRAIT_SIZE * (idx % Constants.PORTRAIT_TILE_X)
                    placeY = Constants.PORTRAIT_SIZE * (idx // Constants.PORTRAIT_TILE_X)
                    # handle flips
                    if flip:
                        placeY += 4 * Constants.PORTRAIT_SIZE
                    printImg.paste(inImg, (placeX, placeY))
                    maxX = max(maxX, placeX + Constants.PORTRAIT_SIZE)
                    maxY = max(maxY, placeY + Constants.PORTRAIT_SIZE)
                    break

    if maxX > 0 and maxY > 0:
        if Constants.CROP_PORTRAITS:
            return printImg.crop((0,0,maxX, maxY))
        return printImg
    return None

def preparePortraitRecolor(path):
    portraitImg = preparePortraitImage(path)
    portraitImg = insertPalette(portraitImg)
    return portraitImg



def simple_quant_portraits(img, overpalette):
    reduced_img = img.copy()
    for emote_loc in overpalette:
        crop_pos = (emote_loc[0] * Constants.PORTRAIT_SIZE, emote_loc[1] * Constants.PORTRAIT_SIZE,
                    (emote_loc[0] + 1) * Constants.PORTRAIT_SIZE, (emote_loc[1] + 1) * Constants.PORTRAIT_SIZE)
        portrait_img = reduced_img.crop(crop_pos)

        reduced_portrait = simple_quant(portrait_img, 15)
        reduced_img.paste(reduced_portrait, crop_pos)

    return reduced_img

def simple_quant(img: Image.Image, colors) -> Image.Image:
    """
    Simple single-palette image quantization. Reduces to specified number of colors and adds one transparent color at index 0.
    The transparent (alpha=0) pixels in the input image are converted to that color.
    If you need to do tiled multi-palette quantization, use Tilequant instead!
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    transparency_map = [px[3] == 0 for px in img.getdata()]
    qimg = img.quantize(colors, dither=0).convert('RGBA')
    # Shift up all pixel values by 1 and add the transparent pixels
    pixels = qimg.load()
    k = 0
    for j in range(img.size[1]):
        for i in range(img.size[0]):
            if transparency_map[k]:
                pixels[i, j] = (0, 0, 0, 0)
            k += 1
    return qimg

def sanitizeLink(url):
    result = re.sub("\?.+", "", url)
    return result
