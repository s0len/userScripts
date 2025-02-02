#   _____                                      _____
#  |  __ \                                    |  __ \
#  | |__) |___ _ __   __ _ _ __ ___   ___ _ __| |__) |   _
#  |  _  // _ \ '_ \ / _` | '_ ` _ \ / _ \ '__|  ___/ | | |
#  | | \ \  __/ | | | (_| | | | | | |  __/ |  | |   | |_| |
#  |_|  \_\___|_| |_|\__,_|_| |_| |_|\___|_|  |_|    \__, |
#                                                     __/ |
#                                                    |___/
# ===================================================================================================
# Author: Drazzilb
# Description: This script will rename your posters to match Plex-Meta-Manager's naming scheme.
# Usage: python3 renamer.py 
# Requirements: requests, tqdm, fuzzywuzzy, pyyaml
# License: MIT License
# ===================================================================================================

script_version = "6.3.3"

from modules.arrpy import arrpy_py_version
from plexapi.exceptions import BadRequest
from modules.logger import setup_logger
from plexapi.server import PlexServer
from modules.version import version
from modules.formatting import create_table
from modules.discord import discord, field_builder
from modules.config import Config
from modules.arrpy import StARR
from unidecode import unidecode
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
from tqdm import tqdm
import filecmp
import shutil
import errno
import json
import html
import sys
import os
import re

script_name = "renamer"
config = Config(script_name)
log_level = config.log_level
logger = setup_logger(log_level, script_name)
version(script_name, script_version, arrpy_py_version, logger, config)

year_regex = re.compile(r"\((19|20)\d{2}\)")
illegal_chars_regex = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
remove_special_chars = re.compile(r'[^a-zA-Z0-9\s]+')

season_name_info = [
    " - Season",
    " - Specials",
    "_Season"
]

words_to_remove = [
    "(US)",
]

prefixes = [
    "The",
    "A",
    "An"
]
suffixes = [
    "Collection",
]

def find_best_match(matches, title):
    best_match = None
    for match in matches:
        for i in match:
            if best_match:
                if i[1] > best_match[1]:
                    best_match = i
                elif i[1] == best_match[1]:
                    if i[0] == title:
                        best_match = i
            else:
                best_match = i
    return best_match

def match_collection(plex_collections, source_file_list, collection_threshold):
    matched_collections = {"matched_media": []}
    almost_matched = {"almost_matched": []}
    not_matched = {"not_matched": []}
    for plex_collection in tqdm(plex_collections, desc="Matching collections", total=len(plex_collections), disable=None):
        plex_normalize_title = normalize_titles(plex_collection)
        matches = [
            process.extract(plex_collection, [item['title'] for item in source_file_list['collections']], scorer=fuzz.ratio),
            process.extract(plex_normalize_title, [item['normalized_title'] for item in source_file_list['collections']], scorer=fuzz.ratio)
        ]
        for prefix in prefixes:
            matches.append(process.extract(plex_collection, [re.sub(rf"^{prefix}\s(?=\S)", '', item['title']) for item in source_file_list['collections']], scorer=fuzz.ratio))
            matches.append(process.extract(plex_normalize_title, [re.sub(rf"^{prefix}\s(?=\S)", '', item['normalized_title']) for item in source_file_list['collections']], scorer=fuzz.ratio))
        for suffix in suffixes:
            matches.append(process.extract(plex_collection, [re.sub(rf"\s*{suffix}*", '', item['title']) for item in source_file_list['collections']], scorer=fuzz.ratio))
            matches.append(process.extract(plex_normalize_title, [re.sub(rf"\s*{suffix}*", '', item['normalized_title']) for item in source_file_list['collections']], scorer=fuzz.ratio))
        best_match = find_best_match(matches, plex_collection)
        folder = illegal_chars_regex.sub('', plex_collection)
        if best_match:
            match_title = best_match[0]
            score = best_match[1]
            for item in source_file_list['collections']:
                file_title = item['title']
                files = item['files']
                file_normalized_title = item['normalized_title']
                without_prefix = []
                for prefix in prefixes:
                    without_prefix = []
                    for prefix in prefixes:
                        without_prefix.append(re.sub(rf"^{prefix}\s(?=\S)", '', item['title']))
                        without_prefix.append(re.sub(rf"^{prefix}\s(?=\S)", '', item['normalized_title']))
                without_suffix = []
                for suffix in suffixes:
                    without_suffix.append(re.sub(rf"\s*{suffix}", '', item['title']))
                    without_suffix.append(re.sub(rf"\s*{suffix}", '', item['normalized_title']))
                if score >= collection_threshold and (
                        match_title == item['title'] or
                        match_title == item['normalized_title'] or
                        match_title in without_prefix or
                        match_title in without_suffix
                ):
                    matched_collections['matched_media'].append({
                        "title": file_title,
                        "normalized_title": file_normalized_title,
                        "plex_collection": plex_collection,
                        "normalized_collection": plex_normalize_title,
                        "year": None,
                        "files": files,
                        "score": score,
                        "best_match": best_match,
                        "folder": folder,
                    })
                    break
                elif score >= collection_threshold - 10 and score < collection_threshold and (
                        match_title == item['title'] or
                        match_title == item['normalized_title'] or
                        match_title in without_prefix or
                        match_title in without_suffix
                ):
                    almost_matched['almost_matched'].append({
                        "title": file_title,
                        "normalized_title": file_normalized_title,
                        "plex_collection": plex_collection,
                        "normalized_collection": plex_normalize_title,
                        "year": None,
                        "files": files,
                        "score": score,
                        "best_match": best_match,
                        "folder": folder,
                    })
                    break
                elif score < collection_threshold - 10 and (
                        match_title == item['title'] or
                        match_title == item['normalized_title'] or
                        match_title in without_prefix or
                        match_title in without_suffix
                ):
                    not_matched['not_matched'].append({
                        "title": file_title,
                        "normalized_title": file_normalized_title,
                        "plex_collection": plex_collection,
                        "normalized_collection": plex_normalize_title,
                        "year": None,
                        "files": files,
                        "score": score,
                        "best_match": best_match,
                        "folder": folder,
                    })
                    break

    logger.debug(f"Not matched collections: {json.dumps(not_matched, ensure_ascii=False, indent=4)}")
    logger.debug(f"Matched collections: {json.dumps(matched_collections, ensure_ascii=False, indent=4)}")
    logger.debug(f"Almost matched collections: {json.dumps(almost_matched, ensure_ascii=False, indent=4)}")
    return matched_collections

