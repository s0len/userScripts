#   _____                                 _             _                  _____
#  |  __ \                               (_)           | |                |  __ \
#  | |__) |___ _ __   __ _ _ __ ___   ___ _ _ __   __ _| |_ ___  _ __ _ __| |__) |   _
#  |  _  // _ \ '_ \ / _` | '_ ` _ \ / _ \ | '_ \ / _` | __/ _ \| '__| '__|  ___/ | | |
#  | | \ \  __/ | | | (_| | | | | | |  __/ | | | | (_| | || (_) | |  | |_ | |   | |_| |
#  |_|  \_\___|_| |_|\__,_|_| |_| |_|\___|_|_| |_|\__,_|\__\___/|_|  |_(_)|_|    \__, |
#                                                                                 __/ |
#                                                                                |___/
# ===================================================================================================
# Author: Drazzilb
# Description: This script will rename all series in Sonarr/Radarr to match the naming scheme of the
#              Naming Convention within Radarr/Sonarr. It will also add a tag to the series so that it can be easily
#              identified as having been renamed.
# Usage: python3 /path/to/renameinatorr.py
# Requirements: requests, pyyaml
# License: MIT License
# ===================================================================================================

script_version = "3.2.3"

from modules.config import Config
from modules.logger import setup_logger
from modules.arrpy import StARR
from modules.arrpy import arrpy_py_version
from modules.version import version
from modules.discord import discord
from modules.formatting import create_table

script_name = "renameinatorr"
config = Config(script_name)
log_level = config.log_level
logger = setup_logger(log_level, script_name)
version(script_name, script_version, arrpy_py_version, logger, config)

def check_all_tagged(all_media, tag_id):
    """
    Check if all media has been tagged.
    
    Args:
        all_media (list): The list of all media.
        tag_id (int): The ID of the tag to check.
        
    Returns:
        bool: True if all media has been tagged, False otherwise.
    """
    for media in all_media:
        if tag_id not in media['tags']:
            return False
    return True

def print_format(items, instance_type, dry_run, total_count, tagged_percent, untagged_percent, media_type, tagged_count, untagged_count):
    """
    Print the format of the output.
    
    Args:
        items (list): The list of items to print.
        library_item_to_rename (list): The list of items to rename.
        instance_type (str): The type of instance to process.
        dry_run (bool): Whether or not to perform a dry run.
        total_count (int): The total number of items to process.
        tagged_percent (float): The percentage of items that have been tagged.
        untagged_percent (float): The percentage of items that have not been tagged.
        media_type (str): The type of media to process.
        tagged_count (int): The number of items that have been tagged.
        untagged_count (int): The number of items that have not been tagged.
    """
    if dry_run:
        tagged = "would have been tagged"
        renamed = "would have been renamed to"
    else:
        tagged = "has been tagged"
        renamed = "renamed to"
    for item, rename_items in items.items():
        title = item
        logger.info(f"Title: {title} {tagged}.")
        current_season = None
        for rename_item in rename_items:
            existing_path = rename_item["existingPath"]
            new_path = rename_item["newPath"]
            if instance_type == "sonarr":
                season_number = rename_item["seasonNumber"]
                if instance_type == "sonarr":
                    season_number = rename_item["seasonNumber"]
                    if current_season != season_number:
                        current_season = season_number
                        logger.info(f"\tSeason {season_number:02d}:")
                    logger.info(f"\t\t{existing_path.split('/')[-1]} {renamed}")
                    logger.info(f"\t\t{new_path.split('/')[-1]}")
                    logger.info(f"")
            if instance_type == "radarr":
                logger.info(f"\t{existing_path.split('/')[-1]} {renamed}")
                logger.info(f"\t{new_path.split('/')[-1]}")
                logger.info(f"")
    if total_count > 0:
        tagged_percent = (tagged_count / total_count) * 100
        untagged_percent = (untagged_count / total_count) * 100
        logger.info(f'Total {media_type}: {total_count}, Tagged {media_type}: {tagged_count} ({tagged_percent:.2f}%), Untagged {media_type}: {untagged_count} ({untagged_percent:.2f}%)\n')
            
