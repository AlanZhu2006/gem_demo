import unittest
from collections import deque
import numpy as np
from real_floor_cloud import FloorSupportedMap

class FloorSupportTest(unittest.TestCase):
    def test_requires_two_past_displaced_depth_matches(self):
        m=FloorSupportedMap.__new__(FloorSupportedMap);m.s=1.
        T=np.eye(4)[:3];old=T.copy();old[0,3]=.04
        K=np.array([[10.,0,10],[0,10,10],[0,0,1]])
        d=np.full((21,21),2.);mask=np.ones_like(d,dtype=bool)
        X=np.array([[0.,0.,2.],[0.,0.,2.2]])
        obs=lambda t:(t,old,d,K,mask)
        m.history={'gem':deque([obs(.5),obs(.75)])}
        np.testing.assert_array_equal(m.supported(X,1.,'gem',T),[True,False])
        for history in ([obs(.5)], [obs(1.1),obs(1.3)], [(t,T,d,K,mask) for t in (.5,.75)]):
            m.history['gem']=deque(history)
            self.assertFalse(m.supported(X,1.,'gem',T).any())

if __name__=='__main__':unittest.main()
