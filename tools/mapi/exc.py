# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 15:00:34 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

class GenericException(BaseException):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, ", ".join((", ".join(repr(v) for v in self.args),
                                                                   ", ".join("{}={}".format(key, value)
                                                                             for key, value in self.kwargs.items()))))

class TransmissionError(GenericException):
    pass

class MapiError(GenericException):
    pass
