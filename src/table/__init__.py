"""A desktop window showing the replay's snapshot rows.

A second subscriber to the server-side replay session the chart drives: same
cursor, same rows, its own window. ``client`` reads the stream, ``columns``
decides how a row renders, ``window`` is the Qt view.
"""
