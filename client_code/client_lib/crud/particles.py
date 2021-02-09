import anvil.users

# MIT License
#
# Copyright (c) 2020 Owen Campbell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# This software is published at https://github.com/meatballs/anvil-orm
import sys

import anvil.server
import anvil.users

__version__ = "0.1.17"


class Attribute:
    """A class to represent an attribute of a model object class.
    Attributes are persisted as columns on the class's relevant data table
    """

    def __init__(self, required=True, default=None, is_uid=False):
        self.required = required
        self.default = default
        self.is_uid = is_uid


class AttributeValue:
    """A class to represent the instance value of an attribute."""

    def __init__(self, name, value, title=None):
        self.name = name
        self.value = value
        self.title = title or name.title()

    def to_dict(self):
        return {"name": self.name, "value": self.value, "title": self.title}


class Relationship:
    """A class to represent a relationship between two model object classes.
    These are persisted as data tables linked columns.
    """

    def __init__(
        self, class_name, required=True, with_many=False, cross_reference=None
    ):
        self.class_name = class_name
        self.required = required
        self.default = None
        if with_many:
            self.default = []
        self.with_many = with_many
        self.cross_reference = cross_reference

    @property
    def cls(self):
        return getattr(sys.modules[self.__module__], self.class_name)


class ModelSearchResultsIterator:
    """A paging iterator over the results of a search cached on the server"""

    def __init__(self, class_name, module_name, rows_id, page_length, max_depth=None):
        self.class_name = class_name
        self.module_name = module_name
        self.rows_id = rows_id
        self.page_length = page_length
        self.next_page = 0
        self.is_last_page = False
        self.max_depth = max_depth
        self.iterator = iter([])

    def __next__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            if self.is_last_page:
                raise
            results, self.is_last_page = anvil.server.call(
                "fetch_objects",
                self.class_name,
                self.module_name,
                self.rows_id,
                self.next_page,
                self.page_length,
                self.max_depth,
            )
            self.iterator = iter(results)
            self.next_page += 1
            return self.__next__()


@anvil.server.serializable_type
class ModelSearchResults:
    """A class to provide lazy loading of search results"""

    def __init__(
        self, class_name, module_name, rows_id, page_length, max_depth, length
    ):
        self.class_name = class_name
        self.module_name = module_name
        self.rows_id = rows_id
        self.page_length = page_length
        self.max_depth = max_depth
        self._length = length

    def __len__(self):
        return self._length

    def __iter__(self):
        return ModelSearchResultsIterator(
            self.class_name,
            self.module_name,
            self.rows_id,
            self.page_length,
            self.max_depth,
        )


def attribute_value(self, name, title=None):
    """A factory function to generate AttributeValue instances"""
    value = getattr(self, name, None)
    return AttributeValue(name=name, value=value, title=title)


def _constructor(attributes, relationships):
    """A function to return the __init__ function for the eventual model class"""
    # We're just merging dicts here but skulpt doesn't support the ** operator
    members = attributes.copy()
    members.update(relationships)

    def init(self, **kwargs):
        self.uid = kwargs.pop("uid", None)

        # Check that we've received arguments for all required members
        required_args = [name for name, member in members.items() if member.required]
        for name in required_args:
            if name not in kwargs:
                raise ValueError(f"No argument provided for required {name}")

        # Check that the arguments received match the model and set the instance attributes if so
        for name, value in kwargs.items():
            if name not in members:
                raise ValueError(
                    f"{type(self).__name__}.__init__ received an invalid argument: '{name}'"
                )
            else:
                setattr(self, name, value)

        # Set the default instance attributes for optional members missing from the arguments
        for name, member in members.items():
            if name not in kwargs:
                setattr(self, name, member.default)

    return init


def _equivalence(self, other):
    """A function to assert equivalence between client and server side copies of model
    instances"""
    return type(self) == type(other) and self.uid == other.uid


def _getitem(self, key):
    """A function to provide dict like indexing"""
    return getattr(self, key, None)


