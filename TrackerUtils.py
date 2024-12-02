
import os
import re
import shutil
import datetime
import xml.etree.ElementTree as ET
import Constants

CURRENT_LICENSE = "CC_BY-NC_4"

MAX_SECONDARY_CREDIT = 2
PHASE_INCOMPLETE = 0
PHASE_EXISTS = 1
PHASE_FULL = 2

class CreditEvent:
    """
    A class for handling credit in credit history
    """
    def __init__(self, datetime, name, old, license, changed):
        self.datetime = datetime
        self.name = name
        self.old = old
        self.license = license
        self.changed = changed

def getStatusEmoji(chosen_node, asset_type):
    pending = chosen_node.__dict__[asset_type+"_pending"]
    added = chosen_node.__dict__[asset_type + "_credit"].primary != ""
    complete = chosen_node.__dict__[asset_type+"_complete"]
    required = chosen_node.__dict__[asset_type+"_required"]
    if complete > PHASE_EXISTS: # star
        return "\u2B50"
    elif len(pending) > 0:
        if complete > PHASE_INCOMPLETE:  # interrobang
            return "\u2049"
        else:  # question
            return "\u2754"
    elif added:
        if len(pending) > 0:  # interrobang
            return "\u2049"
        else:
            if complete > PHASE_INCOMPLETE:  # checkmark
                return "\u2705"
            else:  # white circle
                return "\u26AA"
    else:
        if required:  # X mark
            return "\u274C"
        else:  # black circle
            return "\u26AB"

def getCreditEntries(path):
    credits = getFileCredits(path)

    found_names = {}
    credit_strings = []
    for credit in credits:
        credit_id = credit.name
        if credit.old == "OLD":
            continue
        if credit_id not in found_names:
            credit_strings.append(credit_id)
            found_names[credit_id] = True
    return credit_strings

def hasExistingCredits(cur_credits, orig_author, diff):
    for credit in cur_credits:
        if credit.name == orig_author:
            event_diffs = credit.changed.split(',')
            if diff in event_diffs:
                return True
    return False

def getFileCredits(path):
    id_list = []
    credit_path = os.path.join(path, Constants.CREDIT_TXT)
    if os.path.exists(credit_path):
        with open(credit_path, 'r', encoding='utf-8') as txt:
            for line in txt:
                credit = line.strip().split('\t')
                if len(credit) >= 5:
                    id_list.append(CreditEvent(credit[0], credit[1], credit[2], credit[3], credit[4]))
                else:
                    raise BaseException("Invalid credit line “{}” at {}".format(line, credit_path))
    return id_list

def appendCredits(path, id, diff):
    if diff == '':
        diff = '"'
    with open(os.path.join(path, Constants.CREDIT_TXT), 'a+', encoding='utf-8') as txt:
        txt.write("{0}\t{1}\tCUR\t{2}\t{3}\n".format(str(datetime.datetime.utcnow()), id, CURRENT_LICENSE, diff))

def mergeCredits(path_from, path_to):
    id_list = []
    with open(path_to, 'r', encoding='utf-8') as txt:
        for line in txt:
            credit = line.strip().split('\t')
            id_list.append(CreditEvent(credit[0], credit[1], credit[2], credit[3], credit[4]))

    with open(path_from, 'r', encoding='utf-8') as txt:
        for line in txt:
            credit = line.strip().split('\t')
            id_list.append(CreditEvent(credit[0], credit[1], credit[2], credit[3], credit[4]))

    id_list = sorted(id_list, key=lambda x: x.datetime)

    with open(path_to, 'w', encoding='utf-8') as txt:
        for credit in id_list:
            txt.write("{0}\t{1}\t{2}\t{3}\t{4}\n".format(credit.datetime, credit.name, credit.old, credit.license, credit.changed))

def shiftCredits(fullPath):
    id_list = []
    with open(fullPath, 'r', encoding='utf-8') as txt:
        for line in txt:
            id_list.append(line.strip().split('\t'))
    for idx in range(len(id_list)):
        if id_list[idx][1] == "CHUNSOFT":
            id_list[idx][3] = "Unspecified"
    with open(fullPath, 'w', encoding='utf-8') as txt:
        for entry in id_list:
            txt.write(entry[0] + "\t" + entry[1] + "\t" + entry[2] + "\t" + entry[3] + "\t" + entry[4] + "\n")

def deleteCredits(path, id):
    id_list = []
    fullPath = os.path.join(path, Constants.CREDIT_TXT)
    with open(fullPath, 'r', encoding='utf-8') as txt:
        for line in txt:
            id_list.append(line.strip().split('\t'))
    for entry in id_list:
        if entry[1] == id:
            entry[2] = "OLD"
    with open(fullPath, 'w', encoding='utf-8') as txt:
        for entry in id_list:
            txt.write(entry[0] + "\t" + entry[1] + "\t" + entry[2] + "\t" + entry[3] + "\t" + entry[4] + "\n")

class CreditEntry:
    """
    A class for determining a contributor's contribution
    """
    def __init__(self, name, contact):
        self.name = name
        self.sprites = False
        self.portraits = False
        self.contact = contact

class CreditCompileEntry:
    """
    A class for determining a contributor's contribution
    """
    def __init__(self, name, contact):
        self.name = name
        self.sprite = {}
        self.portrait = {}
        self.contact = contact

