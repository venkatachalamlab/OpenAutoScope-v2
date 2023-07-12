# Modules
import numpy as np

import cv2 as cv

# Methods
## Array Min-Max
def minmax(arr):
    return np.min(arr), np.max(arr)
## Find Mode Pixel
def find_mode_pixel(arr):
    values, counts = np.unique(arr, return_counts=True)
    value_mode = values[np.argmax(counts)]
    return value_mode
## Rectangle Area Overlap Ratio
def rects_overlap(rect1, rect2):
    x1l,y1l,w1,h1,s1 = rect1
    x1r,y1r = x1l+w1, y1l+h1
    x2l,y2l,w2,h2,s2 = rect2
    x2r,y2r = x2l+w2, y2l+h2
    # Cases
    dx, dy = 0, 0
    if x2l <= x1l <= x2r and y2l <= y1l <= y2r:  # 1: top-left
        dx = x1l-x2l
        dy = y1l-y2l
    elif x2l <= x1r <= x2r and y2l <= y1l <= y2r:  # 1: top-right
        dx = x1r-x2l
        dy = y1l-y2l
    elif x2l <= x1l <= x2r and y2l <= y1r <= y2r:  # 1: bottom-left
        dx = x1l-x2l
        dy = y1r-y2l
    elif x2l <= x1r <= x2r and y2l <= y1r <= y2r:  # 1: bottom-right
        dx = x1r-x2l
        dy = y1r-y2l
    area_intersection = dx*dy
    area_min = min(w1*h1, w2*h2)
    return area_intersection / area_min
## Rectangle Center Distance
def rects_distance_ratio(rect1, rect2, normalize=False):
    x1,y1,w1,h1,s1 = rect1
    x2,y2,w2,h2,s2 = rect2
    r1, r2 = np.sqrt(w1*h1), np.sqrt(w2*h2)
    r_max = max(r1, r2)
    distance = np.sqrt(
        (x1+w1/2-x2-w2/2)**2 + (y1+h1/2-y2-h2/2)**2
    )
    if not normalize:
        return distance
    distance_normalized = distance / r_max
    return  distance_normalized - 1.0
## Merge Rectangles
def merge_rectangles(labels, rectangles, threshold_ratio_overlap=0.10, threshold_distance = 30.0):
    rectangles_merged = [
        list(rectangles[0])
    ]
    rectangels_to_merge = [ (i+1,rect) for i, rect in enumerate(rectangles[1:,:]) ]
    while len(rectangels_to_merge) > 0:
        idx = 0
        label_current, rect_current = rectangels_to_merge[idx]
        x0,y0,w0,h0,s0 = rect_current
        x0r, y0r = x0+w0, y0+h0
        ids_merged = {idx}
        for idx, entry in enumerate(rectangels_to_merge):
            label, rect = entry
            if idx == 0:
                continue
            # Check Ratio of Overlap
            ratio_overlap = rects_overlap( rect_current, rect )
            distance = rects_distance_ratio( rect_current, rect, normalize=False )
            if ratio_overlap >= threshold_ratio_overlap or distance <= threshold_distance:
                labels[ labels == label ] = label_current
                x,y,w,h,s = rect
                xr, yr = x+w, y+h
                ids_merged.add(idx)
                x0, y0 = min(x, x0), min(y, y0)
                x0r, y0r = max(xr, x0r), max(yr, y0r)
                s0 += s
        # Remove Indices
        rectangels_to_merge = [
            entry for i, entry in enumerate(rectangels_to_merge) if i not in ids_merged
        ]
        # Store
        rectangles_merged.append([
            x0, y0, x0r-x0+1, y0r-y0+1, s0
        ])
    #
    rectangles_merged = np.array(rectangles_merged)
    centroids = rectangles_merged[:,:2] + rectangles_merged[:,2:4]/2 
    return labels, rectangles_merged, centroids

