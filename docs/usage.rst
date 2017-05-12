=====
Usage
=====

To use catpy in a project::

    import catpy

    client = catpy.CatmaidClient(
        'https://YourCatmaidServer.org/catmaid',
        'Your CATMAID API token string')

    query = {'object_ids': 42}
    annotations = client.fetch('1/annotations/query', method='POST', data=query)

Instructions for getting your CATMAID API token string are available
`in the CATMAID documentation <http://catmaid.readthedocs.io/en/stable/api.html#api-token>`_.

If the CATMAID server requires HTTP basic authentication, initialize the
``CatmaidClient`` with ``auth_name`` and ``auth_pass`` keyword arguments.
