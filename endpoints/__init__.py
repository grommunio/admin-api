#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:21:26 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_

Miscelleaneous API endpoints.
"""

__all__ = ["misc"]

from flask import request, jsonify
from orm import DB
from orm.DataModel import MissingRequiredAttributeError, InvalidAttributeError, MismatchROError
from pyxdameraulevenshtein import damerau_levenshtein_distance as dldist
import re

import api.security as sec

from sqlalchemy.exc import IntegrityError

matchStringRe = re.compile(r"([\w\-]*)")


def defaultListQuery(Model, filters=None, order=None, result="response", automatch=True, autofilter=True, autosort=True):
    """Process a listing query for specified model.

    Automatically uses 'limit' (50), 'offset' (0) and 'level' (1) parameters from the request.

    The return value can be influenced by `result`: `list` will return a list ob objects, while the default `response`
    will return the complete JSON encoded flask response.

    If `automatch` is enabled, the results are filtered by prefix-matching each word against the configured columns. If no
    other sorting is active (`order` is None and no "sort" query parameter is given), the results are ranked by the
    Damerau-Levenshtein distance to the search term. Note that ranking is done after the query and a low `limit` parameter
    may prevent a good match from being selected at all.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to perform the query on
    filters : iterable, optional
        A list of filter expressions to apply to the query. The default is None.
    order : list or Column, optional
        Column(s) to use in an order_by expression. The default is None.
    result : str, optional
        Return type.
    automatch : str, optional
        Name of the column to match against.
    autofilter : list of str, optional
        Whether to apply autofiltering. See DataModel.autofilter for more information. Default is True.
    autosort: boolean, optional
        Whether to apply autosorting. See DataModel.autosort for more information. Default is True.

    Returns
    -------
    Response
        Flask response containing the list data.
    """
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    verbosity = request.args.get("level", 1)
    query = Model.optimized_query(verbosity)
    if autosort:
        query = Model.autosort(query, request.args)
    if order is not None:
        query = query.order_by(*(order if type(order) in (list, tuple) else (order,)))
    if filters is not None:
        query = query.filter(*filters)
    if autofilter:
        query = Model.autofilter(query, request.args)
    if automatch and "match" in request.args:
        matchStr = request.args["match"].lower()
        fields = set(request.args["fields"].split(",")) if "fields" in request.args else None
        query = Model.automatch(query, request.args["match"], fields)
    query = query.limit(limit).offset(offset)
    objects = query.all()
    if order is None and "sort" not in request.args and automatch and "match" in request.args:
        scored = ((min(dldist(str(field).lower(), matchStr) for field in obj.matchvalues() if field is not None), obj)
                  for obj in objects)
        objects = [so[1] for so in sorted(scored, key=lambda entry: entry[0])]
    if result == "list":
        return objects
    return jsonify([obj.todict(verbosity) for obj in objects])


def defaultDetailQuery(Model, ID, errName):
    """Process a detail query for specified model.

    Automatically uses 'level' (2) parameter from the request.
    Returns a 404 error response if no object with the given ID is found.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to perform the query on.
    ID : int
        ID of the object.
    errName : str
        Object name to use in error messages.

    Returns
    -------
    Response
        Flask response containing the object data or an error message.
    """
    verbosity = request.args.get("level", 2)
    query = Model.query.filter(Model.ID == ID)
    query = Model.optimize_query(query, verbosity)
    obj = query.first()
    if obj is None:
        return jsonify(message=errName+" not found"), 404
    return jsonify(obj.todict(verbosity))


def defaultPatch(Model, ID, errName, obj=None):
    """Process a PATCH query for specified model.

    Performs an autopatch() call on the model.
    Returns a 404 error response if no object with the given ID is found.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to perform the query on.
    ID : int
        ID of the object.
    errName : str
        Object name to use in error messages.
    obj : SQLAlchemy model instance, optional
        Object to patch (suppresses object retrieval query). The default is None.

    Returns
    -------
    Response
        Flask response containing the new object data or an error message.
    """
    if request.json is None:
        return jsonify(message="Could not update: no valid JSON data"), 400
    if obj is None:
        obj = Model.query.filter(Model.ID == ID).first()
    if obj is None:
        return jsonify(message=errName+" not found"), 404
    try:
        obj.fromdict(request.json, user=sec.getUserName())
    except (InvalidAttributeError, MismatchROError) as err:
        DB.session.rollback()
        return jsonify(message=err.args[0]), 400
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Could not update: invalid data", error=err.orig.args[1]), 400
    return Model.optimized_query(2).filter(Model.ID == ID).first().fulldesc()


def defaultCreate(Model, result="response"):
    """Create a new object of the specified model.

    Performs a check on the input data, calls Model ctor and tries to insert the object into the database.
    Catches the following errors an returns an appropriate error message with HTTP 400 code:
        - The request does not contain a valid JSON object
        - Parameter check fails
        - Ctor raises a MissingRequiredAttributeError
        - Database commit raises an IntegrityError

    ParametersDefault
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to create a new instance from

    Returns
    -------
    Response
        Flask response containing the new object data or an error message.
    """
    data = request.json
    if data is None:
        return jsonify(message="Invalid JSON object"), 400
    error = Model.checkCreateParams(data)
    if error is not None:
        return jsonify(message=error), 400
    try:
        created = Model(props=data, user=sec.getUserName())
    except MissingRequiredAttributeError as err:
        return jsonify(message=err.args[0]), 400
    except ValueError as err:
        return jsonify(message=err.args[0]), 400
    except InvalidAttributeError as err:
        return jsonify(message=err.args[0]), 400
    if result == "object":
        return created
    DB.session.add(created)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400
    ID = created.ID
    return jsonify(Model.optimized_query(2).filter(Model.ID == ID).first().fulldesc()), 201


def defaultDelete(Model, ID, name):
    """Delete instance with specified ID from the model.

    If no object with the ID exists, a HTTP 404 error is returned.
    If deletion of the object would violate database constraints, a HTTP 400 error is returned.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to delete from.
    ID : int
        ID of the object to delete.
    name : str
        Object name to use in messages.

    Returns
    -------
    Response
        Flask response containing the new object data or an error message.
    """
    obj = Model.query.filter(Model.ID == ID).first()
    if obj is None:
        return jsonify(message=name+" not found"), 404
    try:
        DB.session.delete(obj)
        DB.session.commit()
    except IntegrityError as err:
        return jsonify(message="Object deletion would violate database constraints", error=err.args[0]), 400
    return jsonify(message="{} #{} deleted.".format(name, ID))


def defaultBatchDelete(Model):
    """Delete a list of instances.

    If an ID is not found, it is ignored.
    If deletion of the object would violate database constraints, a HTTP 400 error is returned.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to delete from.

    Returns
    -------
    Response
        Flask response containing the new object data or an error message.
    """
    if "ID" not in request.args:
        return jsonify(message="Missing ID list"), 400
    IDs = request.args["ID"].split(",")
    objs = Model.query.filter(Model.ID.in_(IDs)).all()
    IDs = [obj.ID for obj in objs]
    try:
        for obj in objs:
            DB.session.delete(obj)
        DB.session.commit()
    except IntegrityError as err:
        return jsonify(message="Object deletion would violate database constraints", error=err.args[0]), 400
    return jsonify(message="Delete successful.", deleted=IDs)


def defaultListHandler(Model, filters=None, order=None, result="response", automatch=True, autofilter=True, autosort=True):
    """Handle operations on lists.

    Handles list (GET), create (POST) and batch delete (DELETE) requests for the given model.
    Automatically delegates to appripriate default function according to request method.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to perform the query on
    filters : iterable, optional
        A list of filter expressions to apply to the query. Only applicable for GET requests. The default is None.
    order : list or Column, optional
        Column(s) to use in an order_by expression. Only applicable for GET requests. The default is None.
    result : str, optional
        Return type. See defaultListQuery for more detail. Default is "response"
    automatch : bool, optional
        Whether to apply automatching. See defaultListQuery for more detail.
    autofilter : boolean, optional
        Whether to apply autofiltering. See DataModel.autofilter for more information. Default is True.
    autosort: boolean, optional
        Whether to apply autosorting. See DataModel.autosort for more information. Default is True.

    Returns
    -------
    Response
        Flask response containing data or error message.
    """
    if request.method == "GET":
        return defaultListQuery(Model, filters, order, result, automatch, autofilter, autosort)
    elif request.method == "POST":
        return defaultCreate(Model)
    elif request.method == "DELETE":
        return defaultBatchDelete(Model)


def defaultObjectHandler(Model, ID, name):
    """Handle operations on objects.

    Handles detail (GET), update (PATCH) or delete (DELETE) requests.
    Automatically delegates to appripriate default function according to request method.

    Parameters
    ----------
    Model : SQLAlchemy model with DataModel extension
        Model to perform query on.
    ID : int
        ID of the object to operate on.
    name : str
        Object name to use in messages.

    Returns
    -------
    Response
        Flask response containing data or error message.
    """
    if request.method == "GET":
        return defaultDetailQuery(Model, ID, name)
    elif request.method == "PATCH":
        return defaultPatch(Model, ID, name)
    elif request.method == "DELETE":
        return defaultDelete(Model, ID, name)
