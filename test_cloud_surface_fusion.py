"""Metric conversion and extrinsic regression for the display fusion."""
import unittest
import numpy as np
from types import SimpleNamespace
from cloud_surface_fusion import SurfaceFusion, rasterize_surface

class SurfaceFusionTest(unittest.TestCase):
    def test_translated_cameras_recover_same_metric_plane(self):
        scale=.3
        f=SurfaceFusion(scale)
        K=np.array([[65.,0,39.5],[0,65.,29.5],[0,0,1.]])
        for x,z in [(0.,0.),(.15,.3)]:
            T=np.column_stack([np.eye(3),np.array([x,0,z])*scale])
            p=dict(depth=np.full((60,80),(2.-z)*scale,np.float32),K=K,
                   rgb=np.full((60,80,3),[40,100,180],np.uint8))
            f.integrate(p,np.ones((60,80),bool),T)
        points,colors=f.extract()
        self.assertGreater(len(points),100)
        self.assertLess(np.max(np.abs(points[:,2]/scale-2.)),.015)
        self.assertTrue(np.allclose(np.median(colors,axis=0),[180,100,40],atol=1))
        self.assertEqual(f.frames,2)

    def test_invalid_depth_does_not_add_surface(self):
        f=SurfaceFusion(.3)
        p=dict(depth=np.ones((20,20),np.float32),K=np.array([[20.,0,10],[0,20.,10],[0,0,1.]]),
               rgb=np.full((20,20,3),255,np.uint8))
        f.integrate(p,np.zeros((20,20),bool),np.column_stack([np.eye(3),np.zeros(3)]))
        self.assertEqual(len(f.extract()[0]),0)

    def test_surface_and_obstacle_buffers_choose_depth_independently(self):
        m=SimpleNamespace(w=9,h=9,s=1.,scale=1.,d=0.,n=np.array([0.,1.,0.]),
            raster=np.zeros((81,3),np.uint8),z=np.full(81,-np.inf),z_obs=np.full(81,-np.inf))
        m.project=lambda X:(np.full((len(X),2),4,dtype=int),X[:,2])
        points=np.array([[0.,-.5,1.],[0.,0.,2.]])
        colors=np.array([[30,60,90],[100,120,140]],np.uint8)
        rasterize_surface(m,points,colors,.025)
        self.assertEqual(m.z[40],2.)
        self.assertEqual(m.z_obs[40],1.)
        np.testing.assert_array_equal(m.raster[40],colors[1])
        self.assertTrue(np.isneginf(m.z[0]))

if __name__=='__main__':unittest.main()
