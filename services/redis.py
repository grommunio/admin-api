# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub

from redis import Redis
from redis.exceptions import RedisError


def handleRedisExceptions(service, error):
    if isinstance(error, RedisError):
        return ServiceHub.UNAVAILABLE


@ServiceHub.register("redis", handleRedisExceptions, maxfailures=5)
class RedisService(Redis):
    def __init__(self):
        from tools.config import Config
        conf = Config["sync"].get("connection", {})
        conf["decode_responses"] = True
        Redis.__init__(self, **conf)


@ServiceHub.register("dkimredis", handleRedisExceptions, maxfailures=5)
class DkimRedisService(Redis):
    def __init__(self):
        from tools.config import Config
        cfg = Config.get("dkimRedis") or {}
        conf = dict(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 6380)),
            decode_responses=True,
        )
        if cfg.get("username"):
            conf["username"] = cfg["username"]
        if cfg.get("password"):
            conf["password"] = cfg["password"]
        Redis.__init__(self, **conf)