# Classes
## XYZ 4x Sharpness
class XYZ4xSharpness:
    # Constructor
    def __init__(self, tracker) -> None:
        self.tracker = tracker
        self.PIXELS_MODE = 140
        self.DEVIATION_RATIO_THRESHOLD = 0.3
        self.KERNEL_DILATE = np.ones((13,13))
        self.KERNEL_ERODE = np.ones((7,7))
        self.IMG_BLUR_SIZE = 5
        return
    # Reset
    def reset(self):
        return
    # Detect
    def detect(self, img):
        ##################################################################
        # XY Detection
        img_size = img.size
        ### y is the first index and x is the second index in the image
        ny, nx = img.shape[:2]

        img_mask_objects = self.img_to_objects_mask(img)
        ## Worm(s)/Egg(s) Mask
        _ys, _xs = np.where(~img_mask_objects)
        img_mask_worms = img_mask_objects
        _, labels, rectangles, centroids = cv.connectedComponentsWithStats(
            img_mask_worms.astype(np.uint8)
        )  # output: num_labels, labels, stats, centroids
        centroids = centroids[:,::-1]  # convert to ij -> xy
        # Merge Overlaping or Close Rectangles
        rectangles = rectangles[
            rectangles[:,-1] >= self.tracker.SMALLES_TRACKING_OBJECT
        ]
        labels, rectangles_merged, centroids = merge_rectangles(
            labels, rectangles,
            threshold_ratio_overlap=0.1, threshold_distance=30
        )
        labels_background = set(labels[_xs, _ys])  # labels of background in worm compoenents
        label_values, label_counts = np.unique(labels.flatten(), return_counts=True)
        candidates_info = []
        for label_value, label_count, centroid in zip(label_values, label_counts, centroids):
            # Skip Background's Connected Component
            if label_value in labels_background:
                continue
            # If around the size of a worm
            pixel_ratio = label_count / img_size
            ## TODO: double check if previous condition works better of this one
            ## pixel_ratio <= self.tracker.PIXEL_RATIO_WORM_MAX and label_count >= self.tracker.SMALLES_TRACKING_OBJECT
            if label_count >= self.tracker.SMALLES_TRACKING_OBJECT:
                candidates_info.append([
                    labels == label_value,
                    centroid
                ])
        ## Select Worm from Candidates
        self.tracker.found_trackedworm = False
        img_mask_trackedworm = None
        idx_closest = None
        _d_center_closest = None
        if len(candidates_info) > 0:
            _center_previous = self.tracker.trackedworm_center \
                if self.tracker.tracking and self.tracker.trackedworm_center is not None else np.array([nx/2, ny/2])
            _size_lower = self.tracker.trackedworm_size*(1.0-self.tracker.TRACKEDWORM_SIZE_FLUCTUATIONS) if self.tracker.tracking and self.tracker.trackedworm_size is not None else 0.0
            _size_upper = self.tracker.trackedworm_size*(1.0+self.tracker.TRACKEDWORM_SIZE_FLUCTUATIONS) if self.tracker.tracking and self.tracker.trackedworm_size is not None else 0.0
            for idx, (mask, center) in enumerate(candidates_info):
                # Candidate Info
                _size = mask.sum()
                _d_center = np.max(np.abs(center - _center_previous))
                # Check Distance (center of image or worm if tracked)
                is_close_enough = _d_center <= self.tracker.TRACKEDWORM_CENTER_SPEED
                # Check Size if Tracked a Worm
                if _size_upper != 0.0:
                    is_close_enough = is_close_enough and (_size_lower <= _size <= _size_upper)
                # If Close Enough
                if is_close_enough:
                    self.tracker.found_trackedworm = True
                    if _d_center_closest is None or _d_center < _d_center_closest:
                        idx_closest = idx
                        _d_center_closest = _d_center
                        img_mask_trackedworm = mask
                        if self.tracker.tracking:
                                self.tracker.trackedworm_size = _size
                                self.tracker.trackedworm_center = center.copy()
            return img.copy()

        # Visualize Informations
        img_annotated = img.copy()

        # Worm Mask
        if self.tracker.found_trackedworm:
            ## Extend Worm Boundary
            img_mask_trackedworm_blurred = cv.blur(
                img_mask_trackedworm.astype(np.float32),
                (self.tracker.MASK_KERNEL_BLUR, self.tracker.MASK_KERNEL_BLUR)
            ) > 1e-4
            xs, ys = np.where(img_mask_trackedworm_blurred)
            x_min, x_max = minmax(xs)
            y_min, y_max = minmax(ys)
            self.img_trackedworm_cropped = img[
                x_min:(x_max+1),
                y_min:(y_max+1)
            ]
            self.tracker.x_worm = (x_min + x_max)//2
            self.tracker.y_worm = (y_min + y_max)//2

            # Z Calculations
            self.shrp_hist[self.tracker.shrp_idx] = self.calc_img_sharpness(
                self.img_trackedworm_cropped
            )
        else:
            self.tracker.x_worm, self.tracker.y_worm = None, None
            self.img_trackedworm_cropped = None
            self.tracker.vz = None
        ######################################################################################
        # Z Detection
        self.estimate_vz_by_sharpness()
        # Return
        return img_annotated
    # Image to Object Mask
    def img_to_objects_mask(self, img):
        img_blurred = cv.blur(img, (self.IMG_BLUR_SIZE, self.IMG_BLUR_SIZE))
        # Objects
        pixels_mode = self.PIXELS_MODE
        pixels_mode = find_mode_pixel(img_blurred)
        img_blurred_deviation = np.abs(img_blurred.astype(np.float32) - pixels_mode)/pixels_mode
        img_objects = (img_blurred_deviation >= self.DEVIATION_RATIO_THRESHOLD).astype(np.float32)
        # Erode -> Remove Small Objects
        img_objects_eroded = cv.erode(
            img_objects,
            self.KERNEL_ERODE
        )
        # Dilate -> Expand
        img_objects_dilated = cv.dilate(
            img_objects_eroded,
            self.KERNEL_DILATE
        )
        # Connected Components
        _, labels, rectangles, _ = cv.connectedComponentsWithStats(
            img_objects_dilated.astype(np.uint8)
        )
        for i, rectangle in enumerate(rectangles):
            _size = rectangle[-1]
            if _size <= self.tracker.SMALLES_TRACKING_OBJECT:
                indices = labels == i
                labels[indices] = 0
        # Mask
        mask = labels > 0
        return mask
    # Estimate Vz by Sharpness
    def estimate_vz_by_sharpness(self):
        if self.tracker.shrp_idx == (self.tracker.shrp_hist_size-1):
            # Coarse Sharpness Change
            _n = self.tracker.shrp_hist_size//2
            shrp_old = np.nanmean(self.tracker.shrp_hist[:_n])
            shrp_new = np.nanmean(self.tracker.shrp_hist[_n:])
            # Stop or Move
            if np.isnan(shrp_old) or np.isnan(shrp_new) or self.tracker.vz is None:
                self.tracker.vz = 0
            elif self.tracker.vz == 0:
                self.tracker.vz = self.tracker.VZ_MAX
            elif shrp_old > shrp_new:
                self.tracker.vz = -self.tracker.vz
            # Shift New to Old
            self.tracker.shrp_hist[:_n] = self.tracker.shrp_hist[_n:]
            self.tracker.shrp_idx = _n
        else:
            self.tracker.shrp_idx += 1
        return
    
    def calc_line_sharpness(self, arr1d):
        i_min, i_max = np.argmin(arr1d), np.argmax(arr1d)
        v_min, v_max = arr1d[i_min], arr1d[i_max]
        il, ir = (i_min, i_max) if i_min <= i_max else (i_max, i_min)
        if v_max == v_min:
            return np.nan
        values = (arr1d[il:(ir+1)] - v_min)/(v_max - v_min)
        shrp = np.sum( np.diff(values)**2 )
        return shrp

    def calc_horizontal_sharpness(self, img, x, points, points_extended):
        # Slice Bounds
        y_min, y_max = minmax(points[1][
            points[0] == x
        ])
        y_ext_min, y_ext_max = minmax(points_extended[1][
            points_extended[0] == x
        ])
        # Enough Points
        if y_max - y_min <= self.tracker.SHARPNESS_MIN_LENGTH:
            return np.nan
        # Sharpnesses
        shrp1 = self.calc_line_sharpness(img[
            x, y_ext_min:(y_min+1+self.tracker.SHARPNESS_PADDING)
        ])
        shrp2 = self.calc_line_sharpness(img[
            x, (y_max-self.tracker.SHARPNESS_PADDING):(y_ext_max+1)
        ])
        shrp = (shrp1+shrp2)/2
        # Return
        return shrp

    def calc_vertical_sharpness(self, img, y, points, points_extended):
        # Slice Bounds
        x_min, x_max = minmax(points[0][
            points[1] == y
        ])
        x_ext_min, x_ext_max = minmax(points_extended[0][
            points_extended[1] == y
        ])
        # Enough Points
        if x_max - x_min <= self.tracker.SHARPNESS_MIN_LENGTH:
            return np.nan
        # Sharpnesses
        shrp1 = self.calc_line_sharpness(img[
            x_ext_min:(x_min+1+self.tracker.SHARPNESS_PADDING), y
        ])
        shrp2 = self.calc_line_sharpness(img[
            (x_max-self.tracker.SHARPNESS_PADDING):(x_ext_max+1), y
        ])
        shrp = (shrp1+shrp2)/2
        # Return
        return shrp

    def calc_img_sharpness(self, img):
        # Threshold and Blur
        img_thrshld = img <= self.tracker.MASK_WORM_THRESHOLD
        img_thrshld_medblur = cv.medianBlur(
            img, self.tracker.MASK_MEDIAN_BLUR
        ) <= (self.tracker.MASK_WORM_THRESHOLD_BLURED)
        # Mask and Extentsion
        img_mask = img_thrshld & img_thrshld_medblur
        img_mask_extended = cv.blur(
            img_thrshld_medblur.astype(np.float32),
            (self.tracker.MASK_KERNEL_BLUR, self.tracker.MASK_KERNEL_BLUR)
        ) > 0
        # Points
        xs, ys = np.where(img_mask)
        xs_unique, ys_unique = np.unique(xs), np.unique(ys)
        points = np.array([xs,ys])
        points_extended = np.array(np.where(img_mask_extended))
        # Empty
        if len(points) == 0 or len(points_extended) == 0:
            return np.nan
        # Sharpness
        samples_x = np.random.choice(xs_unique, size=self.tracker.SHRPNESS_SAMPLES, replace=False) \
            if self.tracker.SHRPNESS_SAMPLES < len(xs_unique) else xs_unique
        shrpn_x_avg = np.nanmean([
            self.tracker.calc_horizontal_sharpness(
                img,
                x,
                points, points_extended
            ) for x in samples_x
        ])
        samples_y = np.random.choice(ys_unique, size=self.tracker.SHRPNESS_SAMPLES, replace=False) \
            if self.tracker.SHRPNESS_SAMPLES < len(ys_unique) else ys_unique
        shrpn_y_avg = np.nanmean([  # TODO: This gives warning!!!
            self.calc_vertical_sharpness(
                img,
                y,
                points, points_extended
            ) for y in samples_y
        ])
        shrp = (shrpn_x_avg+shrpn_y_avg)/2
        # Return
        return shrp