# This project has been superseded by the [persistence module](https://anvil-extras.readthedocs.io/en/latest/guides/modules/persistence.html) of [Anvil Extras](https://github.com/anvilistas/anvil-extras) and should no longer be used.

# Anvil ORM
A library for [Anvil Applications](https://anvil.works) that provides Object Relational Mapping (ORM)
functionality.

Using this library, you can write simple classes such as:

```python
@model_type
class Person:
    first_name = Attribute()
    last_name = Attribute()
```

and then use that class to create new Person instances, save them to a data table, 
fetch them back and update them with code as simple as:

```python
from .model import Person

person = Person(first_name="Owen").save()

person.last_name = "Campbell"
person.save()

people = Person.search()
```

And you can do that in both client and server side code!

## Credits
The development of this library was partly funded by [Nanovare](https://www.mojofertility.co)
and [Osmosis Investment Management](https://www.osmosisim.com/)

## Documentation
Installation and usage instructions are at [Readthedocs](https://anvil-orm.readthedocs.io/en/latest/)
