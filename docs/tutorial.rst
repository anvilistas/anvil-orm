Tutorial
========

For this tutorial, we're going to build a model to represent Books and their Authors.
We'll assume you already have an anvil app with the data tables service enabled and
the model library installed.

For a book, we want to store its title, publication date and author. For an author, we
want to store a first name and a last name.

Create the Data Tables
----------------------
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

Create the Model Module
-----------------------
Create a module in the client code section of your app and call it 'model'. Add
the following code to define the Book and Author classes::

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

Add Some Entries
----------------
Create a new module in the client code section of your app, name it 'startup' and set
it as the startup module. Delete its content and replace it with::

    import datetime as dt
    from .model import Book, Author

    print("Creating Luciano")
    luciano = Author(first_name="Luciano", last_name="Ramalho")
    luciano.save()

    print("Creating Drew")
    drew = Author(first_name="Drew", last_name="Neil")
    drew.save()

    print("Creating Fluent Python")
    fluent_python = Book(
        title="Fluent Python",
        published_on=dt.datetime(2015, 8, 21).date(),
        author=luciano
    )
    fluent_python.save()

    print("Creating Practical Vim")
    practical_vim = Book(
        title="Practical Vim",
        published_on=dt.datetime(2017, 1, 1).date(),
        author=drew
    )
    practical_vim.save()

Launch your app and stop it again. You should see the results of the print statements
in its output console.

Check the contents of your data tables. You should see both authors and books in their
respective tables, with id numbers automatically assigned. You should also see two
entries in the sequence table with the 'next' values ready for the next author and book.

Fetch the Entries Back Again
----------------------------
Delete the code in your startup app (or rename it and create a new 'startup' module)
and replace the content with::

    from .model import Book, Author

    for book in Book.search():
        print(book.title)
        print(book.author.first_name)

Launch the app and you should see the title and author's first name for both books
in your output consule.

Make a Change
-------------
Delete the code in your startup app (or rename it and create a new 'startup' module)
and replace the content with::
    
    from .model import Book, Author

    fluent_python = Book.search(title="Fluent Python")[0]
    fluent_python.title = "Fluent Python (Clear, Concise, and Effective Programming)"
    fluent_python.save()

    practical_vim = Book.get(id=2)
    practical_vim.title = "Practical Vim (Edit Text at the Speed of Thought)"
    practical_vim.save()

Start and stop the app and check your data tables. You should see the updated titles
for both book rows.