class TrackerNode:
    name: str
    modreward: bool

    def __init__(self, node_dict):
        temp_list = [i for i in node_dict]
        temp_list = sorted(temp_list)

        main_dict = { }
        for key in temp_list:
            main_dict[key] = node_dict[key]

        self.__dict__ = main_dict

        if "sprite_talk" not in self.__dict__:
            self.sprite_talk = {}
            self.portrait_talk = {}

        self.sprite_credit = CreditNode(node_dict["sprite_credit"])
        self.portrait_credit = CreditNode(node_dict["portrait_credit"])

        sub_dict = { }
        for key in self.subgroups:
            sub_dict[key] = TrackerNode(self.subgroups[key])
        self.subgroups = sub_dict

    def getDict(self):
        node_dict = { }
        for k in self.__dict__:
            node_dict[k] = self.__dict__[k]

        node_dict["sprite_credit"] = self.sprite_credit.getDict()
        node_dict["portrait_credit"] = self.portrait_credit.getDict()

        sub_dict = { }
        for sub_idx in self.subgroups:
            sub_dict[sub_idx] = self.subgroups[sub_idx].getDict()
        node_dict["subgroups"] = sub_dict
        return node_dict

class CreditNode:

    def __init__(self, node_dict):
        temp_list = [i for i in node_dict]
        temp_list = sorted(temp_list)

        main_dict = { }
        for key in temp_list:
            main_dict[key] = node_dict[key]

        self.__dict__ = main_dict

    def getDict(self):
        node_dict = { }
        for k in self.__dict__:
            node_dict[k] = self.__dict__[k]
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

def initCreditDict():
    credit_dict = { }
    credit_dict["primary"] = ""
    credit_dict["secondary"] = []
    credit_dict["total"] = 0
    return credit_dict

def initSubNode(name, canon):
    sub_dict = { }
    sub_dict["name"] = name
    sub_dict["canon"] = canon
    sub_dict["modreward"] = not canon
    sub_dict["portrait_complete"] = 0
    sub_dict["portrait_credit"] = initCreditDict()
    sub_dict["portrait_link"] = ""
    sub_dict["portrait_files"] = {}
    sub_dict["portrait_bounty"] = {}
    sub_dict["portrait_modified"] = ""
    sub_dict["portrait_pending"] = {}
    sub_dict["portrait_recolor_link"] = ""
    sub_dict["portrait_required"] = False
    sub_dict["portrait_talk"] = {}
    sub_dict["sprite_complete"] = 0
    sub_dict["sprite_credit"] = initCreditDict()
    sub_dict["sprite_files"] = {}
    sub_dict["sprite_bounty"] = {}
    sub_dict["sprite_link"] = ""
    sub_dict["sprite_modified"] = ""
    sub_dict["sprite_pending"] = {}
    sub_dict["sprite_recolor_link"] = ""
    sub_dict["sprite_required"] = False
    sub_dict["sprite_talk"] = {}
    sub_dict["subgroups"] = {}
    return TrackerNode(sub_dict)

def getCurrentCompletion(orig_dict, dict, prefix):

    for orig_file in orig_dict.__dict__[prefix + "_files"]:
        if orig_file not in dict.__dict__[prefix + "_files"]:
            return PHASE_INCOMPLETE

    if prefix == "sprite":
        completion = PHASE_FULL
        while completion > PHASE_INCOMPLETE:
            has_all = True
            for idx in Constants.COMPLETION_ACTIONS[completion]:
                file = Constants.ACTIONS[idx]
                if file not in dict.__dict__[prefix + "_files"]:
                    has_all = False
                    break
            if has_all:
                break
            completion -= 1
        return completion
    else:
        completion = PHASE_FULL
        search_flip = False
        for file in dict.__dict__[prefix + "_files"]:
            if file.endswith("^"):
                search_flip = True
                break
        while completion > PHASE_INCOMPLETE:
            has_all = True
            for idx in Constants.COMPLETION_EMOTIONS[completion]:
                file = Constants.EMOTIONS[idx]
                if file not in dict.__dict__[prefix + "_files"]:
                    has_all = False
                    break
                if search_flip:
                    file_flip = file + "^"
                    if file_flip not in dict.__dict__[prefix + "_files"]:
                        has_all = False
                        break
            if has_all:
                break
            completion -= 1
        return completion



def updateFiles(dict, species_path, prefix):
    file_list = []
    if prefix == "sprite":
        if os.path.exists(os.path.join(species_path, Constants.MULTI_SHEET_XML)):
            tree = ET.parse(os.path.join(species_path, Constants.MULTI_SHEET_XML))
            root = tree.getroot()
            anims_node = root.find('Anims')
            for anim_node in anims_node.iter('Anim'):
                name = anim_node.find('Name').text
                file_list.append(name)
    else:
        for inFile in os.listdir(species_path):
            if inFile.endswith(".png"):
                file, _ = os.path.splitext(inFile)
                file_list.append(file)

    for file in file_list:
        if file not in dict.__dict__[prefix + "_files"]:
            dict.__dict__[prefix + "_files"][file] = False

def updateCreditFromEntries(credit_data, credit_entries):
    # updates just the total count and the secondary
    # the primary author is user-defined
    credit_data.total = len(credit_entries)
    credit_data.secondary.clear()

    for credit_entry in reversed(credit_entries):
        if credit_entry != credit_data.primary:
            credit_data.secondary.insert(0, credit_entry)
            if len(credit_data.secondary) >= MAX_SECONDARY_CREDIT:
                break


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
                        dict.subgroups[inFile] = initSubNode("", dict.canon)
                    else:
                        dict.subgroups[inFile] = initSubNode("Form" + inFile, dict.canon)
                elif tier == 2:
                    if inFile == "0001":
                        dict.subgroups[inFile] = initSubNode("Shiny", dict.canon)
                    else:
                        dict.subgroups[inFile] = initSubNode("", dict.canon)
                elif tier == 3:
                    if inFile == "0001":
                        dict.subgroups[inFile] = initSubNode("Male", dict.canon)
                    elif inFile == "0002":
                        dict.subgroups[inFile] = initSubNode("Female", dict.canon)
                    else:
                        dict.subgroups[inFile] = initSubNode("", dict.canon)

            fileSystemToJson(dict.subgroups[inFile], fullPath, prefix, tier + 1)
        elif inFile == Constants.CREDIT_TXT:
            #shiftCredits(fullPath)
            credit_entries = getCreditEntries(species_path)
            credit_data = dict.__dict__[prefix + "_credit"]
            updateCreditFromEntries(credit_data, credit_entries)
        else:
            modify_datetime = datetime.datetime.utcfromtimestamp(os.path.getmtime(fullPath))
            if str(modify_datetime) > last_modify:
                last_modify = str(modify_datetime)

    updateFiles(dict, species_path, prefix)

    updated = False
    if dict.__dict__[prefix + "_modified"] < last_modify:
        dict.__dict__[prefix + "_modified"] = last_modify
        updated = True

    # the link always starts off blank, or is set to blank when last-modified is updated
    if updated:
        dict.__dict__[prefix + "_link"] = ""

