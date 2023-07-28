# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

import os
import time
import json
from collections import defaultdict

import cv2 as cv
import numpy as np
import PySimpleGUI as sg

from openautoscopev2.zmq.client import GUIClient
from openautoscopev2.system.oas import OASwithGUI
from openautoscopev2.devices.utils import array_props_from_string, resolve_path
from openautoscopev2.devices.dual_displayer import DualDisplayer
from openautoscopev2.ui.elements import (
    InputWithIncrements, ReturnHandler,
    ExposureCompound, FramerateCompound, LED,
    ZInterpolationTracking, ToggleRecording, ToggleTracking,
    XYGamePad, ZGamePad, FolderBrowser, ModelsCombo,
    InputwithIncrementsforZOffset, MotorLimit
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
    FP_MODELS_PATHS = os.path.join(
        FP_OAS_GUI_FOLDER,
        "models_path.json"
    )
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

    CAMERA_X_MAX = 1920
    CAMERA_Y_MAX = 1200
    default_b_x_offset = 0 if 'offset_behavior_x' not in all_states else all_states['offset_behavior_x']
    default_b_y_offset = 0 if 'offset_behavior_y' not in all_states else all_states['offset_behavior_y']
    default_g_x_offset = 0 if 'offset_gcamp_x' not in all_states else all_states['offset_gcamp_x']
    default_g_y_offset = 0 if 'offset_gcamp_y' not in all_states else all_states['offset_gcamp_y']
    exposure_behavior = 18 if 'exposure_behavior' not in all_states else all_states['exposure_behavior']
    exposure_gcamp = 18 if 'exposure_gcamp' not in all_states else all_states['exposure_gcamp']
    framerate = 20 if 'framerate' not in all_states else all_states['framerate']
    z_offset = 0 if 'z_offset' not in all_states else all_states['z_offset']
    xygamepad = 0 if 'xypad-input' not in all_states else all_states['xypad-input']
    zgamepad = 0 if 'zpad-input' not in all_states else all_states['zpad-input']
    q = 0.0 if 'q' not in all_states else float(all_states['q'])
    interpolation_tracking = False
    offset_step_small = 2
    offset_step_large = 10
    fmt = "UINT8_YX_512_512"
    (_, _, shape) = array_props_from_string(fmt)
    forwarder_in = str(5000)
    server_client = str(5002)

    tracker_to_displayer_behavior = 5008
    tracker_to_displayer_gcamp = 5009
    binsize = 2

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
        bounds=[-x_bound, x_bound],
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
        bounds=[-y_bound, y_bound],
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
        bounds=[-x_bound, x_bound],
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
        bounds=[-y_bound, y_bound],
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

    ui_tracking_model = ModelsCombo(
        text="Tracking Model",
        key="tracking_model",
        fp=FP_OAS_GUI_FOLDER
    )
    elements.append(ui_tracking_model)

    ui_tracker_z_offset = InputwithIncrementsforZOffset(
        text= "Tracker Z Offset",
        key="z_offset",
        default_value=z_offset
    )
    elements.append(ui_tracker_z_offset)

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

    image_r_x_offset_layout = sg.Column(
        [
            [sg.Image(key="img_frame_r", size=shape)], [*ui_offset_behavior_x.elements]
        ],
        element_justification='center',
        background_color = BACKGROUND_COLOR
    )

    image_g_x_offset_layout = sg.Column(
        [
            [sg.Image(key="img_frame_g", size=shape)], [*ui_offset_gcamp_x.elements]
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
            *ui_interpolation_tracking.elements, sg.VSeparator(), *ui_tracker_z_offset.elements, sg.VSeparator(), *ui_tracking_model.elements
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
    gui_client = GUIClient(port=server_client, port_forwarder_in=f"L{forwarder_in}")
    for element in elements:
        element.set_client(gui_client)

    dual_displayer = DualDisplayer(
        window=window,
        data_r=f"L{tracker_to_displayer_behavior}",
        data_g=f"L{tracker_to_displayer_gcamp}",
        fmt=fmt,
        q=q
    )

    def zero_displayers():
        _tmp = np.zeros(shape, dtype=np.uint8)
        _tmp = cv.imencode('.png', _tmp)[1].tobytes()
        window['img_frame_r'].update(data=_tmp)
        window['img_frame_g'].update(data=_tmp)
        window.refresh()
    zero_displayers()

    event, values = window.read(timeout=0)
    ui_xygamepad.bind()
    ui_zgamepad.bind()

    offset_bx = x_bound + int(values['offset_behavior_x'])
    offset_by = y_bound + int(values['offset_behavior_y'])
    offset_gx = x_bound + int(values['offset_gcamp_x'])
    offset_gy = y_bound + int(values['offset_gcamp_y'])

    for k,v in all_states.items():
        values[k] = v

    values['gui_fp'] = all_states['gui_fp'] if 'gui_fp' in all_states.keys() else FP_OAS_GUI_FOLDER
    values['forwarder_in'] = all_states['forwarder_in'] if 'forwarder_in' in all_states.keys() else forwarder_in
    values['server_client'] = all_states['server_client'] if 'server_client' in all_states.keys() else server_client
    values['tracker_to_displayer_behavior'] = all_states['tracker_to_displayer_behavior'] if 'tracker_to_displayer_behavior' in all_states.keys() else tracker_to_displayer_behavior
    values['tracker_to_displayer_gcamp'] = all_states['tracker_to_displayer_gcamp'] if 'tracker_to_displayer_gcamp' in all_states.keys() else tracker_to_displayer_gcamp
    values['interpolation_tracking'] = all_states['interpolation_tracking'] if 'interpolation_tracking' in all_states.keys() else interpolation_tracking
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
        
        img_r, img_g = dual_displayer.get_frame()
        frame_r = cv.imencode('.png', img_r)[1].tobytes()
        frame_g = cv.imencode('.png', img_g)[1].tobytes()
        window['img_frame_r'].update(data=frame_r)
        window['img_frame_g'].update(data=frame_g)

    window.close()

if __name__ == '__main__':
    main()