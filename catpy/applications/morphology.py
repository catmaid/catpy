import logging

from typing import NamedTuple, List, Dict, Sequence, Any

import numpy as np
import pandas as pd

from catpy.util import add_deprecated_gets, set_request_bool
from .base import CatmaidClientApplication

logger = logging.getLogger(__name__)


def lol_to_df(data, columns, dtypes=None):
    if not dtypes:
        return pd.DataFrame(data, columns=columns)

    col_data = {s: [] for s in columns}
    for row in data:
        for col, item in zip(columns, row):
            col_data[col].append(item)

    try:
        col_dtype = zip(columns, dtypes)
    except TypeError:
        col_dtype = zip(columns, (dtypes for _ in columns))

    col_data = {col: pd.array(col_data[col], dtype=dtype) for col, dtype in col_dtype}
    df = pd.DataFrame(col_data)
    return df[columns]  # < py36, dict ordering


def interpolate_node_locations(parent_xyz, child_xyz, z_res=1, z_offset=0):
    parent_child = np.array([parent_xyz, child_xyz])
    z_slices = np.round((parent_child[:, 2] - z_offset) / z_res).astype(int)

    n_slices_between = abs(np.diff(z_slices)[0]) - 1

    if n_slices_between < 1:
        return

    parent_child[:, 2] = (z_slices * z_res + z_offset).astype(float)

    new_xyz = zip(
        np.linspace(*parent_child[:, 0], num=n_slices_between + 2),
        np.linspace(*parent_child[:, 1], num=n_slices_between + 2),
        np.linspace(*parent_child[:, 2], num=n_slices_between + 2),
    )
    next(new_xyz)  # discard, it's the parent location
    for _ in range(n_slices_between):
        yield next(new_xyz)
    assert next(new_xyz)


def in_roi(roi_xyz, coords_xyz):
    """Closed interval: use intersection_roi"""
    x, y, z = coords_xyz
    return all(
        [
            roi_xyz[0, 0] <= x <= roi_xyz[1, 0],
            roi_xyz[0, 1] <= y <= roi_xyz[1, 1],
            roi_xyz[0, 2] <= z <= roi_xyz[1, 2],
        ]
    )


def treenode_df(response: List[List[Any]]) -> pd.DataFrame:
    return lol_to_df(
        response,
        ["id", "parent", "user", "x", "y", "z", "radius", "confidence"],
        [
            np.uint64,
            pd.UInt64Dtype(),
            np.uint64,
            np.float64,
            np.float64,
            np.float64,
            np.float64,
            np.uint8,
        ],
    )


class SkeletonCompactDetail(NamedTuple):
    id: int
    treenodes: pd.DataFrame
    connectors: pd.DataFrame
    tags: Dict[str, List[int]]

    @classmethod
    def from_response(cls, skid, response):
        node_data = treenode_df(response[0])
        conn_data = lol_to_df(
            response[1],
            ["treenode", "connector", "relation", "x", "y", "z"],
            [np.uint64, np.uint64, np.int8, np.float64, np.float64, np.float64],
        )
        return SkeletonCompactDetail(int(skid), node_data, conn_data, response[2])


class SkeletonCompactArbor(NamedTuple):
    id: int
    treenodes: pd.DataFrame
    connections: pd.DataFrame
    tags: Dict[str, List[int]]

    @classmethod
    def from_response(cls, skid, response):
        node_data = treenode_df(response[0])
        conn_data = lol_to_df(
            response[1],
            ["treenode", "confidence", "connector_id", "confidence", "treenode_id", "skeleton_id", "relation_id", "relation_id"],
            [np.uint64, np.uint8, np.uint64, np.uint8, np.uint64, np.uint64, np.uint8, np.uint8]
        )
        return SkeletonCompactArbor(int(skid), node_data, conn_data, response[2])


class MorphologyFetcher(CatmaidClientApplication):
    def _compact_skeleton_detail(self, skeleton_id, **params):
        return self.get(
            (self.project_id, "skeletons", skeleton_id, "compact-detail"), params=params
        )

    def compact_skeleton_detail(self, skeleton_id, connectors=False, tags=False):
        logger.debug("Getting compact-detail for skeleton %s", skeleton_id)
        params = dict()
        if connectors:
            params["with_connectors"] = "true"
        if tags:
            params["with_tags"] = "true"
        response = self._compact_skeleton_detail(skeleton_id, **params)
        return SkeletonCompactDetail.from_response(int(skeleton_id), response)

    def _compact_skeletons_detail(self, **data):
        return self.post(
            (self.project_id, "skeletons", "compact-detail"), data=data
        )

    def compact_skeletons_detail(self, skeleton_ids: Sequence[int], connectors=False, tags=False):
        logger.debug("Getting compact-detail for %s skeletons", len(skeleton_ids))
        params = {"skeleton_ids": list(skeleton_ids)}
        if connectors:
            params["with_connectors"] = "true"
        if tags:
            params["with_tags"] = "true"
        responses = self._compact_skeletons_detail(**params)
        for skid_str, response in responses["skeletons"].items():
            yield SkeletonCompactDetail.from_response(int(skid_str), response)

    def _compact_arbor(
        self, skeleton_id: int, with_nodes: bool, with_connectors: bool, with_tags: bool,
        ordered: bool = False, with_time: bool = False
    ):
        url = (self.project_id, skeleton_id, int(bool(with_nodes)), int(bool(with_connectors)), int(bool(with_tags)))
        params = {"ordered": set_request_bool(ordered), "with_time": set_request_bool(with_time)}
        return self.get(url, params)

    def compact_arbor(
        self, skeleton_id: int, with_nodes: bool, with_connectors: bool, with_tags: bool,
        ordered: bool = False, with_time: bool = False
    ):
        if with_time:
            raise NotImplementedError("Creation/edit time parsing not implemented")
        data = self._compact_arbor(skeleton_id, with_nodes, with_connectors, with_tags, ordered, with_time)
        return SkeletonCompactArbor.from_response(skeleton_id, data)


add_deprecated_gets(MorphologyFetcher, "compact_skeleton_detail", "compact_skeletons_detail")
