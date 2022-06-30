# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH


def domainFilter(domainSpec, *filters):
    from orm.domains import Domains
    from sqlalchemy import and_
    return and_(True if domainSpec is None else
                Domains.ID == domainSpec if domainSpec.isdigit() else
                Domains.domainname.ilike(domainSpec+"%"), *filters)


def domainCandidates(domainSpec, *filters):
    from orm.domains import Domains
    return Domains.query.filter(domainFilter(domainSpec, *filters))


def userFilter(userSpec, *filters):
    from orm.users import Users
    from sqlalchemy import and_
    return and_(True if userSpec is None else
                Users.ID == userSpec if userSpec.isdigit() else
                Users.username.ilike(userSpec+"%"), *filters)


def userCandidates(userSpec, *filters):
    from orm.users import Users
    return Users.query.filter(userFilter(userSpec, *filters))


def userspecAutocomp(prefix, **kwargs):
    from . import Cli
    if Cli.rlAvail:
        from orm.users import Users
        return (user.username for user in userCandidates(prefix).with_entities(Users.username))
    else:
        return ()


class NotFound(dict):
    pass


def getKey(c, keyspec):
    if keyspec:
        for key in keyspec:
            c = c.get(key, NotFound()) if key else c
    return c


def proptagCompleter(prefix, addSuffix="", **kwargs):
    from tools.constants import PropTags
    PropTags.lookup(None)
    c = []
    if prefix == "" or prefix[0].islower():
        c += [tag.lower()+addSuffix for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0].isupper():
        c += [tag.upper()+addSuffix for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].isupper()):
        c += ["0x{:08x}{}".format(value, addSuffix) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].islower()):
        c += ["0x{:08X}{}".format(value, addSuffix) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix.isnumeric():
        c += [str(value)+addSuffix for value in PropTags._lookup.keys() if isinstance(value, int)]
    return c


class Table:
    """Helper class for pretty printing of tables."""
    class Styled:
        """Class to manage style information of a table cell"""
        stylemarker = None

        def __init__(self, data, align='a', color=None, on_color=None, attrs=[]):
            """Associate style information with data.

            Parameters
            ----------
            data : any
                Data to display
            align : str, optional
                Alignment, can be one of 'a' (auto), 'c' (center), 'l' (left) or 'r' (right).
                Automatic alignment chooses 'r' for numbers and 'l' for everything else.
                The default is 'a'.
            color : str, optional
                Color to apply to the text. The default is None.
            on_color : str, optional
                Background color of the text. The default is None.
            attrs : [str], optional
                List of additional style attributes. The default is [].
            """
            self._init()
            self.align = align if align != "a" else "r" if type(data) in (int, float) else "l"
            self.raw = data
            self.data = str(data).expandtabs()
            self.color = color
            self.on_color = None
            self.attrs = attrs
            self.width = self._width()

        @classmethod
        def _init(cls):
            """Initialize stylemarker re."""
            if cls.stylemarker is not None:
                return
            import re
            cls.stylemarker = cls.stylemarker or re.compile("\x1b\\[[\\d]{1,2}m")

        def _width(self):
            """Return effective width of the string (without style markers and expanded tabs)."""
            return len(self.stylemarker.sub("", self.data).expandtabs())

        def print(self, cli, width, last):
            """Print styled data into string.

            Parameters
            ----------
            cli : Cli
                Cli providing style formatting.
            width : int
                Width of the cell to fill
            last : bool
                Whether this is the last cell of the row

            Returns
            -------
            data : str
                Cell content
            """
            pad = width-self.width
            data = cli.col(self.data, self.color, self.on_color, self.attrs)
            if self.align == "r":
                data = " "*pad+data
            elif self.align == "c":
                data = " "*(pad//2)+data+(" "*((pad+1)//2) if not last else "")
            elif not last:
                data += " "*pad
            return data

    def __init__(self, data, header=None, colsep="  ", empty=None):
        """Create table from data.

        Parameters
        ----------
        data : [[any]]
            Matrix of contents
        header : [any], optional
            Table header. The default is None.
        colsep : str, optional
            Column separator. The default is "  ".
        empty : str, optional
            Text to display when table does not contain data. The default is None.
        """
        self.data = [[self._styled(cell) for cell in row] for row in data] if data else None
        self.header = [self._styled(col, "l", attrs=["underline"]) for col in header] if header else None
        self.empty = empty
        if not (header or data):
            return
        self.colsep = colsep
        head = self.header or self.data[0]
        self.columns = len(head)
        self.colwidth = tuple(col.width for col in head)
        if self.data:
            for line in self.data:
                self.colwidth = tuple(max(self.colwidth[i], line[i].width) for i in range(self.columns))

    @classmethod
    def _styled(cls, data, *args, **kwargs):
        """Augment data with style information.

        Parameters
        ----------
        data : any
            Data to wrap
        *args : any
            Arguments passed on to Styled constructor
        **kwargs : any
            Keyword arguments passed on to Styled constructor.

        Returns
        -------
        Styled
            Data with style information
        """
        return data if isinstance(data, cls.Styled) else cls.Styled(data, *args, **kwargs)

    def printline(self, cli, line):
        """Print a single row of data.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality
        line : [Styled]
            List of cells to print
        """
        cli.print(self.colsep.join(line[i].print(cli, self.colwidth[i], i == self.columns-1) for i in range(self.columns)))

    def print(self, cli):
        """Print the table.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality.
        """
        if not (self.header or self.data) and self.empty:
            cli.print(self.empty)
        if self.header:
            self.printline(cli, self.header)
        if self.data:
            for line in self.data:
                self.printline(cli, line)

    def csv(self, cli):
        """Output table as csv.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality.
        """
        import csv
        if not (self.header or self.data):
            return
        header = [cell.raw for cell in self.header] if self.header else [str(i) for i in range(len(self.data[0]))]
        writer = csv.DictWriter(cli.stdout, fieldnames=header, delimiter=self.colsep[0] or ",")
        if self.header:
            writer.writeheader()
        for row in self.data:
            writer.writerow({name: value.raw for name, value in zip(header, row)})

    def json(self, cli, structured):
        """Output table as JSON

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality.
        structured : bool
            Whether to output data as structured JSON or array-of-arrays
        """
        import json
        if not self.data:
            cli.print("[]")
        header = [cell.raw for cell in self.header] if self.header else [str(i) for i in range(len(self.data[0]))]
        data = [{name: value.raw for name, value in zip(header, row)} for row in self.data] if structured else\
               [[cell.raw for cell in row] for row in self.data]
        cli.print(json.dumps(data, default=lambda x: str(x), separators=(",", ":")))

    def dump(self, cli, format):
        """Dump table contents in specified format

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality.
        format : str
            Output format. Can be one of `csv`, `json-flat` and `json-structured`. Everything else will print the table.
        """
        if format == "csv":
            self.csv(cli)
        elif format in ("json-flat", "json-structured"):
            self.json(cli, format == "json-structured")
        else:
            self.print(cli)
