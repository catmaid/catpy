=====
Usage
=====

``CatmaidClient``
=================

The basic feature of catpy is a class for interacting with CATMAID's REST API::

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

``CatmaidClientApplication``
============================

To write your own class making use of the ``CatmaidClient``, we recommend subclassing the
``CatmaidClientApplication`` abstract base class. This wraps an existing ``CatmaidClient`` instance, and passes through
calls to ``get``, ``post``, ``fetch``, ``base_url`` and ``project_id``, allowing easier
composition of applications and minimising work if you want to change e.g. the project ID of all of the applications
you're working with::

    from catpy.applications import CatmaidClientApplication

    class AnnotationFetcher(CatmaidClientApplication):
        def fetch_annotations(self, object_ids):
            return self.post((self.project_id, 'annotations', 'query'), {'object_ids': object_ids})

    client.project_id = 1

    annotation_fetcher = AnnotationFetcher(client)
    annotations = annotation_fetcher.fetch_annotations(42)

``CatmaidClient`` and all ``CatmaidClientApplication`` s are subclasses of ``AbstractCatmaidClient`` ,
for type checking purposes.

Some included ``CatmaidClientApplication`` s, importable from ``catpy.applications`` are:

- ``ExportWidget``: Replicates some of the functionality of the frontend's Export Widget
- ``NameResolver``: Resolves string names into integer IDs for some objects (e.g. stacks, users, neurons)
- ``RelationIdentifier``: Converts database IDs into a connector relation enum

``CoordinateTransformer``
=========================

A common task requires transforming coordinates between project (real) and stack (pixel) space. A class is provided for
this purpose::

    from catpy import CoordinateTransformer

    transformer = CoordinateTransformer.from_catmaid(client, stack_id=5)
    stack_coords = {'x': 150, 'y': 252, 'z': 2}
    project_coords = transformer.stack_to_project(stack_coords)
    stack_coords == transformer.project_to_stack(project_coords)

N.B.: Stacks may not be oriented the same way as projects. In stack space, ``z`` is depth,
``y`` is the vertical dimension, and ``x`` is the horizontal dimension of image tiles.

Stack coordinates are unscaled (i.e. zoom level 0) by default. Stack coordinates can be scaled
for different zoom levels like so::

    scaled_coords = transformer.stack_to_scaled(stack_coords, tgt_zoom=-2, src_zoom=0)

By switching the ``src_zoom`` and ``tgt_zoom`` arguments, this method is its own inverse.

N.B.: projects dealing with multiple stacks at different anisotropies have a different concept
of scale levels than a simple project-stack relationship, and so these scale levels may not match up
with what you see in the CATMAID UI.

``CatmaidUrl``
==============

This simple class handles reading and generating deep links to particular views in the CATMAID UI::

    from catpy import CatmaidUrl

    url_obj = CatmaidUrl.from_catmaid(client, x=20, y=30, z=40)
    url_obj.stack_id = 5
    url_obj.tool = 'tracingtool'

    url_str = str(url_obj)
    url_str == https://YourCatmaidServer.org/catmaid/?pid=1&zp=40?yp=30?xp=20?tool=tracingtool?sid0=5&s0=0'

    url_obj2 = CatmaidUrl.from_url(url_str)
    url_obj2.stack_id == 5
    url_obj2.open()  # opens default web browser at this URL



``ImageFetcher``
================

This handles fetching ROIs of greyscale uint8 image data from some of CATMAID's common tile sources::

    from catpy.image import ImageFetcher

    fetcher = ImageFetcher.from_catmaid(client, stack_id=5)
    fetcher.set_fastest_mirror()

    shallow_top_left = [10, 200, 400]
    deep_bottom_right = [15, 250, 450]
    roi = [shallow_top_left, deep_bottom_right]

    volume = fetcher.get_stack_space(roi)
    volume.shape == (5, 50, 50)

Image data can be written straight into an existing numpy array or h5py dataset using the ``out``
kwarg of the get_* methods.

Fetched tiles are LRU cached: the size of the cache can be controlled with the ``cache_items`` and
``cache_bytes`` kwargs of the constructor.

The ``output_orientation`` kwarg controls whether ROIs are re-ordered on the way in and data
transposed on the way out, to allow ``ImageFetcher`` to be used easily with scripts relying on
e.g. 'xyz' ordering. Note that the project-stack orientation is only used for conveniently converting
project-spaced ROIs into stack-spaced ROIs: the returned data is transposed from stack space into
the requested orientation, rather than going stack -> project -> requested.

N.B.: There is also an experimental ``ThreadedImageFetcher`` for large ROIs over slow connections. For
small ROIs and fast connections, the threading overhead may erase the benefits of parallelised downloads.

Miscellaneous utilities
=========

Some additional tools are found in ``catpy.utils`` .
