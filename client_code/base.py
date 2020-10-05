#    Anvil Model
#    Copyright 2020 Owen Campbell
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#   This program is published at https://github.com/meatballs/anvil-navigation
import anvil.server

__version__ = "0.1.0"


class Relationship:
    def __init__(self, name, cls):
        self.name = name
        self.cls = cls


def _constructor(attributes, relationships):
  
    def init(self, **kwargs):
        self.id = None
        valid_keys = attributes + [r.name for r in relationships]
        for key, value in kwargs.items():
            if key not in valid_keys:
                raise ValueError(f"{type(self).__name__}.__init__ received an invalid argument: '{key}'")
            else:
                setattr(self, key, value)
        
    return init


@classmethod
def _from_row(cls, row):
    attrs = dict(row)
    id = attrs.pop("id")
    for column in cls.relationships:
        attrs[column.name] = column.cls._from_row(row[column.name])
    result = cls(**attrs)
    result.id = id
    return result


@classmethod
def _get(cls, id):
    return anvil.server.call("get_object", cls.__name__, id)


@classmethod
def _list(cls, **filter_args):
    """Returns an iterator of data table Row objects"""
    return anvil.server.call("list_objects", cls.__name__, **filter_args)

  
def _save(self):
    anvil.server.call("save_object", self)
 
    
def model(cls):
    """A decorator to provide a usable model class"""
    attributes = getattr(cls, "attributes", [])
    relationships = getattr(cls, "relationships", [])
    model = type(cls.__name__, (object, ), {
        "attributes": attributes,
        "relationships": relationships,
        "__module__": cls.__module__,
        "__init__": _constructor(attributes, relationships),
        "_from_row": _from_row,
        "get": _get,
        "list": _list,
        "save": _save
    })              
    return anvil.server.serializable_type(model)