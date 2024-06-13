# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

import os
import math
import json

from typing import Dict, List, Tuple
from collections import defaultdict
import PySimpleGUI as sg

from openautoscopev2.zmq.client import GUIClient
from openautoscopev2.devices.utils import resolve_path

BACKGROUND_COLOR = '#B3B6B7'
TEXT_COLOR = '#1B2631'
BUTTON_COLOR = '#626567'

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

class AbstractElement:
    def __init__(self) -> None:
        self.events = set()
        self.elements = list()
        self.client = None

    def disable(self):
        for element in self.elements:
            try:
                element.update(disabled=True)
            except Exception as e:
                pass

    def enable(self):
        for element in self.elements:
            try:
                element.update(disabled=False)
            except Exception as e:
                pass
    
    def set_client(self, client: GUIClient):
        self.client = client

    def handle(self, **kwargs):
        raise NotImplementedError()

    def add_values(self, values):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def add_state(self, all_states):
        raise NotImplementedError()

    def load_state(self, all_states):
        raise NotImplementedError()

class InputAutoselect(AbstractElement):
    def __init__(
            self,
            key: str, default_text: int,
            size, type_caster=int,
            bounds=(None, None), font=None,
            disabled=False
        ) -> None:
        super().__init__()
        self.key = key
        self.default_text = default_text
        self.type_caster = type_caster
        self.bound_lower, self.bound_upper = bounds
        self.disabled = disabled
        self.input = sg.Input(
            default_text=self.default_text,
            key=self.key,
            justification='righ',
            size=size,
            font=font,
            disabled=self.disabled
        )
        self.events = { self.key }
        self.elements = [ self.input ]

    def handle(self, **kwargs):
        value = self.get()
        if self.bound_lower is not None:
            value = max( self.bound_lower, value )
        if self.bound_upper is not None:
            value = min( self.bound_upper, value )
        self.input.update(value=value)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        raw = self.input.get()
        if not isinstance(raw, str):
            # If user inputs '-' before writing anything else
            if raw.replace('-', '').strip() == '':
                return self.type_caster(0)
            return self.type_caster(raw)

        if raw.strip() == "":
            return self.type_caster(self.bound_lower)

        sign = "-" if raw[0] == "-" else ""
        res = sign + "".join([
            c for c in raw if c.isdigit() or (self.type_caster == float and c=='.')  # TODO: This will fail if input is not correct! add better handling.
        ])
        # If user inputs '-' before writing anything else
        if res.replace('-', '').strip() == '':
            return self.type_caster(self.bound_lower)
        return self.type_caster(res)

    def set_bounds(self, bound_lower=None, bound_upper=None):
        if bound_lower is not None:
            self.bound_lower = bound_lower
        if bound_upper is not None:
            self.bound_upper = bound_upper
        self.handle()

    def add_state(self, all_states):
        all_states[self.key] = self.get()

    def load_state(self, all_states):
        self.input.update(value = all_states[self.key])
        self.handle()


class ReturnHandler(AbstractElement):
    def __init__(self) -> None:
        super().__init__()
        self.key = "RETURN-KEY"
        self.elements = [
            sg.Button(visible=False, key=self.key, bind_return_key=True)
        ]
        self.events = { self.key }

    def set_window(self, window):
        self.window = window

    def handle(self, **kwargs):
        element_focused = self.window.find_element_with_focus()
        self.window.write_event_value(
            element_focused.key,
            '<RETURN-KEY-CALL>'
        )

    def add_values(self, values):
        return

