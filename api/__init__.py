# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 10:47:13 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import yaml

from openapi_core import create_spec
from tools.config import Config

BaseRoute = "/api/v1"  # Common prefix for all endpoints

apiSpec = None  # API specification
apiVersion = None  # API specification version. Extracted from the OpenAPI document.
backendVersion = "0.12.1"  # Backend version number


def _loadOpenApiSpec():
    global apiVersion, apiSpec
    with open("res/openapi.yaml", "r") as file:
        openapi_defs = yaml.load(file, Loader=yaml.SafeLoader)
    if "servers" in Config["openapi"]:
        openapi_defs["servers"] += Config["openapi"]["servers"]
    apiSpec = create_spec(openapi_defs)
    apiVersion = openapi_defs["info"]["version"]


_loadOpenApiSpec()
