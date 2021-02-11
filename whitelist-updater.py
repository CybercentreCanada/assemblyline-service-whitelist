# This module checks first online the hash for NSRL file, then compares with hash of local copy.
# If hashes are different, download new NSRL file

import logging
import os
import pycdlib
import requests
import subprocess
import tempfile
import zipfile

from util import download_big_file
from util import calculate_sha1

from assemblyline.common import log

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO


def get_online_hashes(cur_logger):
    hashes = {}
    hash_url = 'https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/version.txt'
    cur_logger.info("Downloading online rds_modernm hash from %s" % hash_url)

    res = requests.get(hash_url)

    if res.ok:
        for line in res.text.split("\n"):
            if "," in line:
                cur_hash, version_info = [x.strip("\"") for x in line.strip().split(",")]
                date, version, iso_type = version_info.split(" ")
                hashes[iso_type] = {
                    'hash': cur_hash.upper(),
                    'date': date,
                    'version': version
                }

    return hashes


def download_extract_zip(cur_logger, url, target_path, extracted_path, internal_file):
    cur_logger.info(f"Downloading RDS ZIP from {url}...")
    download_big_file(url, target_path)

    cur_logger.info(f"Unzipping downloaded file {target_path}... into {extracted_path}")

    with zipfile.ZipFile(target_path) as z:
        with open(extracted_path, 'wb') as f:
            # TODO: do block by block cause I'm getting OOMKilled
            f.write(z.read(internal_file))
    cur_logger.info(f"Unzip finished, created file {extracted_path}")


def download_extract_iso(cur_logger, url, target_path, extracted_path, internal_file):
    cur_logger.info(f"Downloading RDS ISO from {url}...")
    download_big_file(url, target_path)
    zip_file = f"{target_path}.zip"

    iso = pycdlib.PyCdlib()
    iso.open(target_path)

    cur_logger.info("ISO contains followings files:")

    for child in iso.list_children(iso_path='/'):
        cur_logger.info(child.file_identifier())

    cur_logger.info("Extracting NSRLFILE.ZIP form ISO...")
    with open(zip_file, "wb") as zip_fh:
        iso.get_file_from_iso_fp(zip_fh, iso_path='/NSRLFILE.ZIP;1')
    iso.close()

    cur_logger.info(f"Unzipping {zip_file} ...")

    with zipfile.ZipFile(zip_file) as z:
        with open(extracted_path, 'wb') as f:
            # TODO: do block by block cause I'm getting OOMKilled
            f.write(z.read(internal_file))
    cur_logger.info(f"Unzip finished, created file {extracted_path}")


def update(cur_logger, working_directory, hashes, iso_type, url, download_name, internal_file):
    cur_logger.info(f"Checking for updates on RDS - {iso_type.upper()}")
    if iso_type not in hashes:
        cur_logger.error(f"Failed to find hash for {iso_type.upper()}!")
        return

    cur_logger.info(f"Online hash is: {hashes[iso_type]['hash']}")
    target_path = os.path.join(working_directory, download_name)
    extracted_path = os.path.join(working_directory, f"NSRL_{iso_type}.txt")

    file_exist = False

    if os.path.isfile(target_path) and os.path.isfile(extracted_path):
        cur_logger.info(f"{download_name} already exist on disk, validating hash...")
        local_hash = calculate_sha1(target_path)
        if local_hash == hashes[iso_type]['hash']:
            cur_logger.info("The hashes match, we don't have to re-download!")
            file_exist = True

    if not file_exist:
        if download_name.endswith(".zip"):
            download_extract_zip(cur_logger, url, target_path, extracted_path, internal_file)
        else:
            download_extract_iso(cur_logger, url, target_path, extracted_path, internal_file)

        linux_command = "awk -F, 'NR > 1{ print \"sadd\", \"\\\"hashes\\\"\", \"\"$1\"\" }' " \
                        "%s | redis-cli --pipe" % extracted_path
        cur_logger.info(
            "Going to import %s into Redis by executing system command %s " %
            (extracted_path, linux_command))
        result = subprocess.run([linux_command], stdout=subprocess.PIPE, shell=True)
        cur_logger.info("Import finished with output %s" % result.stdout)

    else:
        cur_logger.info("Online hash and local hash are the same, skipping...")


def run_updater(cur_logger):
    # Setup working directory
    working_directory = os.path.join(tempfile.gettempdir(), 'whitelist_updates')
    # TODO: Cleanup ?
    # shutil.rmtree(working_directory, ignore_errors=True)
    os.makedirs(working_directory, exist_ok=True)

    # Get hashes
    hashes = get_online_hashes(cur_logger)

    update_list = [
        ['minimal', "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/rds_modernm.zip",
         "rds_modernm.zip", 'rds_modernm/NSRLFile.txt'],
        ['android', "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/RDS_android.iso",
         "RDS_android.iso", 'NSRLFile.txt']
    ]

    for x in update_list:
        update(cur_logger, working_directory, hashes, *x)


if __name__ == "__main__":
    log.init_logging('updater.whitelist')
    logger = logging.getLogger('assemblyline.updater.whitelist')
    run_updater(logger)