def match_media(media, source_file_list, type):
    matched_media = {"matched_media": []}
    not_matched = {"not_matched": []}
    for item in tqdm(media, desc="Matching media", total=len(media), disable=None):
        alternate_title = False
        alternate_titles = []
        normalized_alternate_titles = []
        arr_title = item['title']
        try:
            original_title = item['originalTitle']
        except KeyError:
            original_title = None
        arr_path = os.path.basename(item['path'])
        arr_path = year_regex.sub("", arr_path).strip()
        normalized_arr_path = normalize_titles(arr_path)
        try:
            arr_path_year = year_regex.search(item['path'])
            arr_path_year = int(arr_path_year.group(0)[1:-1])
        except AttributeError:
            if item['status'] == 'upcoming' or item['status'] == 'announced':
                continue
            else:
                logger.warning(f"Unable to find year in {item['title']} path")
        try:
            if item['alternateTitles']:
                for i in item['alternateTitles']:
                    alternate_titles.append(i['title'])
                    normalized_alternate_titles.append(normalize_titles(i['title']))
        except KeyError:
            alternate_titles = []
        year_from_title = year_regex.search(item['title'])
        arr_normalized_title = normalize_titles(arr_title)
        secondary_year = None
        if year_from_title:
            try:
                arr_year = int(year_from_title.group(0)[1:-1])
            except ValueError:
                logger.error(f"Could not convert year to int: {year_from_title.group(0)[1:-1]} for {item['title']}")
                continue
        else:
            arr_year = item['year']
        try:
            if item['secondaryYear']:
                secondary_year = item['secondaryYear']
        except KeyError:
            secondary_year = None
        path = item['path']
        folder = os.path.basename(os.path.normpath(path))
        files = []
        for i in source_file_list[type]:
            file_title = i['title']
            file_normalized_title = i['normalized_title']
            files = i['files']
            file_year = i['year']
            if (
                    arr_title == file_title or
                    arr_normalized_title == file_normalized_title or
                    arr_path == file_title or
                    normalized_arr_path == file_normalized_title or
                    original_title == file_title or
                    file_title in alternate_titles or
                    file_normalized_title in normalized_alternate_titles
            ) and (
                    arr_year == file_year or
                    secondary_year == file_year or
                    arr_path_year == file_year
            ):
                matched_media['matched_media'].append({
                    "title": file_title,
                    "normalized_title": file_normalized_title,
                    "arr_title": arr_title,
                    "arr_normalized_title": arr_normalized_title,
                    "arr_path": arr_path,
                    "normalized_arr_path": normalized_arr_path,
                    "year": file_year,
                    "arr_year": arr_year,
                    "arr_path_year": arr_path_year,
                    "secondaryYear": secondary_year,
                    "files": files,
                    "alternate_title": alternate_title,
                    "folder": folder,
                })
                break
            elif (
                    arr_title == file_title or
                    arr_normalized_title == file_normalized_title or
                    arr_path == file_title or
                    normalized_arr_path == file_normalized_title or
                    original_title == file_title or
                    file_title in alternate_titles or
                    file_normalized_title in normalized_alternate_titles
            ) and (
                    arr_year != file_year or
                    secondary_year != file_year or
                    arr_path_year != file_year
            ):
                not_matched['not_matched'].append({
                    "title": file_title,
                    "normalized_title": file_normalized_title,
                    "arr_title": arr_title,
                    "arr_normalized_title": arr_normalized_title,
                    "arr_path": arr_path,
                    "normalized_arr_path": normalized_arr_path,
                    "year": file_year,
                    "arr_year": arr_year,
                    "arr_path_year": arr_path_year,
                    "secondaryYear": secondary_year,
                    "files": files,
                    "alternate_title": alternate_title,
                    "folder": folder,
                })
    logger.debug(f"Matched media: {json.dumps(matched_media, ensure_ascii=False, indent=4)}")
    logger.debug(f"Not matched media: {json.dumps(not_matched, ensure_ascii=False, indent=4)}")
    return matched_media

