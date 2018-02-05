=====
Usage
=====

To use catpy in a project::

    import catpy

    client = catpy.CatmaidClient(
        'https://YourCatmaidServer.org/catmaid',
        'Your CATMAID API token string'
    )

    query = {'object_ids': 42}
    annotations = client.fetch('1/annotations/query', method='POST', data=query)

Instructions for getting your CATMAID API token string are available
`in the CATMAID documentation <http://catmaid.readthedocs.io/en/stable/api.html#api-token>`_.

If the CATMAID server requires HTTP basic authentication, initialize the
``CatmaidClient`` with ``auth_name`` and ``auth_pass`` keyword arguments.

For convenience, the ``'GET'`` and ``'POST'`` methods have their own shortcuts::

    annotations = client.post('1/annotations/query', data=query)
    connectors = client.get('1/connectors/links/', params={"skeleton_ids": [11524047]})

To make it easier to include variables, you can pass an iterable of URL components instead of a single string::

    project_id = 1
    annotations = client.post([project_id, 'annotations', 'query'], data=query)

To write your own class making use of the ``CatmaidClient``, we recommend subclassing the
``CatmaidClientApplication`` abstract base class. This wraps an existing ``CatmaidClient`` instance, and passes through
 calls to ``get``, ``post``, ``fetch``, ``base_url`` and ``project_id``, allowing easier
composition of applications and minimising work if you want to change e.g. the project ID of all of the applications
you're working with::

    from catpy.client import CatmaidClientApplication

    class AnnotationFetcher(CatmaidClientApplication):
        def fetch_annotations(self, object_ids):
            return self.post((self.project_id, 'annotations', 'query'), {'object_ids': object_ids})

    client.project_id = 1

    annotation_fetcher = AnnotationFetcher(client)
    annotations = annotation_fetcher.fetch_annotations(42)

A common task requires transforming coordinates between project (real) and stack (pixel) space. A class is provided for
this purpose::

    from catpy.client import CoordinateTransformer

    transformer = CoordinateTransformer.from_catmaid(client, stack_id=5)
    stack_coords = {'x': 150, 'y': 252, 'z': 2}
    project_coords = transformer.stack_to_project(stack_coords)
    stack_coords == transformer.project_to_stack(project_coords)
