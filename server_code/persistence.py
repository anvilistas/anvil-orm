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
import re

import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

from . import model

camel_pattern = re.compile(r"(?<!^)(?=[A-Z])")


def get_sequence_value(sequence_id):
    row = app_tables.sequence.get(id=sequence_id) or app_tables.sequence.add_row(
        id=sequence_id, next=1
    )
    result = row["next"]
    row["next"] += 1
    return result


def camel_to_snake(name):
    return camel_pattern.sub("_", name).lower()


def get_row(class_name, id):
    table = getattr(app_tables, camel_to_snake(class_name))
    return table.get(id=id)


@anvil.server.callable
def get_object(class_name, id):
    cls = getattr(model, class_name)
    return cls._from_row(get_row(class_name, id))


@anvil.server.callable
def list_objects(class_name, **filter_args):
    cls = getattr(model, class_name)
    table = getattr(app_tables, camel_to_snake(class_name))
    rows = table.search(**filter_args)
    return [cls._from_row(row) for row in rows]


@anvil.server.callable
def save_object(instance):
    table_name = camel_to_snake(type(instance).__name__)
    table = getattr(app_tables, table_name)

    attributes = {
        name: getattr(instance, name)
        for name, attribute in instance._attributes.items()
    }
    relationships = {
        name: get_row(relationship.cls.__name__, getattr(instance, name).id)
        for name, relationship in instance._relationships.items()
    }

    if instance.id is None:
        with tables.Transaction():
            id = get_sequence_value(table_name)
            table.add_row(id=id, **attributes, **relationships)
    else:
        row = table.get(id=instance.id)
        row.update(**attributes, **relationships)