def rename_file(matched_media, destination_dir, dry_run, action_type, print_only_renames):
    messages = []
    discord_messages = []
    asset_folders = config.asset_folders
    destination_files = os.listdir(destination_dir)
    for media in tqdm(matched_media['matched_media'], desc="Renaming files", total=len(matched_media['matched_media']), disable=None):
        files = media['files']
        folder = media['folder']
        if asset_folders:
            if dry_run:
                if not os.path.exists(os.path.join(destination_dir, folder)):
                    discord_messages.append(folder)
            else:
                if not os.path.exists(os.path.join(destination_dir, folder)):
                    messages.append(f"Creating asset folder: {folder}")
                    os.makedirs(os.path.join(destination_dir, folder), exist_ok=True)
                    discord_messages.append(folder)
        for file in files:
            path = os.path.dirname(file)
            old_file_name = os.path.basename(file)
            source_file_path = os.path.join(path, file)
            file_extension = os.path.splitext(file)[1]
            if any(word in file for word in season_name_info):
                season_number = re.search(r"Season (\d+)", file)
                if season_number:
                    season_number = season_number.group(1)
                    season_number = season_number.zfill(2)
                    if asset_folders:
                        new_file_name = f"Season{season_number}{file_extension}"
                    else:
                        new_file_name = f"{folder}_Season{season_number}{file_extension}"
                elif season_number := re.search(r"Season (\d\d)", file):
                    if asset_folders:
                        season_number = season_number.group(1)
                        new_file_name = f"Season{season_number}{file_extension}"
                    else:
                        season_number = season_number.group(1)
                        new_file_name = f"{folder}_Season{season_number}{file_extension}"
                elif " - Specials" in file:
                    if asset_folders:
                        new_file_name = f"Season00{file_extension}"
                    else:
                        new_file_name = f"{folder}_Season00{file_extension}"
                elif "_Season" in file:
                    new_file_name = file
                else:
                    logger.error(f"Unable to find season number for {file}")
                    continue
            else:
                if asset_folders:
                    new_file_name = f"poster{file_extension}"
                else:
                    new_file_name = f"{folder}{file_extension}"
            if asset_folders:
                destination_file_path = os.path.join(destination_dir, folder, new_file_name)
            else:
                destination_file_path = os.path.join(destination_dir, new_file_name)
            if config.source_overrides:
                if path in config.source_overrides:
                    if asset_folders:
                        for root, dirs, files in os.walk(destination_dir):
                            basedir = os.path.basename(root)
                            if basedir == folder:
                                for file in files:
                                    if os.path.splitext(file)[0] == os.path.splitext(new_file_name)[0] and file_extension != os.path.splitext(file)[1]:
                                        if dry_run:
                                            messages.append(f"Would remove {file} from {basedir}")
                                        else:
                                            messages.append(f"Removed {file} from {basedir}")
                                            os.remove(os.path.join(root, file))
                    else:
                        for i in destination_files:
                            if folder == os.path.splitext(i)[0] and file_extension != os.path.splitext(i)[1]:
                                if dry_run:
                                    messages.append(f"Would remove {i} from {destination_dir}")
                                else:
                                    messages.append(f"Removed {i} from {destination_dir}")
                                    os.remove(os.path.join(destination_dir, i))
            if new_file_name != old_file_name:
                processsed_file_info, discord_message = process_file(old_file_name, new_file_name, action_type, dry_run, destination_file_path, source_file_path, '-renamed->')
                messages.extend(processsed_file_info)
                if not asset_folders:
                    discord_messages.extend(discord_message)
            else:
                if not print_only_renames:
                    processsed_file_info, discord_message = process_file(old_file_name, new_file_name, action_type, dry_run, destination_file_path, source_file_path, '-not-renamed->>')
                    messages.extend(processsed_file_info)
                    if not asset_folders:
                        discord_messages.extend(discord_message)
            if not asset_folders:
                for i in discord_messages:
                    discord_messages = [os.path.splitext(i)[0] for i in discord_messages]
    return messages, discord_messages

