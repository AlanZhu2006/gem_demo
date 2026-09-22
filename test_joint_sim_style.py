import unittest
from types import SimpleNamespace
import numpy as np
from joint_sim_style import local_to_floor, goal_state

class FloorTrajectoryTest(unittest.TestCase):
    def test_forward_left_and_yaw_are_not_height(self):
        m=SimpleNamespace(n=np.array([0.,1.,0.]),s=.3)
        m.fwd_at=lambda a,t:np.array([0.,0.,1.])
        m.pos_at=lambda a,t:np.array([1.,-.5,2.])
        m.to_floor=lambda X,lift:np.asarray(X)*[1,0,1]
        p=local_to_floor(m,'gem',30,[[1,0,9],[0,1,-9]])
        np.testing.assert_allclose(p,[[1,-.006,2.3],[.7,-.006,2.]])

class GoalCardStateTest(unittest.TestCase):
    def test_arrival_and_failure_are_separate_per_arm(self):
        pair={'arms':{
            'gem':{'legs':[dict(stage='A',start=0,stop=11,arrival_step=10,reached=True)]},
            'base':{'legs':[dict(stage='A',start=0,stop=16,arrival_step=None,reached=False)]}}}
        self.assertEqual(goal_state(pair,'gem','A',{'gem':9,'base':9},9),'active')
        self.assertEqual(goal_state(pair,'gem','A',{'gem':10,'base':10},10),'arrived')
        self.assertEqual(goal_state(pair,'base','A',{'gem':10,'base':10},10),'active')
        self.assertEqual(goal_state(pair,'base','A',{'gem':10,'base':15},15),'stopped')
        self.assertEqual(goal_state(pair,'gem','B',{'gem':10,'base':15},15),'pending')

if __name__=='__main__':unittest.main()