def isDataPopulated(sub_dict):
    if sub_dict.sprite_credit.primary != "":
        return True
    if sub_dict.portrait_credit.primary != "":
        return True

    for sub_idx in sub_dict.subgroups:
        if isDataPopulated(sub_dict.subgroups[sub_idx]):
            return True
    return False

def deleteData(tracker_dict, portrait_path, sprite_path, idx):
    next_idx = "{:04d}".format(int(idx) + 1)
    while next_idx in tracker_dict:
        # replace with the index in front
        tracker_dict[idx] = tracker_dict[next_idx]
        # replace the path with the index in front
        if os.path.exists(os.path.join(portrait_path, idx)):
            shutil.rmtree(os.path.join(portrait_path, idx))
        if os.path.exists(os.path.join(sprite_path, idx)):
            shutil.rmtree(os.path.join(sprite_path, idx))

        if os.path.exists(os.path.join(portrait_path, next_idx)):
            shutil.move(os.path.join(portrait_path, next_idx), os.path.join(portrait_path, idx))
        if os.path.exists(os.path.join(sprite_path, next_idx)):
            shutil.move(os.path.join(sprite_path, next_idx), os.path.join(sprite_path, idx))

        idx = next_idx
        next_idx = "{:04d}".format(int(idx) + 1)

    del tracker_dict[idx]
    if os.path.exists(os.path.join(portrait_path, idx)):
        shutil.rmtree(os.path.join(portrait_path, idx))
    if os.path.exists(os.path.join(sprite_path, idx)):
        shutil.rmtree(os.path.join(sprite_path, idx))


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

def isTrackerIdxEqual(idx1, idx2):
    if len(idx1) != len(idx2):
        return False

    for ii in range(len(idx1)):
        if idx1[ii] != idx2[ii]:
            return False

    return True

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

def genderDiffExists(form_dict, asset_type, gender):
    if "0000" not in form_dict.subgroups:
        return False
    normal_dict = form_dict.subgroups["0000"].subgroups

    gender_idx = findSlotIdx(normal_dict, gender)
    if gender_idx is not None:
        gender_dict = normal_dict[gender_idx]
        if gender_dict.__dict__[asset_type + "_required"]:
            return True

    return False

def genderDiffPopulated(form_dict, asset_type):
    if "0000" not in form_dict.subgroups:
        return False
    normal_dict = form_dict.subgroups["0000"].subgroups

    genders = ["Male", "Female"]
    for gender in genders:
        gender_idx = findSlotIdx(normal_dict, gender)
        if gender_idx is not None:
            gender_dict = normal_dict[gender_idx]
            if gender_dict.__dict__[asset_type + "_credit"].primary != "":
                return True

    return False

def createGenderDiff(form_dict, asset_type, gender_name):
    if "0000" not in form_dict.subgroups:
        form_dict.subgroups["0000"] = initSubNode("", form_dict.canon)
    normal_dict = form_dict.subgroups["0000"]
    createShinyGenderDiff(normal_dict, asset_type, gender_name)

    shiny_dict = form_dict.subgroups["0001"]
    createShinyGenderDiff(shiny_dict, asset_type, gender_name)

def createShinyGenderDiff(color_dict, asset_type, gender_name):
    gender_idx = findSlotIdx(color_dict.subgroups, gender_name)
    if gender_idx is None:
        gender_dict = initSubNode(gender_name, color_dict.canon)
        if gender_name == "Male":
            color_dict.subgroups["0001"] = gender_dict
        else:
            color_dict.subgroups["0002"] = gender_dict
    else:
        gender_dict = color_dict.subgroups[gender_idx]
    gender_dict.__dict__[asset_type + "_required"] = True


def removeGenderDiff(form_dict, asset_type):
    normal_dict = form_dict.subgroups["0000"]
    nothing_left = removeColorGenderDiff(normal_dict, asset_type, "Male")
    nothing_left &= removeColorGenderDiff(normal_dict, asset_type, "Female")
    if nothing_left:
        del form_dict.subgroups["0000"]

    shiny_dict = form_dict.subgroups["0001"]
    removeColorGenderDiff(shiny_dict, asset_type, "Male")
    removeColorGenderDiff(shiny_dict, asset_type, "Female")

def removeColorGenderDiff(color_dict, asset_type, gender):
    # return whether or not the gender was fully deleted
    gender_idx = findSlotIdx(color_dict.subgroups, gender)
    if gender_idx is None:
        return True

    gender_dict = color_dict.subgroups[gender_idx]
    gender_dict.__dict__[asset_type + "_required"] = False
    if not gender_dict.__dict__["sprite_required"] and not gender_dict.__dict__["portrait_required"]:
        del color_dict.subgroups[gender_idx]
        return True

    return False

def createFormNode(name, canon):
    forme_dict = initSubNode(name, canon)
    forme_dict.sprite_required = True
    forme_dict.portrait_required = True
    shiny_dict = initSubNode("Shiny", canon)
    forme_dict.subgroups["0001"] = shiny_dict
    shiny_dict.sprite_required = True
    shiny_dict.portrait_required = True
    return forme_dict

