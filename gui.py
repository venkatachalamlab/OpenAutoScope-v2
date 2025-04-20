# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

import os
import time, datetime
import json
from collections import defaultdict

import cv2 as cv
import numpy as np
import PySimpleGUI as sg
sg.set_options(suppress_error_popups=True)  # There are **random** image display errors from inside `PySimpleGUI`, while the actual image data is fine. Turning this off to prevent interruption in experiments. Note: writing the recording happens fine and independently, but expreiment control is intrrupted.

from openautoscopev2.zmq.client import GUIClient
from openautoscopev2.system.oas import OASwithGUI
from openautoscopev2.devices.utils import array_props_from_string, resolve_path
from openautoscopev2.devices.dual_displayer import DualDisplayer
from openautoscopev2.devices.experiments import ExperimentFoodPatchTimed, ExperimentPeriodicExposure, ExperimentOptogeneticExposure
from openautoscopev2.ui.elements import (
    InputWithIncrements, ReturnHandler,
    ExposureCompound, FramerateCompound, LED,
    ZInterpolationTracking, ToggleRecording, ToggleTracking,
    XYGamePad, ZGamePad, FolderBrowser,
    TrackingModelsCombo, FocusModelsCombo,
    InputwithIncrementsforZOffset, MotorLimit,
    ZAutoFocus, WriteEveryNFrames,
    InitializeExperiment, ExperimentArguments
)

from openautoscopev2.icons.icons import *

def jload(fp):
    with open(fp, 'r', encoding='utf-8') as in_file:
        return json.load( in_file )

def jdump(obj, fp):
    with open(fp, 'w', encoding='utf-8') as out_file:
        json.dump(
            obj, out_file,
            sort_keys=False,
            ensure_ascii=False,
            indent=1
        )

