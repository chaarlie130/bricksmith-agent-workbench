"""3D Occupancy Voxel Grid and Spatial Envelope for BrickSmith Assemblies."""
from __future__ import annotations

import numpy as np

from bricksmith.core.part import LDU_PER_STUD
from bricksmith.core.graph import AssemblyGraph
from bricksmith.geometry.bounds import BoundingBox3D, calculate_bounds


class OccupancyGrid(np.ndarray):
    """3D boolean numpy array representing spatial occupancy of brick geometry.
    Extends np.ndarray with spatial bounds and centroid properties.
    """
    bounds: BoundingBox3D
    origin_ldu: np.ndarray
    resolution_studs: float
    voxel_size_ldu: float

    def __new__(
        cls,
        input_array: np.ndarray,
        bounds: BoundingBox3D,
        origin_ldu: np.ndarray,
        resolution_studs: float = 1.0,
        voxel_size_ldu: float = LDU_PER_STUD,
    ):
        obj = np.asarray(input_array).view(cls)
        obj.bounds = bounds
        obj.origin_ldu = origin_ldu
        obj.resolution_studs = resolution_studs
        obj.voxel_size_ldu = voxel_size_ldu
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.bounds = getattr(obj, "bounds", None)
        self.origin_ldu = getattr(obj, "origin_ldu", None)
        self.resolution_studs = getattr(obj, "resolution_studs", 1.0)
        self.voxel_size_ldu = getattr(obj, "voxel_size_ldu", LDU_PER_STUD)

    @property
    def centroid_ldu(self) -> np.ndarray:
        """Physical center of mass of the occupied voxels in LDU."""
        occ = np.argwhere(self)
        if len(occ) == 0:
            return self.origin_ldu.copy() if self.origin_ldu is not None else np.zeros(3)
        return self.origin_ldu + (np.mean(occ, axis=0) + 0.5) * self.voxel_size_ldu

    @property
    def centroid_studs(self) -> np.ndarray:
        """Physical center of mass of the occupied voxels in studs."""
        return self.centroid_ldu / LDU_PER_STUD


def calculate_grid_centroid(
    grid: np.ndarray,
    bounds: BoundingBox3D,
    resolution_studs: float = 1.0,
) -> np.ndarray:
    """Calculate the world centroid of an occupancy grid in studs."""
    res_ldu = resolution_studs * LDU_PER_STUD
    occ = np.argwhere(grid)
    if len(occ) == 0:
        return bounds.min_ldu / LDU_PER_STUD
    centroid_ldu = bounds.min_ldu + (np.mean(occ, axis=0) + 0.5) * res_ldu
    return centroid_ldu / LDU_PER_STUD


def generate_occupancy_grid(
    graph: AssemblyGraph,
    resolution_studs: float = 1.0,
) -> np.ndarray:
    """Generate a 3D boolean occupancy array representing where bricks exist in space.
    
    Args:
        graph: Input AssemblyGraph model.
        resolution_studs: Voxel edge resolution in studs (default 1.0 stud = 20 LDU).
        
    Returns:
        OccupancyGrid (np.ndarray): 3D boolean array where True represents occupied volume.
    """
    bounds = calculate_bounds(graph)
    if not graph.parts:
        empty = np.zeros((0, 0, 0), dtype=bool)
        return OccupancyGrid(
            empty,
            bounds=bounds,
            origin_ldu=bounds.min_ldu,
            resolution_studs=resolution_studs,
            voxel_size_ldu=resolution_studs * LDU_PER_STUD,
        )

    res_ldu = resolution_studs * LDU_PER_STUD
    shape = np.maximum(np.ceil(bounds.size_ldu / res_ldu).astype(int), 1)
    grid = np.zeros(shape, dtype=bool)

    for inst_id, part in graph.parts.items():
        if inst_id in bounds.part_bounds:
            lo, hi = bounds.part_bounds[inst_id]
        else:
            lo = part.position - 10.0
            hi = part.position + 10.0

        i0 = np.clip(np.floor((lo - bounds.min_ldu) / res_ldu).astype(int), 0, shape - 1)
        i1 = np.clip(np.ceil((hi - bounds.min_ldu) / res_ldu).astype(int), 1, shape)
        grid[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] = True

    return OccupancyGrid(
        grid,
        bounds=bounds,
        origin_ldu=bounds.min_ldu,
        resolution_studs=resolution_studs,
        voxel_size_ldu=res_ldu,
    )
