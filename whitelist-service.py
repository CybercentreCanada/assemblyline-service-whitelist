import base64
import datetime
import json
import os
import re
import tempfile
import sys
import hashlib
import redis

from tempfile import mkstemp
from urllib.parse import urlparse

from assemblyline.odm import IP_ONLY_REGEX
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.result import Result, ResultSection, BODY_FORMAT


class Whitelist(ServiceBase):
    def __init__(self, config=None):
        super(Whitelist, self).__init__(config)

    def start(self):
        self.log.info(
            f"start() from {self.service_attributes.name} service called")

    def execute(self, request):
        BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

        sha1 = hashlib.sha1()

        with open(request.file_path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)

        fileHash = sha1.hexdigest().upper()

        r = redis.Redis(host='redisdb', port=6379)
        hashInDB = r.sismember ("hashes",fileHash)

        if hashInDB:
            self.log.info("{0} with SHA1 {1} found in whitelist".format(request.file_name, fileHash))
            request.drop()
        else:
            self.log.info("{0} with SHA1 {1} NOT found in whitelist".format(request.file_name, fileHash))

        result = Result()
        request.result = result