def main():
    FP_OAS_GUI_FOLDER = os.path.dirname(os.path.abspath(__file__))
    fp_data_path = os.path.join(
        FP_OAS_GUI_FOLDER,
        "data"
    )
    fp_configs = os.path.join(
        FP_OAS_GUI_FOLDER,
        "configs.json"
    )
    all_states = jload(fp_configs) if os.path.exists(fp_configs) else dict()
    if 'data_directory' in all_states:
        all_states['data_directory'] = resolve_path(
            fp = all_states['data_directory'],
            fp_base_dir = FP_OAS_GUI_FOLDER
        )
    else:
        all_states['data_directory'] = os.path.join(FP_OAS_GUI_FOLDER, 'data')

    fp_data_path = all_states['data_directory']

    if not os.path.exists(fp_data_path):
        os.mkdir(fp_data_path)

    BACKGROUND_COLOR = '#B3B6B7'
    BUTTON_COLOR = '#626567'
    ICON_SIZE = (64, 64)

    CAMERA_X_MAX = 1920 if 'sensor_width' not in all_states else all_states['sensor_width']
    CAMERA_Y_MAX = 1200 if 'sensor_height' not in all_states else all_states['sensor_height']
    exposure_behavior = 18 if 'exposure_behavior' not in all_states else all_states['exposure_behavior']
    exposure_gcamp = 18 if 'exposure_gcamp' not in all_states else all_states['exposure_gcamp']
    framerate = 20 if 'framerate' not in all_states else all_states['framerate']
    z_offset = 0 if 'z_offset' not in all_states else all_states['z_offset']
    xygamepad = 0 if 'xypad-input' not in all_states else all_states['xypad-input']
    zgamepad = 0 if 'zpad-input' not in all_states else all_states['zpad-input']
    q = 0.0 if 'q' not in all_states else float(all_states['q'])
    interpolation_tracking = False
    z_autofocus_tracking = False
    offset_step_small = 2
    offset_step_large = 8
    binsize = 2 if 'binsize' not in all_states else all_states['binsize']
    fmt = "UINT8_YX_{}_{}".format(int(1024//binsize), int(1024//binsize))
    default_b_x_offset = 0 if 'offset_behavior_x' not in all_states else all_states['offset_behavior_x']
    default_b_y_offset = 0 if 'offset_behavior_y' not in all_states else all_states['offset_behavior_y']
    default_g_x_offset = 0 if 'offset_gcamp_x' not in all_states else all_states['offset_gcamp_x']
    default_g_y_offset = 0 if 'offset_gcamp_y' not in all_states else all_states['offset_gcamp_y']

    default_b_x_offset -= default_b_x_offset % (binsize * 2)
    default_b_y_offset -= default_b_y_offset % (binsize * 2)
    default_g_x_offset -= default_g_x_offset % (binsize * 2)
    default_g_y_offset -= default_g_y_offset % (binsize * 2)

    default_b_x_offset = min(max(default_b_x_offset, -(CAMERA_X_MAX - 1024) // 2), (CAMERA_X_MAX - 1024) // 2)
    default_b_y_offset = min(max(default_b_y_offset, -(CAMERA_Y_MAX - 1024) // 2), (CAMERA_Y_MAX - 1024) // 2)
    default_g_x_offset = min(max(default_g_x_offset, -(CAMERA_X_MAX - 1024) // 2), (CAMERA_X_MAX - 1024) // 2)
    default_g_y_offset = min(max(default_g_y_offset, -(CAMERA_Y_MAX - 1024) // 2), (CAMERA_Y_MAX - 1024) // 2)

    (_, _, shape) = array_props_from_string(fmt)
    shape_displayer = (512, 512)
    forwarder_in = str(5000)
    forwarder_out = str(5001)
    forwarder_control = int(4862)
    server_client = str(5002)

    tracker_to_displayer_behavior = 5008
    tracker_to_displayer_gcamp = 5009


    y_bound = int((CAMERA_Y_MAX - binsize * shape[0]) / (2 * binsize))
    x_bound = int((CAMERA_X_MAX - binsize * shape[1]) / (2 * binsize))


    elements = []

    ui_return_handler = ReturnHandler()
    elements.append(ui_return_handler)

    ui_recording_toggle = ToggleRecording(
        key="recording",
        icon_off=ICON_RECORDING_OFF,
        icon_on=ICON_RECORDING_ON,
        icon_size=ICON_SIZE
    )
    elements.append(ui_recording_toggle)

    ui_tracking_toggle = ToggleTracking(
        key="tracking",
        icon_off=ICON_TRACKING_OFF,
        icon_on=ICON_TRACKING_ON,
        icon_size=ICON_SIZE
    )
    elements.append(ui_tracking_toggle)

    ui_offset_behavior_x = InputWithIncrements(
        text = "X Offset",
        key="offset_behavior_x",
        default_value=default_b_x_offset,
        binsize=binsize,
        x_bound=x_bound * binsize,
        y_bound=y_bound * binsize,
        bounds=[-x_bound * binsize, x_bound * binsize],
        increments=[-offset_step_large,
                    -offset_step_small,
                    offset_step_small,
                    offset_step_large],
        type_caster=int
    )
    elements.append(ui_offset_behavior_x)

    ui_offset_behavior_y = InputWithIncrements(
        text = "Y Offset",
        key="offset_behavior_y",
        default_value=default_b_y_offset,
        binsize=binsize,
        x_bound=x_bound * binsize,
        y_bound=y_bound * binsize,
        bounds=[-y_bound * binsize, y_bound * binsize],
        increments=[-offset_step_large,
                    -offset_step_small,
                    offset_step_small,
                    offset_step_large],
        type_caster=int
    )
    elements.append(ui_offset_behavior_y)

    ui_offset_gcamp_x = InputWithIncrements(
        text = "X Offset",
        key="offset_gcamp_x",
        default_value=default_g_x_offset,
        bounds=[-x_bound * binsize, x_bound * binsize],
        binsize=binsize,
        x_bound=x_bound * binsize,
        y_bound=y_bound * binsize,
        increments=[-offset_step_large,
                    -offset_step_small,
                    offset_step_small,
                    offset_step_large],
        type_caster=int
    )
    elements.append(ui_offset_gcamp_x)

    ui_offset_gcamp_y = InputWithIncrements(
        text = "Y Offset",
        key="offset_gcamp_y",
        default_value=default_g_y_offset,
        bounds=[-y_bound * binsize, y_bound * binsize],
        binsize=binsize,
        x_bound=x_bound * binsize,
        y_bound=y_bound * binsize,
        increments=[-offset_step_large,
                    -offset_step_small,
                    offset_step_small,
                    offset_step_large],
        type_caster=int
    )
    elements.append(ui_offset_gcamp_y)

    ui_led_ir = LED(
        text="760nm LED",
        key='led_b',
        icon_off=ICON_LED_IR_OFF,
        icon_on=ICON_LED_IR_ON,
        icon_size=ICON_SIZE
    )
    elements.append(ui_led_ir)

    ui_led_gfp = LED(
        text="470nm LED",
        key='led_g',
        icon_off=ICON_LED_GFP_OFF,
        icon_on=ICON_LED_GFP_ON,
        icon_size=ICON_SIZE
    )
    elements.append(ui_led_gfp)

    ui_led_opt = LED(
        text="595nm LED",
        key='led_o',
        icon_off=ICON_LED_OPT_OFF,
        icon_on=ICON_LED_OPT_ON,
        icon_size=ICON_SIZE
    )
    elements.append(ui_led_opt)

    ui_exposure_gfp = ExposureCompound(
        text='GFP Exposure Time',
        key='exposure_gcamp',
        icon=ICON_EXPOSURE,
        icon_size=ICON_SIZE,
        camera_name='gcamp',
        exposure=exposure_gcamp,
        framerate=framerate
    )
    elements.append(ui_exposure_gfp)

    ui_exposure_behavior = ExposureCompound(
        text='IR Exposure Time',
        key='exposure_behavior',
        icon=ICON_EXPOSURE,
        icon_size=ICON_SIZE,
        camera_name='behavior',
        exposure=exposure_behavior,
        framerate=framerate
    )
    elements.append(ui_exposure_behavior)

    ui_framerate = FramerateCompound(
        ui_exposure_behavior,
        ui_exposure_gfp,
        framerate_default=framerate,
        icon=ICON_FPS,
        icon_size=ICON_SIZE
    )
    elements.append(ui_framerate)

    ui_interpolation_tracking = ZInterpolationTracking(state=interpolation_tracking)
    elements.append(ui_interpolation_tracking)

    ui_z_auto_focus = ZAutoFocus(state=z_autofocus_tracking)
    elements.append(ui_z_auto_focus)

    ui_tracking_model = TrackingModelsCombo(
        text="Tracking Model",
        key="tracking_model",
        fp=FP_OAS_GUI_FOLDER
    )
    elements.append(ui_tracking_model)

    ui_focus_model = FocusModelsCombo(
        text="Focus Model",
        key="focus_model",
        fp=FP_OAS_GUI_FOLDER
    )
    elements.append(ui_focus_model)

    ui_tracker_z_offset = InputwithIncrementsforZOffset(
        text= "Tracker Z Offset",
        key="z_offset",
        default_value=z_offset
    )
    elements.append(ui_tracker_z_offset)

    ui_write_every_n_frames = WriteEveryNFrames()
    elements.append(ui_write_every_n_frames)

    ui_experiment_load_patches = InitializeExperiment(
        key="load_experiment"
    )
    elements.append(ui_experiment_load_patches)

    ui_experiment_arguments = ExperimentArguments()
    elements.append(ui_experiment_arguments)

    ui_xygamepad = XYGamePad(
        icon_xleft=ICON_X_NEG, icon_xright=ICON_X_POS,
        icon_yleft=ICON_Y_NEG, icon_yright=ICON_Y_POS,
        default_value=xygamepad
    )
    elements.append(ui_xygamepad)

    ui_zgamepad = ZGamePad(
        icon_zpos=ICON_Z_POS, icon_zneg=ICON_Z_NEG,
        default_value=zgamepad
    )
    elements.append(ui_zgamepad)

    ui_folder_browser = FolderBrowser(
        default_path = fp_data_path
    )
    elements.append(ui_folder_browser)

    ui_motor_limit = MotorLimit()
    elements.append(ui_motor_limit)

    led_column_layout = sg.Column(
        [[*ui_led_ir.elements], 
        [*ui_led_gfp.elements], 
        [*ui_led_opt.elements]],
        background_color = BACKGROUND_COLOR
    )
    exp_fps_column_layout = sg.Column(
        [[*ui_framerate.elements],
        [*ui_exposure_behavior.elements],
        [*ui_exposure_gfp.elements]],
        background_color = BACKGROUND_COLOR
    )
    r_y_offset_layout = sg.Column(
        [
            [element_i] for element_i in ui_offset_behavior_y.elements
        ],
        element_justification='center',
        background_color = BACKGROUND_COLOR
    )

    g_y_offset_layout = sg.Column(
        [
            [element_i] for element_i in ui_offset_gcamp_y.elements
        ],
        element_justification='center',
        background_color = BACKGROUND_COLOR
    )

    ui_displayer_behavior = sg.Image(key="img_frame_r", size=shape_displayer)
    ui_displayer_gcamp = sg.Image(key="img_frame_g", size=shape_displayer)
    image_r_x_offset_layout = sg.Column(
        [
            [ui_displayer_behavior], [*ui_offset_behavior_x.elements]
        ],
        element_justification='center',
        background_color = BACKGROUND_COLOR
    )

    image_g_x_offset_layout = sg.Column(
        [
            [ui_displayer_gcamp], [*ui_offset_gcamp_x.elements]
        ],
        element_justification='center',
        background_color = BACKGROUND_COLOR
    )

    directories = sg.Column(
        [
            ui_folder_browser.elements,
        ],
        background_color = BACKGROUND_COLOR
    )

    layout = [
        [
            *ui_return_handler.elements,
        ],[
            *ui_recording_toggle.elements, *ui_tracking_toggle.elements, directories
        ],[
            sg.HorizontalSeparator(),
        ],[
            [
                exp_fps_column_layout,
                sg.VSeparator(),
                led_column_layout,
                sg.VSeparator(),
                *ui_xygamepad.elements,
                *ui_zgamepad.elements,
                sg.VSeparator(),
                *ui_motor_limit.elements
            ],
        ],[
            sg.HorizontalSeparator(),
        ],[
            *ui_interpolation_tracking.elements, sg.VSeparator(), *ui_tracker_z_offset.elements, sg.VSeparator(), *ui_tracking_model.elements, *ui_focus_model.elements,
        ],[
            *ui_z_auto_focus.elements, sg.VSeparator(), *ui_write_every_n_frames.elements, sg.VSeparator(), *ui_experiment_load_patches.elements, *ui_experiment_arguments.elements
        ],[
            sg.HorizontalSeparator(),
        ],[
            [r_y_offset_layout, image_r_x_offset_layout, 
            sg.VSeparator(), 
            g_y_offset_layout, image_g_x_offset_layout]
        ],[
            sg.HorizontalSeparator(),
        ],[
            sg.Button('Quit', button_color=BUTTON_COLOR)
        ]
    ]

    registered_events = defaultdict(list)
    for element in elements:
        for event in element.events:
            registered_events[event].append(element)

    window = sg.Window(
        'OpenAutoScope2.0 GUI',
        layout,
        finalize=True,
        background_color=BACKGROUND_COLOR
    )
    ui_return_handler.set_window(window)
    gui_client = GUIClient(
        port_server=server_client,
        port_sendto_forwarder=f"L{forwarder_in}",
        port_recvfrom_forwarder=f"L{forwarder_out}",
        port_forwarder_control=forwarder_control,
        sg_window=window
    )
    for element in elements:
        element.set_client(gui_client)
    # Experiment Designed
    # ## Food Patch Entry
    # experiment = ExperimentFoodPatchTimed(
    #     d_turn_on_outside_um=1000.0,
    #     t_turn_on_after_entry_s=5*60.0,
    #     t_rest_between_exposures_s=20*60.0,
    #     fp_folder_scan=None,
    #     client=gui_client
    # )
    # ## Periodic Blue Exposure
    # experiment = ExperimentPeriodicExposure(
    #     duration_exposure_seconds=0.5,
    #     duration_rest_seconds=10.0*60,
    #     client=gui_client
    # )
    ## Optogenetic Stimulaiton
    experiment = ExperimentOptogeneticExposure(
        client=gui_client,
        duration_exposure_seconds=0.5
    )
    ## Setting experiment argument element
    ui_experiment_load_patches.set_experiment(experiment)
    ui_experiment_arguments.set_experiment(experiment)


    dual_displayer = DualDisplayer(
        window=window,
        data_r=f"L{tracker_to_displayer_behavior}",
        data_g=f"L{tracker_to_displayer_gcamp}",
        fmt="UINT8_YX_512_512",
        q=q,
        show_gfp_stats=True
    )

    def zero_displayers():
        _tmp = np.zeros(shape_displayer, dtype=np.uint8)
        _tmp = cv.imencode('.png', _tmp)[1].tobytes()
        ui_displayer_behavior.update(data=_tmp)
        ui_displayer_gcamp.update(data=_tmp)
        window.refresh()
    zero_displayers()

    event, values = window.read(timeout=0)
    ui_xygamepad.bind()
    ui_zgamepad.bind()

    offset_bx = x_bound + default_b_x_offset // binsize
    offset_by = y_bound + default_b_y_offset // binsize
    offset_gx = x_bound + default_g_x_offset // binsize
    offset_gy = y_bound + default_g_y_offset // binsize

    for k,v in all_states.items():
        values[k] = v

    values['gui_fp'] = all_states['gui_fp'] if 'gui_fp' in all_states.keys() else FP_OAS_GUI_FOLDER
    values['forwarder_in'] = all_states['forwarder_in'] if 'forwarder_in' in all_states.keys() else forwarder_in
    values['forwarder_out'] = all_states['forwarder_out'] if 'forwarder_out' in all_states.keys() else forwarder_out
    values['forwarder_control'] = all_states['forwarder_control'] if 'forwarder_control' in all_states.keys() else forwarder_control
    values['server_client'] = all_states['server_client'] if 'server_client' in all_states.keys() else server_client
    values['tracker_to_displayer_behavior'] = all_states['tracker_to_displayer_behavior'] if 'tracker_to_displayer_behavior' in all_states.keys() else tracker_to_displayer_behavior
    values['tracker_to_displayer_gcamp'] = all_states['tracker_to_displayer_gcamp'] if 'tracker_to_displayer_gcamp' in all_states.keys() else tracker_to_displayer_gcamp
    values['interpolation_tracking'] = all_states['interpolation_tracking'] if 'interpolation_tracking' in all_states.keys() else interpolation_tracking
    values['z_autofocus_tracking'] = all_states['z_autofocus_tracking'] if 'z_autofocus_tracking' in all_states.keys() else z_autofocus_tracking
    values['format'] = all_states['format'] if 'format' in all_states.keys() else fmt
    values['binsize'] = all_states['binsize'] if 'binsize' in all_states.keys() else binsize

    oas_with_gui = OASwithGUI(**values)
    oas_with_gui.run()

    time.sleep(1)

    client_cli_cmd = "DO _flir_camera_set_region_behavior 1 {} {} {} {} {}".format(
        shape[0], shape[1], binsize, offset_by, offset_bx
    )
    gui_client.process(client_cli_cmd)

    client_cli_cmd = "DO _flir_camera_set_region_gcamp 1 {} {} {} {} {}".format(
        shape[0], shape[1], binsize, offset_gy, offset_gx
    )
    gui_client.process(client_cli_cmd)

    while True:
        event, values = window.read(timeout=10)
        if event == sg.WIN_CLOSED or event == 'Quit':
            gui_client.process("DO shutdown")
            break

        for element in elements:
            element.add_values(values)

        for element in registered_events[event]:
            element.handle(event = event, **values)

        for element in elements:
            element.add_values(values)

        # Get & update images
        img_r, img_g = dual_displayer.get_frame()
        retval_r, frame_r = cv.imencode('.png', img_r)
        retval_g, frame_g = cv.imencode('.png', img_g)
        if retval_r:
            ui_displayer_behavior.update(data=frame_r.tobytes())
        if retval_g:
            ui_displayer_gcamp.update(data=frame_g.tobytes())

        # Get & update the focus
        # TODO add the focus update here later! possibly

        # TODO: show more stats about the imageing
        # e.g. stepper motor positions, ...

        # Client polling
        gui_client.listen_for_commands()

        # Update new stage coordinates
        if event == "CLIENT-STAGE-COORDS":
            experiment.set_state(**values)  # TODO: should I add it to registered events? I don't think so. but I can unify it by adding ".handle" and ".add_values". :dunno:
            # Show on displayer
            if getattr(experiment, 'd_min_patches', None) is not None:
                text = f"Dist (um): {experiment.d_min_patches:>9.1f}, State: {experiment.state}"
                dual_displayer.set_beh_text(text)
        else:  # Ping the timers
            experiment.ping_time()

    window.close()


if __name__ == '__main__':
    main()
