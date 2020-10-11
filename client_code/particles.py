# MIT License

# Copyright (c) 2020 Owen Campbell

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# This software is published at https://github.com/meatballs/anvil-model
import sys

import anvil.server

__version__ = "0.1.0"


class Attribute:
    def __init__(self, required=True, default=None):
        self.required = required
        self.default = default


class AttributeValue:
    def __init__(self, name, value, title=None):
        self.name = name
        self.value = value
        self.title = title or name.title()

    def to_dict(self):
        return {"name": self.name, "value": self.value, "title": self.title}


class Relationship:
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
    def __init__(self, class_name, module_name, rows_id, page_length):
        self.class_name = class_name
        self.module_name = module_name
        self.rows_id = rows_id
        self.page_length = page_length
        self.next_page = 0
        self.is_last_page = False
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
            )
            self.iterator = iter(results)
            self.next_page += 1
            return self.__next__()


@anvil.server.serializable_type
class ModelSearchResults:
    def __init__(self, class_name, module_name, rows_id, page_length):
        self.class_name = class_name
        self.module_name = module_name
        self.rows_id = rows_id
        self.page_length = page_length

    def __iter__(self):
        return ModelSearchResultsIterator(
            self.class_name, self.module_name, self.rows_id, self.page_length
        )


def attribute_value(self, name, title=None, datetime_format=None):
    value = getattr(self, name, None)
    if datetime_format is not None and value is not None:
        value = value.strftime(datetime_format)
    return AttributeValue(name=name, value=value, title=title)


def _constructor(attributes, relationships):
    # We're just merging dicts here but skulpt doesn't support the ** operator
    members = attributes.copy()
    members.update(relationships)

    def init(self, **kwargs):
        self.id = kwargs.pop("id", None)

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


def equivalence(self, other):
    return self.id == other.id


def _from_row(relationships):
    @classmethod
    def instance_from_row(cls, row, cross_references=None):
        if cross_references is None:
            cross_references = set()

        if anvil.server.context.type == "client":
            attrs = dict(list(row))
        else:
            attrs = dict(row)

        id = attrs.pop("id")

        for name, relationship in relationships.items():
            xref = None
            if relationship.cross_reference is not None:
                xref = (cls.__name__, id, name)

            if xref is not None and xref in cross_references:
                break

            if xref is not None:
                cross_references.add(xref)

            if not relationship.with_many:
                attrs[name] = relationship.cls._from_row(row[name], cross_references)
            else:
                attrs[name] = [
                    relationship.cls._from_row(member, cross_references)
                    for member in row[name]
                ]

        result = cls(**attrs)
        result.id = id
        return result

    return instance_from_row


@classmethod
def _get(cls, id):
    return anvil.server.call("get_object", cls.__name__, cls.__module__, id)


@classmethod
def search(cls, page_length=100, server_function=None, **search_args):
    _server_function = server_function or "basic_search"
    return anvil.server.call(
        _server_function, cls.__name__, cls.__module__, page_length, **search_args
    )


def _save(self):
    anvil.server.call("save_object", self)


def model_type(cls):
    """A decorator to provide a usable model class"""

    # Skuplt doesn't appear to like using the __dict__ attribute of the cls, so we
    # have to use dir and getattr instead
    attributes = {
        key: getattr(cls, key)
        for key in dir(cls)
        if isinstance(getattr(cls, key), Attribute)
    }
    relationships = {
        key: getattr(cls, key)
        for key in dir(cls)
        if isinstance(getattr(cls, key), Relationship)
    }
    methods = {
        key: getattr(cls, key)
        for key in dir(cls)
        if callable(getattr(cls, key)) and not key.startswith("__")
    }
    class_attributes = {
        key: getattr(cls, key)
        for key in dir(cls)
        if not key.startswith("__")
        and not isinstance(getattr(cls, key), (Attribute, Relationship))
    }

    for relationship in relationships.values():
        relationship.__module__ = cls.__module__

    members = {
        "__module__": cls.__module__,
        "__init__": _constructor(attributes, relationships),
        "__eq__": equivalence,
        "_attributes": attributes,
        "_relationships": relationships,
        "_from_row": _from_row(relationships),
        "attribute_value": attribute_value,
        "get": _get,
        "search": search,
        "save": _save,
    }
    members.update(methods)
    members.update(class_attributes)

    model = type(cls.__name__, (object,), members)
    return anvil.server.serializable_type(model)
