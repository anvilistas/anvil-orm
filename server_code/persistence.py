import anvil.users

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
import functools
import re
from importlib import import_module
from uuid import uuid4

import anvil.server
from anvil.server import Capability
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

from .particles import ModelSearchResults

__version__ = "0.1.0"
camel_pattern = re.compile(r"(?<!^)(?=[A-Z])")

anvil.server.call("anvil.private.enable_profiling")


def caching_query(search_function):
    """A decorator to stash the results of a data tables search."""

    @functools.wraps(search_function)
    def wrapper(class_name, module_name, page_length, with_class_name, **search_args):
        if with_class_name:
            search_args["class_name"] = class_name
        rows_id = uuid4().hex
        rows = search_function(**search_args)
        anvil.server.session[rows_id] = rows
        return ModelSearchResults(class_name, module_name, rows_id, page_length)

    return wrapper


def _get_sequence_value(name):
    """Get and increment the next value for a given sequence"""
    row = app_tables.sequence.get(name=name) or app_tables.sequence.add_row(
        name=name, next=1
    )
    result = row["next"]
    row["next"] += 1
    return result


def _camel_to_snake(name):
    """Convert a CamelCase string to snake_case"""
    return camel_pattern.sub("_", name).lower()


def get_table(class_name):
    """Return the data tables table for the given class name"""
    table_name = _camel_to_snake(class_name)
    return getattr(app_tables, table_name)


def _get_row(class_name, uid):
    """Return the data tables row for for a given object instance"""
    table = getattr(app_tables, _camel_to_snake(class_name))
    return table.get(uid=uid)


def _search_rows(class_name, uids):
    """Return the data tables rows for a given list of object instances"""
    return get_table(class_name).search(uid=q.any_of(*uids))


@anvil.server.callable
def get_object(class_name, module_name, uid):
    """Create a model object instance from the relevant data table row"""
    if anvil.server.call("has_read_permission", class_name, uid):
        module = import_module(module_name)
        cls = getattr(module, class_name)
        instance = cls._from_row(_get_row(class_name, uid))
        if anvil.server.call("has_update_permission", class_name, uid):
            instance.update_capability = Capability([class_name, uid])
        if anvil.server.call("has_delete_permission", class_name, uid):
            instance.delete_capability = Capability([class_name, uid])
        return instance


@anvil.server.callable
def fetch_objects(class_name, module_name, rows_id, page, page_length):
    """Return a list of object instances from a cached data tables search"""
    module = import_module(module_name)
    cls = getattr(module, class_name)
    rows = anvil.server.session.get(rows_id, [])
    start = page * page_length
    end = (page + 1) * page_length
    is_last_page = end >= len(rows)
    if is_last_page:
        del anvil.server.session[rows_id]
    return [cls._from_row(row) for row in rows[start:end]], is_last_page


@anvil.server.callable
@caching_query
def basic_search(class_name, **search_args):
    """Perform a data tables search against the relevant table for the given class"""
    return get_table(class_name).search(**search_args)


@anvil.server.callable
def save_object(instance):
    """Persist an instance to the database by adding or updating a row"""
    class_name = type(instance).__name__
    table_name = _camel_to_snake(class_name)
    table = get_table(class_name)

    attributes = {
        name: getattr(instance, name)
        for name, attribute in instance._attributes.items()
    }
    single_relationships = {
        name: _get_row(relationship.cls.__name__, getattr(instance, name).uid)
        for name, relationship in instance._relationships.items()
        if not relationship.with_many and getattr(instance, name) is not None
    }
    multi_relationships = {
        name: list(
            _search_rows(
                relationship.cls.__name__,
                [
                    member.uid
                    for member in getattr(instance, name)
                    if member is not None
                ],
            )
        )
        for name, relationship in instance._relationships.items()
        if relationship.with_many
    }

    members = {**attributes, **single_relationships, **multi_relationships}
    cross_references = [
        {"name": name, "relationship": relationship}
        for name, relationship in instance._relationships.items()
        if relationship.cross_reference is not None
    ]

    has_permission = False
    if instance.uid is not None:
        if getattr(instance, "update_capability") is not None:
            Capability.require(
                instance.update_capability, [class_name, instance.uid]
            )
            has_permission = True
            row = table.get(uid=instance.uid)
            row.update(**members)
        else:
            raise ValueError("You do not have permission to update this object")
    else:
        if anvil.server.call("has_create_permission", class_name):
            has_permission = True
            uid = _get_sequence_value(table_name)
            instance.uid = uid
            row = table.add_row(uid=uid, **members)
            if anvil.server.call("has_update_permission", class_name, uid):
                instance.update_capability = Capability([class_name, uid])
            if anvil.server.call("has_delete_permission", class_name, uid):
                instance.delete_capability = Capability([class_name, uid])
        else:
            raise ValueError("You do not have permission to save this object")

    if has_permission:
        # Very simple cross reference update
        for xref in cross_references:

            # We only update the 'many' side of a cross reference
            if not xref["relationship"].with_many:
                xref_row = single_relationships[xref["name"]]
                column_name = xref["relationship"].cross_reference

                # And we simply ensure that the 'one' side is included in the 'many' side.
                # We don't do any cleanup of possibly redundant entries on the 'many' side.
                if row not in xref_row[column_name]:
                    xref_row[column_name] += [row]

    return instance


@anvil.server.callable
def delete_object(instance):
    """Delete the data tables row for the given model instance"""
    class_name = type(instance).__name__
    Capability.require(instance.delete_capability, [class_name, instance.uid])
    table = get_table(type(instance).__name__)
    table.get(uid=instance.uid).delete()
