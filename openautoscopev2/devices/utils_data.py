# Last update: 2024-10-22 SinRas
# Modules
import cv2 as cv

from glob import glob
from bisect import bisect_left

from tqdm import tqdm

import numpy as np
from h5py import File as h5File

import gc, sys, os
from os.path import join
import subprocess

from functools import lru_cache



# Methods
############################################################################################################
## CMD
def run_cmd(cmd):
    if isinstance(cmd, str):
        resp = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elif isinstance(cmd, list):
        resp = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        raise NotImplementedError()
    stdout, stderr = resp.stdout.decode('utf-8'), resp.stderr.decode('utf-8')
    return resp, stdout, stderr
## Get line count for log-files
@lru_cache
def get_file_linecount(fp):
    # Based on OS
    if sys.platform.lower() == 'linux' or sys.platform.lower() == 'darwin':  # Linux or OSX
        _, stdout, _ = run_cmd(["wc", "-l", fp])
        n, _ = stdout.split(maxsplit=1)
    elif sys.platform.lower().startswith('win'):  # Windows
        _, stdout, _ = run_cmd(f'find /c /v "" {fp}')
        n = stdout.strip().split()[-1]
    else:
        raise NotImplementedError()
    return int(n)
## Load and process log-files based on their writing conventions
LOG_STATE_NAMES = [ 'x', 'y', 'z', 'sx', 'sy', 'sz', 'ledb', 'ledg', 'ledo', 'wormx', 'wormy' ]
def load_process_log_files(fp_folder, time_lower=None, time_upper=None):
    # Parameters
    event_to_idx = {
        'x': 0, 'y': 1, 'z': 2,
        'sx': 3, 'sy': 4, 'sz': 5,
        'ledb': 6, 'ledg': 7, 'ledo': 8,
        'wormx': 9, 'wormy': 10,
    }
    # Process Log Files
    fp_logs = sorted(glob(f"{fp_folder}/*_log.txt"))
    state = np.zeros(len(event_to_idx), dtype=np.float32)
    ## Allocate Numpy Arrays
    n_logs_total = 0
    for fp_log in fp_logs:
        print(f"Getting linecounts for: {fp_log}")
        n_logs_total += get_file_linecount(fp_log)
    ## Load States
    print(f"Starting with Total Log records: {n_logs_total}")
    states = np.zeros((n_logs_total, len(event_to_idx)), dtype=np.float32)
    times_states = np.zeros(n_logs_total, dtype=np.float64)
    state_idx = 0
    for fp_log in fp_logs:
        print(f"Getting linecounts for: {fp_log}")
        linecount = get_file_linecount(fp_log)
        with open(fp_log, 'r') as in_file:
            for line in tqdm(in_file.readlines(), total=linecount, desc=f"loading --> {fp_log}"):
                # Preprocess
                line = line.strip()
                if len(line) == 0:
                    continue
                # Extract
                time, event = line.split(maxsplit=1)
                time = float(time)
                # Parse
                ## Some events have two timestamps in the beginning! :facepalm:
                if event[0].isdigit():
                    event = event.split(maxsplit=1)[1]
                ## Parse Event
                if '{"position":' in event:  # sample event: {"position": [26848, -4874, -21668]}
                    x,y,z = event[14:-2].split(',')
                    update = {
                        'x': int(x),
                        'y': int(y),
                        'z': int(z)
                    }
                elif event.startswith("<TEENSY COMMANDS> executing: sx"):
                    update = {
                        'sx': int(event[31:])
                    }
                elif event.startswith("<TEENSY COMMANDS> executing: sy"):
                    update = {
                        'sy': int(event[31:])
                    }
                elif event.startswith("<TEENSY COMMANDS> executing: sz"):
                    update = {
                        'sz': int(event[31:])
                    }
                elif event.startswith('<CLIENT WITH GUI> command sent: DO _teensy_commands_set_toggle_led'):
                    update = {
                        'ledi': 1 if event[-1] == 'n' else 0
                    }
                elif event.startswith('<CLIENT WITH GUI> command sent: DO _teensy_commands_set_led'):
                    led_name, power = event[60:].split()
                    update = {
                        f"led{led_name}": int(power),
                    }
                elif '<TRACKER-WORM-COORDS>' in event:
                    parsed = event[event.rfind('(')+1:-1].split(',')
                    wormx, wormy = float(parsed[0]), float(parsed[1])
                    update = {
                        'wormx': wormx,
                        'wormy': wormy,
                    }
                else:
                    update = dict()
                ## Update State
                for key, value in update.items():
                    idx = event_to_idx[key]
                    state[idx] = value
                # Store State
                ## Skip bounds
                if time_lower is not None and time < time_lower:
                    continue
                if time_upper is not None and time > time_upper:
                    continue
                ## Store
                states[state_idx] = state.copy()
                times_states[state_idx] = time
                state_idx += 1
            # GC
            _ = gc.collect()
    _ = gc.collect()
    return states[:state_idx], times_states[:state_idx]
############################################################################################################
# Load all H5 files and return them as a list
def load_files_data_times(fp_folder):
    files = []
    for fp in sorted(glob(f"{fp_folder}/*.h5")):
        try:
            files.append( h5File(fp) )
        except Exception as e:
            print(f"Error in loading file:\n--->{fp}\n###\n{str(e)}\n###")
    datas = [
        file['data'] for file in files
    ]
    times = [
        file['times'] for file in files
    ]
    return files, datas, times
# Combine all file connections to a single object to ease of manipulations
class SerializeDatas:
    # Constructur
    def __init__(self, data_list):
        self.data_list = data_list
        self.shape = self.data_list[0].shape
        self.ns = [
            len(x) for x in self.data_list
        ]
        self.n = sum(self.ns)
        self.shape = (self.n, *self.shape[1:])
        return
    # Len
    def __len__(self):
        return self.n
    # Index
    def __getitem__(self, t):
        idx = 0
        while t >= self.ns[idx]:
            t -= self.ns[idx]
            idx += 1
        return self.data_list[idx][t]
## ImgToProcess
class ImgToProcess:
    def __init__(self, data, fn_process, rescale=False):
        self.data = data
        self.fn_process = fn_process
        self.rescale = rescale
        self.shape = self.data.shape
        _shape_frame = self.fn_process(self.data[0]).shape
        self.shape = ( self.shape[0], *_shape_frame ) 
        return
    def __len__(self):
        return len(self.data)
    def __getitem__(self, t):
        result = self.fn_process( self.data[t] ).astype(np.uint8)
        if self.rescale and result.max() != 0:
            result *= (255//result.max())
        return result
############################################################################################################
## Binning
def change_binning(img, binning):
    if binning == 1:
        return img.copy()
    nx, ny = img.shape
    nx_new, ny_new = nx//binning, ny//binning
    return cv.resize(img, (nx_new,ny_new), cv.INTER_AREA)