def createSpeciesNode(name):

    sub_dict = initSubNode(name, True)
    sub_dict.sprite_required = True
    sub_dict.portrait_required = True
    forme_dict = initSubNode("", True)
    sub_dict.subgroups["0000"] = forme_dict
    shiny_dict = initSubNode("Shiny", True)
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

def updateCreditCompilation(name_path, credit_dict):

    with open(name_path, 'w+', encoding='utf-8') as txt:
        txt.write("All custom graphics not originating from official PMD games are licensed under Attribution-NonCommercial 4.0 International http://creativecommons.org/licenses/by/4.0/.\n")
        txt.write("All graphics referred to in this file can be found in http://sprites.pmdcollab.org/\n\n")
        for handle in credit_dict:
            if len(credit_dict[handle].sprite) > 0 or len(credit_dict[handle].portrait) > 0:
                name_components = []
                if len(credit_dict[handle].name):
                    name_components.append(credit_dict[handle].name)

                if handle.startswith("<@!"):
                    name_components.append("Discord:{0}".format(handle))

                if len(credit_dict[handle].contact):
                    name_components.append("Contact:{0}".format(credit_dict[handle].contact))

                txt.write("{0}\n".format("\t".join(name_components)))

                if len(credit_dict[handle].portrait) > 0:
                    txt.write("\tPortrait:\n")
                    # for each portrait
                    for id_key in credit_dict[handle].portrait:
                        all_parts = []
                        for subpart in credit_dict[handle].portrait[id_key]:
                            all_parts.append(subpart)
                        if len(all_parts) > 0:
                            txt.write("\t\t{0}: {1}\n".format(id_key, ",".join(all_parts)))

                if len(credit_dict[handle].sprite) > 0:
                    txt.write("\tSprite:\n")
                    # for each sprite
                    for id_key in credit_dict[handle].sprite:
                        all_parts = []
                        for subpart in credit_dict[handle].sprite[id_key]:
                            all_parts.append(subpart)
                        if len(all_parts) > 0:
                            txt.write("\t\t{0}: {1}\n".format(id_key, ",".join(all_parts)))
                txt.write("\n")

def updateCompilationStats(name_dict, dict, species_path, prefix, form_name_list, credit_dict):
    # generate the form name
    form_name = " ".join([i for i in form_name_list if i != ""])
    # is there a credits txt?  read it
    credits = getFileCredits(species_path)
    # for each entry, update the credit dict
    for credit in credits:
        if credit.old == "CUR":
            # add entry if not existing
            if credit.name not in credit_dict:
                if credit.name in name_dict:
                    credit_dict[credit.name] = CreditCompileEntry(name_dict[credit.name].name, name_dict[credit.name].contact)
                else:
                    credit_dict[credit.name] = CreditCompileEntry("", "")
            compile_entry = credit_dict[credit.name]
            asset_dict = compile_entry.__dict__[prefix]
            if form_name not in asset_dict:
                asset_dict[form_name] = {}
            subpart_dict = asset_dict[form_name]
            subpart_list = credit.changed.split(',')
            for subpart in subpart_list:
                subpart_dict[subpart] = True

    for sub_dict in dict.subgroups:
        form_name_list.append(dict.subgroups[sub_dict].name)
        updateCompilationStats(name_dict, dict.subgroups[sub_dict], os.path.join(species_path, sub_dict), prefix, form_name_list, credit_dict)
        form_name_list.pop()

def updateNameFile(name_path, name_dict, include_all):
    with open(name_path, 'w+', encoding='utf-8') as txt:
        txt.write("Name\tDiscord\tContact\n")
        for handle in name_dict:
            if include_all or name_dict[handle].sprites or name_dict[handle].portraits:
                txt.write("{0}\t{1}\t{2}\n".format(name_dict[handle].name, handle, name_dict[handle].contact))

def addNameStat(name_dict, name, portrait):
    if name != "":
        if name not in name_dict:
            name_dict[name] = CreditEntry("", "")
        if not portrait:
            name_dict[name].sprites = True
        else:
            name_dict[name].portraits = True

def updateNameStats(name_dict, dict):
    addNameStat(name_dict, dict.sprite_credit.primary, False)
    for secondary in dict.sprite_credit.secondary:
        addNameStat(name_dict, secondary, False)
    addNameStat(name_dict, dict.portrait_credit.primary, True)
    for secondary in dict.portrait_credit.secondary:
        addNameStat(name_dict, secondary, True)

    for sub_dict in dict.subgroups:
        updateNameStats(name_dict, dict.subgroups[sub_dict])

def renameJsonCredits(dict, old_name, new_name):
    if dict.sprite_credit.primary == old_name:
        dict.sprite_credit.primary = new_name
    for idx in range(len(dict.sprite_credit.secondary)):
        if dict.sprite_credit.secondary[idx] == old_name:
            dict.sprite_credit.secondary[idx] = new_name

    if dict.portrait_credit.primary == old_name:
        dict.portrait_credit.primary = new_name
    for idx in range(len(dict.portrait_credit.secondary)):
        if dict.portrait_credit.secondary[idx] == old_name:
            dict.portrait_credit.secondary[idx] = new_name

    for sub_dict in dict.subgroups:
        renameJsonCredits(dict.subgroups[sub_dict], old_name, new_name)


def renameFileCredits(species_path, old_name, new_name):
    # renames all mentions of an author to a different author
    for inFile in os.listdir(species_path):
        fullPath = os.path.join(species_path, inFile)
        if os.path.isdir(fullPath):
            renameFileCredits(fullPath, old_name, new_name)
        elif inFile == Constants.CREDIT_TXT:
            id_list = []
            with open(fullPath, 'r', encoding='utf-8') as txt:
                for line in txt:
                    id_list.append(line.strip().split('\t'))
            for entry in id_list:
                if entry[1] == old_name:
                    entry[1] = new_name
            with open(fullPath, 'w', encoding='utf-8') as txt:
                for entry in id_list:
                    txt.write(entry[0] + "\t" + entry[1] + "\t" + entry[2] + "\t" + entry[3] + "\t" + entry[4] + "\n")