class ToggleRecording(AbstractElement):
    def __init__(
            self,
            key: str,
            icon_off, icon_on,
            icon_size: Tuple[int, int]
        ) -> None:
        super().__init__()
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.text_on = "Recording"
        self.text_off = "Not Recording"
        self.icon_size = icon_size
        self.key = key
        self.key_toggle = f"{self.key}-TOGGLE"
        self.button = sg.Button(
            image_data=self.icon_off,
            image_size=self.icon_size,
            key=self.key_toggle,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.text = sg.Text(
            text=self.text_off, s=15,
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text
        ]
        self.events = {
            self.key_toggle
        }
        self.state = False

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            if self.state:
                client_cli_cmd = f"DO _writer_stop"
                self.button.update(image_data=self.icon_off)
                self.text.update(value=self.text_off)
            else:
                client_cli_cmd = f"DO _writer_start"
                self.button.update(image_data=self.icon_on)
                self.text.update(value=self.text_on)
            self.state = not self.state
            self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return self.state

class ToggleTracking(AbstractElement):
    def __init__(
            self,
            key: str,
            icon_off, icon_on,
            icon_size: Tuple[int, int]
        ) -> None:
        super().__init__()
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.text_on = "Tracking"
        self.text_off = "Not Tracking"
        self.icon_size = icon_size
        self.key = key
        self.key_toggle = f"{self.key}-TOGGLE"
        self.button = sg.Button(
            image_data=self.icon_off,
            image_size=self.icon_size,
            key=self.key_toggle,
            button_color=(sg.theme_background_color(), sg.theme_background_color())
        )
        self.text = sg.Text(
            text=self.text_off, s=16,
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text
        ]
        self.events = {
            self.key_toggle
        }
        self.state = False
        return

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            if self.state:
                client_cli_cmd = f"DO _tracker_stop"
                self.button.update(image_data=self.icon_off)
                self.text.update(value=self.text_off)
            else:
                client_cli_cmd = f"DO _tracker_start"
                self.button.update(image_data=self.icon_on)
                self.text.update(value=self.text_on)
            self.state = not self.state
            self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return self.state

class InputWithIncrements(AbstractElement):
    def __init__(self, text:str, key: str, default_value: int, binsize: int, x_bound: int,
        y_bound: int, increments: List[int] = [-1, 1], bounds: List[int] = [-1024, 1024], type_caster=int) -> None:
        super().__init__()
        self.text = text
        self.bounds = bounds
        self.binsize = binsize
        self.default_value = default_value
        self.x_bound = x_bound
        self.y_bound = y_bound
        self.bound_lower = min(self.bounds)
        self.bound_upper = max(self.bounds)
        self.key = key
        self.increments =  increments
        self.type_caster = type_caster
        self.key_to_offset = {
            f"{key}--{inc}": inc for inc in self.increments
        }
        self.events = set(self.key_to_offset)
        self.events.add(self.key)
        self.input_as = InputAutoselect(
            key=key,
            default_text=self.default_value,
            size=4,
            type_caster=self.type_caster,
            disabled=True,
            bounds=bounds
        )
        self.elements = [
            sg.Text(self.text, background_color = BACKGROUND_COLOR)
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc < 0
        ] + [ 
            *self.input_as.elements 
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc > 0
        ]
        _, self.camera_name, self.offset_direction = self.key.split('_')
        self.key_offset_other = 'offset_{}_{}'.format(
            self.camera_name,
            'x' if self.offset_direction == 'y' else 'y'
        )
        return

    def handle(self, **kwargs):
        event = kwargs['event']
        offset_other = kwargs[self.key_offset_other]
        if event != self.key:
            inc = self.key_to_offset[event]
            value_current = self.type_caster( kwargs[self.key] )
            value_new = min(
                self.bound_upper,
                max(
                    self.bound_lower,
                    value_current + inc * self.binsize
                )
            )
            self.input_as.input.update(value = value_new)
        self.input_as.handle(**kwargs)
        value_new = self.get()
        if self.offset_direction == 'x':
            offset_x, offset_y = (self.x_bound + value_new) // self.binsize, (self.y_bound + int(offset_other)) // self.binsize
        else:
            offset_x, offset_y = (self.x_bound + int(offset_other)) // self.binsize, (self.y_bound + value_new) // self.binsize

        client_cli_cmd = "DO _flir_camera_set_region_{} 1 {} {} {} {} {}".format(
            self.camera_name, int(1024 / self.binsize), int(1024 / self.binsize), self.binsize, offset_y, offset_x
        )
        self.client.process(client_cli_cmd)

    def get(self):
        return self.input_as.get()

    def add_values(self, values):
        values[self.key] = self.get()

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        self.handle({
            self.key: self.get()
        })

class LED(AbstractElement):
    def __init__(
            self,
            text: str, key: str,
            icon_off, icon_on,
            icon_size: Tuple[int, int]
        ) -> None:
        super().__init__()
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.icon_size = icon_size
        self.key = key
        self.led_name = self.key.split("_")[1]
        self.key_toggle = f"{self.key}-TOGGLE"
        self.button = sg.Button(
            image_data=self.icon_off,
            image_size=self.icon_size,
            key=self.key_toggle,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.text = sg.Text(
            text=text,
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text
        ]
        self.events = {
            self.key_toggle
        }
        self.state = False

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            self.state = not self.state
            image_data = self.icon_on if self.state else self.icon_off
            self.button.update(image_data=image_data)
            
        state = 1 if self.state else 0
        client_cli_cmd = f"DO _teensy_commands_set_led {self.led_name} {state}"
        self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return self.state

class ExposureCompound(AbstractElement):
    def __init__(
            self, text:str, key: str,
            icon, icon_size: Tuple[int, int],
            camera_name: str,
            exposure,
            framerate,
            type_caster = int,
        ) -> None:
        super().__init__()
        self.key = key
        self.icon = icon
        self.icon_size = icon_size
        self.camera_name = camera_name
        self.bounds = (1, math.floor(995/framerate))

        self.text = text
        self.button = sg.Button(
            image_data=self.icon,
            image_size=self.icon_size,
            enable_events=False,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.text_element = sg.Text(
            text=self.text + f'(min:{self.bounds[0]}, max:{self.bounds[1]})', s=30,
            background_color = BACKGROUND_COLOR
        )
        self.input_as = InputAutoselect(
            key=self.key, default_text=exposure, size=6, type_caster=type_caster,
            bounds=self.bounds
        )
        self.unit = sg.Text(
            text='ms',
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text_element, *self.input_as.elements, self.unit
        ]
        self.events = {
            self.key
        }

    def handle(self, **kwargs):
        framerate = kwargs['framerate']
        self.input_as.handle(**kwargs)
        exposure_time = self.get()
        client_cli_cmd = "DO _flir_camera_set_exposure_framerate_{} {} {}".format(
            self.camera_name, exposure_time, framerate
        )
        self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()
 
    def set_bounds(self, bound_lower=None, bound_upper=None):
        bound_upper = self.bounds[1] if bound_upper is None else bound_upper
        bound_lower = self.bounds[0] if bound_lower is None else bound_lower
        self.bounds = (bound_lower, bound_upper)
        self.input_as.set_bounds(
            bound_lower=self.bounds[0],
            bound_upper=self.bounds[1]
        )
        self.text_element.update(
            value=self.text + f'(min:{self.bounds[0]}, max:{self.bounds[1]})'
        )

    def get(self):
        return self.input_as.get()

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state(all_states)

class FramerateCompound(AbstractElement):
    def __init__(
            self,
            element_exposure_behavior: ExposureCompound,
            element_exposure_gfp: ExposureCompound,
            icon, icon_size,
            framerate_default: int,
            key: str = 'framerate',
            text: str = "Imaging Frame Rate (min:1, max:48)",
            type_caster = int
        ) -> None:
        super().__init__()
        self.element_exposure_behavior = element_exposure_behavior
        self.element_exposure_gfp = element_exposure_gfp
        self.key = key
        self.icon = icon
        self.icon_size = icon_size
        self.bounds = (1, math.floor(995/framerate_default))
        self.button = sg.Button(
            image_data=icon,
            image_size=icon_size,
            enable_events=False
        )
        self.text = sg.Text(
            text=text, s=30,
            background_color = BACKGROUND_COLOR
        )
        self.input_as = InputAutoselect(
            key=self.key, default_text=framerate_default, size=6, type_caster=type_caster,
            bounds=self.bounds
        )
        self.unit = sg.Text(
            text='Hz',
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text, *self.input_as.elements, self.unit
        ]
        self.events = {
            self.key
        }

    def handle(self, **kwargs):
        self.input_as.handle(**kwargs)
        framerate = self.get()
        self.bounds = (self.bounds[0], math.floor(995/framerate))
        self.element_exposure_behavior.set_bounds(bound_upper=self.bounds[1])
        self.element_exposure_gfp.set_bounds(bound_upper=self.bounds[1])
        self.element_exposure_behavior.handle(framerate=framerate)
        self.element_exposure_gfp.handle(framerate=framerate)

    def add_values(self, values):
        values[self.key] = self.get()

    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )

    def get(self):
        return self.input_as.get()

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state(all_states)
        self.handle({
            self.key: self.get()
        })

class ZInterpolationTracking(AbstractElement):
    def __init__(self, state) -> None:
        super().__init__()
        self.key = "ZINTERP"
        self.color_disabled = BACKGROUND_COLOR
        self.color_set = "#0B5345"
        self.color_unset = BUTTON_COLOR
        self.key_checkbox = f"{self.key}-CHECKBOX"
        self.key_p1 = f"{self.key}-P1"
        self.key_p2 = f"{self.key}-P2"
        self.key_p3 = f"{self.key}-P3"

        self.checkbox = sg.Checkbox(
            text="Plane Interpolation Z-Tracking",
            key=self.key_checkbox,
            enable_events=True,
            default=state,
            background_color = BACKGROUND_COLOR,
            s=39
        )
        self.p1 = sg.Button(
            button_text="Set Point 1",
            key=self.key_p1,
            enable_events=True,
            disabled=not(state),
            button_color=self.color_disabled if not(state) else self.color_unset
        )
        self.p1_is_set = False
        self.p2 = sg.Button(
            button_text="Set Point 2",
            key=self.key_p2,
            enable_events=True,
            disabled=not(state),
            button_color=self.color_disabled if not(state) else self.color_unset
        )
        self.p2_is_set = False
        self.p3 = sg.Button(
            button_text="Set Point 3",
            key=self.key_p3,
            enable_events=True,
            disabled=not(state),
            button_color=self.color_disabled if not(state) else self.color_unset
        )
        self.p3_is_set = False

        self.elements = [
            self.checkbox, self.p1, self.p2, self.p3,
        ]
        self.events = {
            self.key_checkbox, self.key_p1, self.key_p2, self.key_p3,
        }
        self.initial_toggle = True

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_checkbox:
            p_disabled = not self.checkbox.get()
            client_cli_cmd = "DO _tracker_interpolate_z_tracking {}".format(int(self.checkbox.get()))
            self.client.process(client_cli_cmd)
            button_color = self.color_disabled if p_disabled else self.color_unset
            self.p1.update(disabled=p_disabled, button_color=button_color)
            self.p2.update(disabled=p_disabled, button_color=button_color)
            self.p3.update(disabled=p_disabled, button_color=button_color)
            self.p1_is_set, self.p2_is_set, self.p3_is_set = False, False, False
            # Initial toggle will use hard-coded parameters
            if self.initial_toggle and self.checkbox.get():
                self.initial_toggle = False
                # Enable all
                self.p1_is_set, self.p2_is_set, self.p3_is_set = True, True, True
                self.p1.update(button_color=self.color_set)
                self.p2.update(button_color=self.color_set)
                self.p3.update(button_color=self.color_set)
                # Set coords
                client_cli_cmd = "DO _tracker_set_point 1"
                self.client.process("DO _teensy_commands_set_pos tracker_behavior 1 413 -263 3534")
                self.client.process("DO _teensy_commands_set_pos tracker_behavior 2 -2238 12873 3173")
                self.client.process("DO _teensy_commands_set_pos tracker_behavior 3 -11810 2374 3451")
                print("DEFAULT Z-INTERPOLATIONS SET")


        elif event == self.key_p1:
            self.p1_is_set = True
            self.p1.update(button_color=self.color_set)
            client_cli_cmd = "DO _tracker_set_point 1"
            self.client.process(client_cli_cmd)
        elif event == self.key_p2:
            self.p2_is_set = True
            self.p2.update(button_color=self.color_set)
            client_cli_cmd = "DO _tracker_set_point 2"
            self.client.process(client_cli_cmd)
        elif event == self.key_p3:
            self.p3_is_set = True
            self.p3.update(button_color=self.color_set)
            client_cli_cmd = "DO _tracker_set_point 3"
            self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return {
            'checkbox': self.checkbox.get(),
            'p1': self.p1_is_set,
            'p2': self.p2_is_set,
            'p3': self.p3_is_set,
        }


class ZAutoFocus(AbstractElement):
    def __init__(self, state) -> None:
        super().__init__()
        self.key = "ZAUTOFOCUS"
        self.key_checkbox = f"{self.key}-CHECKBOX"
        self.key_offset = f"{self.key}-OFFSET"

        self.checkbox = sg.Checkbox(
            text="Z-AutoFocus Tracking",
            key=self.key_checkbox,
            enable_events=True,
            default=state,
            background_color=BACKGROUND_COLOR,
            s=39
        )
        self.input_as = InputAutoselect(
            key=self.key_offset, default_text="0.0", size=6, type_caster=float,
            bounds=[-0.1, 0.1]
        )

        self.elements = [
            self.checkbox,
            *self.input_as.elements
        ]
        self.events = {
            self.key_checkbox,
            self.key_offset,
        }

    def handle(self, **kwargs):
        event = kwargs['event']
        # Checkbox Toggling
        if event == self.key_checkbox:
            client_cli_cmd = "DO _tracker_set_z_autofocus_tracking {}".format(int(self.checkbox.get()))
            self.client.process(client_cli_cmd)
        # Text Input handle
        if event == self.key_offset:
            self.input_as.handle(**kwargs)
        # Turned ON or new offset value
        if self.checkbox.get() and (
                event == self.key_checkbox or
                event == self.key_offset
            ):  # I know at the moment the second condition is always true! :P
            z_autofocus_offset = self.get()['offset']
            # Set the offset value!
            client_cli_cmd = "DO _tracker_set_z_autofocus_tracking_offset {}".format(
                z_autofocus_offset
            )
            self.client.process(client_cli_cmd)


    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return {
            'checkbox': self.checkbox.get(),
            'offset': self.input_as.get(),
        }

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state(all_states)
        self.handle({
            self.key: self.get()
        })

class WriteEveryNFrames(AbstractElement):
    def __init__(self) -> None:
        super().__init__()
        self.key = "WRITEEVERYNFRAMES"
        self.text = sg.Text("Write every N frames: ", background_color=BACKGROUND_COLOR)
        self.input_as = InputAutoselect(
            key=self.key, default_text="10", size=6, type_caster=int,
            bounds=[1, None]
        )

        self.elements = [
            self.text,
            *self.input_as.elements
        ]
        self.events = {self.key}

    def handle(self, **kwargs):
        self.input_as.handle(**kwargs)
        write_every_n_frames = self.get()
        # Set the offset value!
        client_cli_cmd = "DO _writer_set_write_every_n_frames {}".format(
            write_every_n_frames
        )
        self.client.process(client_cli_cmd)
        return


    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return self.input_as.get()

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state(all_states)
        self.handle({
            self.key: self.get()
        })

class ModelsCombo(AbstractElement):
    def __init__(self, text: str, key: str, fp) -> None:
        super().__init__()
        self.fp_models = os.path.join(fp, 'models.json')
        self.models_dict = jload(self.fp_models)
        self.models = list(self.models_dict.keys())
        self.default_value = self.models[0]

        self.key = key
        self.key_combo = f"{self.key}--COMBO"
        self.events = {
            self.key,
            self.key_combo
        }

        self.text = sg.Text(text, background_color = BACKGROUND_COLOR)
        self.combo = sg.Combo(
            values=self.models,
            default_value=self.default_value,
            key=self.key_combo,
            enable_events=True,
            s=25,
            button_background_color=BUTTON_COLOR
        )
        self.elements = [ self.text, self.combo ]

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_combo:
            model = self.get()
            client_cli_cmd = "DO _tracker_set_tracking_mode {}".format(model)
            self.client.process(client_cli_cmd)
    
    def get(self):
        return self.combo.get()

    def add_values(self, values):
        values[self.key] = self.get()
    
    def add_state(self, all_states):
        all_states[self.key_combo] = self.get()

    def load_state(self, all_states):
        self.combo.update(value=all_states[self.key_combo])
        self.handle({
            self.key_combo: self.get()
        })

class InputwithIncrementsforZOffset(AbstractElement):
    def __init__(self, text:str, key: str, default_value: int, increments: List[int] = [-1, 1], type_caster=int) -> None:
        super().__init__()
        self.text = text
        self.default_value = default_value
        self.bounds = [-1024, 1024]
        self.bound_lower = min(self.bounds)
        self.bound_upper = max(self.bounds)
        self.key = key
        self.increments =  increments
        self.type_caster = type_caster
        self.key_to_offset = {
            f"{key}--{inc}": inc for inc in self.increments
        }
        self.events = set(self.key_to_offset)
        self.events.add(self.key)
        self.input_as = InputAutoselect(
            key=key,
            default_text=self.default_value,
            size=4,
            type_caster=self.type_caster,
            bounds=self.bounds
        )
        self.elements = [
            sg.Text(self.text, background_color = BACKGROUND_COLOR)
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc < 0
        ] + [ 
            *self.input_as.elements 
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc > 0
        ]

    def handle(self, **kwargs):
        event = kwargs['event']
        if event != self.key:
            inc = self.key_to_offset[event]
            value_current = self.get()
            value_new = value_current + inc
            self.input_as.input.update(value = value_new)
        self.input_as.handle(**kwargs)
        value_new = self.get()
        client_cli_cmd = f"DO _tracker_set_offset_z {value_new}"
        self.client.process(client_cli_cmd)

    def get(self):
        return self.input_as.get()

    def add_values(self, values):
        values[self.key] = self.get()

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        self.handle()

class XYGamePad(AbstractElement):
    def __init__(self,
            icon_xleft, icon_xright, icon_yleft, icon_yright,
            key="xypad", input_size=5, input_bounds=(0,1048),
            default_value = 0,
            font=(None,19),
            icon_size: Tuple[int, int] = (64, 64),
        ) -> None:
        super().__init__()

        self.icon_xleft = icon_xleft
        self.icon_xright = icon_xright
        self.icon_yleft = icon_yleft
        self.icon_yright = icon_yright
        self.icon_size = icon_size

        self.key = key
        self.key_input = f"{self.key}-input"
        self.key_xleft = f"{self.key}_$X$$-$"
        self.key_xright = f"{self.key}_$X$$+$"
        self.key_yleft = f"{self.key}_$Y$$-$"
        self.key_yright = f"{self.key}_$Y$$+$"

        self.default_value = default_value

        self.button_xleft = sg.Button(
            key=self.key_xleft,
            image_data=self.icon_xleft,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.button_xright = sg.Button(
            key=self.key_xright,
            image_data=self.icon_xright,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.button_yleft = sg.Button(
            key=self.key_yleft,
            image_data=self.icon_yleft,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.button_yright = sg.Button(
            key=self.key_yright,
            image_data=self.icon_yright,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.input_as = InputAutoselect(
            key=self.key_input,
            default_text=str(self.default_value),
            bounds=input_bounds,
            size=input_size,
            type_caster=int,
            font=font
        )
        self.buttons = [
            self.button_xleft, self.button_xright,
            self.button_yleft, self.button_yright,
        ]
        
        self.elements = [
            self.button_xleft,
            sg.Column(
                [[self.button_yright], 
                [*self.input_as.elements], 
                [self.button_yleft]],
                background_color = BACKGROUND_COLOR
            ),
            self.button_xright,
        ]
        self.events = { self.key, self.key_input }
        for button in self.buttons:
            self.events.add(button.key)
            self.events.add( f"{button.key}-Press" )
            self.events.add( f"{button.key}-Release" )

    def handle(self, **kwargs):
        event = kwargs['event']
        self.input_as.handle(**kwargs)

        if event.endswith("-Release"):
            motor = 'x' if '$X$' in event else 'y'
            client_cli_cmd = f"DO _teensy_commands_move{motor} 0"
            self.client.process(client_cli_cmd)

        elif event.endswith("-Press"):
            motor = 'x' if '$X$' in event else 'y'
            sign = 1 if '$+$' in event else -1
            speed = self.get()
            client_cli_cmd = f"DO _teensy_commands_move{motor} {sign*speed}"
            self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )

    def get(self):
        return self.input_as.get()

    def bind(self):
        for button in self.buttons:
            button.bind('<ButtonPress>', "-Press", propagate=False)
            button.bind('<ButtonRelease>', "-Release", propagate=False)

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state( all_states )

class ZGamePad(AbstractElement):
    def __init__(self,
            icon_zpos, icon_zneg,
            default_value: int,
            key="zpad", input_size=5, input_bounds=(0,1048),
            font=(None,19),
            icon_size: Tuple[int, int] = (64, 64),
        ) -> None:
        super().__init__()

        self.icon_zpos = icon_zpos
        self.icon_zneg = icon_zneg
        self.icon_size = icon_size

        self.key = key
        self.key_input = f"{self.key}-input"
        self.key_zpos = f"{self.key}_$Z$$+$"
        self.key_zneg = f"{self.key}_$Z$$-$"

        self.default_value = default_value


        self.button_zpos = sg.Button(
            key=self.key_zpos,
            image_data=self.icon_zpos,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.button_zneg = sg.Button(
            key=self.key_zneg,
            image_data=self.icon_zneg,
            image_size=self.icon_size,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        
        self.input_as = InputAutoselect(
            key=self.key_input,
            default_text=str(self.default_value),
            bounds=input_bounds,
            size=input_size,
            type_caster=int,
            font=font
        )
        self.buttons = [
            self.button_zpos, self.button_zneg,
        ]
        
        self.elements = [
            sg.Column(
                [[self.button_zpos], 
                [*self.input_as.elements], 
                [self.button_zneg]],
                background_color = BACKGROUND_COLOR
            ),
        ]
        self.events = { self.key, self.key_input }
        for button in self.buttons:
            self.events.add(button.key)
            self.events.add( f"{button.key}-Press" )
            self.events.add( f"{button.key}-Release" )

    def handle(self, **kwargs):
        event = kwargs['event']
        self.input_as.handle(**kwargs)

        if event.endswith("-Release"):
            client_cli_cmd = f"DO _teensy_commands_movez 0"
            self.client.process(client_cli_cmd)
        elif event.endswith("-Press"):
            sign = 1 if '$+$' in event else -1
            speed = self.get()
            client_cli_cmd = f"DO _teensy_commands_movez {sign*speed}"
            self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )

    def get(self):
        return self.input_as.get()

    def bind(self):
        for button in self.buttons:
            button.bind('<ButtonPress>', "-Press", propagate=False)
            button.bind('<ButtonRelease>', "-Release", propagate=False)

    def add_state(self, all_states):
        self.input_as.add_state(all_states)

    def load_state(self, all_states):
        self.input_as.load_state( all_states )

class FolderBrowser(AbstractElement):
    def __init__(self, default_path) -> None:
        super().__init__()
        self.key = "data_directory"
        self.key_browser = f"{self.key}-BROWSER"
        self.default_path = default_path
        self.folder_browser = sg.FolderBrowse(
            key=self.key_browser,
            button_text = "Browse",
            button_color=BUTTON_COLOR,
            target = self.key,
            initial_folder = "."
        )
        self.input = sg.Input(
            key = self.key,
            default_text=self.default_path,
            size=90,
            readonly=True,
            enable_events=True
        )
        self.elements = [
            sg.Text("Data Directory: ", s=(13), background_color = BACKGROUND_COLOR),
            self.folder_browser,
            self.input
        ]
        self.events = {
            self.key,
            self.key_browser
        }

    def handle(self, **kwargs):
        directory = self.get()
        client_cli_cmd = f"DO set_directories {directory}"
        self.client.process(client_cli_cmd)

    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return self.input.get()

    def add_state(self, all_states):
        all_states[self.key] = self.get()

    def load_state(self, all_states):
        fp_folder = all_states[self.key]
        self.input.update(value=fp_folder)
        self.handle()

class MotorLimit(AbstractElement):
    def __init__(self) -> None:
        super().__init__()
        self.key = "motorlimit"
        self.color_set = "#0B5345"
        self.color_unset = BUTTON_COLOR
        self.key_zp = f"{self.key}-zp"
        self.key_zn = f"{self.key}-zn"
        self.key_yp = f"{self.key}-yp"
        self.key_yn = f"{self.key}-yn"
        self.key_xp = f"{self.key}-xp"
        self.key_xn = f"{self.key}-xn"

        self.zp = sg.Button(
            button_text="Set Max Z",
            key=self.key_zp,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.zp_is_set = False

        self.zn = sg.Button(
            button_text="Set Min Z",
            key=self.key_zn,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.zn_is_set = False

        self.yp = sg.Button(
            button_text="Set Max Y",
            key=self.key_yp,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.yp_is_set = False

        self.yn = sg.Button(
            button_text="Set Min Y",
            key=self.key_yn,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.yn_is_set = False

        self.xp = sg.Button(
            button_text="Set Max X",
            key=self.key_xp,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.xp_is_set = False

        self.xn = sg.Button(
            button_text="Set Min X",
            key=self.key_xn,
            enable_events=True,
            disabled=False,
            size = 10,
            button_color=self.color_unset
        )
        self.xn_is_set = False

        self.elements = [sg.Column(
            [[self.zp],
             [self.zn],
             [self.yp],
             [self.yn],
             [self.xp],
             [self.xn]],
             background_color = BACKGROUND_COLOR
            )
        ]
        self.events = {
            self.key_zp, self.key_zn, self.key_yp, self.key_yn, self.key_xp, self.key_xn
        }

    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_zp:
            if not self.zp_is_set:
                self.zp_is_set = True
                self.zp.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit z p"
                self.client.process(client_cli_cmd)

        elif event == self.key_zn:
            if not self.zn_is_set:
                self.zn_is_set = True
                self.zn.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit z n"
                self.client.process(client_cli_cmd)

        elif event == self.key_yn:
            if not self.yn_is_set:
                self.yn_is_set = True
                self.yn.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit y n"
                self.client.process(client_cli_cmd)

        elif event == self.key_yp:
            if not self.yp_is_set:
                self.yp_is_set = True
                self.yp.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit y p"
                self.client.process(client_cli_cmd)

        elif event == self.key_xn:
            if not self.xn_is_set:
                self.xn_is_set = True
                self.xn.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit x n"
                self.client.process(client_cli_cmd)

        elif event == self.key_xp:
            if not self.xp_is_set:
                self.xp_is_set = True
                self.xp.update(button_color=self.color_set)
                client_cli_cmd = "DO _tennsy_commands_set_motor_limit x p"
                self.client.process(client_cli_cmd)


    def add_values(self, values):
        values[self.key] = self.get()

    def get(self):
        return {
            'xp': self.xp_is_set,
            'yp': self.yp_is_set,
            'zp': self.zp_is_set,
            'xn': self.xn_is_set,
            'yn': self.yn_is_set,
            'zn': self.zn_is_set,
        }
