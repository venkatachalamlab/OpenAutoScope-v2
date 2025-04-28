# Copyright 2023
# Authors: Mahdi Torkashvand, Sina Rasouli

import numpy as np

def is_nan(x):
    return ( x is None or np.isnan(x) )


class PIDController():

    def __init__(self, Kpy, Kpx, Kiy, Kix, Kdy, Kdx, SPy, SPx):

        self.Kpy = Kpy
        self.Kiy = Kiy
        self.Kdy = Kdy

        self.Kpx = Kpx
        self.Kix = Kix
        self.Kdx = Kdx

        self.SPx0 = SPx
        self.SPy0 = SPy

        self.SPy = self.SPx0
        self.SPx = self.SPy0
        
        self.reset()
        return
    
    def reset(self):
        self.Ey = 0.0
        self.Ex = 0.0
        
        self.Iy = 0.0
        self.Ix = 0.0

        self.Vy = 0.0
        self.Vx = 0.0

        self.SPy = self.SPx0
        self.SPx = self.SPy0
        return

    def get_velocity(self, y, x):

        # If both coords are None/NaN, stop tracking
        # and reset to initial parameters
        if is_nan(x) and is_nan(y):
            self.reset()
            return int(-self.Vy), int(self.Vx)

        Ey = self.SPy - y if y is not None and not np.isnan(y) else self.SPy
        Ex = self.SPx - x if x is not None and not np.isnan(x)  else self.SPx

        self.Iy = 0.1*Ey + 0.9*self.Iy
        self.Ix = 0.1*Ex + 0.9*self.Ix
        
        Dy = Ey - self.Ey
        Dx = Ex - self.Ex

        self.Ey = Ey
        self.Ex = Ex

        self.Vy = self.Kpy * np.sign(Ey) * (Ey / 50)**2 * 50 + self.Kiy * self.Iy + self.Kdy * Dy
        self.Vx = self.Kpx * np.sign(Ex) * (Ex / 50)**2 * 50 + self.Kix * self.Ix + self.Kdx * Dx

        return int(-self.Vy), int(self.Vx)
