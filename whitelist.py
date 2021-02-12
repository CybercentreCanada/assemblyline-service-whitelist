
import os
import redis

from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.result import Result, ResultSection, Heuristic

REDIS_SERVER = os.environ.get('REDIS_SERVER', "whitelist-redisdb")


class Whitelist(ServiceBase):
    def __init__(self, config=None):
        super(Whitelist, self).__init__(config)

    def start(self):
        self.log.info(
            f"start() from {self.service_attributes.name} service called")

    def execute(self, request):
        result = Result()
        file_hash = request.sha1.upper()
        r = redis.Redis(host=REDIS_SERVER, port=6379)

        if r.sismember("hashes", file_hash):
            msg = "{0} with SHA1 {1} found in whitelist".format(request.file_name, file_hash)
            result.add_section(ResultSection(msg, heuristic=Heuristic(1)))
            request.drop()

        request.result = result
