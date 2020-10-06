import anvil.server

__version__ = "0.1.0"


class Attribute:
    def __init__(self, required=True, default=None):
        self.required = required
        self.default = default


class Relationship:
    def __init__(self, cls):
        self.cls = cls


def _constructor(attributes, relationships):
    def init(self, **kwargs):
        self.id = kwargs.pop("id", None)

        for name, relationship in relationships.items():
            if name not in kwargs:
                raise ValueError(f"No argument for mandatory relationship {name}")

        valid_keys = [key for key in attributes] + [key for key in relationships]
        for key, value in kwargs.items():
            if key not in valid_keys:
                raise ValueError(
                    f"{type(self).__name__}.__init__ received an invalid argument: '{key}'"
                )
            else:
                setattr(self, key, value)

        for name, attribute in attributes.items():
            if name not in kwargs:
                setattr(self, name, attribute.default)

    return init


def _representation(cls, attributes, relationships):
    def representation(self):
        attribute_repr = [
            f"{key}={getattr(self, key)}" for key, value in attributes.items()
        ]
        relationship_repr = [
            f"{key}_id={getattr(self, key).id}" for key, value in relationships.items()
        ]
        return f"{cls.__name__}({', '.join(attribute_repr)}, {', '.join(relationship_repr)})"

    return representation


def equivalence(self, other):
    return self.id == other.id


def _from_row(relationships):
    @classmethod
    def instance_from_row(cls, row):
        attrs = dict(row)
        id = attrs.pop("id")
        for name, relationship in relationships.items():
            attrs[name] = relationship.cls._from_row(row[name])
        result = cls(**attrs)
        result.id = id
        return result

    return instance_from_row


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

    members = {
        "__module__": cls.__module__,
        "__init__": _constructor(attributes, relationships),
        "__eq__": equivalence,
        "__repr__": _representation(cls, attributes, relationships),
        "_from_row": _from_row(relationships),
        "get": _get,
        "list": _list,
        "save": _save,
    }
    members.update(methods)
    members.update(class_attributes)

    model = type(cls.__name__, (object,), members)
    return anvil.server.serializable_type(model)
