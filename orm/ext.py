# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 16:33:58 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from . import DB
from .DataModel import DataModel, Id, Text, Int

from sqlalchemy.dialects.mysql import INTEGER, TINYINT


class AreaList(DataModel, DB.Model):
    __table_name__ = "area_list"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    dataType = DB.Column("data_type", TINYINT, nullable=False)
    masterPath = DB.Column("master_path", DB.VARCHAR(256), nullable=False)
    slavePath = DB.Column("slave_path", DB.VARCHAR(256), nullable=False)
    accelPath = DB.Column("accel_path", DB.VARCHAR(256))
    maxSpace = DB.Column("max_space", INTEGER(10, unsigned=True), nullable=False)
    maxFiles = DB.Column("max_files", INTEGER(10, unsigned=True), nullable=False)

    _dictmapping_ = ((Id(),
                      Int("dataType", flags="patch"),
                      Text("masterPath", flags="patch"),
                      Text("slavePath", flags="patch"),
                      Text("accelPath", flags="patch"),
                      Int("maxSpace", flags="patch"),
                      Int("maxFiles", flags="patch")),)

    USER = 0
    DOMAIN = 1
    INDEPENDENT = 2
