import numpy as np
import os
import onnxruntime
from skimage import filters
import cv2 as cv
import time


IMG_BLUR_SIZE = 5
KERNEL_DILATE = np.ones((13,13))
KERNEL_ERODE = np.ones((7,7))
SMALLEST_TRACKING_OBJECT = 200
SIZE_FLUCTUATIONS = 0.25
CENTER_SPEED = 100
MASK_MEDIAN_BLUR = 9
MASK_KERNEL_BLUR = 5


class Detector():
    
    def __init__(self, tracker, gui_fp):
        self.tracker = tracker
        self.ort_xy10x = onnxruntime.InferenceSession(os.path.join(gui_fp, r'openautoscopev2/models/10x.onnx'))
        self.ort_xy10x_all = onnxruntime.InferenceSession(os.path.join(gui_fp, r'openautoscopev2/models/10x_all.onnx'))
        self.ort_xy10x_all_with_noise = onnxruntime.InferenceSession(os.path.join(gui_fp, r'openautoscopev2/models/10x_all_with_noise.onnx'))
        self.ort_xy10x_all_focus = onnxruntime.InferenceSession(os.path.join(gui_fp, r'openautoscopev2/models/10x_all_focus_model109.onnx'))
        # DEBUG
        self.DEBUG_counter = 0
        self.DEBUG_total_time_XYtracker = 0.0
        self.DEBUG_total_time_autofocus = 0.0

    def default(self, img):
        self.tracker.found_trackedworm = False
        return img
    
    def xy4x(self, img):
        frame = img.copy()
        ny, nx = frame.shape[:2]
        otsu = filters.threshold_otsu(frame)
        threshold = 1.2 * otsu if otsu > 50 else 110
        img_mask_objects = img_to_object_mask_threshold(frame, threshold=threshold)
        _ys, _xs = np.where(~img_mask_objects)
        _, labels, _, centroids = cv.connectedComponentsWithStats(
            img_mask_objects.astype(np.uint8)
        ) 
        centroids = centroids[:,::-1]
        labels_background = set(labels[_ys, _xs])
        label_values, label_counts = np.unique(labels.flatten(), return_counts=True)
        candidates_info = []
        for label_value, label_count, centroid in zip(label_values, label_counts, centroids):
            if label_value in labels_background:
                continue
            if label_count >= SMALLEST_TRACKING_OBJECT:
                candidates_info.append([
                    labels == label_value,
                    centroid
                ])
        self.tracker.found_trackedworm = False
        img_mask_trackedworm = None
        _d_center_closest = None
        if len(candidates_info) > 0:
            _center_previous = self.tracker.trackedworm_center \
                if self.tracker.tracking and self.tracker.trackedworm_center is not None else np.array([ny/2, nx/2])
            _size_lower = self.tracker.trackedworm_size*(1.0-SIZE_FLUCTUATIONS) if self.tracker.tracking and self.tracker.trackedworm_size is not None else 0.0
            _size_upper = self.tracker.trackedworm_size*(1.0+SIZE_FLUCTUATIONS) if self.tracker.tracking and self.tracker.trackedworm_size is not None else 0.0
            for _, (mask, center) in enumerate(candidates_info):
                _size = mask.sum()
                _d_center = np.max(np.abs(center - _center_previous))
                is_close_enough = _d_center <= CENTER_SPEED
                if _size_upper != 0.0:
                    is_close_enough = is_close_enough and (_size_lower <= _size <= _size_upper)
                if is_close_enough:
                    self.tracker.found_trackedworm = True
                    if _d_center_closest is None or _d_center < _d_center_closest:
                        _d_center_closest = _d_center
                        img_mask_trackedworm = mask
                        if self.tracker.tracking:
                                self.tracker.trackedworm_size = _size
                                self.tracker.trackedworm_center = center.copy()

        if self.tracker.found_trackedworm:
            img_mask_trackedworm_blurred = cv.blur(
                img_mask_trackedworm.astype(np.float32),
                (MASK_KERNEL_BLUR, MASK_KERNEL_BLUR)
            ) > 1e-4
            ys, xs = np.where(img_mask_trackedworm_blurred)
            y_min, y_max = minmax(ys)
            x_min, x_max = minmax(xs)
            self.tracker.x_worm = (x_min + x_max)//2
            self.tracker.y_worm = (y_min + y_max)//2

            frame = cv.rectangle(frame, (x_min, y_min), (x_max, y_max), 255, 2)
        frame = cv.circle(frame, (255, 255), radius=2, color=255, thickness=2)
        
        return frame

    def xy10x(self, img):
        frame = img.copy()
        self.tracker.found_trackedworm = True
        frame_cropped = frame[56:-56,56:-56]
        batch_1_400_400 = {
            'input': np.repeat(
                frame_cropped[None, None, :, :], 3, 1
            ).astype(np.float32)
        }
        ort_outs = self.ort_xy10x.run( None, batch_1_400_400 )
        # The network is trained to output (x, y)
        self.tracker.x_worm, self.tracker.y_worm = ort_outs[0][0].astype(np.int64) + 56

        frame = cv.circle(frame, (int(self.tracker.x_worm), int(self.tracker.y_worm)), radius=10, color=255, thickness=2)
        frame = cv.circle(frame, (255, 255), radius=2, color=255, thickness=2)

        return frame

    def xy10x_all(self, img):
        frame = img.copy()
        self.tracker.found_trackedworm = True
        batch_1_512_512 = {
            'input': np.repeat(
                frame[None, None, :, :], 3, 1
            ).astype(np.float32)
        }
        # The network is trained to output (x, y)
        _start = time.time()
        ort_outs = self.ort_xy10x_all.run( None, batch_1_512_512 )
        self.tracker.x_worm, self.tracker.y_worm = ort_outs[0][0].astype(np.int64)
        _duration = time.time() - _start
        self.DEBUG_total_time_XYtracker += _duration
        # Network predicts z-focus
        _start = time.time()
        ort_outs = self.ort_xy10x_all_focus.run( None, batch_1_512_512 )
        self.tracker.z_worm_focus = np.float32(ort_outs[0][0][0])
        _duration = time.time() - _start
        self.DEBUG_total_time_autofocus += _duration
        self.DEBUG_counter += 1
        if self.DEBUG_counter%300 == 0:
            print("Average inference XY/focus: {:>5.3f}/{:>5.3f} (ms)".format(
                1000*self.DEBUG_total_time_XYtracker/self.DEBUG_counter,
                1000*self.DEBUG_total_time_autofocus/self.DEBUG_counter
            ))

        frame = cv.circle(frame, (int(self.tracker.x_worm), int(self.tracker.y_worm)), radius=10, color=255, thickness=2)
        frame = cv.circle(frame, (255, 255), radius=2, color=255, thickness=2)

        return frame
    
    def xy10x_all_with_noise(self, img):
        frame = img.copy()
        self.tracker.found_trackedworm = True
        batch_1_512_512 = {
            'input': np.repeat(
                frame[None, None, :, :], 3, 1
            ).astype(np.float32)
        }
        # The network is trained to output (x, y)
        _start = time.time()
        ort_outs = self.ort_xy10x_all_with_noise.run( None, batch_1_512_512 )
        self.tracker.x_worm, self.tracker.y_worm = ort_outs[0][0].astype(np.int64)
        _duration = time.time() - _start
        self.DEBUG_total_time_XYtracker += _duration
        # Network predicts z-focus
        _start = time.time()
        ort_outs = self.ort_xy10x_all_focus.run( None, batch_1_512_512 )
        self.tracker.z_worm_focus = np.float32(ort_outs[0][0][0])
        _duration = time.time() - _start
        self.DEBUG_total_time_autofocus += _duration
        self.DEBUG_counter += 1
        if self.DEBUG_counter%300 == 0:
            print("Average inference XY/focus: {:>5.3f}/{:>5.3f} (ms)".format(
                1000*self.DEBUG_total_time_XYtracker/self.DEBUG_counter,
                1000*self.DEBUG_total_time_autofocus/self.DEBUG_counter
            ))

        frame = cv.circle(frame, (int(self.tracker.x_worm), int(self.tracker.y_worm)), radius=10, color=255, thickness=2)
        frame = cv.circle(frame, (255, 255), radius=2, color=255, thickness=2)

        return frame

def minmax(arr):
    return np.min(arr), np.max(arr)

def img_to_object_mask_threshold(img, threshold):
    img_blurred = cv.blur(img, (IMG_BLUR_SIZE, IMG_BLUR_SIZE))
    img_objects = (img_blurred < threshold).astype(np.float32)
    img_objects_eroded = cv.erode(img_objects, KERNEL_ERODE).astype(np.float32)
    img_objects_dilated = cv.dilate(img_objects_eroded, KERNEL_DILATE).astype(np.float32)
    _, labels, rectangles, _ = cv.connectedComponentsWithStats(img_objects_dilated.astype(np.uint8))
    for i, rectangle in enumerate(rectangles):
        _size = rectangle[-1]
        if _size <= SMALLEST_TRACKING_OBJECT:
            indices = labels == i
            labels[indices] = 0
    mask = labels > 0
    return mask