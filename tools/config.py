# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import yaml
import logging
from os import scandir

logger = logging.getLogger("config")


def _defaultConfig():
    _defaultSyncPolicy = {
      "allowbluetooth": 2,
      "allowbrowser": 1,
      "allowcam": 1,
      "allowconsumeremail": 1,
      "allowdesktopsync": 1,
      "allowhtmlemail": 1,
      "allowinternetsharing": 1,
      "allowirda": 1,
      "allowpopimapemail": 1,
      "allowremotedesk": 1,
      "allowsimpledevpw": 1,
      "allowsmimeencalgneg": 2,
      "allowsmimesoftcerts": 1,
      "allowstoragecard": 1,
      "allowtextmessaging": 1,
      "allowunsignedapps": 1,
      "allowunsigninstallpacks": 1,
      "allowwifi": 1,
      "alphanumpwreq": 0,
      "approvedapplist": [],
      "attenabled": 1,
      "devencenabled": 0,
      "devpwenabled": 0,
      "devpwexpiration": 0,
      "devpwhistory": 0,
      "maxattsize": "",
      "maxcalagefilter": 0,
      "maxdevpwfailedattempts": 8,
      "maxemailagefilter": 0,
      "maxemailbodytruncsize": -1,
      "maxemailhtmlbodytruncsize": -1,
      "maxinacttimedevlock": 900,
      "mindevcomplexchars": 3,
      "mindevpwlenngth": 4,
      "pwrecoveryenabled": 0,
      "reqdevenc": 0,
      "reqencsmimealgorithm": 0,
      "reqencsmimemessages": 0,
      "reqmansyncroam": 0,
      "reqsignedsmimealgorithm": 0,
      "reqsignedsmimemessages": 0,
      "unapprovedinromapplist": []
    }
    return {
        "openapi": {
            "validateRequest": True,
            "validateResponse": True
            },
        "options": {
            "disableDB": False,
            "dataPath": "/usr/share/grommunio-admin-common",
            "propnames": "propnames.txt",
            "portrait": "portrait.jpg",
            "domainStoreRatio": 10,
            "domainPrefix": "/var/lib/gromox/domain/",
            "userPrefix": "/var/lib/gromox/user/",
            "exmdbHost": "::1",
            "exmdbPort": "5000",
            "domainStorageLevels": 1,
            "userStorageLevels": 2,
            "domainAcceleratedStorage": None,
            "userAcceleratedStorage": None,
            "dashboard": {
                "services": []
                }
            },
        "security": {
            "jwtPrivateKeyFile": "res/jwt-privkey.pem",
            "jwtPublicKeyFile": "res/jwt-pubkey.pem"
            },
        "mconf": {},
        "logs": {},
        "sync": {
            "defaultPolicy": _defaultSyncPolicy,
            "policyHosts": ["127.0.0.1", "localhost", "::1"]
            },
        "chat": {
            "connection": {},
            },
        }


def initLoggers():
    if "logging" not in Config:
        return
    logconf = Config["logging"]
    logging.getLogger().setLevel(logconf.get("level", logging.WARNING))
    for logger, conf in logconf.get("loggers", {}).items():
        logging.getLogger(logger).setLevel(conf.get("level", logging.NOTSET))


def _recursiveMerge_(dst, add):
    """Recursively merge two dictionaries.

    Add values from `src` to `dst`. If a key from `src` is already present in `dst`,
    the merge strategy depends on their types:
        - If both are lists, the lists are concatenated
        - If both are dicts, they are merged recursively
        - Otherwise the value from `dst` is overwritten
    """
    assert type(dst) is dict and type(add) is dict
    for key in add.keys():
        if key in dst:
            if type(dst[key]) is list and type(add[key]) is list:
                dst[key] += add[key]
            elif type(dst[key]) is dict and type(add[key]) is dict:
                _recursiveMerge_(dst[key], add[key])
            else:
                dst[key] = add[key]
        else:
            dst[key] = add[key]


def _loadConfig_():
    """Load configuration file.

    Try to load configuration from './config.yaml'.
    If the file exists, the default configuration is updated.

    If the optional value 'confdir' is present,
    the specified directory is searched for further YAML files,
    which are recursively merged into the config.
    """
    config = _defaultConfig()
    try:
        with open("config.yaml", "r") as file:
            _recursiveMerge_(config, yaml.load(file, Loader=yaml.SafeLoader))
        if "confdir" in config:
            configFiles = sorted([file.path for file in scandir(config["confdir"]) if file.name.endswith(".yaml")])
            for configFile in configFiles:
                try:
                    with open(configFile) as file:
                        confd = yaml.load(file, Loader=yaml.SafeLoader)
                    if confd is not None:
                        _recursiveMerge_(config, confd)
                except Exception as err:
                    logger.error("Failed to load '{}': {}".format(configFile, " - ".join(str(arg) for arg in err.args)))
    except Exception as err:
        logger.error("Failed to load 'config.yaml': {}".format(" - ".join(str(arg) for arg in err.args)))
    return config


Config = _loadConfig_()


def validate():
    """Verify configuration validity.

    Returns
    -------
    str
        Error message, or None if validation succeeds
    """
    from openapi_schema_validator import OAS30Validator
    from openapi_spec_validator.exceptions import ValidationError
    try:
        with open("res/config.yaml") as file:
            configSchema = yaml.load(file, yaml.loader.SafeLoader)
    except Exception:
        return "Could not open schema file"
    validator = OAS30Validator(configSchema)
    try:
        validator.validate(Config)
    except ValidationError as err:
        return err.args[0]