def process_file(old_file_name, new_file_name, action_type, dry_run, destination_file_path, source_file_path, arrow):
    output = []
    discord_output = []
    if dry_run:
        if action_type == 'copy':
            if os.path.isfile(destination_file_path):
                if filecmp.cmp(source_file_path, destination_file_path):
                    logger.debug(f"Copy -> File already exists: {destination_file_path}")
                    pass
                else:
                    output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                    discord_output.append(new_file_name)
            else:
                output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                discord_output.append(new_file_name)
        if action_type == 'hardlink':
            if os.path.isfile(destination_file_path):
                if filecmp.cmp(source_file_path, destination_file_path):
                    logger.debug(f"Hardlink -> File already exists: {destination_file_path}")
                    pass
                else:
                    output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                    discord_output.append(new_file_name)
            else:
                output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                discord_output.append(new_file_name)
        elif action_type == 'move':
            output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
            discord_output.append(new_file_name)
    else:
        if action_type == 'copy':
            try:
                if os.path.isfile(destination_file_path):
                    if filecmp.cmp(source_file_path, destination_file_path):
                        logger.debug(f"Copy -> File already exists: {destination_file_path}")
                        pass
                    else:
                        shutil.copyfile(source_file_path, destination_file_path)
                        output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                        discord_output.append(new_file_name)
                else:
                    shutil.copyfile(source_file_path, destination_file_path)
                    output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                    discord_output.append(new_file_name)
            except OSError as e:
                logger.error(f"Unable to copy file: {e}")
        elif action_type == 'move':
            try:
                shutil.move(source_file_path, destination_file_path)
                output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                discord_output.append(new_file_name)
            except OSError as e:
                logger.error(f"Unable to move file: {e}")
        elif action_type == 'hardlink':
            try:
                os.link(source_file_path, destination_file_path)
                output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                discord_output.append(new_file_name)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    if os.path.samefile(source_file_path, destination_file_path):
                        logger.debug(f"Hardlink -> File already exists: {destination_file_path}")
                        pass
                    else:
                        os.replace(destination_file_path, source_file_path)
                        os.link(source_file_path, destination_file_path)
                        output.append(f"Action Type: {action_type.capitalize()}: {old_file_name} {arrow} {new_file_name}")
                        discord_output.append(new_file_name)
                else:
                    logger.error(f"Unable to hardlink file: {e}")
                    return
        else:
            logger.error(f"Unknown action type: {action_type}")
    return output, discord_output

def load_dict(title, year, files):
    return {
        "title": title,
        "normalized_title": None,
        "year": year,
        "files": files
    }

def normalize_titles(title):
    normalized_title = title
    for word in words_to_remove:
        normalized_title = title.replace(word, '')
    normalized_title = year_regex.sub('', normalized_title)
    normalized_title = illegal_chars_regex.sub('', normalized_title)
    normalized_title = unidecode(html.unescape(normalized_title))
    normalized_title = normalized_title.rstrip()
    normalized_title = normalized_title.replace('&', 'and')
    normalized_title = re.sub(remove_special_chars, '', normalized_title).lower()
    normalized_title = normalized_title.replace(' ', '')
    return normalized_title

