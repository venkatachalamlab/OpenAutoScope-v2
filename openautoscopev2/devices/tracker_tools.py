import numpy as np
import os
import json
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


class TrackerModels:

    def __init__(self, tracker, gui_fp):
        self.gui_fp = gui_fp
        self.tracker = tracker
        # Initial load
        self.models_json = dict()
        self.ort_dict = dict()
        self.selected_tracking_mode = None
        self.selected_focus_mode = None
        self.load_models()
        # Reporting prcessing time
        self.verbose_cycle_counter = 0
        self.verbose_total_time_XYtracker = 0.0
        self.verbose_total_time_autofocus = 0.0
        

    def load_models(self):
        # Load `models.json`
        fp_models_json = os.path.join(self.gui_fp, 'models.json')
        if not os.path.exists(fp_models_json):
            self.tracker._send_log( f"<TrackerModels> File does not exist! {fp_models_json}" )
            return
        ## Load models info
        with open(fp_models_json, "r") as in_file:
            self.models_json = json.load(in_file)
        ## Load ONNX sessions
        for model_key, entry in self.models_json.items():
            # Skip thresholding model
            if entry['path'].strip() == "":
                continue
            # Check model path
            fp_model = os.path.join(self.gui_fp, entry['path'])
            if not os.path.exists(fp_model):
                self.tracker._send_log( f"<TrackerModels> Model file does not exist! {fp_model}" )
                continue
            # Load inference runtime
            self.ort_dict[model_key] = onnxruntime.InferenceSession(fp_model)
        # # Tracking Models
        # self.ort_xy10x = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x.onnx'))
        # self.ort_xy10x_all = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_all.onnx'))
        # self.ort_xy10x_all_with_noise = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_all_with_noise.onnx'))
        # self.ort_xy10x_all_with_highnoise_SCL_L1 = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_20241017_DepNet16SC_dropout000_datasetfinal_high_noised_L1_lr1e3_318.onnx'))
        # self.ort_xy10x_all_with_highnoise_SCL_L2 = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_20241017_DepNet16SC_dropout000_datasetfinal_high_noised_350.onnx'))
        # self.ort_xy4x_all_with_noise = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/4x_all_with_noise.onnx'))
        # # Focus Models
        # self.ort_xy10x_all_focus = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_all_focus_model109.onnx'))
        # self.ort_xy10x_all_with_highnoise_SCL_focus = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/10x_20241017_DepNet16FocusSC_dropout000_high_noised_L1_lr1e2_444.onnx'))
        # self.ort_xy4x_all_focus_with_noise = onnxruntime.InferenceSession(os.path.join(self.gui_fp, r'openautoscopev2/models/4x_all_focus_with_noise.onnx'))
        return

    def detect(self, img):
        img_annotated = img
        # Z focus
        ## Set this parameters: self.tracker.z_worm_focus
        if self.selected_focus_mode is None or self.selected_focus_mode == "":
            self.tracker.z_worm_focus = None
        else:
            model_key = f"focus_{self.selected_focus_mode}"
            z_focus_sign = float(self.models_json[model_key]['sign'])
            ort_runtime = self.ort_dict[model_key]
            img_annotated = self.z_focus_single_channel_full_image(img_annotated, ort_runtime, sign=z_focus_sign)

        # XY tracking
        ## Set these two: self.tracker.x_worm, self.tracker.y_worm = ort_outs[0][0].astype(np.int64)
        if self.selected_tracking_mode is None or self.selected_tracking_mode == "":
            self.tracker.x_worm, self.tracker.y_worm = None, None
        elif self.selected_tracking_mode == "xy_threshold":
            img_annotated = self.xy_threshold(img_annotated)
        else:
            model_key = f"tracking_{self.selected_tracking_mode}"
            ort_runtime = self.ort_dict[model_key]
            img_annotated = self.xy_tracking_single_channel_full_image(img_annotated, ort_runtime)

        # Reports
        self.verbose_cycle_counter += 1
        if self.verbose_cycle_counter%300 == 0:
            # Print to CMD
            print("Average inference XY/focus: {:>5.3f}/{:>5.3f} (ms)".format(
                1000*self.verbose_total_time_XYtracker/self.verbose_cycle_counter,
                1000*self.verbose_total_time_autofocus/self.verbose_cycle_counter
            ))
            # Reset
            self.verbose_cycle_counter = 0
            self.verbose_total_time_XYtracker = 0.0
            self.verbose_total_time_autofocus = 0.0

        # Return
        return img_annotated

    def set_tracking_mode(self, tracking_mode):
        self.selected_tracking_mode = tracking_mode
        return
    def set_focus_mode(self, focus_mode):
        self.selected_focus_mode = focus_mode
        return

    def default(self, img):
        self.tracker.found_trackedworm = False
        self.selected_tracking_mode = None
        self.selected_focus_mode = None
        return img

    def xy_threshold(self, img):
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
    
    def xy_tracking_single_channel_full_image(self, img, ort_runtime):
        frame = img.copy()
        self.tracker.found_trackedworm = True
        batch_1_512_512 = {
            'input': frame[np.newaxis, np.newaxis, :, :].astype(np.float32),
        }
        # The network is trained to output (x, y)
        _start = time.time()
        ort_outs = ort_runtime.run( None, batch_1_512_512 )
        self.tracker.x_worm, self.tracker.y_worm = ort_outs[0][0].astype(np.int64)
        _duration = time.time() - _start
        self.verbose_total_time_XYtracker += _duration
        

        frame = cv.circle(frame, (int(self.tracker.x_worm), int(self.tracker.y_worm)), radius=10, color=255, thickness=2)
        frame = cv.circle(frame, (255, 255), radius=2, color=255, thickness=2)

        return frame
    
    def z_focus_single_channel_full_image(self, img, ort_runtime, sign):
        frame = img.copy()
        # Network predicts z-focus
        batch_1_512_512 = {
            'input': frame[np.newaxis, np.newaxis, :, :].astype(np.float32),
        }
        _start = time.time()
        ort_outs = ort_runtime.run( None, batch_1_512_512 )
        self.tracker.z_worm_focus = np.float32(ort_outs[0][0][0]) * sign
        _duration = time.time() - _start
        self.verbose_total_time_autofocus += _duration
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