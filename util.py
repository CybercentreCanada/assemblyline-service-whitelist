from urllib.request import urlopen
import os
import tqdm
import hashlib
import logging

logger = logging.getLogger('assemblyline.updater.whitelist')

def calculateSHA1(localFilePath):
    BLOCK_SIZE = 64*1024

    sha1 = hashlib.sha1()

    with open(localFilePath, 'rb') as f:
        size = os.path.getsize(localFilePath)
        while True:
            data = f.read(BLOCK_SIZE)
            if not data:
                break
            sha1.update(data)

    nsrlZipHash = sha1.hexdigest().upper()
    return nsrlZipHash

def downloadBigFile(url, localFilePath):
    try:
        handle =  urlopen(url)

        size = int(handle.info()["Content-Length"])
        actualSize = 0
        name = localFilePath
        BLOCK_SIZE = 64*1024

        fo = open(name, "wb")
        while True:
            block = handle.read(BLOCK_SIZE)
            actualSize += len(block)
            if len(block) == 0:
                break
            fo.write(block)
        fo.close()

        logger.info("Download finished and saved into %s, totally downloaded  = %s bytes" % (localFilePath, actualSize))
    except (urllib.URLError, socket.timeout) as e:
        try:
            fo.close()
        except:
            pass
        logger.error("Download failed %s " % e)