# MIT License
#
# Copyright (c) 2020 The Anvil ORM project team members listed at
# https://github.com/anvilistas/anvil-orm/graphs/contributors
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
# This software is published at # https://github.com/anvilistas/anvil-orm
import anvil

from app import model, session
from app.client_lib import navigation

__version__ = "0.1.18"


def _camel_to_snake(name):
    """Convert a CamelCase string to snake_case"""
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")


class CRUDForm:
    model_name = None
    max_depth = 1

    @property
    def form_name(self):
        return _camel_to_snake(self.model_name)

    @property
    def model_class(self):
        return getattr(model, self.model_name)


class CreateUpdateMixin:
    def __init__(self, item=None, **properties):
        if item is None:
            item = dict(code=None)
        self.item = item
        self.init_components(**properties)


class ReadMixin(CRUDForm):
    def __init__(self, **properties):
        self.create_button.set_event_handler("click", self.create_button_click)
        self.refresh_items()
        self.init_components(**properties)

    def refresh_items(self):
        items = session.cache.refresh(self.model_name, self.max_depth)
        if len(items) == 0:
            items = []
        self.repeating_panel.items = items

    def create_button_click(self, **event_args):
        form = navigation.get_form(f"{self.form_name}_create_update")
        response = anvil.alert(
            content=form,
            buttons=[("Cancel", "cancel"), ("OK", "ok")],
            dismissible=False,
        )
        if response == "ok":
            self.model_class(**form.item).save()
            self.refresh_items()

    def form_show(self, **event_args):
        session.publisher.subscribe(self.form_name, self, self.handle_messages)

    def form_hide(self, **event_args):
        session.publisher.unsubscribe(self.form_name, self)

    def handle_messages(self, message):
        self.refresh_items()


class RowMixin(CRUDForm):
    def __init__(self, **properties):
        self.init_components(**properties)

    def edit_link_click(self, **event_args):
        form = navigation.get_form(f"{self.form_name}_create_update", item=self.item)
        response = anvil.alert(
            content=form,
            buttons=[("Cancel", "cancel"), ("OK", "ok")],
            dismissible=False,
        )
        if response == "ok":
            form.item.save()
            session.publisher.publish(self.form_name, "edited")

    def delete_link_click(self, **event_args):
        confirm = anvil.confirm("Are you sure you wish to delete this item?")
        if confirm:
            self.item.delete()
            session.publisher.publish(self.form_name, "deleted")
