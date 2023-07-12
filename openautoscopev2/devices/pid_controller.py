#! python
#
# Copyright 2021
# Authors: Mahdi Torkashvand

import numpy as np


class PIDController():
    """
    This PID controller calculates the velocity based
    on the current y,x value of the point of interest."""

    def __init__(self, Kpy, Kpx, Kiy, Kix, Kdy, Kdx, SPy, SPx):

        self.Kpy = Kpy
        self.Kiy = Kiy
        self.Kdy = Kdy

        self.Kpx = Kpx
        self.Kix = Kix
        self.Kdx = Kdx

        self.SPy = SPy
        self.SPx = SPx
        
        self.reset()
        return
    
    def reset(self):
        self.Ey = 0.0
        self.Ex = 0.0
        
        self.Iy = 0.0
        self.Ix = 0.0

        self.Vy = 0.0
        self.Vx = 0.0
        return

    def get_velocity(self, y, x):

        Ey = self.SPy - y
        Ex = self.SPx - x
        
        # self.Iy += Ey
        # self.Ix += Ex

        self.Iy = 0.1*Ey + 0.9*self.Iy
        self.Ix = 0.1*Ex + 0.9*self.Ix
        
        Dy = Ey - self.Ey
        Dx = Ex - self.Ex

        self.Ey = Ey
        self.Ex = Ex

        self.Vy = self.Kpy * Ey + self.Kiy * self.Iy + self.Kdy * Dy
        self.Vx = self.Kpx * Ex + self.Kix * self.Ix + self.Kdx * Dx

        # self.Vy = 0.9*self.Kpy * Ey + 0.1 * self.Vy
        # self.Vx = 0.9*self.Kpx * Ex + 0.1 * self.Vx

        return int(self.Vy), int(self.Vx)