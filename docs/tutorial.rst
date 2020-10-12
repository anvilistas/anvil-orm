Tutorial
========

For this tutorial, we're going to build a model to represent Books and their Authors.
We'll assume you already have an anvil app with the data tables service enabled and
the model library installed.

For a book, we want to store its title, publication date and author. For an author, we
want to store a first name and a last name.

Create a data table called 'author' with three columns:
    * a number column called 'id'
    * a text column called 'first_name'
    * a text column called 'last_name'

Create a second table called 'book' with four columns:
    * a number column called 'id'
    * a text column called 'title'
    * a date column called 'published_on' 
    * a column which links to a single column in the 'author' table named 'author'.

Finally, create a table called 'sequence' with two columns:
    * a text column called 'id'
    * a number column called 'next'

Next, create a module in the client code section of your app and call it 'model'. Add
the following code to define the Book and Author classes:

```python
from .particles import model_type, Attribute, Relationship

@model_type
class Author:
    first_name = Attribute()
    last_name = Attribute()


@model_type
class Book:
    title = Attribute()
    published_on = Attribute()
    author = Relationship(cls="Author")
```
