# Modules
import os, gc
import time
import pickle
from pathlib import Path
from tqdm import tqdm
from glob import glob
import numpy as np
import matplotlib.pyplot as plt
import cv2 as cv
from openautoscopev2.devices.utils_data import (
    load_process_log_files, load_files_data_times, SerializeDatas,
    change_binning, ImgToProcess
)
from openautoscopev2.zmq.client import GUIClient

# Parameters
## 10x
DIFF_COORDS_TO_PIXELS_10x = np.array([
    [ 0.00, 1.1],
    [-1.2, 0.00],
], dtype=np.float64)
MM_PER_PIXEL_10x = 1/512
MASK_MEDIAN_BLUR_SIZE_10x = 51
MASK_THRESHOLD_10x = 2
## 4x
DIFF_COORDS_TO_PIXELS_4x = np.array([
    [ 0.00, 0.55],
    [-0.60, 0.00],
], dtype=np.float64)
MM_PER_PIXEL_4x = 1/410  # Calibrated with 1mm slide, 410 pixels corresponded to 1mm vertically
MASK_MEDIAN_BLUR_SIZE_4x = 31  # previous 31  TODO: change this, 25 worked
MASK_THRESHOLD_4x = 2  # 10 before, TODO: change this, 2 worked
SIZE_SMALLEST_FOREGROUND_4X = 50
## Select
MASK_THRESHOLD = MASK_THRESHOLD_4x
SIZE_SMALLEST_FOREGROUND = SIZE_SMALLEST_FOREGROUND_4X
MASK_MEDIAN_BLUR_SIZE = MASK_MEDIAN_BLUR_SIZE_4x
DIFF_COORDS_TO_PIXELS = DIFF_COORDS_TO_PIXELS_4x
MM_PER_PIXEL = MM_PER_PIXEL_4x
UM_PER_PIXEL = 1000*MM_PER_PIXEL

# Methods
def pdump(obj, fp_write):
    with open(fp_write, 'wb') as out_file:
        pickle.dump(obj, out_file)
    return
def img_remove_small_objects(img_mask, size_threshold = 20):
    n_labels, labels, stats, _ = cv.connectedComponentsWithStats(img_mask.astype(np.uint8))
    img_mask_refined = np.zeros_like(img_mask, dtype=np.bool_)
    for label in range(1, n_labels):
        obj_area = stats[label,-1]
        if obj_area > size_threshold:
            img_mask_refined |= labels == label
    return img_mask_refined
