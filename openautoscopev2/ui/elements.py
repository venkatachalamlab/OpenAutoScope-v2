# Modules
import json

from typing import Dict, List, Tuple
from collections import defaultdict
import PySimpleGUI as sg

from openautoscopev2.zmq.client import GUIClient
from openautoscopev2.devices.utils import resolve_path

# Parameters
BACKGROUND_COLOR = '#B3B6B7'
TEXT_COLOR = '#1B2631'
BUTTON_COLOR = '#626567'
# Methods
## Input for Ports
def sg_input_port(key, port):
    return sg.Input(
        key=key,
        size=5,
        default_text=str(port)
    )
## JLoad
def jload(fp):
    with open(fp, 'r', encoding='utf-8') as in_file:
        return json.load( in_file )
## JDump
def jdump(obj, fp):
    with open(fp, 'w', encoding='utf-8') as out_file:
        json.dump(
            obj, out_file,
            sort_keys=False,
            ensure_ascii=False,
            indent=1
        )
    return

# Classes
## Abstract Element with disable/enable, status
class AbstractElement:
    # Constructor
    def __init__(self) -> None:
        self.events = set()
        self.elements = list()
        self.client = None
        return
    # Handle
    def handle(self, **kwargs):
        raise NotImplementedError()
    # Disable
    def disable(self):
        for element in self.elements:
            try:
                element.update(disabled=True)
            except Exception as e:
                pass
        return
    def enable(self):
        for element in self.elements:
            try:
                element.update(disabled=False)
            except Exception as e:
                pass
        return
    # Values
    def add_values(self, values):
        raise NotImplementedError()
    # Get Value
    def get(self):
        raise NotImplementedError()
    # Set Client
    def set_client(self, client: GUIClient):
        self.client = client
        return
    # State
    def add_state(self, all_states):
        return
    def load_state(self, all_states):
        return

## Return Key Handler
class ReturnHandler(AbstractElement):
    # Constructor
    def __init__(self) -> None:
        super().__init__()
        self.key = "RETURN-KEY"
        self.elements = [
            sg.Button(visible=False, key=self.key, bind_return_key=True)
        ]
        self.events = { self.key }
        return
    def set_window(self, window):
        self.window = window
        return
    def handle(self, **kwargs):
        element_focused = self.window.find_element_with_focus()
        self.window.write_event_value(
            element_focused.key,
            '<RETURN-KEY-CALL>'
        )
        return
    def add_values(self, values):
        return
    def disable(self):
        return
    def enable(self):
        return

## Input Element with Autoselect and Enter Event handling
class InputAutoselect(AbstractElement):
    def __init__(self, key: str, default_text: int, size, type_caster=int, bounds=(None, None), font=None) -> None:
        super().__init__()
        self.key = key
        self.default_text = default_text
        self.type_caster = type_caster
        self.bound_lower, self.bound_upper = bounds
        self.input = sg.Input(
            default_text=self.default_text,
            key=self.key,
            justification='righ',
            size=size,
            font=font
        )
        self.events = { self.key }
        self.elements = [ self.input ]
        return
    # Handle
    def handle(self, **kwargs):
        value = self.get()
        if self.bound_lower is not None:
            value = max( self.bound_lower, value )
        if self.bound_upper is not None:
            value = min( self.bound_upper, value )
        self.input.update(value=value)
        return
    # Values
    def add_values(self, values):
        values[self.key] = self.get()
        return
    # Value
    def get(self):
        raw = self.input.get()
        if not isinstance(raw, str):
            return self.type_caster(raw)
        # remove character values
        # don't forget the sign
        sign = "-" if raw[0] == "-" else ""
        res = sign + "0" + "".join([
            c for c in raw if c.isdigit()
        ])
        return self.type_caster( res )
    # Bounds
    def set_bounds(self, bound_lower=None, bound_upper=None):
        if bound_lower:
            self.bound_lower = bound_lower
        if bound_upper:
            self.bound_upper = bound_upper
        self.handle()
        return
    # State
    def add_state(self, all_states):
        all_states[self.key] = self.get()
        return
    def load_state(self, all_states):
        self.input.update(value = all_states[self.key])
        self.handle()
        return