def getDirFromIdx(base_path, asset_type, full_idx):
    full_arr = [base_path, asset_type] + full_idx
    return os.path.join(*full_arr)

def moveNodeFiles(dir_from, dir_to, merge_credit, is_dir):
    cur_files = os.listdir(dir_from)
    for file in cur_files:
        # exclude tmp as it is a special folder name for temp files
        if file == "tmp":
            continue
        full_base_path = os.path.join(dir_from, file)
        if merge_credit and file == Constants.CREDIT_TXT:
            #mergeCredits(full_base_path, os.path.join(dir_to, file))
            #os.remove(full_base_path)
            shutil.move(full_base_path, os.path.join(dir_to, file))
        elif os.path.isdir(full_base_path) == is_dir:
            shutil.move(full_base_path, os.path.join(dir_to, file))

def deleteNodeFiles(dir_to, include_credit):
    cur_files = os.listdir(dir_to)
    for file in cur_files:
        # exclude tmp as it is a special folder name for temp files
        if file == "tmp":
            continue
        full_base_path = os.path.join(dir_to, file)
        if os.path.isdir(full_base_path):
            continue
        if include_credit or file != Constants.CREDIT_TXT:
            os.remove(full_base_path)

def clearCache(chosen_node, recursive):
    chosen_node.sprite_link = ""
    chosen_node.portrait_link = ""
    chosen_node.sprite_recolor_link = ""
    chosen_node.portrait_recolor_link = ""

    if recursive:
        for subgroup in chosen_node.subgroups:
            clearCache(chosen_node.subgroups[subgroup], recursive)

def swapNodeMiscFeatures(node_from, node_to):
    for key in node_from.__dict__:
        if key.startswith("sprite"):
            pass
        elif key.startswith("portrait"):
            pass
        elif key == "canon" or key == "modreward" or key == "subgroups":
            pass
        else:
            tmp = node_to.__dict__[key]
            node_to.__dict__[key] = node_from.__dict__[key]
            node_from.__dict__[key] = tmp

def swapNodeAssetFeatures(node_from, node_to, asset_type):
    for key in node_from.__dict__:
        if key.startswith(asset_type):
            tmp = node_to.__dict__[key]
            node_to.__dict__[key] = node_from.__dict__[key]
            node_from.__dict__[key] = tmp


def swapFolderPaths(base_path, tracker, asset_type, full_idx_from, full_idx_to):

    # swap the nodes in tracker, don't do it recursively
    chosen_node_from = getNodeFromIdx(tracker, full_idx_from, 0)
    chosen_node_to = getNodeFromIdx(tracker, full_idx_to, 0)

    swapNodeAssetFeatures(chosen_node_from, chosen_node_to, asset_type)

    # prepare to swap textures
    gen_path_from = getDirFromIdx(base_path, asset_type, full_idx_from)
    gen_path_to = getDirFromIdx(base_path, asset_type, full_idx_to)

    if not os.path.exists(gen_path_from):
        os.makedirs(gen_path_from, exist_ok=True)

    if not os.path.exists(gen_path_to):
        os.makedirs(gen_path_to, exist_ok=True)

    # move textures to a temp folder
    gen_path_tmp = os.path.join(gen_path_from, "tmp")
    os.makedirs(gen_path_tmp, exist_ok=True)
    moveNodeFiles(gen_path_from, gen_path_tmp, False, False)

    # swap the folders
    moveNodeFiles(gen_path_to, gen_path_from, False, False)
    moveNodeFiles(gen_path_tmp, gen_path_to, False, False)
    shutil.rmtree(gen_path_tmp)


def replaceNodeAssetFeatures(node_from, node_to, asset_type):
    node_new = initSubNode("", False)
    for key in node_from.__dict__:
        if key.startswith(asset_type):
            if key == asset_type + "_files":
                # pass in keys and set to false, only if new keys are introduced
                for file_key in node_from.__dict__[key]:
                    if file_key not in node_to.__dict__[key]:
                        node_to.__dict__[key][file_key] = False
            elif key == asset_type + "_talk":
                # do not overwrite
                pass
            elif key == asset_type + "_bounty":
                for status_key in node_from.__dict__[key]:
                    if status_key not in node_to.__dict__[key]:
                        node_to.__dict__[key][status_key] = 0
                    node_to.__dict__[key][status_key] = node_to.__dict__[key][status_key] + node_from.__dict__[key][status_key]
            else:
                node_to.__dict__[key] = node_from.__dict__[key]
            node_from.__dict__[key] = node_new.__dict__[key]

def replaceFolderPaths(base_path, tracker, asset_type, full_idx_from, full_idx_to):

    # swap the nodes in tracker, don't do it recursively
    chosen_node_from = getNodeFromIdx(tracker, full_idx_from, 0)
    chosen_node_to = getNodeFromIdx(tracker, full_idx_to, 0)

    replaceNodeAssetFeatures(chosen_node_from, chosen_node_to, asset_type)

    # prepare to swap textures
    gen_path_from = getDirFromIdx(base_path, asset_type, full_idx_from)
    gen_path_to = getDirFromIdx(base_path, asset_type, full_idx_to)

    if not os.path.exists(gen_path_from):
        os.makedirs(gen_path_from, exist_ok=True)

    if not os.path.exists(gen_path_to):
        os.makedirs(gen_path_to, exist_ok=True)

    # swap the folders
    deleteNodeFiles(gen_path_to, False)
    moveNodeFiles(gen_path_from, gen_path_to, True, False)


