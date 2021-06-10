# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

import re

email = re.compile(r"^(?P<user>[a-zA-Z0-9_.+-]+)@(?P<domain>[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$")
domain = re.compile(r"^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")