## LED Combined Elements
class LEDCompound(AbstractElement):
    # Cosntructor
    def __init__(
            self, text: str, key: str,
            led_name: str,
            icon_off, icon_on,
            icon_size: Tuple[int, int],
            type_caster = int,
            bounds=(None, None)
        ) -> None:
        super().__init__()
        self.icon_on = icon_on
        self.type_caster = type_caster
        self.icon_off = icon_off
        self.icon_size = icon_size
        self.led_name = led_name
        self.bounds = bounds
        self.key = key
        self.key_toggle = f"{self.key}-TOGGLE"
        self.key_input= f"{self.key}-INPUT"
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
        self.input_as = InputAutoselect(
            key=self.key_input, default_text='0', size=3, type_caster=type_caster,
            bounds=self.bounds
        )
        self.elements = [
            self.button, self.text, *self.input_as.elements
        ]
        self.events = {
            self.key_toggle, self.key_input
        }
        self.toggle = False
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            self.toggle = not self.toggle
            image_data = self.icon_on if self.toggle else self.icon_off
            self.button.update(image_data=image_data)
        elif event == self.key_input:
            self.input_as.handle(**kwargs)
        if self.toggle:
            intensity = self.type_caster(self.get() * 2.55)
            client_cli_cmd = f"DO _teensy_commands_set_led {self.led_name} {intensity}"
            self.client.process(client_cli_cmd)
        else:
            client_cli_cmd = f"DO _teensy_commands_set_led {self.led_name} 0"
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )
        return
    def get(self):
        if not self.toggle:
            return 0
        return self.input_as.get()

## LED IR
class LEDIR(AbstractElement):
    # Cosntructor
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
        self.input = sg.Input(default_text='100', size=3, disabled=True, key='')
        self.elements = [
            self.button, self.text, self.input
        ]
        self.events = {
            self.key_toggle
        }
        self.toggle = False
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            self.toggle = not self.toggle
            image_data = self.icon_on if self.toggle else self.icon_off
            self.button.update(image_data=image_data)
        state_str = "n" if self.toggle else "f"
        client_cli_cmd = f"DO _teensy_commands_set_toggle_led {state_str}"
        self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def get(self):
        return self.toggle

## Recording
class ToggleRecording(AbstractElement):
    # Cosntructor
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
        self.toggle = False
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            self.toggle = not self.toggle
            if self.toggle:
                client_cli_cmd = f"DO _writer_start"
                self.button.update(image_data=self.icon_on)
                self.text.update(value=self.text_on)
            else:
                client_cli_cmd = f"DO _writer_stop"
                self.button.update(image_data=self.icon_off)
                self.text.update(value=self.text_off)
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def get(self):
        return self.toggle

## Tracking
class ToggleTracking(AbstractElement):
    # Cosntructor
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
        self.toggle = False
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_toggle:
            self.toggle = not self.toggle
            if self.toggle:
                client_cli_cmd = f"DO _tracker_start"
                self.button.update(image_data=self.icon_on)
                self.text.update(value=self.text_on)
            else:
                client_cli_cmd = f"DO _tracker_stop"
                self.button.update(image_data=self.icon_off)
                self.text.update(value=self.text_off)
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def get(self):
        return self.toggle

## Exposure Combined Elements
class ExposureCompound(AbstractElement):
    # Cosntructor
    def __init__(
            self, text:str, key: str,
            icon, icon_size: Tuple[int, int],
            camera_name: str,
            type_caster = int,
            bounds=(None, None)
        ) -> None:
        super().__init__()
        self.key = key
        self.icon = icon
        self.icon_size = icon_size
        self.camera_name = camera_name
        self.bounds = bounds
        self.text = text
        self.button = sg.Button(
            image_data=self.icon,
            image_size=self.icon_size,
            # disabled=True,
            enable_events=False,
            button_color=(sg.theme_background_color(),sg.theme_background_color())
        )
        self.text_element = sg.Text(
            text=self.text + f'(min:{self.bounds[0]}, max:{self.bounds[1]})', s=30,
            background_color = BACKGROUND_COLOR
        )
        self.input_as = InputAutoselect(
            key=self.key, default_text='18000', size=6, type_caster=type_caster,
            bounds=self.bounds
        )
        self.unit = sg.Text(
            text='\U000003bcs',
            background_color = BACKGROUND_COLOR
        )
        self.elements = [
            self.button, self.text_element, *self.input_as.elements, self.unit
        ]
        self.events = {
            self.key
        }
        return
    # Handle
    def handle(self, **kwargs):
        framerate = kwargs['framerate']
        self.input_as.handle(**kwargs)
        exposure_time = self.get()
        client_cli_cmd = "DO _flir_camera_set_exposure_framerate_{} {} {}".format(
            self.camera_name, exposure_time, framerate
        )
        self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def set_bounds(self, bound_lower=None, bound_upper=None):
        bound_lower = self.bounds[0] if bound_lower is None else bound_lower
        bound_upper = self.bounds[1] if bound_upper is None else bound_upper
        self.bounds = (bound_lower, bound_upper)
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )
        self.text_element.update(
            value=self.text + f'(min:{self.bounds[0]}, max:{self.bounds[1]})'
        )
        return
    def get(self):
        return self.input_as.get()
    # State
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state(all_states)
        return