def swapNodeMiscCanon(chosen_node_from, chosen_node_to):
    for key in chosen_node_from.__dict__:
        if key == "canon" or key == "modreward":
            tmp = chosen_node_to.__dict__[key]
            chosen_node_to.__dict__[key] = chosen_node_from.__dict__[key]
            chosen_node_from.__dict__[key] = tmp

    for sub_id in chosen_node_from.subgroups:
        if sub_id in chosen_node_to.subgroups:
            sub_from = chosen_node_from.subgroups[sub_id]
            sub_to = chosen_node_from.subgroups[sub_id]
            swapNodeMiscCanon(sub_from, sub_to)

def swapAllSubNodes(base_path, tracker, full_idx_from, full_idx_to):
    # swap the subnode objects
    chosen_node_from = getNodeFromIdx(tracker, full_idx_from, 0)
    chosen_node_to = getNodeFromIdx(tracker, full_idx_to, 0)

    tmp = chosen_node_from.subgroups
    chosen_node_from.subgroups = chosen_node_to.subgroups
    chosen_node_to.subgroups = tmp

    # swap back the canon-ness and modreward aspect
    for sub_id in chosen_node_from.subgroups:
        if sub_id in chosen_node_to.subgroups:
            sub_from = chosen_node_from.subgroups[sub_id]
            sub_to = chosen_node_to.subgroups[sub_id]
            swapNodeMiscCanon(sub_from, sub_to)

    # swap the subfolders for each asset
    asset_types = ["sprite", "portrait"]

    for asset_type in asset_types:
        gen_path_from = getDirFromIdx(base_path, asset_type, full_idx_from)
        gen_path_to = getDirFromIdx(base_path, asset_type, full_idx_to)

        if not os.path.exists(gen_path_from):
            os.makedirs(gen_path_from, exist_ok=True)

        if not os.path.exists(gen_path_to):
            os.makedirs(gen_path_to, exist_ok=True)

        # move dirs to a temp folder
        gen_path_tmp = os.path.join(gen_path_from, "tmp")
        os.makedirs(gen_path_tmp, exist_ok=True)
        moveNodeFiles(gen_path_from, gen_path_tmp, False, True)

        # swap the folders
        moveNodeFiles(gen_path_to, gen_path_from, False, True)
        moveNodeFiles(gen_path_tmp, gen_path_to, False, True)
        shutil.rmtree(gen_path_tmp)


def hasLock(dict, asset_type, recursive):
    for file in dict.__dict__[asset_type + "_files"]:
        if dict.__dict__[asset_type + "_files"][file]:
            return True

    if recursive:
        for subgroup in dict.subgroups:
            if hasLock(dict.subgroups[subgroup], asset_type, recursive):
                return True

    return False

def setCanon(dict, canon):
    dict.canon = canon

    for subgroup in dict.subgroups:
        setCanon(dict.subgroups[subgroup], canon)



def MigrateName(tracker, dict, base_path, full_idx, full_name):
    """
    to sort sprites:
    rename "Starter" to "Cutscene"
    for each node and subnode:
    check whether the node's name is "Starter"
    if so, rename it to "cutscene"
    """
    for sub_idx in dict.subgroups:
        new_node = dict.subgroups[sub_idx]
        new_idx = full_idx + [sub_idx]
        new_name = [idx for idx in full_name]

        expanded_idx = [idx for idx in new_idx]
        while len(expanded_idx) < 4:
            expanded_idx.append("----")

        if len(new_idx) == 2:
            if "Starter" in new_node.name:
                print("{0}\t{1}".format("\t".join(expanded_idx), " ".join(new_name)))
                new_node.name = new_node.name.replace("Starter", "Cutscene")

        MigrateName(tracker, new_node, base_path, new_idx, new_name)

def MigrateNode(tracker, node, base_path, full_idx, full_name):
    """
    to sort sprites:
    rename "Starter" to "Cutscene"
    for each node and subnode:
    check whether the node's name is "Starter"
    if so, rename it to "cutscene"
    check whether the node is a cutscene
    if so, switch with the cutscene node
    If a normal is to be moved, its shiny must be moved too!
    """

    for sub_idx in node.subgroups:
        new_node = node.subgroups[sub_idx]
        new_idx = full_idx + [sub_idx]
        new_name = [idx for idx in full_name]
        if new_node.name != "":
            new_name.append(new_node.name)

        sprite_ready = migrateAsset(tracker, base_path, "sprite", new_idx)
        portrait_ready = migrateAsset(tracker, base_path, "portrait", new_idx)


        expanded_idx = [idx for idx in new_idx]
        while len(expanded_idx) < 4:
            expanded_idx.append("----")

        if sprite_ready != "-" or portrait_ready != "-":
            print("{0}\t{1}\t{2}\t{3}".format(sprite_ready, portrait_ready, "\t".join(expanded_idx), " ".join(new_name)))

        MigrateNode(tracker, new_node, base_path, new_idx, new_name)

def switchToCutscene(tracker, base_path, full_idx, full_name):
    """
    to sort sprites:
    rename "Starter" to "Cutscene"
    for each node and subnode:
    check whether the node is a cutscene
    if so, switch with the cutscene node
    If a normal is to be moved, its shiny must be moved too!
    """

def isNonStarterSlot(tracker, full_idx):
    if len(full_idx) < 2:
        return True

    dict = getNodeFromIdx(tracker, full_idx[:2], 0)
    return "Starter" not in dict.name


def isRecolor(tracker, full_idx):
    if len(full_idx) < 2:
        return False

    if len(full_idx) > 2 and full_idx[2] == "0001":
        return True

    dict = getNodeFromIdx(tracker, full_idx[:2], 0)
    return "Altcolor" in dict.name

def findDictIdxByName(parent_dict, name):
    for idx in parent_dict.subgroups:
        dict = parent_dict.subgroups[idx]
        if dict.name == name:
            return idx
    return None

