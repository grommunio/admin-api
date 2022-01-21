# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

import api
from api.core import API, secure

from flask import jsonify

import json

try:
    with open("res/storelangs.json") as file:
        storeLangs = json.load(file)
except Exception as err:
    API.logger.warn("Failed to load store languages ({}): {}"
                    .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)))
    storeLangs = []


@API.route(api.BaseRoute+"/defaults/storeLangs", methods=["GET"])
@secure(requireAuth=False)
def getStoreLangs():
    return jsonify(data=storeLangs)