## Framerate Compound
class FramerateCompound(AbstractElement):
    # Cosntructor
    def __init__(
            self,
            element_exposure_behavior: ExposureCompound,
            element_exposure_gfp: ExposureCompound,
            icon, icon_size,
            key: str = 'framerate',
            text: str = "Imaging Frame Rate (min:1, max:48)",
            framerate_default: int = 20,
            bounds=(1, 48),
            type_caster = int
        ) -> None:
        super().__init__()
        self.element_exposure_behavior = element_exposure_behavior
        self.element_exposure_gfp = element_exposure_gfp
        self.key = key
        self.framerate_default = framerate_default
        self.icon = icon
        self.icon_size = icon_size
        self.bounds = bounds
        self.button = sg.Button(
            image_data=icon,
            image_size=icon_size,
            # disabled=True,
            enable_events=False
        )
        self.text = sg.Text(
            text=text, s=30,
            background_color = BACKGROUND_COLOR
        )
        self.input_as = InputAutoselect(
            key=self.key, default_text=str(framerate_default), size=6, type_caster=type_caster,
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
        return
    # Handle
    def handle(self, **kwargs):
        self.input_as.handle(**kwargs)
        framerate = self.get()
        # Update Bounds
        bound_upper = int( 995000/framerate )
        self.element_exposure_behavior.set_bounds(bound_upper=bound_upper)
        self.element_exposure_gfp.set_bounds(bound_upper=bound_upper)
        # Handle
        self.element_exposure_behavior.handle(framerate=framerate)
        self.element_exposure_gfp.handle(framerate=framerate)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )
        return
    def get(self):
        return self.input_as.get()
    # State
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state(all_states)
        self.handle({
            self.key: self.get()
        })
        return

class InputWithIncrements(AbstractElement):
    # Constructor
    def __init__(self, text:str, key: str, default_value: int, increments: List[int] = [-1, 1], bounds: List[int] = [-1024, 1024], type_caster=int) -> None:
        super().__init__()
        self.text = text
        self.default_value = default_value
        self.bounds = bounds
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
            bounds=bounds
        )
        self.elements = [
            sg.Text(self.text, background_color = BACKGROUND_COLOR)
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc < 0
        ] + [ *self.input_as.elements ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc > 0
        ]
        _, self.camera_name, self.offset_direction = self.key.split('_')
        self.key_offset_other = 'offset_{}_{}'.format(
            self.camera_name,
            'x' if self.offset_direction == 'y' else 'y'
        )
        return
    # Handle
    def handle(self, **kwargs):
        binsize = 2  # DEBUG it should not be constant! comply with run_gui.py
        event = kwargs['event']
        offset_other = kwargs[self.key_offset_other]
        if event != self.key:
            inc = self.key_to_offset[event]
            value_current = self.type_caster( kwargs[self.key] )
            value_new = min(
                self.bound_upper,
                max(
                    self.bound_lower,
                    value_current + inc
                )
            )
            self.input_as.input.update(value = value_new)
        # Get Values and Set
        self.input_as.handle(**kwargs)
        value_new = self.get()
        if self.offset_direction == 'x':
            offset_x, offset_y = 224 + value_new, 44 + int(offset_other)
        else:
            offset_x, offset_y = 224 + int(offset_other), 44 + value_new
        client_cli_cmd = "DO _flir_camera_set_region_{} 1 {} {} {} {} {}".format(
            self.camera_name, 512, 512, binsize, offset_y, offset_x  # DEBUG shape can change! make it complient with run_gui.py
        )
        self.client.process(client_cli_cmd)
        return
    # Get
    def get(self):
        return self.input_as.get()
    # Values
    def add_values(self, values):
        values[self.key] = self.get()
        return
    # State
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        self.handle({
            self.key: self.get()
        })
        return