def getStarterCounterpart(tracker, full_idx, starter):
    if starter:
        if len(full_idx) < 2:
            dict = getNodeFromIdx(tracker, full_idx, 0)
            starter_idx = findDictIdxByName(dict, "Starter")
            if starter_idx is None:
                return None
            return full_idx + [starter_idx]
        else:
            parent_dict = getNodeFromIdx(tracker, full_idx[:1], 0)
            dict = parent_dict.subgroups[full_idx[1]]
            if dict.name == "":
                starter_idx = findDictIdxByName(parent_dict, "Starter")
            else:
                starter_idx = findDictIdxByName(parent_dict, dict.name + "_Starter")
            if starter_idx is None:
                return None
            return full_idx[:1] + [starter_idx] + full_idx[2:]
    else:
        parent_dict = getNodeFromIdx(tracker, full_idx[:1], 0)
        dict = parent_dict.subgroups[full_idx[1]]
        if dict.name == "Starter":
            return full_idx[:1] + ["0000"] + full_idx[2:]
        else:
            starter_idx = findDictIdxByName(parent_dict, dict.name.replace("_Starter", ""))
            if starter_idx is None:
                return None
            return full_idx[:1] + [starter_idx] + full_idx[2:]

import SpriteUtils

def printReadyMigrationDests(tracker, dict, base_path, full_idx, full_name):

    for sub_idx in dict.subgroups:
        new_dict = dict.subgroups[sub_idx]
        new_idx = full_idx + [sub_idx]
        new_name = [idx for idx in full_name]
        if new_dict.name != "":
            new_name.append(new_dict.name)

        sprite_ready = getStatusForMigrationDest(tracker, base_path, "sprite", new_idx)
        portrait_ready = getStatusForMigrationDest(tracker, base_path, "portrait", new_idx)

        expanded_idx = [idx for idx in new_idx]
        while len(expanded_idx) < 4:
            expanded_idx.append("----")

        if sprite_ready != "-" or portrait_ready != "-":
            print("{0}\t{1}\t{2}\t{3}".format(sprite_ready, portrait_ready, "\t".join(expanded_idx), " ".join(new_name)))

        printReadyMigrationDests(tracker, new_dict, base_path, new_idx, new_name)

def printReadyMigrations(tracker, dict, base_path, full_idx, full_name):

    for sub_idx in dict.subgroups:
        new_dict = dict.subgroups[sub_idx]
        new_idx = full_idx + [sub_idx]
        new_name = [idx for idx in full_name]
        if new_dict.name != "":
            new_name.append(new_dict.name)

        #sprite_ready = getReadyForMigration(tracker, base_path, "sprite", new_idx)
        #portrait_ready = getReadyForMigration(tracker, base_path, "portrait", new_idx)
        sprite_ready = getStatusForMigration(tracker, base_path, "sprite", new_idx)
        portrait_ready = getStatusForMigration(tracker, base_path, "portrait", new_idx)

        expanded_idx = [idx for idx in new_idx]
        while len(expanded_idx) < 4:
            expanded_idx.append("----")

        if sprite_ready == "X" or portrait_ready == "X" or sprite_ready == "!" or portrait_ready == "!":
            print("{0}\t{1}\t{2}\t{3}".format(sprite_ready, portrait_ready, "\t".join(expanded_idx), " ".join(new_name)))

            #if portrait_ready == "X" or portrait_ready == "!":
            #    chosen_node = getNodeFromIdx(tracker, new_idx, 0)
            #    locked = []
            #    for part in chosen_node.portrait_files:
            #        if chosen_node.portrait_files[part]:
            #            locked.append(part)
            #    gen_path = os.path.join(base_path, "portrait", "/".join(new_idx))
            #    file_data, ext = SpriteUtils.generateFileData(gen_path, "portrait", False, locked)
            #    file_data.seek(0)
            #    with open(os.path.join("C:/Users/Gram/Downloads/Locked", "-".join(new_idx) + ext), "wb") as f:
            #        f.write(file_data.getbuffer())

        printReadyMigrations(tracker, new_dict, base_path, new_idx, new_name)

def getStatusForMigration(tracker, base_path, asset_type, full_idx):
    dict = getNodeFromIdx(tracker, full_idx, 0)
    status = getStarterCutsceneNormal(dict, asset_type, base_path, full_idx)

    if status == "starter":
        return "O"
    elif status == "cutscene":
        starter_idx = getStarterCounterpart(tracker, full_idx, True)
        starter_dict = getNodeFromIdx(tracker, starter_idx, 0)
        if status == "cutscene":
            # must have a partially filled starter counterpart, or sound the alarm
            if starter_dict is None:
                return "!"
            if starter_dict.__dict__[asset_type + "_complete"] < PHASE_EXISTS:
                return "!"

        return "X"
    else:
        return "-"


def getStatusForMigrationDest(tracker, base_path, asset_type, full_idx):

    dict = getNodeFromIdx(tracker, full_idx, 0)
    is_base = isNonStarterSlot(tracker, full_idx)

    if is_base:
        return "-"
    else:
        if dict.__dict__[asset_type + "_complete"] > PHASE_INCOMPLETE:
            return "O"
        else:
            return "X"

def migrateAsset(tracker, base_path, asset_type, full_idx):

    """
    If a starter version exists, it must be switched with its respective non-starter version
    """

    node = getNodeFromIdx(tracker, full_idx, 0)
    is_base = isNonStarterSlot(tracker, full_idx)

    if not is_base:
        if node.__dict__[asset_type + "_complete"] > PHASE_INCOMPLETE:
            # switch with its non-starter slot
            non_starter_idx = getStarterCounterpart(tracker, full_idx, False)
            non_starter_node = getNodeFromIdx(tracker, non_starter_idx, 0)

            # clear caches
            clearCache(node, True)
            clearCache(non_starter_node, True)

            swapFolderPaths(base_path, tracker, asset_type, full_idx, non_starter_idx)
            return "O"

    return "-"


