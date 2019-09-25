import numpy as np


def get_virtual_treenodes(treenodes_response, z_depth):
    """
    Get the locations of all virtual nodes in the given skeleton response,
    with the IDs of the material nodes proximal and distal to the virtual slab.

    Parameters
    ----------
    treenodes_response: sequence of sequences of any
        "nodes" element of compact-skeleton or compact-arbor API response:
        row values are [treenode_id, parent_id, _, location_x, location_y, location_z, ...]
    z_depth: float
        Z resolution of the stack

    Returns
    -------
    iterator of (
        (proximal_treenode_id, distal_treenode_id),
        [
            (proximal_vnode_x, proximal_vnode_y, proximal_vnode_z),
            ...
            (distal_vnode_x, distal_vnode_y, distal_vnode_z)
        ]
    )
    """
    data = dict()
    for row in treenodes_response:
        parent = row[1]
        data[int(row[0])] = {
            "parent": None if parent is None else int(parent),
            "location": np.array(row[3:6], dtype=float),
        }

    for tnid, d in data.items():
        parent_id = d["parent"]
        if parent_id is None:
            continue
        parent_loc = data[parent_id]["location"]
        virtual_treenodes = list(
            interpolate_treenodes(parent_loc, d["location"], z_depth)
        )
        if virtual_treenodes:
            yield (d["parent"], tnid), virtual_treenodes


def interpolate_treenodes(parent_xyz, child_xyz, z_depth, z_offset=0):
    """
    Yield the locations of virtual treenodes between two material treenodes.

    The parent and child's z coordinates will be quantized to the nearest multiple of z_depth.
    Virtual nodes will be projected onto any multiples of z_depth between the parent and child,
    and their (x, y, z) coordinates will be yielded in parent -> child order.

    Parameters
    ----------
    parent_xyz : sequence of (float, float, float)
    child_xyz : sequence of (float, float, float)
    z_depth : float
        e.g. z-resolution
    z_offset: float
        offset of z in project coordinates, default 0

    Returns
    -------
    Iterator of (x,y,z) tuples
    """
    parent_child_xyz = np.array((parent_xyz, child_xyz), dtype=float)

    z_slices = np.round((parent_child_xyz[:, 2] - z_offset) / z_depth)

    n_vnodes = int(abs(np.diff(z_slices)[0])) - 1

    if n_vnodes < 1:
        return

    parent_child_xyz[:, 2] = z_slices * z_depth + z_offset

    it = zip(
        *[np.linspace(*parent_child_xyz[:, idx], num=n_vnodes + 2) for idx in range(3)]
    )
    next(it)  # discard first (parent location)
    for _ in range(n_vnodes):
        yield next(it)
    # discard last (child location)
