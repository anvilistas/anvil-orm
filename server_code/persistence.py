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
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

from . import model

__version__ = "0.1.0"

def get_sequence_value(sequence_id):
    row = app_tables.sequence.get(id=sequence_id) or app_tables.sequence.add_row(id=sequence_id, next=1)
    result = row["next"]
    row["next"] += 1
    return result


def get_row(class_name, id):
    table = getattr(app_tables, class_name.lower())
    return table.get(id=id)

    
@anvil.server.callable
def get_object(class_name, id):
    cls = getattr(model, class_name)
    return cls._from_row(get_row(class_name, id))
  
  
@anvil.server.callable
def list_objects(class_name, **filter_args):
    cls = getattr(model, class_name)
    table = getattr(app_tables, class_name.lower())
    return table.search(**filter_args)
      
      
@anvil.server.callable
def save_object(instance):
      table_name = type(instance).__name__.lower()
      table = getattr(app_tables, table_name)

      attributes = {attribute: getattr(instance, attribute) for attribute in instance.attributes}
      relationships = {
          relationship.name: get_row(relationship.cls.__name__, getattr(instance, relationship.name).id)
          for relationship in instance.relationships
      }  
      
      if instance.id is None:
          with tables.Transaction():
              kwargs["id"] = get_sequence_value(table_name)
              table.add_row(**attributes, **relationships)
      else:
          row = table.get(id=instance.id)
          row.update(**attributes, **relationships)