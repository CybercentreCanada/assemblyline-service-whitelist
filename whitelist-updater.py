# This module checks first online the hash for NSRL file, then compares with hash of local copy.
# If hashes are different, download new NSRL file

import requests
import os
from os import path
import zipfile
import socket
import urllib
from util import downloadBigFile
from util import calculateSHA1
import subprocess
import logging

import sys
import pycdlib

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

logger = logging.getLogger('assemblyline.updater.whitelist')

# ****************************UPDATE  modernm RDS***************************************************************
logger.info("Checking Modern RDS (minimal)")

hashUrl = 'https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/version.txt'

nsrlModernmZipUrl = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/rds_modernm.zip"
localNsrlModernmZipFilePath = path.join(".", "rds_modernm.zip")

logger.info("Downloading online rds_modernm hash from %s" % hashUrl)
hashFileResponse = requests.get(hashUrl)

onlineHash = ""

for item in hashFileResponse.text.split("\n"):
    if "minimal" in item:
        onlineHash =  item.strip().split(",")[0].strip("\"").upper()

logger.info("Online rds_modernm hash is %s" % onlineHash )

logger.info("Checking if NSRL rds_modernm zip already downloaded.")

localRdsModernmZipFileExists = True

if not os.path.isfile(localNsrlModernmZipFilePath):
    logger.info("%s does not exist yet" % localNsrlModernmZipFilePath )
    localRdsModernmZipFileExists = False
else:
    logger.info("./rds_modernm.zip already available")

localNsrlModernmZipHash = ""

if localRdsModernmZipFileExists:
    logger.info("Calculating hash of %s, this may take some time..." % localNsrlModernmZipFilePath )

    localNsrlModernmZipHash = calculateSHA1(localNsrlModernmZipFilePath)
    logger.info("Hash of local NSRL ZIP = %s" % localNsrlModernmZipHash)

if(onlineHash != localNsrlModernmZipHash or not(localRdsModernmZipFileExists)):
     logger.info("Downloading %s ..." % nsrlModernmZipUrl)
     downloadBigFile(nsrlModernmZipUrl, localNsrlModernmZipFilePath)

     localNSRLModernmTxtFile ="./NSRL_Modernm.txt"

     logger.info("Unzipping downloaded file %s ... into %s" % (localNsrlModernmZipFilePath, localNSRLModernmTxtFile))

     logger.info("Unzipping %s ...", localNsrlModernmZipFilePath)

     with zipfile.ZipFile(localNsrlModernmZipFilePath) as z:
        with open(localNSRLModernmTxtFile, 'wb') as f:
            f.write(z.read('rds_modernm/NSRLFile.txt'))
     logger.info("Unzip finished, created file %s" % localNSRLModernmTxtFile)


     linuxCommand = "awk -F, 'NR > 1{ print \"sadd\", \"\\\"hashes\\\"\", \"\"$1\"\" }' %s | redis-cli --pipe" % localNSRLModernmTxtFile
     logger.info("Going to import %s into Redis by executing system command %s " % (localNSRLModernmTxtFile, linuxCommand) )
     result = subprocess.run([linuxCommand], stdout=subprocess.PIPE, shell=True)
     logger.info("Import finished with output %s" % result.stdout)

else:
     logger.info("Online hash and local rds_modernm  hash are the same, exiting.")


# ***************************** UPDATE Android RDS **************************************************************
logger.info("Checking Android NSRL list ")

androidIsoUrl = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/RDS_android.iso"

onlineHash = ""

for item in hashFileResponse.text.split("\n"):
    if "android" in item:
        onlineHash = item.strip().split(",")[0].strip("\"").upper()

logger.info("Online Android NSRL ISO hash is %s" % onlineHash)

logger.info("Checking if Android NSRL ISO already downloaded locally.")

localAndroidNsrlIsoFileExists = True
localNsrlIsoFilePath = path.join(".", "RDS_android.iso")

if not os.path.isfile(localNsrlIsoFilePath):
    logger.info("%s does not exist yet" % localNsrlIsoFilePath)
    localAndroidNsrlIsoFileExists = False
else:
    logger.info("Android NSRL iso already downloaded locally.")

localAndroidNsrlIsoHash = ""

if localAndroidNsrlIsoFileExists:
    logger.info("Calculating hash of local  Android NSRL iso %s, this may take some time " % localNsrlIsoFilePath )

    localAndroidNsrlIsoHash = calculateSHA1(localNsrlIsoFilePath)
    logger.info("Hash of local Android NSRL ISO = %s" % localAndroidNsrlIsoHash)

if(onlineHash != localAndroidNsrlIsoHash or not(localAndroidNsrlIsoFileExists)):
    logger.info("Downloading %s ..." % androidIsoUrl)
    downloadBigFile(androidIsoUrl, localNsrlIsoFilePath)

    iso = pycdlib.PyCdlib()
    iso.open(localNsrlIsoFilePath)

    logger.info("ISO contains followings files:")

    for child in iso.list_children(iso_path='/'):
        logger.info(child.file_identifier())

    logger.info("Copying NSRLFILE.ZIP from ISO to buffer... ")
    extracted_iso = BytesIO()
    iso.get_file_from_iso_fp(extracted_iso, iso_path='/NSRLFILE.ZIP;1')

    logger.info("Flushing buffer to ./NSRLFILE_ANDROID.ZIP ... ")

    with open("NSRLFILE_ANDROID.ZIP", "wb") as f:
        f.write(extracted_iso.getbuffer())

    logger.info("Unzipping ./NSRLFILE_ANDROID.ZIP ...")

    localNSRLAndroidTxtFile ="./NSRL_Android.txt"

    with zipfile.ZipFile("./NSRLFILE_ANDROID.ZIP") as z:
        with open(localNSRLAndroidTxtFile, 'wb') as f:
            f.write(z.read('NSRLFile.txt'))
    logger.info("Unzip finished, created file %s" % localNSRLAndroidTxtFile)

    iso.close()

    linuxCommand = "awk -F, 'NR > 1{ print \"sadd\", \"\\\"hashes\\\"\", \"\"$1\"\" }' %s | redis-cli --pipe" % localNSRLAndroidTxtFile
    logger.info("Going to import %s into Redis by executing system command %s " % (localNSRLAndroidTxtFile, linuxCommand) )
    result = subprocess.run([linuxCommand], stdout=subprocess.PIPE, shell=True)
    logger.info("Import finished with output %s" % result.stdout)
else:
    logger.info("Online hash and local Android ISO hash are the same, exiting.")