class InputwithIncrementsforZOffset(AbstractElement):
    # Constructor
    def __init__(self, text:str, key: str, default_value: int, increments: List[int] = [-1, 1], bounds: List[int] = [-1024, 1024], type_caster=int) -> None:
        super().__init__()
        self.text = text
        self.default_value = default_value
        self.bounds = bounds
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
            bounds=bounds
        )
        self.elements = [
            sg.Text(self.text, background_color = BACKGROUND_COLOR)
        ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc < 0
        ] + [ *self.input_as.elements ] + [
            sg.Button(button_text=f"{inc}",key=event, s=(3, 1), button_color=BUTTON_COLOR) for event, inc in self.key_to_offset.items() if inc > 0
        ]
        return

    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        if event != self.key:
            inc = self.key_to_offset[event]
            value_current = self.get()
            value_new = value_current + inc
            self.input_as.input.update(value = value_new)
        # Get Values and Set
        self.input_as.handle(**kwargs)
        value_new = self.get()
        client_cli_cmd = f"DO _tracker_set_offset_z {value_new}"
        self.client.process(client_cli_cmd)
        return
    
    def get(self):
        return self.input_as.get()

    def add_values(self, values):
        values[self.key] = self.get()
        return
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        self.handle()
        return


class ModelsCombo(AbstractElement):
    def __init__(self, text: str, key: str, fp_models_paths: str, default_value: str = None, fp_gui_folder: str = ".") -> None:
        super().__init__()
        self.fp_models_paths = fp_models_paths
        self.fp_gui_folder = fp_gui_folder
        self.model_paths = dict()
        self.default_value = default_value

        self.key = key
        self.key_combo = f"{self.key}--COMBO"
        self.events = {
            self.key,
            self.key_combo
        }
        # Elements
        self.text = sg.Text(text, background_color = BACKGROUND_COLOR)  # TODO: add tooltip
        self.combo = sg.Combo(
            values=["10x_default_all"] if default_value is None else [default_value],
            default_value="10x_default_all" if default_value is None else default_value,
            key=self.key_combo,
            enable_events=True,
            s=25,
            button_background_color=BUTTON_COLOR
        )
        self.elements = [ self.text, self.combo ]
        return
    
    def _load_models(self):
        # TODO: load models each time the combo is selected or in some other way
        self.model_paths = {
            key: resolve_path(fp, self.fp_gui_folder) for key,fp in jload( self.fp_models_paths ).items()
        }
        values = list(self.model_paths)
        self.combo.update(
            values=values, value=values[0]
        )
        return


    def handle(self, **kwargs):
        event = kwargs['event']
        if event == self.key_combo:
            key = self.get()
            fp_model = self.model_paths[key]
            client_cli_cmd = "DO _tracker_set_tracking_system {} {}".format(key, fp_model)
            self.client.process(client_cli_cmd)
        return
    
    def get(self):
        return self.combo.get()

    def add_values(self, values):
        values[self.key] = self.model_paths[self.get()]
        return
    
    def add_state(self, all_states):
        all_states[self.key_combo] = self.get()
        return
    def load_state(self, all_states):
        self.combo.update(value=all_states[self.key_combo])
        self.handle({
            self.key_combo: self.get()
        })
        return