def _setitem(self, key, value):
    setattr(self, key, value)


def _from_row(unique_identifier, attributes, relationships):
    """A factory function to generate a model instance from a data tables row."""

    @classmethod
    def instance_from_row(cls, row, cross_references=None, max_depth=None, depth=0):
        if anvil.server.context.type == "client":
            raise TypeError(
                "_from_row is a server side function and cannot be called from client code"
            )

        if row is None:
            return None

        if cross_references is None:
            cross_references = set()

        attrs = dict(row)
        attrs = {
            key: value
            for key, value in attrs.items()
            if key in attributes or key == "uid"
        }
        if "uid" not in attrs:
            attrs["uid"] = attrs[unique_identifier]

        for name, relationship in relationships.items():
            xref = None
            attrs[name] = None

            if relationship.cross_reference is not None:
                xref = (cls.__name__, attrs["uid"], name)

            if xref is not None and xref in cross_references:
                break

            if xref is not None:
                cross_references.add(xref)

            if max_depth is None or depth < max_depth:
                if not relationship.with_many:
                    attrs[name] = relationship.cls._from_row(
                        row[name], cross_references, max_depth, depth + 1
                    )
                else:
                    attrs[name] = []
                    if row[name]:
                        attrs[name] = [
                            relationship.cls._from_row(
                                member, cross_references, max_depth, depth + 1
                            )
                            for member in row[name]
                        ]

        return cls(**attrs)

    return instance_from_row


@classmethod
def _get(cls, uid, max_depth=None):
    """Provide a method to fetch an object from the server"""
    return anvil.server.call("get_object", cls.__name__, cls.__module__, uid, max_depth)


@classmethod
def _search(
    cls,
    page_length=100,
    max_depth=None,
    server_function=None,
    with_class_name=True,
    **search_args,
):
    """Provides a method to retrieve a set of model instances from the server"""
    _server_function = server_function or "basic_search"
    results = anvil.server.call(
        _server_function,
        cls.__name__,
        cls.__module__,
        page_length,
        max_depth,
        with_class_name,
        **search_args,
    )
    return results


def _save(self):
    """Provides a method to persist an instance to the database"""
    return anvil.server.call("save_object", self)


def _delete(self):
    """Provides a method to delete an instance from the database"""
    anvil.server.call("delete_object", self)


def model_type(cls):
    """A decorator to provide a usable model class"""
    class_members = {
        key: value for key, value in cls.__dict__.items() if not key.startswith("__")
    }
    attributes = {
        key: value
        for key, value in class_members.items()
        if isinstance(value, Attribute)
    }
    unique_identifier = "uid"
    unique_identifiers = [key for key, value in attributes.items() if value.is_uid]
    if unique_identifiers:
        if len(unique_identifiers) > 1:
            raise AttributeError("Multiple unique identifiers defined")
        else:
            unique_identifier = unique_identifiers[0]

    relationships = {
        key: value
        for key, value in class_members.items()
        if isinstance(value, Relationship)
    }
    methods = {key: value for key, value in class_members.items() if callable(value)}
    class_attributes = {
        key: value
        for key, value in class_members.items()
        if not isinstance(value, (Attribute, Relationship))
    }

    for relationship in relationships.values():
        relationship.__module__ = cls.__module__

    members = {
        "__module__": cls.__module__,
        "__init__": _constructor(attributes, relationships),
        "__eq__": _equivalence,
        "__getitem__": _getitem,
        "__setitem__": _setitem,
        "_attributes": attributes,
        "_relationships": relationships,
        "_from_row": _from_row(unique_identifier, attributes, relationships),
        "_unique_identifier": unique_identifier,
        "update_capability": None,
        "delete_capability": None,
        "search_capability": None,
        "attribute_value": attribute_value,
        "get": _get,
        "search": _search,
        "save": _save,
        "expunge": _delete,
        "delete": _delete,
    }
    members.update(methods)
    members.update(class_attributes)

    model = type(cls.__name__, (object,), members)
    return anvil.server.portable_class(model)
