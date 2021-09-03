# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from sqlalchemy import func, or_
from sqlalchemy.inspection import inspect as inspecc
from sqlalchemy.orm import joinedload, aliased

from collections.abc import Iterable

import logging
logger = logging.getLogger("DataModel")


def _isCollection(obj):
    """Determine if whether an object is a collection."""
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def _str2bool(string):
    if string.lower() in ("true", "1", "yes"):
        return True
    elif string.lower() in ("false", "0", "no"):
        return False
    raise ValueError("Argument must be either 'true' or 'false'")


class MismatchROError(BaseException):
    """Exception raised when a read-only attribute does not match."""

    pass


class InvalidAttributeError(BaseException):
    """Exception raised when an unknown attribute is to be modified."""

    pass


class MissingRequiredAttributeError(BaseException):
    """Exception raised when a required attribute is not specified."""

    pass


class DataModel:
    """Central class for data structuring.

    Provides standardizes implementation for reading and writing data from and to SQLAlchemy mapped tables.
    """

    class Prop:
        """Property representation.

        Manages property settings.
        """

        def __init__(self, attr, alias=None, flags=None, args=(), kwargs={}, mask=None, target=None, dispname=None,
                     flat=None, func=None, link=None, filter=None, qopt=joinedload, proxy=None, arg_tf=None, match="default",
                     **unknown):
            """
            Initialize Prop.

            Parameters
            ----------
            attr : str
                Name of the attribute to map.
            alias : str, optional
                Alias of the attribute. If set, effectively replaces `attr` to front-facing operations. The default is None.
            flags : str, optional
                Comma separated list of flags. Recognized values are:
                    - ref: The attribute is a relationship that should be dereferenced
                    - call: The attribude is a method that returns the actual value
                    - sort: The attribute is available for sorting. Can also be set with _sortables_
                    - patch: The attribute can be set/updated
                    - init: Like `patch` but only if the current value is `None`
                    - managed: The referenced object(s) are fully managed through this class (enables transparent CUD)
                        The default is None.
                    - match: Use this attribute for matching. Can also be set with _matchables_
                    - hidden: The attribute is not included at any level
            args : Collection, optional
                List of arguments passed to the function if `call` or `func` is set. The default is None.
            kwargs : dict, optional
                Keyword arguments passed to the function if `call` or `func` is set. The default is None.
            mask : str, optional
                Name of the attribute masked by the relationship (i.e. the foreign key column). The default is None.
            target : str, optional
                Name of the foreign attribute to use for sorting and matching. The default is None.
            flat : str, optional
                If set, do not serialize ref into an object, but use its `flat` attribute directly. The default is None.
            func : function, optional
                Call `func` on the attribute. Effectively executes func(attr, *args, **kwargs). The default is None.
            link : str, optional
                Name of the attribute identifying the foreign object. The default is None.
            filter : str, optional
                Type of multi-value filtering to apply. Valid values are 'set' and 'range. The default is None.
            qopt : function, optional
                Type of query optimization to use for the relationship. The default is `joinedload`.
            proxy: str, optional
                Name of the relationship containing the attribute. Usable only for search/filter/match operations.
            arg_tf: function, optional
                Function transform request arguments into the correct format/type. Used by filter and match operations.
            match: str, optional
                Mode used by automatch. Default mode uses substring matching, "exact" performs equality matching.
            **unknown : dict
                Keyword arguments not recognized by DataModel. Will issue a warning in the logger.
            """
            self.attr = attr
            self._alias = alias
            self.flags = set(f.strip() for f in flags.split(",")) if flags is not None else set()
            self.args = args or ()
            self.kwargs = kwargs
            self.mask = mask
            self.target = target
            self.flat = flat
            self.dispname = dispname
            self.func = func
            self.qopt = qopt
            self.link = link
            self.filter = filter
            self.proxy = proxy
            self.arg_tf = arg_tf
            self.match = match
            if len(unknown):
                logger.warn("Unknown DataModel parameters: "+", ".join(unknown.keys()))

        def __repr__(self):
            """Return string representation."""
            return "DataModel.Prop({}, {}, {}, {}, {}, {}, {})".format(self.attr, self.alias, ", ".join(self.flags), self.args,
                                                                       self.kwargs, self.mask, self.target, self.dispname,
                                                                       self.flat, self.func, self.link, self.filter, self.qopt)

        @property
        def key(self):
            """Return front facing key.

            Returns
            -------
            str
                alias, if set, attr otherwise.
            """
            return self.alias or self.attr

        def value(self, base, transform="all"):
            """Return value.

            Parameters
            ----------
            base : Insatance or Class
                Base Object
            transform : str, optional
                Transformation to apply. Valid values are:
                    - 'unmask': Return unmasked value
                    - 'raw': Do not apply any transformation.
                    - 'targetval' (Instance only): Get attribute specified by target attribute (unmask if not set)
                    - 'all' (Instance only): Perform dereferencing and function transormations
                    The default is "all".
            """
            if self.proxy is not None:
                foreign = getattr(base, self.proxy)
                foreign._init()
                return foreign._meta.lookup[self.target].value(foreign, transform)
            if transform == "unmask" or (transform == "targetval" and self.target is None):
                return getattr(base, self.mask or self.attr)
            val = getattr(base, self.attr)
            if transform == "raw":
                return val
            elif transform == "targetval":
                return getattr(self.value(base, "raw"), self.target, None)
            if "ref" in self.flags:
                val = {k: self.deref(v) for k, v in val.items()} if isinstance(val, dict) else\
                      [self.deref(v) for v in val] if _isCollection(val) else self.deref(val)
            elif self.func is not None:
                val = self.func(val, *self.args, **self.kwargs)
            elif "call" in self.flags:
                val = base.val(*self.args, **self.kwargs)
            return val

        def resolve(self, Model, query, unmask=False):
            """Resolve foreign columns and add join statements.

            Parameters
            ----------
            Model : Class
                Class deriving from DataModel
            query : SQLAlchemy BaseQuery
                Current query to add joins to
            unmask : boolean, optional
                Unmask final column. The default is False.

            Returns
            -------
            Column
                Column that can be used for filter/sort/match expressions. Automatically aliased.
            SQLAlchemy BaseQuery
                Query with applied joins if necessary
            """
            if self.proxy is not None:
                val = getattr(Model, self.proxy)
                FModel = aliased(inspecc(val).property.mapper.entity)
                FModel._init()
                return FModel._meta.lookup[self.target].resolve(FModel, query.outerjoin(FModel, val), unmask)
            val = getattr(Model, self.attr)
            if unmask or self.target is None:
                return self.value(Model, "unmask" if unmask else "raw"), query
            alias = aliased(inspecc(val).property.mapper.entity)
            column = getattr(alias, self.target)
            return column, query.outerjoin(alias, val)

        def deref(self, value):
            """Dereference value."""
            return None if value is None else value.ref() if self.flat is None else value.ref()[self.flat]

        @property
        def alias(self):
            """Get alias, if set. Otherwise return attr."""
            return self._alias or self.attr

        def writable(self, base):
            """Check whether tha attribute is writable."""
            return "patch" in self.flags or (self.value(base) is None and "init" in self.flags)

        def tf(self, value):
            """Transform string argument to filter value.

            If arg_tf is set, the transform is provided entirely by that function. if a ValueError is raised, None is returned.
            If no arg_tf is set, return the value if it is a non-empty string, otherwise None.

            Parameters
            ----------
            value : str
                Value to transform

            Returns
            -------
            any
                Transformed value or None if transformation fails or value is empty
            """
            try:
                if self.arg_tf:
                    return self.arg_tf(value)
                else:
                    return None if len(value) == 0 else value
            except ValueError:
                return None

    class Meta:
        """Class storing the metadata.

        Stores all mapped props and keeps shortcuts for filtering and reverse lookup
        """

        def __init__(self, dictmap, sortables, matchables):
            """Initialize metadata.

            Parameters
            ----------
            dictmap : tuple of tuples
                List of levels, each consisting of a list of properties. Properties can be strings, dicts or Prop instances
            sortables : Collection
                List of prop names that are available for sorting
            """
            self.levels = tuple(tuple(entry if type(entry) == DataModel.Prop else
                                      DataModel.Prop(entry) if type(entry) == str else
                                      DataModel.Prop(**entry) for entry in level) for level in dictmap)
            self.lookup = {prop.key: prop for prop in self.props() if prop.key is not None}
            for s in sortables:
                self.lookup[s].flags.add("sort")
            for m in matchables:
                self.lookup[m].flags.add("match")
            self.filters = tuple(self.props(predicate=lambda prop: prop.filter is not None))
            self.matchables = tuple(self.props(predicate=lambda prop: "match" in prop.flags))

        def props(self, level=None, predicate=lambda x: True):
            """Return list of props available at level, fulfilling the predicate.

            Parameters
            ----------
            level : int, optional
                If set, return only props that are on this level or below. The default is None.
            predicate : function, optional
                Include only props for which predicate returns True. The default is lambda x: True.

            Returns
            -------
            Generator Object
                Iterator listing all Prop objects matching the constraints
            """
            return (prop for lev in range(len(self.levels))
                    for prop in self.levels[lev]
                    if (level is None or lev <= int(level)) and predicate(prop))

    _meta = None

    def __init__(self, props, *args, **kwargs):
        """Default-construct object.

        All arguments are passed on to fromdict() to perform model driven initialization.
        Parameters
        ----------
        props : dict
            Dict containing properties.
        *args : Collection
            Further arguments
        **kwargs : dict
            Further keyword arguments
        """
        self.fromdict(props, *args, **kwargs)

    @classmethod
    def _init(cls):
        """Initialize metadata object."""
        if cls._meta is None:
            cls._meta = cls.Meta(getattr(cls, "_dictmapping_", ((),)),
                                 getattr(cls, "_sortables_", set()),
                                 getattr(cls, "_matchables_", tuple()))

    def ref(self, **kwargs):
        """Generate level 0 representation.

        See todict for more information.
        """
        return self.todict(0, **kwargs)

    def overview(self, **kwargs):
        """Generate level 1 representation.

        See todict for more information.
        """
        return self.todict(1, **kwargs)

    def fulldesc(self, **kwargs):
        """Generate level 2 representation.

        See todict for more information.
        """
        return self.todict(2, **kwargs)

    def todict(self, verbosity, exclude=set()):
        """Create dictionary representation of the object.

        Parameters
        ----------
        verbosity : int
            Level of detail.
        exclude : set
            Attributes to exclude

        Returns
        -------
        dict
            Dictionary representation
        """
        self._init()
        return {prop.key: prop.value(self) for prop in self._meta.props(verbosity, lambda x: x.proxy is None)
                if "hidden" not in prop.flags and prop.attr not in exclude}

    @classmethod
    def optimize_query(cls, query, verbosity):
        """Optimize query by eager loading relationships.

        Parameters
        ----------
        cls : Class
            CLass inheriting from DataModel
        query : SQLAlchemy Query
            Query to add eager loading options to
        verbosity : int
            Level of detail

        Returns
        -------
        SQLAlchemy Query
            Query with eager loading options added

        """
        cls._init()
        return query.options(prop.qopt(prop.value(cls, "raw"))
                             for prop in cls._meta.props(verbosity, lambda prop: "ref" in prop.flags))

    @classmethod
    def optimized_query(cls, verbosity):
        """Generate an optimized query.

        See `optimize_query` for more information.
        """
        return cls.optimize_query(cls.query, verbosity)

    def fromdict(self, patches, *args, **kwargs):
        """Update object from dictionary representation.

        Parameters
        ----------
        patches : dict
            Dictionary containing updates.
        init : boolean, optional
            Whether the object is initialized (otherwise its an update operation). The default is False.

        Raises
        ------
        InvalidAttributeError
            An atrribute in the patch is not recognized
        MismatchROError
            An attribute that is not writable differs in the patch.

        Returns
        -------
        Instance
            The updated object (self)
        """
        self._init()
        reverse = self._meta.lookup
        for key, value in patches.items():
            if key not in reverse or reverse[key].proxy is not None:
                raise InvalidAttributeError("Unknown attribute '{}'".format(key))
            prop = reverse[key]
            if not prop.writable(self) and prop.value(self) != patches[key]:
                raise MismatchROError("Attribute '{}' is read only and does not match".format(key))
        for key, value in patches.items():
            if key not in reverse:
                continue
            prop = reverse[key]
            if not prop.writable(self):
                continue
            if "ref" not in prop.flags:
                setattr(self, prop.attr, value)
            else:
                attr = getattr(self, prop.attr)
                try:
                    Element = inspecc(getattr(type(self), prop.attr)).property.mapper.entity
                except Exception:
                    logger.warn("Failed to inspect attribute '{}' - ignored".format(prop.attr))
                    continue
                if prop.mask is not None and "managed" not in prop.flags:
                    setattr(self, prop.mask, value)
                elif isinstance(attr, dict) and isinstance(value, dict):
                    elements = {k: Element({prop.link: k, **(value[k] if prop.flat is None else {prop.flat: value[k]})},
                                           self, *args, **kwargs)
                                for k, v in value.items() if k not in attr}  # New elements
                    elements.update({k: a.fromdict(value[k] if prop.flat is None else {prop.flat: value[k]})
                                     for k, a in attr.items() if k in value})  # Updated elements
                    setattr(self, prop.attr, elements)
                elif _isCollection(attr) and _isCollection(value):
                    if "managed" in prop.flags:
                        current = {getattr(val, prop.link) for val in attr}
                        fID = prop.link
                        patch = {val[fID]: val for val in value if fID in val and val[fID] in current} if prop.flat is None else\
                                {val: val for val in value if val in current}
                        new = (val for val in value if fID not in val or val[fID] not in current) if prop.flat is None else\
                              (val for val in value if val not in current)
                        setattr(self, prop.attr,
                                [val.fromdict(patch[getattr(val, fID)], *args, **kwargs)
                                 for val in attr if getattr(val, fID) in patch] +
                                [Element(val, self, *args, **kwargs) for val in new])
                    else:
                        current = {getattr(val, prop.link) for val in attr}
                        requested = set(value)
                        common, new = requested & current, requested - current
                        setattr(self, prop.attr, [val for val in attr if getattr(val, prop.link) in common] +
                                                 [Element(newId, self) for newId in new])
                elif "managed" in prop.flags:
                    if value is None:
                        setattr(self, prop.attr, None)
                    elif attr is None:
                        setattr(self, prop.attr, Element(value, *args, **kwargs))
                    else:
                        attr.fromdict(value, *args, **kwargs)
                else:
                    try:
                        attr.fromdict(value, *args, **kwargs)
                    except InvalidAttributeError as err:
                        raise InvalidAttributeError("Cannot patch attribute '{}': {}".format(key, err.args[0])) from None
                    except MismatchROError as err:
                        raise MismatchROError("Cannot patch attribute '{}': {}".format(key, err.args[0])) from None
        return self

    @staticmethod
    def checkCreateParams(data):
        """Validate parameters for creation.

        If parameter validation fails, a descriptive error message should be returned.

        The data object may be modified to allow preprocessing of data.

        Parameters
        ----------
        data : dict
            Dictionary containing the data to create a new object from
        """
        pass

    @classmethod
    def autofilter(cls, query, args):
        """Apply valid filters to the query.

        Valid filters are determined by the `_filters_` class property. Every key in `args` that is a valid filter is added
        to the query.

        Parameters
        ----------
        cls : Class
            Class inheriting from DataModel
        query : Query
            SQLAlchemy Query
        args : dict
            Dictionary containing filters

        Returns
        -------
        Query
            Query with applied filters
        """
        cls._init()
        activeFilters = ((prop, tuple(prop.tf(v) for v in args[prop.key].split(",")))
                         for prop in cls._meta.filters if prop.key in args)
        for prop, values in activeFilters:
            if prop.proxy is not None:
                attr, query = prop.resolve(cls, query, True)
            else:
                attr = prop.value(cls, transform="unmask")
            if prop.filter == "range":
                query = query.filter(attr == values[0]) if len(values) == 1 else\
                        query.filter((attr >= values[0]) & (attr <= values[1]))
            elif prop.filter == "set":
                query = query.filter(or_(attr == v for v in values))
        return query

    @classmethod
    def autosort(cls, query, sorts):
        """Apply valid sort expressions to query.

        Valid sorts are determined by the `_sortables_` class property. Uses values stored in the "sort" key from args.
        Values can be given in the format of "column" or "coloumn,order", where order can be one of "asc" or "desc". If no
        order is specified, "asc" is used by default.
        If more than one sort value is given, all values are applied to the query in order given.

        Parameters
        ----------
        cls : Class
            Class inheriting from DataModel
        query : Query
            SQLAlchemy Query
        sorts : list
            List of sort expressions

        Returns
        -------
        Query
            Query with applied order by expresions
        """
        cls._init()
        for s in sorts:
            column, order = s.split(",", 1) if "," in s else (s, "asc")
            prop = cls._meta.lookup.get(column)
            if prop is None or "sort" not in prop.flags:
                continue
            if prop.target is None:
                column = prop.value(cls, "unmask")
                query = query.order_by(column.desc() if order == "desc" else column.asc())
            else:
                column, query = prop.resolve(cls, query)
                query = query.order_by(func.isnull(column), column.desc() if order == "desc" else column.asc())
        return query

    @classmethod
    def automatch(cls, query, expr, fields=None):
        """Add fuzzy matching to query."""
        cls._init()
        matchexpr = tuple("%"+substr+"%" for substr in expr.split())
        matchables = cls._meta.matchables if fields is None else (m for m in cls._meta.matchables if m.alias in fields)
        targets = []
        for prop in matchables:
            column, query = prop.resolve(cls, query)
            targets.append((prop, column))
        filters = [column.ilike(match) for match in matchexpr for prop, column in targets if prop.match == "default"] +\
                  [column == prop.tf(expr) for prop, column in targets if prop.match == "exact" and prop.tf(expr) is not None]
        query = query.filter(or_(filter for filter in filters))
        return query.reset_joinpoint()

    def matchvalues(self, fields=None):
        """Return iterator for values relevant for matching."""
        matchables = self._meta.matchables if fields is None else (m for m in self._meta.matchables if m.alias in fields)
        return (prop.value(self, "targetval") for prop in matchables)

    @classmethod
    def augment(cls, props: dict, kwargs: dict):
        """Add keyword arguments to prop dictionary.

        Only arguments that can be resolved to attributes are inserted.

        Parameters
        ----------
        props : dict
            Property dictionary to update
        kwargs : dict
            Keyword arguments dictionary
        """
        cls._init()
        props.update((key, value) for key, value in kwargs.items() if key in cls._meta.lookup)


