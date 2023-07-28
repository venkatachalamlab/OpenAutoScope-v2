# Copyright 2023
# Authors: Mahdi Torkashvand, Sina Rasouli

import numpy as np


class PIDController():

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

        Ey = self.SPy - y if not np.isnan(y) and y is not None else self.SPy
        Ex = self.SPx - x if not np.isnan(x) and x is not None else self.SPx

        self.Iy = 0.1*Ey + 0.9*self.Iy
        self.Ix = 0.1*Ex + 0.9*self.Ix
        
        Dy = Ey - self.Ey
        Dx = Ex - self.Ex

        self.Ey = Ey
        self.Ex = Ex

        self.Vy = self.Kpy * np.sign(Ey) * (Ey / 50)**2 * 50 + self.Kiy * self.Iy + self.Kdy * Dy
        self.Vx = self.Kpx * np.sign(Ex) * (Ex / 50)**2 * 50 + self.Kix * self.Ix + self.Kdx * Dx

        return int(-self.Vy), int(self.Vx)
