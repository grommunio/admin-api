# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:19:34 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

import yaml
import logging
import logging.config
from os import scandir


_defaultConfig_ = {"openapi": {
                     "validateRequest": True,
                     "validateResponse": True
                   },
                   "options": {
                     "disableDB": False,
                     "dataPath": "/usr/share/grammm/common",
                     "propnames": "propnames.txt",
                     "portrait": "admin/api/portrait.jpg"
                   },
                   "security": {
                     "requireAuth": True
                   }
                   }


def _recursiveMerge_(dst, add):
    """Recursively merge two dictionaries.

    Add values from `src` to `dst`. If a key from `src` is already present in `dst`,
    the merge strategy depends on their types:
        - If both are lists, the lists are concatenated
        - If both are dicts, they are merged recursevly
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
    config = _defaultConfig_
    try:
        with open("config.yaml", "r") as file:
            _recursiveMerge_(config, yaml.load(file, Loader=yaml.SafeLoader))
        if "confdir" in config:
            configFiles = sorted([file.path for file in scandir(config["confdir"]) if file.name.endswith(".yaml")])
            for configFile in configFiles:
                with open(configFile) as file:
                    confd = yaml.load(file, Loader=yaml.SafeLoader)
                if confd is not None:
                    _recursiveMerge_(config, confd)
    except FileNotFoundError:
        pass
    if "logging" in config:
        logging.config.dictConfig(config["logging"])
    if not config["openapi"]["validateRequest"]:
        logging.warn("Request validation is disabled!")
    if not config["openapi"]["validateResponse"]:
        logging.warn("Response validation is disabled!")
    return config


Config = _loadConfig_()