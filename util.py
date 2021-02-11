
from urllib.request import urlopen
import hashlib
import logging

logger = logging.getLogger('assemblyline.updater.whitelist')

BLOCK_SIZE = 64 * 1024


def calculate_sha1(local_file_path):
    sha1 = hashlib.sha1()

    with open(local_file_path, 'rb') as f:
        while True:
            data = f.read(BLOCK_SIZE)
            if not data:
                break
            sha1.update(data)

    nsrl_zip_hash = sha1.hexdigest().upper()
    return nsrl_zip_hash


def download_big_file(url, local_file_path):
    fo = None
    try:
        handle = urlopen(url)

        actual_size = 0
        name = local_file_path

        fo = open(name, "wb")
        while True:
            block = handle.read(BLOCK_SIZE)
            actual_size += len(block)
            if len(block) == 0:
                break
            fo.write(block)
        fo.close()

        logger.info(f"Download finished and saved into {local_file_path}, totally downloaded  = {actual_size} bytes")
    except Exception as e:
        # noinspection PyBroadException
        try:
            fo.close()
        except Exception:
            pass
        logger.error("Download failed %s " % e)