## Z-Interpolation Tracking
class ZInterpolationTracking(AbstractElement):
    # Cosntructor
    def __init__(self) -> None:
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
            text="Use Plane Interpolation for Z-Tracking",
            key=self.key_checkbox,
            enable_events=True,
            default=False,
            background_color = BACKGROUND_COLOR,
            s=39
        )
        self.p1 = sg.Button(
            button_text="Set Point 1",
            key=self.key_p1,
            enable_events=True,
            disabled=True,
            button_color=self.color_disabled
        )
        self.p1_is_set = False
        self.p2 = sg.Button(
            button_text="Set Point 2",
            key=self.key_p2,
            enable_events=True,
            disabled=True,
            button_color=self.color_disabled
        )
        self.p2_is_set = False
        self.p3 = sg.Button(
            button_text="Set Point 3",
            key=self.key_p3,
            enable_events=True,
            disabled=True,
            button_color=self.color_disabled
        )
        self.p3_is_set = False

        self.elements = [
            self.checkbox, self.p1, self.p2, self.p3,
        ]
        self.events = {
            self.key_checkbox, self.key_p1, self.key_p2, self.key_p3,
        }
        return
    # Handle
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
        elif event == self.key_p1:
            self.p1_is_set = True
            self.p1.update(button_color=self.color_set)
            client_cli_cmd = "DO set_point 1"
            self.client.process(client_cli_cmd)
        elif event == self.key_p2:
            self.p2_is_set = True
            self.p2.update(button_color=self.color_set)
            client_cli_cmd = "DO set_point 2"
            self.client.process(client_cli_cmd)
        elif event == self.key_p3:
            self.p3_is_set = True
            self.p3.update(button_color=self.color_set)
            client_cli_cmd = "DO set_point 3"
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def get(self):
        return {
            'checkbox': self.checkbox.get(),
            'p1': self.p1_is_set,
            'p2': self.p2_is_set,
            'p3': self.p3_is_set,
        }

## XY Game Pad
class XYGamePad(AbstractElement):
    # Constructor
    def __init__(self,
            icon_xleft, icon_xright, icon_yleft, icon_yright,
            key="xypad", input_size=5, input_bounds=(0,2048),
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
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        self.input_as.handle(**kwargs)
        # X Press
        if event.endswith("-Release"):
            # Stop velocity
            motor = 'x' if '$X$' in event else 'y'
            client_cli_cmd = f"DO _teensy_commands_move{motor} 0"
            self.client.process(client_cli_cmd)
        elif event.endswith("-Press"):
            # Set Velocity
            motor = 'x' if '$X$' in event else 'y'
            sign = 1 if '$+$' in event else -1
            speed = self.get()
            client_cli_cmd = f"DO _teensy_commands_move{motor} {sign*speed}"
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )
        return
    def get(self):
        return self.input_as.get()
    # Bind Buttons
    def bind(self):
        for button in self.buttons:
            button.bind('<ButtonPress>', "-Press", propagate=False)
            button.bind('<ButtonRelease>', "-Release", propagate=False)
        return
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        return

## Z Game Pad
class ZGamePad(AbstractElement):
    # Constructor
    def __init__(self,
            icon_zpos, icon_zneg,
            key="zpad", input_size=5, input_bounds=(0,2048),
            font=(None,19),
            icon_size: Tuple[int, int] = (64, 64),
            default_value: int = 0
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
        return
    # Handle
    def handle(self, **kwargs):
        event = kwargs['event']
        self.input_as.handle(**kwargs)
        # X Press
        if event.endswith("-Release"):
            # Stop velocity
            client_cli_cmd = f"DO _teensy_commands_movez 0"
            self.client.process(client_cli_cmd)
        elif event.endswith("-Press"):
            # Set Velocity
            sign = 1 if '$+$' in event else -1
            speed = self.get()
            client_cli_cmd = f"DO _teensy_commands_movez {sign*speed}"
            self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def set_bounds(self, bound_lower=None, bound_upper=None):
        self.input_as.set_bounds(
            bound_lower=bound_lower,
            bound_upper=bound_upper
        )
        return
    def get(self):
        return self.input_as.get()
    # Bind Buttons
    def bind(self):
        for button in self.buttons:
            button.bind('<ButtonPress>', "-Press", propagate=False)
            button.bind('<ButtonRelease>', "-Release", propagate=False)
        return
    def add_state(self, all_states):
        self.input_as.add_state(all_states)
        return
    def load_state(self, all_states):
        self.input_as.load_state( all_states )
        return
## Folder Browser
class FolderBrowser(AbstractElement):
    # Constructor
    def __init__(self, default_path = "./") -> None:
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
        return
    # Handle
    def handle(self, **kwargs):
        # Stop velocity
        directory = self.get()
        client_cli_cmd = f"DO _set_directories {directory}"
        self.client.process(client_cli_cmd)
        return
    def add_values(self, values):
        values[self.key] = self.get()
        return
    def get(self):
        return self.input.get()

    # State
    def add_state(self, all_states):
        all_states[self.key] = self.get()
        return
    def load_state(self, all_states):
        fp_folder = all_states[self.key]
        self.input.update(value=fp_folder)
        self.handle()
        return