def add_file_to_asset(category_dict, file):
    category_dict['files'].append(file)

def find_or_create_show(show_list, title, year, files, path):
    for show in show_list:
        if title == show['title'] and year == show['year']:
            add_file_to_asset(show, files[0])
            return
    show = load_dict(title, year, files)
    show_list.append(show)

def get_files(path):
    files = []
    try:
        files = os.listdir(path)
    except FileNotFoundError:
        logger.error(f"Path not found: {path}")
    return files

def sort_files(files, path, dict, basename):
    for file in tqdm(files, desc=f'Sorting assets from \'{basename}\' directory', total=len(files), disable=None):
        full_path = os.path.join(path, file)
        if file.startswith('.'):
            continue
        base_name, extension = os.path.splitext(file)
        if not re.search(r'\(\d{4}\)', base_name):
            collection = load_dict(base_name, None, [full_path])
            dict['collections'].append(collection)
        else:
            file_name = os.path.splitext(file)[0]
            match = re.search(r'\((\d{4})\)', base_name)
            year = int(match.group(1)) if match else None
            title = base_name.replace(f'({year})', '').strip()
            if any(file.startswith(file_name) and any(file_name + season_name in file for season_name in season_name_info) for file in files):
                find_or_create_show(dict['series'], title, year, [full_path], path)
            elif any(word in file for word in season_name_info):
                for season_name in season_name_info:
                    if season_name in file:
                        title = title.split(season_name)[0].strip()
                find_or_create_show(dict['series'], title, year, [full_path], path)
            else:
                movie = load_dict(title, year, [full_path])
                dict['movies'].append(movie)
    return dict

def get_assets_files(assets_path, override_paths):
    asset_files = {asset_type: [] for asset_type in ['series', 'movies', 'collections']}
    override_files = {asset_type: [] for asset_type in ['series', 'movies', 'collections']}
    if assets_path:
        files = get_files(assets_path)
        basename = os.path.basename(assets_path.rstrip('/'))
        asset_files = sort_files(files, assets_path, asset_files, basename)
    if isinstance(override_paths, str):
        override_paths = [override_paths]
    if override_paths:
        for path in tqdm(override_paths, desc="Processing override paths", total=len(override_paths)):
            files = get_files(path)
            basename = os.path.basename(path.rstrip('/'))
            override_files = sort_files(files, path, override_files, basename)
            if override_files and asset_files:
                asset_files = handle_override_files(asset_files, override_files, path, asset_types=['series', 'movies', 'collections'])
    for asset_type in asset_files:
        for asset in asset_files[asset_type]:
            normalized_title = normalize_titles(asset['title'])
            asset['normalized_title'] = normalized_title
            asset['files'].sort()
    logger.debug(json.dumps(asset_files, indent=4))
    return asset_files

def handle_override_files(asset_files, override_files, path, asset_types):
    for type in asset_types:
        for override_asset in override_files[type]:
            asset_found = False
            for asset in asset_files[type]:
                if override_asset['title'] == asset['title'] and override_asset['year'] == asset['year']:
                    asset_found = True
                    for override_file in override_asset['files']:
                        over_ride_file_name = os.path.split(override_file)[1]
                        asset['files'] = [f for f in asset['files'] if os.path.split(f)[1] != over_ride_file_name]
                        asset['files'].append(override_file)
                        logger.debug(f"Override: Added {override_file} to {asset['title']}")
                    break
            if not asset_found:
                asset_files[type].append(override_asset)
                logger.debug(f"Override: Added {override_asset['title']} to {type} from {path}")
    return asset_files

