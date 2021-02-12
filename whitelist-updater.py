# This updater is made to follow the NSRL file format which is a CSV file with the following format:
# "SHA-1","MD5","CRC32","FileName","FileSize","ProductCode","OpSystemCode","SpecialCode"
#
# You can then create your own whitelist set that matches that format to have your own set of hashes...
import json

import certifi
import logging
import os
import pycdlib
import requests
import shutil
import subprocess
import tempfile
import time
import yaml
import zipfile

from assemblyline.common import log
from assemblyline.common.isotime import iso_to_epoch

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

UPDATE_CONFIGURATION_PATH = os.environ.get('UPDATE_CONFIGURATION_PATH', "/tmp/whitelist_updater_config.yaml")


BLOCK_SIZE = 64 * 1024


def add_cacert(cert: str):
    # Add certificate to requests
    cafile = certifi.where()
    with open(cafile, 'a') as ca_editor:
        ca_editor.write(f"\n{cert}")


def url_download(source, target_path, cur_logger, previous_update=None):
    uri = source['uri']
    username = source.get('username', None)
    password = source.get('password', None)
    ca_cert = source.get('ca_cert', None)
    ignore_ssl_errors = source.get('ssl_ignore_errors', False)
    auth = (username, password) if username and password else None

    proxy = source.get('proxy', None)
    headers = source.get('headers', None)

    cur_logger.info(f"This source is configured to {'ignore SSL errors' if ignore_ssl_errors else 'verify SSL'}.")
    if ca_cert:
        cur_logger.info("A CA certificate has been provided with this source.")
        add_cacert(ca_cert)

    # Create a requests session
    session = requests.Session()
    session.verify = not ignore_ssl_errors

    # Let https requests go through proxy
    if proxy:
        os.environ['https_proxy'] = proxy

    try:
        if isinstance(previous_update, str):
            previous_update = iso_to_epoch(previous_update)

        # Check the response header for the last modified date
        response = session.head(uri, auth=auth, headers=headers)
        last_modified = response.headers.get('Last-Modified', None)
        if last_modified:
            # Convert the last modified time to epoch
            last_modified = time.mktime(time.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z"))

            # Compare the last modified time with the last updated time
            if previous_update and last_modified <= previous_update:
                # File has not been modified since last update, do nothing
                cur_logger.info("The file has not been modified since last run, skipping...")
                return False

        if previous_update:
            previous_update = time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(previous_update))
            if headers:
                headers['If-Modified-Since'] = previous_update
            else:
                headers = {'If-Modified-Since': previous_update}

        cur_logger.info(f"Downloading file from: {source['uri']}")
        with session.get(uri, auth=auth, headers=headers, stream=True) as response:
            # Check the response code
            if response.status_code == requests.codes['not_modified']:
                # File has not been modified since last update, do nothing
                cur_logger.info("The file has not been modified since last run, skipping...")
                return False
            elif response.ok:
                with open(target_path, 'wb') as f:
                    for content in response.iter_content(BLOCK_SIZE):
                        f.write(content)

                # Clear proxy setting
                if proxy:
                    del os.environ['https_proxy']

                # Return file_path
                return True
    except requests.Timeout:
        pass
    except Exception as e:
        # Catch all other types of exceptions such as ConnectionError, ProxyError, etc.
        cur_logger.info(str(e))
        return False
    finally:
        # Close the requests session
        session.close()


def download_extract_zip(cur_logger, source, target_path, extracted_path, working_directory, previous_update):
    if url_download(source, target_path, cur_logger, previous_update=previous_update):
        cur_logger.info(f"Unzipping downloaded file {target_path}... into {extracted_path}")

        with zipfile.ZipFile(target_path) as z:
            z.extract(source['pattern'], working_directory)
        os.unlink(target_path)

        os.rename(os.path.join(working_directory, source['pattern']), extracted_path)
        cur_logger.info(f"Unzip finished, created file {extracted_path}")


def download_extract_iso(cur_logger, source, target_path, extracted_path, working_directory, previous_update):
    # NSRL ISO only!
    if url_download(source, target_path, cur_logger, previous_update=previous_update):
        zip_file = f"{target_path}.zip"

        iso = pycdlib.PyCdlib()
        iso.open(target_path)

        cur_logger.info("Extracting NSRLFILE.ZIP form ISO...")
        with open(zip_file, "wb") as zip_fh:
            iso.get_file_from_iso_fp(zip_fh, iso_path='/NSRLFILE.ZIP;1')
        iso.close()
        os.unlink(target_path)

        cur_logger.info(f"Unzipping {zip_file} ...")
        with zipfile.ZipFile(zip_file) as z:
            z.extract(source['pattern'], working_directory)
        os.unlink(zip_file)

        os.rename(os.path.join(working_directory, source['pattern']), extracted_path)
        cur_logger.info(f"Unzip finished, created file {extracted_path}")


def update(cur_logger, working_directory, source, previous_update, previous_hash):
    cur_logger.info(f"Processing source: {source['name'].upper()}")
    download_name = os.path.basename(source['uri'])
    target_path = os.path.join(working_directory, 'dl', download_name)
    extracted_path = os.path.join(working_directory, source['name'])

    if download_name.endswith(".zip"):
        download_extract_zip(cur_logger, source, target_path,
                             extracted_path, working_directory, previous_update)
    elif download_name.endswith(".iso"):
        download_extract_iso(cur_logger, source, target_path,
                             extracted_path, working_directory, previous_update)
    else:
        url_download(source, extracted_path, cur_logger, previous_update=previous_update)

    if os.path.exists(extracted_path) and os.path.isfile(extracted_path):
        linux_command = "awk -F, 'NR > 1{ print \"sadd\", \"\\\"hashes\\\"\", \"\"$1\"\" }' " \
                        "%s | redis-cli --pipe" % extracted_path
        cur_logger.info(
            "Going to import %s into Redis by executing system command %s " %
            (extracted_path, linux_command))
        result = subprocess.run([linux_command], stdout=subprocess.PIPE, shell=True)
        os.unlink(extracted_path)

        cur_logger.info("Import finished with output:")
        for line in result.stdout.split(b"\n"):
            cur_logger.info(f"\t{line.decode()}")


def run_updater(cur_logger, update_config_path):
    # Setup working directory
    working_directory = os.path.join(tempfile.gettempdir(), 'whitelist_updates')
    shutil.rmtree(working_directory, ignore_errors=True)
    os.makedirs(os.path.join(working_directory, 'dl'), exist_ok=True)

    update_config = {}
    if update_config_path and os.path.exists(update_config_path):
        with open(update_config_path, 'r') as yml_fh:
            update_config = yaml.safe_load(yml_fh)
    else:
        cur_logger.error(f"Update configuration file doesn't exist: {update_config_path}")
        exit()

    # Exit if no update sources given
    if 'sources' not in update_config.keys() or not update_config['sources']:
        cur_logger.error(f"Update configuration does not contain any source to update from")
        exit()

    previous_update = update_config.get('previous_update', None)
    previous_hash = json.loads(update_config.get('previous_hash', None) or "{}")

    for source in update_config['sources']:
        update(cur_logger, working_directory, source, previous_update, previous_hash)

    cur_logger.info("Done!")


if __name__ == "__main__":
    log.init_logging('updater.whitelist')
    logger = logging.getLogger('assemblyline.updater.whitelist')
    run_updater(logger, UPDATE_CONFIGURATION_PATH)