def process_instance(instance_type, instance_name, url, api, tag_name, count, dry_run, reset, unattended):
    """
    Process the instance based on the instance type.
    
    Args:
        instance_type (str): The type of instance to process.
        instance_name (str): The name of the instance to process.
        url (str): The URL of the instance to process.
        api (str): The API key of the instance to process.
        tag_name (str): The name of the tag to use.
        count (int): The number of items to process.
        dry_run (bool): Whether or not to perform a dry run.
        reset (bool): Whether or not to reset the tag.
        unattended (bool): Whether or not to run unattended.
    """
    library_item_to_rename = []
    app = StARR(url, api, logger)
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
    logger.debug(f'{"Count:":<20}{count if count else "Not Set"}')
    logger.debug(f'{"tag_name:":<20}{tag_name if tag_name else "Not Set"}')
    logger.debug(f'{"reset: {reset}":<20}{reset if reset else "Not Set"}')
    logger.debug(f'{"unattended:":<20}{unattended if unattended else "Not Set"}')
    logger.debug(f'{"URL:":<20}{url if url else "Not Set"}')
    logger.debug(f'{"API:":<20}{"*" * (len(api) - 5)}{api[-5:] if api else "Not Set"}')
    logger.debug(f'{"Instance Type:":<20}{instance_type if instance_type else "Not Set"}')
    logger.debug(f'{"ARR name:":<20}{server_name if instance_name else "Not Set"}')
    logger.debug('*' * 40 + '\n')
    media = app.get_media()
    if instance_type == "Radarr":
        media_type = "Movies"
    elif instance_type == "Sonarr":
        media_type = "Series"
    logger.debug(f"Length of Media for {instance_name}: {len(media)}")
    arr_tag_id = app.get_tag_id_from_name(tag_name)
    if not arr_tag_id:
        if not dry_run:
            arr_tag_id = app.create_tag(tag_name)
        else:
            logger.info(f"Tag {tag_name} would have been created.")
        if arr_tag_id:
            logger.debug(f"Tag: {tag_name} | Tag ID: {arr_tag_id}")
    else:
        logger.debug(f"Tag: {tag_name} | Tag ID: {arr_tag_id}")
    all_tagged = check_all_tagged(media, arr_tag_id)
    all_media_ids = [item["id"] for item in media]
    if reset:
        if not dry_run:
            app.remove_tags(all_media_ids, arr_tag_id)
            logger.info(f'All of {instance_name} have had the tag {tag_name} removed.')
            all_tagged = False 
        else:
            logger.info(f'All of {instance_name} would have had the tag {tag_name} removed.')
            all_tagged = False
    elif all_tagged and unattended:
        if not dry_run:
            app.remove_tags(all_media_ids, arr_tag_id)
            logger.info(f'All of {instance_name} have had the tag {tag_name} removed.')
            discord(None, logger, config, script_name, description=f"All of {instance_name} have had the tag {tag_name} removed.", color=0x00ff00, content=None)
            all_tagged = False
        else:
            logger.info(f'All of {instance_name} would have had the tag {tag_name} removed.')
            discord(None, logger, config, script_name, description=f"All of {instance_name} would have had the tag {tag_name} removed.",color=0x00ff00, content=None)
            all_tagged = False
    elif all_tagged and not unattended:
        logger.info(f'All of {instance_name} has been tagged with {tag_name}')
        logger.info("If you would like to remove the tag and re-run the script, please set reset to True or set unattended to True.")
        logger.info(f"Skipping {instance_name}...")
        discord(None, logger, config, script_name, description=f"All of {instance_name} has been tagged with {tag_name}, please set reset to True or set unattended to True to remove the tag and re-run the script, {instance_name} will be skipped.", color=0x00ff00, content=None)
        return
    if not all_tagged:
        untagged_media = [
            m for m in media if arr_tag_id not in m['tags']]
        media_to_process = untagged_media[:count]
        items = []
        media_ids = []

        if not all_tagged:
            untagged_media = [
                m for m in media if arr_tag_id not in m['tags']]
        media_to_process = untagged_media[:count]
        items = {}
        media_ids = []
        tagged_count = 0
        untagged_count = 0
        new_tag = 0
        for item in media_to_process:
            title = item["title"]
            media_id = item["id"]
            media_ids.append(media_id)
            library_item_to_rename = app.get_rename_list(media_id)
            items[title] = library_item_to_rename
        if not dry_run:
            app.rename_media(media_ids)
            app.add_tags(media_ids, arr_tag_id)
            new_tag += 1
            app.refresh_media(media_ids)
        for m in media:
            if (arr_tag_id in m["tags"]):
                tagged_count += 1
            elif (arr_tag_id not in m["tags"]):
                untagged_count += 1
        total_count = (tagged_count + new_tag) + untagged_count
        tagged_percent = ((tagged_count + new_tag) / total_count) * 100
        untagged_percent = (untagged_count / total_count) * 100
        print_format(items, instance_type.lower(), dry_run, total_count, tagged_percent, untagged_percent, media_type, tagged_count, untagged_count)

# TODO: Add support for parrent folders
def rename_folder():
    pass

def main():
    data = [
        ["Script Settings"]
    ]
    create_table(data, log_level="debug", logger=logger)
    logger.debug(f'{"Dry_run:":<20}{config.dry_run if config.dry_run else "False"}')
    logger.debug(f'{"Log level:":<20}{log_level if log_level else "INFO"}')
    logger.debug(f'*' * 40 + '\n')
    if config.dry_run:
        data = [
            ["Dry Run"],
            ["NO CHANGES WILL BE MADE"]
        ]
        create_table(data, log_level="info", logger=logger)
    instance_data = {
        'Radarr': config.radarr_data,
        'Sonarr': config.sonarr_data
    }

    for instance_type, instances in instance_data.items():
        for instance in instances:
            instance_name = instance['name']
            url = instance['url']
            api = instance['api']
            script_name = None
            if instance_type == "Radarr" and config.radarr:
                data = next((data for data in config.radarr if data['name'] == instance_name), None)
                if data:
                    script_name = data['name']
                    count = data['count']
                    tag_name = data['tag_name']
                    reset = data['reset']
                    unattended = data['unattended']
            elif instance_type == "Sonarr" and config.sonarr:
                data = next((data for data in config.sonarr if data['name'] == instance_name), None)
                if data:
                    script_name = data['name']
                    count = data['count']
                    tag_name = data['tag_name']
                    reset = data['reset']
                    unattended = data['unattended']
            if script_name and instance_name == script_name:
                process_instance(instance_type, instance_name, url, api, tag_name, count, config.dry_run, reset, unattended)

if __name__ == "__main__":
    """
    Main entry point for the script.
    """
    main()