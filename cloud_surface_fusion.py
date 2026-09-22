"""Causal TSDF display fusion; source predictions and trajectories stay untouched."""
import numpy as np
import cv2
import open3d as o3d


class SurfaceFusion:
    def __init__(self, scale, voxel_m=.025, trunc_m=.10):
        self.scale = scale
        self.voxel_m = voxel_m
        self.volume = o3d.pipelines.integration.ScalableTSDFVolume(
            voxel_length=voxel_m, sdf_trunc=trunc_m,
            color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8)
        self.frames = 0

    def integrate(self, prediction, mask, c2w):
        depth = np.where(mask, prediction['depth'] / self.scale, 0).astype(np.float32)
        rgb = np.ascontiguousarray(prediction['rgb'])
        h, w = depth.shape
        K = prediction['K']
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            o3d.geometry.Image(rgb), o3d.geometry.Image(depth), depth_scale=1.,
            depth_trunc=12., convert_rgb_to_intensity=False)
        intr = o3d.camera.PinholeCameraIntrinsic(
            w, h, float(K[0,0]), float(K[1,1]), float(K[0,2]), float(K[1,2]))
        pose = np.eye(4)
        pose[:3,:3] = c2w[:3,:3]
        pose[:3,3] = c2w[:3,3] / self.scale
        self.volume.integrate(rgbd, intr, np.linalg.inv(pose))
        self.frames += 1

    def extract(self):
        cloud = self.volume.extract_point_cloud()
        return (np.asarray(cloud.points) * self.scale,
                np.clip(np.asarray(cloud.colors)[:, ::-1] * 255, 0, 255).astype(np.uint8))


def rasterize_surface(m, points, colors, voxel_m):
    """Depth-ranked surfel footprints, without interpolation across empty regions."""
    m.raster.fill(0); m.z.fill(-np.inf); m.z_obs.fill(-np.inf)
    if not len(points):
        return
    uv, zz = m.project(points)
    valid = (uv[:,0]>=0)&(uv[:,0]<m.w)&(uv[:,1]>=0)&(uv[:,1]<m.h)
    ids = np.flatnonzero(valid)
    ids = ids[np.argsort(zz[ids], kind='stable')]
    if not len(ids):
        return
    if len(ids) >= 2**24:
        raise ValueError('Surfel rank exceeds exact float32 integer range')
    rank = np.arange(1, len(ids)+1, dtype=np.float32)
    pix = uv[ids,1]*m.w+uv[ids,0]
    base = np.zeros(m.h*m.w, np.float32)
    np.maximum.at(base, pix, rank)
    radius = max(1, int(np.ceil(voxel_m*m.s*m.scale/2)))
    yy, xx = np.mgrid[-radius:radius+1, -radius:radius+1]
    kernel = (xx*xx+yy*yy <= radius*radius+1).astype(np.uint8)
    chosen = cv2.dilate(base.reshape(m.h,m.w), kernel).ravel().astype(np.int64)
    hit = chosen>0
    winners = ids[chosen[hit]-1]
    m.raster[hit] = colors[winners]
    m.z[hit] = zz[winners]
    above = (m.d-points[ids]@m.n)/m.s > .25
    base.fill(0)
    np.maximum.at(base, pix[above], rank[above])
    chosen = cv2.dilate(base.reshape(m.h,m.w), kernel).ravel().astype(np.int64)
    hit = chosen>0
    m.z_obs[hit] = zz[ids[chosen[hit]-1]]