def fp_folder_to_combined_frame(fp_folder: str, idx_start: int = 0, include_subfolders: bool = False, save_frame: bool = True):
    global DIFF_COORDS_TO_PIXELS
    # TODO: these were set based on 10x, should change for 4x?
    LX, LY = 500, 512  # Bound on RIGHT to select from each image
    LX2, LY2 = 30, 0 # Bound on LEFT to select from each image
    ############################################################
    # Connect to data
    _wildcard = os.path.join( fp_folder, "*_behavior" ) if include_subfolders else fp_folder
    files, datas, times = load_files_data_times( _wildcard )
    series = SerializeDatas(datas)
    ## Change image to 512*512 by binning
    _, _nx, _ny = series.shape
    if _nx != 512:
        _binning = _nx//512
        def do_img_beh(img):
            return change_binning(img, _binning)
        series = ImgToProcess(series, fn_process=do_img_beh)
    n_imgs, nx, ny = series.shape
    times = np.concatenate([ t[:] for t in times ])
    ############################################################
    # Load Logs
    _fp_folder_logs = fp_folder if include_subfolders else str(Path(fp_folder).parent)
    log_states, log_times = load_process_log_files( _fp_folder_logs )
    # Interpolate xy stage coordinates
    coords_scanning = np.zeros((n_imgs, 2))
    for idx_col in range(2):
        coords_scanning[:,idx_col] = np.interp(times, log_times, log_states[:, idx_col])
    ############################################################
    # Make collage
    _diff_coords = coords_scanning-coords_scanning[[idx_start]]
    pixel_diffs_di_dj = np.matmul( _diff_coords, DIFF_COORDS_TO_PIXELS ).astype(np.int64)
    idx_img_by_distance = np.argsort(
        np.linalg.norm(_diff_coords, axis=1)
    )
    
    _idx_min, _idx_max = pixel_diffs_di_dj.min(), pixel_diffs_di_dj.max()
    r0 = coords_scanning[idx_start]
    p0 = np.array([nx//2,ny//2])-_idx_min
    _frame_size = (_idx_max - _idx_min)+1+512  # CAUTION: BASED ON IMAGE WIDTHS. hard coded for now!
    print("Frame Width/Height:", _frame_size)
    frame = np.zeros((_frame_size, _frame_size), dtype=np.uint8)
    frame_min = np.zeros((_frame_size, _frame_size), dtype=np.uint8) + 255
    frame_mask_food = np.zeros((_frame_size, _frame_size), dtype=np.bool_)
    for idx_img in tqdm( idx_img_by_distance ):
        i, j = pixel_diffs_di_dj[idx_img]-_idx_min
        img = series[idx_img][LX2:LX, LY2:LY]
        # Image
        frame[(i+LX2):(i+LX), (j+LY2):(j+LY)] = img
        # Minimum
        frame_min[(i+LX2):(i+LX), (j+LY2):(j+LY)] = np.minimum(
            frame_min[(i+LX2):(i+LX), (j+LY2):(j+LY)],
            img
        )
        # Mask
        # TODO: numbers set based on 10x, change for 4x?
        img_blur_small = cv.GaussianBlur(img, (31,31), 2.0).astype(np.float32)
        img_blur_large = cv.GaussianBlur(img, (31,31), 5.0).astype(np.float32)
        img_mask = np.abs(img_blur_small - img_blur_large) > MASK_THRESHOLD
        img_mask = img_remove_small_objects(img_mask, size_threshold=SIZE_SMALLEST_FOREGROUND)
        frame_mask_food[(i+LX2):(i+LX), (j+LY2):(j+LY)] |= img_mask
    ############################################################################################
    # Close files
    [ f.close() for f in files ]
    # Save figure
    if save_frame:
        ## Food
        fp_write_figure = os.path.join( fp_folder, "frame_food.png" )
        plt.ioff()
        plt.figure(figsize=(20,20))
        plt.imshow(frame, cmap='gray')
        plt.savefig(fp_write_figure, bbox_inches='tight')
        plt.close('all')
        ## Mask
        fp_write_figure = os.path.join( fp_folder, "frame_mask_food.png" )
        plt.ioff()
        plt.figure(figsize=(20,20))
        plt.imshow(frame_mask_food, cmap='gray')
        plt.savefig(fp_write_figure, bbox_inches='tight')
        plt.close('all')
    # Return
    _ = gc.collect()
    return frame, frame_min, frame_mask_food, (p0, r0)
def frame_mask_food_to_contour_food( frame_mask_food: np.ndarray, fp_write_figure: str = None ):
    # Find background
    # TODO: numbers set based on 10x, change for 4x?
    frame_mask = (cv.medianBlur(frame_mask_food.astype(np.uint8), MASK_MEDIAN_BLUR_SIZE) == 0).astype(np.uint8)
    n_labels, labels, stats, centroids = cv.connectedComponentsWithStats(frame_mask)
    # Complement of foregroun on sides
    frame_mask = labels != np.mean(labels[0,:]).round(0)
    # Largest background object
    n_labels, labels, stats, centroids = cv.connectedComponentsWithStats(frame_mask.astype(np.uint8))
    frame_mask = (labels == ( np.argmax(stats[1:,-1])+1 )).astype(np.uint8)
    # Contour region region
    contours, _ = cv.findContours(frame_mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    contour_food = contours[0]
    # Convert to Convex Hull
    contour_food = cv.convexHull(contour_food)
    # Save figure
    if fp_write_figure is not None:
        ## Mask
        plt.ioff()
        plt.figure(figsize=(20,20))
        plt.imshow(frame_mask, cmap='gray')
        plt.plot(contour_food[:,0,0], contour_food[:,0,1], 'r.-')
        plt.savefig(fp_write_figure, bbox_inches='tight')
        plt.close('all')
    # Return
    _ = gc.collect()
    return frame_mask, contour_food
def distance_to_foodpatch_um( r, r0, p0, contour_food ):
    # Displacement in stage coordinates
    dr = (r-r0)
    # Displacement in pixel coordinates
    dp = np.matmul( dr, DIFF_COORDS_TO_PIXELS )
    # Correct for XY difference
    p = p0 + dp[::-1]
    # Distance
    # Convention: positive -> outside, negative -> inside, zero -> on the contour
    d_pixels = -cv.pointPolygonTest(
        contour_food, p,
        True
    )
    d_um = d_pixels * UM_PER_PIXEL
    # Return
    return d_um
# def contour_food_r_from_entry( entry ):
#     p0, r0 = entry['p0_r0']
#     contour_food_r = r0 + np.matmul(
#         (entry['contour_food']-p0[np.newaxis, np.newaxis,:])[:,:,::-1],
#         np.linalg.pinv(DIFF_COORDS_TO_PIXELS)
#     )
#     return contour_food_r
# def r_to_p_for_a_patch(r, r0, p0):
#     # Displacement in stage coordinates
#     dr = (r-r0)
#     # Displacement in pixel coordinates
#     dp = np.matmul( dr, DIFF_COORDS_TO_PIXELS )
#     # Correct for XY difference
#     p = p0 + dp[::-1]
#     # Return
#     return p

# Classes
class ExperimentFoodPatchTimed:
    # Constructor
    def __init__(
            self,
            d_turn_on_outside_um: float, t_turn_on_after_entry_s: float, t_rest_between_exposures_s: float,
            fp_folder_scan: str,
            client: GUIClient
        ):
        # Paremeters
        self.name = 'EXPERIMENT_FOOD_PATCH_TIMED'
        self.initialization_text = "Load FoodPatch Scans"
        self.d_turn_on_outside_um = d_turn_on_outside_um
        self.t_turn_on_after_entry_s = t_turn_on_after_entry_s
        self.t_rest_between_exposures_s = t_rest_between_exposures_s
        self.fp_folder_scan = fp_folder_scan
        self.client = client
        ## States
        self.states_possible = {
            'off',  # Off food and further than `d_turn_on_outside_um` away from food boundary
            'food-outside-close',  # Off food and closer than `d_turn_on_outside_um` to food boundary
            'food-contacted-timing',  # Contacted food boundary, so LED will be on for `t_turn_on_after_entry_s` seconds
            'cooldown'  # LED exposure finished, giving worm some rest before another round of exposure. Also it needs to exit food before another round of exposure.
        }
        self.state = 'off'
        self.client.turn_off_blue_led()
        # Log
        msg = f"initial state: -> off"
        self.log(msg)
        # State transitions:
        # off -> food-outside-close
        # food-outside-close -> off, food-contacted-timing
        # food-contacted-timing -> cooldown
        # cooldown -> off, food-outside-close
        # Food patch processing
        self.food_patch_infos = dict()
        self.is_initialized = False
        
        return
    
    # Initialize
    def initialize(self, fp_folder: str):
        if self.is_initialized:
            print("ALREADY INITIALIZED.")
            return
        if fp_folder is None:
            print("PATH VARIABLE IS NONE!")
            return
        # Skip if no scanned food patch
        fp_folder_scan = os.path.join( fp_folder, "foodscan" )
        if not os.path.exists(fp_folder_scan):
            print("PATH TO FOOD SCAN DOES NOT EXIST!")
            print(f"path: {fp_folder_scan}")
            return
        self.fp_folder_scan = fp_folder_scan
        if self.fp_folder_scan is not None:
            self.extract_food_patch_infos()
            self.is_initialized = True
        return

    # State
    def set_state(self, **kwargs):
        # Update coords
        stage_coords = kwargs["CLIENT-STAGE-COORDS"]
        self.set_coords(stage_coords)
        # Calculate distance if any patch is loaded
        if self.fp_folder_scan is None or not self.is_initialized:
            return
        self.calc_d_min_patches()
        # State transitions
        ## off
        if self.state == 'off':
            # Did it get close to any patch?
            if self.any_patch_closer_than_d():
                _state_prev = self.state
                self.state = 'food-outside-close'
                self.client.turn_on_blue_led()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        elif self.state == 'food-outside-close':
            # Did it get far away?
            if not self.any_patch_closer_than_d():
                _state_prev = self.state
                self.state = 'off'
                self.client.turn_off_blue_led()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
            elif self.d_min_patches <= -100:  # inside food deeper than 50um
                _state_prev = self.state
                self.state = 'food-contacted-timing'
                self.client.turn_on_blue_led()
                self.time_foodentry = time.time()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        elif self.state == 'food-contacted-timing':  # inside food, now timed exposure
            if (time.time() - self.time_foodentry) >= self.t_turn_on_after_entry_s:
                _state_prev = self.state
                self.state = 'cooldown'
                self.client.turn_off_blue_led()
                self.time_cooldown_start = time.time()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        elif self.state == 'cooldown':  # give worm some time to recover from the exposure
            # if (time.time() - self.time_cooldown_start) >= self.t_rest_between_exposures_s and not self.any_patch_closer_than_d():
            if (time.time() - self.time_cooldown_start) >= self.t_rest_between_exposures_s and self.d_min_patches > 200:
                _state_prev = self.state
                self.state = 'off'
                self.client.turn_off_blue_led()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        # Return
        return
    
    # Coords
    def set_coords(self, stage_coords):
        self.stage_coords = stage_coords
        self.r = np.array(self.stage_coords[:2])  # only take stage x-y coords into account
        return
    
    # Any patch closer than `d_turn_on_outside_um`
    def any_patch_closer_than_d(self):
        return self.d_min_patches <= self.d_turn_on_outside_um
    
    # Is off food
    def outside_all_patches(self):
        return self.d_min_patches > 0
    
    # Minimum distance to patches (used for "how far inside")
    def calc_d_min_patches(self):
        idx_foodpatch_closest = -1
        d_min_patches = None
        for idx_foodpatch, entry_foodpatch in self.food_patch_infos.items():
            p0, r0 = entry_foodpatch['p0_r0']
            d_to_patch_um = distance_to_foodpatch_um(
                self.r,
                r0, p0, entry_foodpatch['contour_food']
            )
            if d_min_patches is None or d_min_patches > d_to_patch_um:
                d_min_patches = d_to_patch_um
                idx_foodpatch_closest = idx_foodpatch
        self.d_min_patches = float(d_min_patches)
        self.idx_foodpatch_closest = idx_foodpatch_closest
        # Log
        msg = f"Closest food patch idx/distance (um): {self.idx_foodpatch_closest}/{self.d_min_patches}"
        self.log(msg)
        return
    
    # Extract food patch infos
    def extract_food_patch_infos(self):
        # Extract patch from each folder
        fp_folders = sorted(glob(
            os.path.join(self.fp_folder_scan, "*_behavior")
        ))
        # Recording to perimeter infos
        for idx, fp_folder in enumerate(tqdm(fp_folders, desc='Loading food patch scans: ')):
            idx_center = 0  # Convention is to start recording on the edge of the food boundary
            entry = {
                'idx_center': idx_center,
                'fp_folder': fp_folder,
            }
            # Load data into a collaged/unified frame
            frame, frame_min, frame_mask_food, (p0, r0) = fp_folder_to_combined_frame( fp_folder, idx_start=idx_center )
            # Use mask to extract contours in (local) pixel coordinates
            fp_write_masked_contour = os.path.join(fp_folder, "frame_masked_food_contour.png")
            frame_mask_contour, contour_food = frame_mask_food_to_contour_food( frame_mask_food, fp_write_figure=fp_write_masked_contour )
            # Store infos
            entry['frame'] = frame
            entry['frame_min'] = frame_min
            entry['frame_mask_food'] = frame_mask_food
            entry['p0_r0'] = (p0, r0)
            entry['frame_mask_contour'] = frame_mask_contour
            entry['contour_food'] = contour_food
            self.food_patch_infos[idx] = entry
            # Store infos as Pickle
            fp_write_foodpatch_infos = os.path.join(fp_folder, "foodpatch_infos.pkl")
            pdump(entry, fp_write_foodpatch_infos)
        # Return
        return
    
    # Ping time
    def ping_time(self):
        return

    # Log through client
    def log(self, msg: str):
        self.client.log( f"<{self.name}> {msg}" )


# Classes
class ExperimentPeriodicExposure:
    # Constructor
    def __init__(
            self,
            duration_exposure_seconds: float,
            duration_rest_seconds: float,
            client: GUIClient
        ):
        # Paremeters
        self.name = 'EXPERIMENT_PERIODIC_EXPOSURE'
        self.initialization_text = "Start periodic exposure"
        self.duration_exposure_seconds = duration_exposure_seconds
        self.duration_rest_seconds = duration_rest_seconds
        self.client = client
        ## States
        self.states_possible = {
            'off',  # Experiment has not started yet
            'exposure',  # Expose for specific duration
            'cooldown',  # Let the worm/fleuroscent agents recover for duration
        }
        self.state = 'off'
        self.client.turn_off_blue_led()
        # Log
        msg = f"initial state: -> off"
        self.log(msg)
        # State transitions:
        # off -> exposure
        # exposure -> cooldown
        # cooldown -> exposure
        # Food patch processing
        self.is_initialized = False
        self.timestamp_state_started = None
        
        return
    
    # Initialize
    def initialize(self, fp_folder: str):
        if self.is_initialized:
            print("ALREADY INITIALIZED.")
            return
        # Start for the first time
        self.is_initialized = True
        _state_prev = self.state
        self.state = 'exposure'
        self.client.turn_on_blue_led()
        self.timestamp_state_started = time.time()
        # Log
        msg = f"state transition: {_state_prev} -> {self.state}"
        self.log(msg)
        return

    # State
    def set_state(self, **kwargs):
        # Ignore changes if not initialized
        if not self.is_initialized or self.state == 'off':
            return
        # State transitions
        ## Exposure
        if self.state == 'exposure':
            duration_state = time.time() - self.timestamp_state_started
            if duration_state >= self.duration_exposure_seconds:
                _state_prev = self.state
                self.state = 'cooldown'
                self.client.turn_off_blue_led()
                self.timestamp_state_started = time.time()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        elif self.state == 'cooldown':
            duration_state = time.time() - self.timestamp_state_started
            if duration_state >= self.duration_rest_seconds:
                _state_prev = self.state
                self.state = 'exposure'
                self.client.turn_on_blue_led()
                self.timestamp_state_started = time.time()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        # Return
        return

    # Ping time
    def ping_time(self):
        self.set_state()
        return

    # Log through client
    def log(self, msg: str):
        self.client.log( f"<{self.name}> {msg}" )
        return


# Classes
class ExperimentOptogeneticExposure:
    # Constructor
    def __init__(
            self,
            client: GUIClient,
            duration_exposure_seconds: float = 0.0
        ):
        # Paremeters
        self.name = 'EXPERIMENT_OPTOGENETIC_EXPOSURE'
        self.initialization_text = "Start optogenetic exposure"
        self.arguments_text = "Exposure time (ms): "
        self.duration_exposure_seconds = duration_exposure_seconds
        self.client = client
        ## States
        self.states_possible = {
            'off',  # Experiment has not started yet
            'exposure',  # Expose for specific duration
            'cooldown',  # Let the worm/fleuroscent agents recover for duration
        }
        self.state = 'off'
        self.client.turn_off_opto_led()
        # Log
        msg = f"initial state: -> off"
        self.log(msg)
        # State transitions:
        # off -> exposure
        # exposure -> cooldown
        # cooldown -> exposure
        # Food patch processing
        self.is_initialized = True
        self.timestamp_state_started = None
        return

    # Set Arguments
    def set_arguments(self, **kwargs):
        # Exposure in milliseconds
        self.duration_exposure_seconds = float(kwargs['value'])/1000
        # Return
        return
    
    # Initialize
    def initialize(self, fp_folder: str):
        # Skip if already exposing
        if self.state == 'exposure':
            return
        # Start for the first time
        _state_prev = self.state
        self.state = 'exposure'
        self.client.turn_on_opto_led()
        self.timestamp_state_started = time.time()
        # Log
        msg = f"state transition: {_state_prev} -> {self.state}"
        self.log(msg)
        return

    # State
    def set_state(self, **kwargs):
        # Ignore changes if not initialized
        if not self.is_initialized or self.state == 'off':
            return
        # State transitions
        ## Exposure
        if self.state == 'exposure':
            duration_state = time.time() - self.timestamp_state_started
            if duration_state >= self.duration_exposure_seconds:
                _state_prev = self.state
                self.state = 'off'
                self.client.turn_off_opto_led()
                self.timestamp_state_started = time.time()
                # Log
                msg = f"state transition: {_state_prev} -> {self.state}"
                self.log(msg)
        # Return
        return

    # Ping time
    def ping_time(self):
        self.set_state()
        return

    # Log through client
    def log(self, msg: str):
        self.client.log( f"<{self.name}> {msg}" )
        return


# Main
if __name__ == '__main__':
    # TODO: do we want it to be an actual deivce (process)? possibly :dunno:
    # at least for today, I will stick with a simple class instanciation
    print("Running `experiments.py` directly.")