def _addFlags(kwargs, flags):
    """Add flags to dictmapping entry."""
    kwargs["flags"] = ",".join((kwargs["flags"], flags)) if "flags" in kwargs else flags


def RefProp(attr, mask=None, target=None, **kwargs):
    """Create a refernce property."""
    _addFlags(kwargs, "ref")
    return DataModel.Prop(attr, mask=mask, target=target, **kwargs)


def Id(name="ID", **kwargs):
    """Create an ID property."""
    _addFlags(kwargs, "init,sort")
    return DataModel.Prop(name, filter="set", **kwargs)


def Text(name, **kwargs):
    """Create a name property."""
    _addFlags(kwargs, "sort,match")
    return DataModel.Prop(name, filter="range", **kwargs)


def Int(name, **kwargs):
    """Create a name property."""
    _addFlags(kwargs, "sort")
    return DataModel.Prop(name, filter=kwargs.pop("filter", "range"), **kwargs)


def Bool(attr, **kwargs):
    """Create a bool property."""
    _addFlags(kwargs, "sort")
    return DataModel.Prop(attr, func=bool, filter="set", arg_tf=_str2bool, **kwargs)


def BoolP(attr, **kwargs):
    """Create a bool property."""
    _addFlags(kwargs, "sort")
    return DataModel.Prop(attr, arg_tf=_str2bool, filter="set", **kwargs)


def Proxy(attr, proxy, **kwargs):
    """Create a proxy propery."""
    return DataModel.Prop(attr, target=attr, proxy=proxy, **kwargs)


def Date(attr, time=False, **kwargs):
    """Create a date attribute."""
    format = "%Y-%m-%d %H:%M:%S" if time else"%Y-%m-%d"
    _addFlags(kwargs, "sort")
    return DataModel.Prop(attr, func=lambda date: date.strftime(format) if date else None, filter="range", **kwargs)
