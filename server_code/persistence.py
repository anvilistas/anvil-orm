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
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

from .particles import ModelSearchResults

__version__ = "0.1.0"
camel_pattern = re.compile(r"(?<!^)(?=[A-Z])")


def caching_query(func):
    @functools.wraps(func)
    def wrapper(module_name, page_length, **search_args):
        rows_id = uuid4().hex
        rows = func(**search_args)
        anvil.server.session[rows_id] = rows
        return ModelSearchResults(
            search_args["class_name"], module_name, rows_id, page_length
        )

    return wrapper


def get_sequence_value(sequence_id):
    row = app_tables.sequence.get(id=sequence_id) or app_tables.sequence.add_row(
        id=sequence_id, next=1
    )
    result = row["next"]
    row["next"] += 1
    return result


def camel_to_snake(name):
    return camel_pattern.sub("_", name).lower()


def get_table(class_name):
    table_name = camel_to_snake(class_name)
    return getattr(app_tables, table_name)


def get_row(class_name, id):
    table = getattr(app_tables, camel_to_snake(class_name))
    return table.get(id=id)


def search_rows(class_name, ids):
    return get_table(class_name).search(id=q.any_of(*ids))


@anvil.server.callable
def get_object(class_name, module_name, id):
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls._from_row(get_row(class_name, id))


@anvil.server.callable
def fetch_objects(class_name, module_name, rows_id, page, page_length):
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
def basic_search(**search_args):
    table = get_table(search_args.pop("class_name"))
    return table.search(**search_args)


@anvil.server.callable
def save_object(instance):
    table = get_table(type(instance).__name__)

    attributes = {
        name: getattr(instance, name)
        for name, attribute in instance._attributes.items()
    }
    single_relationships = {
        name: get_row(relationship.cls.__name__, getattr(instance, name).id)
        for name, relationship in instance._relationships.items()
        if not relationship.with_many
    }
    multi_relationships = {
        name: list(
            search_rows(
                relationship.cls.__name__,
                [member.id for member in getattr(instance, name)],
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

    with tables.Transaction():
        if instance.id is None:
            id = get_sequence_value(table_name)
            row = table.add_row(id=id, **members)
        else:
            row = table.get(id=instance.id)
            row.update(**members)

        # Very simple cross reference update
        for xref in cross_references:

            # We only update the 'many' side of a cross reference
            if not xref["relationship"].with_many:
                xref_row = single_relationships[xref["name"]]
                xref_column = xref_row[xref["relationship"].cross_reference]

                # And we simply ensure that the 'one' side is included in the 'many' side.
                # We don't do any cleanup of possibly redundant entries on the 'many' side.
                if row not in xref_column:
                    xref_column += row