def process_instance(instance_type, instance_name, url, api, final_output, asset_files):
    collections = []
    media = []
    collection_names = []
    if instance_type == "Plex":
        if config.library_names:
            app = PlexServer(url, api)
            for library_name in config.library_names:
                try:
                    library = app.library.section(library_name)
                    logger.debug(f"Library: {library_name} found in {instance_name}")
                    collections += library.collections()
                except BadRequest:
                    logger.error(f"Error: {library_name} does not exist in {instance_name}")
            # collection_names = [collection.title for collection in collections if collection.smart != True]
            collection_names = [collection.title for collection in collections]
            logger.debug(json.dumps(collection_names, indent=4))
        else:
            message = f"Error: No library names specified for {instance_name}"
            final_output.append(message)
            return final_output, None
        # get freindlyname of plex server
        server_name = app.friendlyName
        data = [
        [f"Plex Server: {server_name}"],
        ]
        create_table(data, log_level="info", logger=logger)
    else:
        app = StARR(url, api, logger)
        media = app.get_media()
        server_name = app.get_instance_name()
        data = [
            [server_name],
        ]
        create_table(data, log_level="info", logger=logger)
    data = [
        [f"{server_name} Settings"]
    ]
    create_table(data, log_level="debug", logger=logger)
    logger.debug('*' * 40)
    logger.debug(f"Script Settings for {instance_name}:")
    logger.debug(f'{"URL:":<20}{url if url else "Not Set"}')
    logger.debug(f'{"API:":<20}{"*" * (len(api) - 5)}{api[-5:] if api else "Not Set"}')
    logger.debug(f'{"Instance Type:":<20}{instance_type if instance_type else "Not Set"}')
    logger.debug(f'{"ARR name:":<20}{server_name if instance_name else "Not Set"}')
    logger.debug('*' * 40 + '\n')
    matched_media = []
    if instance_type == "Plex":
        matched_media = match_collection(collection_names, asset_files, config.collection_threshold)
    elif instance_type == "Radarr":
        matched_media = match_media(media, asset_files, "movies")
    elif instance_type == "Sonarr":
        matched_media = match_media(media, asset_files, "series")
    if matched_media:
        message, discord_messages = rename_file(matched_media, config.destination_dir, config.dry_run, config.action_type, config.print_only_renames)
        final_output.extend(message)
    else:
        message = f"No matches found for {instance_name}"
        final_output.append(message)
    return final_output, discord_messages

def print_output(final_output):
    if final_output:
        for message in final_output:
            logger.info(message)
        return
    else:
        return
    
def notification(file_list):
    if file_list:
        for instance_type, file_list in file_list.items():
            if not file_list:
                continue
            fields = field_builder(file_list, name="Renamed Posters")
            for field_number, field in fields.items():
                discord(field, logger, config, script_name, description=f"Number of posters added {len(file_list)}", color=0x00FF00, content=None)
        else:
            return

def main():
    data = [
        ["Script Settings"],
    ]
    create_table(data, log_level="debug", logger=logger)
    logger.debug(f'*' * 40)
    logger.debug(f'{"Dry_run:":<20}{config.dry_run if config.dry_run else "False"}')
    logger.debug(f'{"Log level:":<20}{log_level if log_level else "INFO"}')
    logger.debug(f'{"Asset folders:":<20}{config.asset_folders if config.asset_folders else "False"}')
    logger.debug(f'{"Library names:":<20}{config.library_names if config.library_names else "Not set"}')
    logger.debug(f'{"Source dir:":<20}{config.source_dir if config.source_dir else "Not set"}')
    logger.debug(f'{"Source overrides:":<20}{config.source_overrides if config.source_overrides else "Not set"}')
    logger.debug(f'{"Destination dir:":<20}{config.destination_dir if config.destination_dir else "Not set"}')
    logger.debug(f'{"Threshold:":<20}{config.collection_threshold}')
    logger.debug(f'{"Action type:":<20}{config.action_type}')
    logger.debug(f'{"Print only renames:":<20}{config.print_only_renames}')
    logger.debug(f'*' * 40 + '\n')
    if config.dry_run:
        data = [
            ["Dry Run"],
            ["NO CHANGES WILL BE MADE"]
        ]
        create_table(data, log_level="info", logger=logger)

    asset_files = get_assets_files(config.source_dir, config.source_overrides)
    
    instance_data = {
        'Plex': config.plex_data,
        'Radarr': config.radarr_data,
        'Sonarr': config.sonarr_data
    }
    discord_output = {}
    for instance_type, instances in instance_data.items():
        for instance in instances:
            final_output = []
            instance_name = instance['name']
            url = instance['url']
            api = instance['api']
            script_name = None
            if instance_type == "Radarr" and config.radarr:
                data = next((data for data in config.radarr if data['name'] == instance_name), None)
                if data:
                    script_name = data['name']
            elif instance_type == "Sonarr" and config.sonarr:
                data = next((data for data in config.sonarr if data['name'] == instance_name), None)
                if data:
                    script_name = data['name']
            elif instance_type == "Plex":
                script_name = instance_name
            if script_name and instance_name == script_name:
                final_output, file_list = process_instance(instance_type, instance_name, url, api, final_output, asset_files)
                discord_output[instance_name] = file_list
                print_output(final_output)
    notification(discord_output)

if __name__ == "__main__":
    main()
