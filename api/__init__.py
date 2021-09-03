# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH


BaseRoute = "/api/v1"  # Common prefix for all endpoints

apiSpec = None  # API specification
apiVersion = None  # API specification version. Extracted from the OpenAPI document.
backendVersion = "1.2.0"  # Backend version number


def _loadOpenApiSpec():
    global apiVersion, apiSpec
    try:
        import json
        with open("res/openapi.json", "r") as file:
            apiSpec = json.load(file)
    except FileNotFoundError:
        import yaml
        with open("res/openapi.yaml", "r") as file:
            apiSpec = yaml.load(file, Loader=yaml.SafeLoader)
    apiVersion = apiSpec["info"]["version"]


_loadOpenApiSpec()