def getReadyForMigration(tracker, base_path, asset_type, full_idx):


    dict = getNodeFromIdx(tracker, full_idx, 0)
    is_base = isNonStarterSlot(tracker, full_idx)
    is_recolor = isRecolor(tracker, full_idx)
    """
    if a "cutscene mon" slot is detected, verify it has a counterpart "starter" slot that is at least partially filled, alarm if not
    if a mon has the word "starter" in it, verify its counterpart non-starter slot is a "cutscene mon", alarm if not
    """
    status = getStarterCutsceneNormal(dict, asset_type, base_path, full_idx)
    if is_base:
        starter_idx = getStarterCounterpart(tracker, full_idx, True)
        starter_dict = getNodeFromIdx(tracker, starter_idx, 0)
        if status == "cutscene":
            # must have a partially filled starter counterpart, or sound the alarm
            if starter_dict is None:
                return "X"
            if dict.__dict__[asset_type + "_complete"] < PHASE_EXISTS:
                return "X"
        else:
            # should NOT have a starter counterpart, or sound the alarm
            if starter_dict is not None:
                return "X"
    else:
        if status != "starter":
            # ??? Invalid starter!
            return "X"

        non_starter_idx = getStarterCounterpart(tracker, full_idx, False)
        non_starter_dict = getNodeFromIdx(tracker, non_starter_idx, 0)
        # non-starter dict MUST be cutscene
        non_starter_status = getStarterCutsceneNormal(non_starter_dict, asset_type, base_path, non_starter_idx)
        if non_starter_status != "cutscene":
            return "X"

    if status == "starter":
        return "~"
    elif status == "cutscene":
        return "O"
    else:
        return "-"


def getStarterCutsceneNormal(dict, asset_type, base_path, full_idx):
    lock_dict = dict.__dict__[asset_type + "_files"]

    if asset_type == "sprite":

        ds_starter_action_map = {
            0: "Walk",
            1: "Attack",
            2: "",
            3: "",
            4: "",
            5: "Sleep",
            6: "Hurt",
            7: "Idle",
            8: "Swing",
            9: "Double",
            10: "Hop",
            11: "Charge",
            12: "Rotate",
            13: "EventSleep",
            14: "Wake",
            15: "Eat",
            16: "Tumble",
            17: "Pose",
            18: "Pull",
            19: "Pain",
            20: "Float",
            21: "DeepBreath",
            22: "Nod",
            23: "Sit",
            24: "LookUp",
            25: "Sink",
            26: "Trip",
            27: "Laying",
            28: "LeapForth",
            29: "Head",
            30: "Cringe",
            31: "LostBalance",
            32: "TumbleBack",
            33: "Faint",
            34: "HitGround"
        }

        # maps number to animation
        ds_index_map = { }

        if os.path.exists(os.path.join(base_path, asset_type, "/".join(full_idx), Constants.MULTI_SHEET_XML)):
            tree = ET.parse(os.path.join(base_path, asset_type, "/".join(full_idx), Constants.MULTI_SHEET_XML))
            root = tree.getroot()
            anims_node = root.find('Anims')
            for anim_node in anims_node.iter('Anim'):
                name = anim_node.find('Name').text
                ds_index = -1
                idx_node = anim_node.find('Index')
                if idx_node is not None:
                    ds_index = int(idx_node.text)
                if ds_index >= 0:
                    ds_index_map[ds_index] = name

        # check for locks on all starter-required animations
        # iterate through all ds_indices required, confirming they exist,
        # and also confirm they map to the right names, if applicable
        # and also confirm they're locked
        is_starter = True
        for ds_idx in ds_starter_action_map:
            if ds_idx not in ds_index_map:
                is_starter = False
                break

            actual_name = ds_index_map[ds_idx]
            if not lock_dict[actual_name]:
                is_starter = False
                break

            needed_name = ds_starter_action_map[ds_idx]
            if needed_name != "" and needed_name != actual_name:
                is_starter = False
                break

        if is_starter:
            """
            A "standard starter" has all 13 animation locks [they must map to indices 1-13],
            plus SPECIFICALLY NAMED animations up to 35 [they must map to specific indices], all locked
            """
            return "starter"
        else:
            total_locks = 0
            for ds_idx in ds_index_map:
                action = ds_index_map[ds_idx]
                if lock_dict[action]:
                    total_locks += 1

            if total_locks > 13:
                """
                A "cutscene mon" has 13 animation locks, PLUS any that do not conform to the starter standard
                """

                return "cutscene"
            else:
                """
                A "normal" mon has 13 animation locks or less
                """
                return "standard"
    elif asset_type == "portrait":
        total_locks = 0
        for emote in lock_dict:
            if lock_dict[emote] and emote[-1] != '^':
                total_locks += 1

        if total_locks <= 1:
            """
            A "normal" mon has 1 portrait locked
            """
            # check for 1 or less locks
            return "standard"
        else:
            # A POSSIBLY "standard starter" mon has very specifically the standard starter emotes locked, no more no less
            starter_set = Constants.COMPLETION_EMOTIONS[PHASE_FULL]
            for idx, emote in enumerate(Constants.EMOTIONS):
                must_have = (idx in starter_set)
                is_locked = (emote in lock_dict) and lock_dict[emote]
                if must_have != is_locked:
                    return "cutscene"

            # If it's a POSSIBLY "standard starter"...
            # check if it has proper starter anims, it's a cutscene if no
            sprite_type = getStarterCutsceneNormal(dict, "sprite", base_path, full_idx)
            if sprite_type != "starter":
                return "cutscene"

            return "starter"

    raise Exception()

"""
String operations
"""
def sanitizeName(str):
    return re.sub("\W+", "_", str).title()

def sanitizeCredit(str):
    return re.sub("\t\n", "", str)

