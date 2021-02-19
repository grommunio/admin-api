# -*- coding: utf-8 -*-

import re

class ClassFilter:
    class Condition:
        sqlops = {"eq": "=",
                  "ne": "<>",
                  "lt": "<",
                  "le": "<=",
                  "gt": ">",
                  "ge": ">=",
                  "li": "RLIKE",
                  "ex": "IS NOT NULL",
                  "nx": "IS NULL"}

        unary = {"ex", "nx"}

        columns = {"username"}

        def __init__(self, data):
            if "p" in data and "c" in data:
                raise ValueError("Filter cannot be column and property filter at the same time")
            self.type = "p" if "p" in data else "c" if "c" in data else None
            if self.type is None:
                raise ValueError("Cannot deduct type (missing 'c' or 'p' property)")
            self.op = data.get("op")
            self.target = data[self.type]
            self.value = None if self.op in self.unary else data.get("val")
            if self.op not in self.sqlops:
                raise ValueError("Invalid operator '{}'".format(self.op))
            if self.type == "c" and self.target not in self.columns:
                raise ValueError("Invalid column '{}'".format(self.target))
            if self.op not in self.unary and ("val" not in data or type(data["val"]) != str):
                raise ValueError("Invalid filter value (must be string)")

        def sql(self, alias):
            value = None if self.value is None else "'{}'".format(self.value if self.op == "li" else self.value)
            if self.type == "c":
                return "{}.{} {} {}".format(alias, self.target, self.sqlops[self.op], "" if self.op in self.unary else value)
            elif self.type == "p":
                return "{}.propval_str {} {}".format(alias, self.sqlops[self.op], "" if self.op in self.unary else value)

    def __init__(self, data):
        if isinstance(data, str):
            import json
            data = json.loads(data)
        self.expressions = [[self.Condition(entry) for entry in conj] for conj in data]
        if len(self.expressions) == 0 or min(len(disj) for disj in self.expressions) == 0:
            raise ValueError("Cannot use empty filter expression")

    def sql(self, columns):
        tags = {expr.target for conj in self.expressions for expr in conj if expr.type == "p"}
        joins = " ".join("LEFT JOIN user_properties AS up_{tag} on u.id=up_{tag}.user_id AND up_{tag}.proptag='{tag}'"
                          .format(tag=tag) for tag in tags)
        filters = ") AND (".join(" OR ".join(expr.sql("u" if expr.type == "c" else "up_"+str(expr.target)) for expr in conj)
                               for conj in self.expressions)
        return "SELECT {} FROM users AS u {} WHERE ({})".format(columns, joins, filters)
