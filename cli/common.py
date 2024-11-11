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
            cls.stylemarker = re.compile("\x1b\\[[\\d]{1,2}m")

        def _cut(self, width):
            """Cut cell content to specified width.

            Has no effect if width is larger than cell content.
            If content is larger than width, the content is truncated, replacing the last char with an ellipsis,
            preserving any terminal style codes present.

            Parameters
            ----------
            width : int
                Maximum cell width

            Returns
            -------
            str
                Cell content, truncated if necessary
            """
            if self.width <= width:
                return self.data
            if width <= 1:
                return "…"
            markers = self.stylemarker.findall(self.data)
            if not markers:
                return self.data[:width-1]+"…"
            text = self.stylemarker.split(self.data)
            cutIdx = -1
            overshoot = self.width-width+1
            while overshoot > 0:
                if len(text[cutIdx]) < overshoot:
                    overshoot -= len(text[cutIdx])
                    text[cutIdx] = ""
                else:
                    text[cutIdx] = text[cutIdx][:-overshoot]+"…"
                    overshoot = 0
                cutIdx -= 1
            segments = [None]*(len(markers)+len(text))
            segments[::2] = text
            segments[1::2] = markers
            return "".join(segments)

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
            data = self._cut(width)
            pad = width-self.width
            data = cli.col(data, self.color, self.on_color, self.attrs)
            if self.align == "r":
                data = " "*pad+data
            elif self.align == "c":
                data = " "*(pad//2)+data+(" "*((pad+1)//2) if not last else "")
            elif not last:
                data += " "*pad
            return data

    FORMATS = ("csv", "json-flat", "json-kv", "json-object", "json-structured", "pretty")

    def __init__(self, data, header=None, colsep=None, empty=None):
        """Create table from data.

        If colsep is not specified, the default column separator is chosen by
        the output formatter ('  ' for pretty, ',' for csv).

        Parameters
        ----------
        data : [[any]]
            Matrix of contents
        header : [any], optional
            Table header. The default is None.
        colsep : str, optional
            Column separator. The default is None.
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
        self.columns = max(max(len(row) for row in data) if data else 0, len(head))
        self.colwidth = tuple(head[i].width if i < len(head) else 0 for i in range(self.columns))
        if self.data:
            for line in self.data:
                self.colwidth = tuple(max(self.colwidth[i], line[i].width if i < len(line) else 0)
                                      for i in range(self.columns))

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

    def _narrow(self):
        """Recalculate column width to fit table to terminal.

        If the terminal is wider than the table or terminal width cannot be determined, no changes to column width are made.
        Otherwise, columns are truncated, longest to shortest, until the table fits the terminal.

        Returns
        -------
        list[int]
            List of adjusted column widths
        """
        import shutil
        colsep = self.colsep or "  "
        sepWidth = len(colsep)*(self.columns-1)  # total width occupied by separators
        contentWidth = sum(self.colwidth)
        termWidth = shutil.get_terminal_size((0, 0)).columns
        if termWidth == 0 or contentWidth+sepWidth <= termWidth:
            return self.colwidth
        if termWidth <= sepWidth+self.columns:  # each column would be reduced to 1 anyway
            return tuple(1 for _ in range(self.columns))
        widthIdx = sorted(zip(self.colwidth, range(self.columns)), reverse=True)
        termWidth -= sepWidth
        if termWidth <= self.columns*widthIdx[-1][0]:  # smallest column width is still too wide
            colwidth = [termWidth//self.columns]*self.columns
        else:  # cut the longest columns until it fits
            narrowIdx = 1  # index in widthIdx up to which narrowing is performed
            while termWidth < contentWidth - sum(w[0]-widthIdx[narrowIdx][0] for w in widthIdx[0:narrowIdx]):
                narrowIdx += 1
            narrowedWidth = (termWidth-sum(w[0] for w in widthIdx[narrowIdx:])) // narrowIdx
            colwidth = [min(w, narrowedWidth) for w in self.colwidth]
        for i in range(termWidth-sum(colwidth)):  # number of columns that can be wider by 1 char
            colwidth[widthIdx[i][1]] += 1
        return colwidth

    def printline(self, cli, line, colwidth):
        """Print a single row of data.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality
        line : [Styled]
            List of cells to print
        """
        colsep = self.colsep or "  "
        cli.print(colsep.join(line[i].print(cli, colwidth[i], i == self.columns-1) for i in range(len(line))))

    def print(self, cli):
        """Print the table.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality.
        """
        if not self.data and self.empty:
            cli.print(self.empty)
            return
        colwidth = self._narrow()
        if self.header:
            self.printline(cli, self.header, colwidth)
        if self.data:
            for line in self.data:
                self.printline(cli, line, colwidth)

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
        writer = csv.DictWriter(cli.stdout, fieldnames=header, delimiter=self.colsep or ",")
        if self.header:
            writer.writeheader()
        if not self.data:
            return
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
            return
        header = [cell.raw for cell in self.header] if self.header else [str(i) for i in range(len(self.data[0]))]
        data = [{name: value.raw for name, value in zip(header, row)} for row in self.data] if structured else\
               [[cell.raw for cell in row] for row in self.data]
        cli.print(json.dumps(data, default=lambda x: str(x), separators=(",", ":")))

    def jsonObject(self, cli, full):
        """Create single JSON object with the first column as key

        If full is True, the remaining columns are packed into an object, (like json-structured),
        otherwise only the second column is used as value and any additional columns are ignored.

        Parameters
        ----------
        cli : Cli
            Cli providing printing functionality
        full : bool
            Whether to provide value as object
        """
        import json

        def getV(row):
            return None if len(row) < 2 else row[1].raw

        def getO(row):
            return {name.raw: value.raw for name, value in zip(self.header[1:], row[1:])}

        if not self.data:
            cli.print("{}")
            return
        mkValue = getO if full else getV
        data = {str(row[0].raw): mkValue(row) for row in self.data}
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
        elif format in ("json-kv", "json-object"):
            self.jsonObject(cli, format == "json-object")
        else:
            self.print(cli)
