import network
import gc
from machine import ADC, Pin, SoftI2C
import json
import ssd1306
from time import sleep, ticks_ms, ticks_diff


# APPLICATION STATE


class State:
    error = None
    selected_task_index = None
    active_task = None
    timer_started_at = None

    @classmethod
    def change_for_knob_turn(cls, index_value):
        cls.selected_task_index = index_value

    @classmethod
    def change_for_button_push(cls):
        if cls.error is not None:
            return

        if cls.active_task:
            cls.active_task = None
            cls.timer_started_at = None
        else:
            cls.active_task = Config.tasks[cls.selected_task_index]
            cls.timer_started_at = ticks_ms()


class Error:
    GENERAL = "GENERAL"
    WIFI_CONNECTION = "WIFI_CONNECTION"
    CONFIG_READ = "CONFIG_READ"
    CONFIG_PARSE = "CONFIG_PARSE"
    CONFIG_API = "CONFIG_API"
    CONFIG_WIFI = "CONFIG_WIFI"
    CONFIG_SERVICE_ID = "CONFIG_SERVICE_ID"


# CONFIG


class ClockodoTask:
    def __init__(self, name, project_id=None, customer_id=None):
        self.project_id = project_id
        self.customer_id = customer_id
        self.name = name

    @staticmethod
    def from_json(json):
        name = json.get("name")
        customer_id = json.get("customer_id")
        project_id = json.get("project_id")

        no_name = name is None
        no_id = customer_id is None and project_id is None
        if no_name or no_id:
            return None

        return ClockodoTask(name=name, customer_id=customer_id, project_id=project_id)


class ConfigFile:
    FILENAME = "config.json"

    @classmethod
    def read_and_parse(cls):
        try:
            file = open(cls.FILENAME, "r")
            config_json = file.read()
            file.close()
        except:
            State.error = Error.CONFIG_READ

        try:
            return json.loads(config_json)
        except:
            State.error = Error.CONFIG_PARSE


class Config:
    class Wifi:
        essid = None
        password = None

    api_key = None
    api_user = None
    wifi = Wifi
    tasks = []

    @classmethod
    def validate(cls):
        if not cls.wifi.essid or not cls.wifi.password:
            State.error = Error.CONFIG_WIFI
        elif not cls.api_key or not cls.api_user:
            State.error = Error.CONFIG_API
        elif not cls.service_id:
            State.error = Error.CONFIG_SERVICE_ID

    @classmethod
    def load(cls):
        config_json = ConfigFile.read_and_parse()
        cls.api_key = config_json.get("api_key")
        cls.api_user = config_json.get("api_user")
        cls.service_id = config_json.get("service_id")
        cls.wifi.essid = config_json.get("wifi_essid")
        cls.wifi.password = config_json.get("wifi_password")

        cls.tasks = []
        config_tasks = config_json.get("tasks", [])
        for task_data in config_tasks:
            task = ClockodoTask.from_json(task_data)

            if task is not None:
                cls.tasks.append(task)

        cls.validate()


# WIFI


class Wifi:
    CONNECTION_TIMEOUT = 10000
    station_interface = network.WLAN(network.STA_IF)
    access_point_interface = network.WLAN(network.AP_IF)
    last_connect_at = None

    @classmethod
    def wait_for_connection(cls):
        while not cls.station_interface.isconnected():
            diff = ticks_diff(ticks_ms(), cls.last_connect_at)
            if diff < cls.CONNECTION_TIMEOUT:
                continue
            else:
                break

        if not cls.station_interface.isconnected():
            raise

    @classmethod
    def connect(cls):
        if cls.station_interface.isconnected():
            return

        essid = Config.wifi.essid
        password = Config.wifi.password

        if not essid or not password:
            return

        cls.station_interface.active(True)
        cls.access_point_interface.active(False)

        cls.last_connect_at = ticks_ms()

        try:
            cls.station_interface.connect(essid, password)
            cls.wait_for_connection()
        except:
            State.error = Error.WIFI_CONNECTION


# PERIPHERALS


class Knob:
    MAX_ATTN_VALUE = 4095
    GPIO_PIN = 36

    scale = MAX_ATTN_VALUE
    poti = ADC(Pin(GPIO_PIN))
    poti.atten(ADC.ATTN_11DB)
    previous_value = 0

    @classmethod
    def scale_value(cls, value):
        return round((cls.scale / 4095) * value)

    @classmethod
    def value(cls):
        read_value = cls.poti.read()
        return cls.scale_value(read_value)

    @classmethod
    def handle_turn(cls):
        current_value = cls.value()

        if current_value != cls.previous_value:
            cls.previous_value = current_value
            State.change_for_knob_turn(current_value)


class Button:
    GPIO_PIN = 13
    pin = Pin(GPIO_PIN, Pin.IN, Pin.PULL_UP)
    previous_value = 1

    @classmethod
    def handle_push(cls):
        current_value = cls.pin.value()

        if current_value == 0 and cls.previous_value == 1:
            cls.previous_value = 0
            State.change_for_button_push()

        elif current_value == 1:
            cls.previous_value = 1


class Display:
    SCL_PIN = 22
    SDA_PIN = 21
    WIDTH = 128
    HEIGHT = 64
    CHAR_WIDTH = 8
    LINE_HEIGHT = 10
    CHARS_PER_LINE = round(WIDTH / CHAR_WIDTH)

    scl = Pin(SCL_PIN)
    sda = Pin(SDA_PIN)
    i2c = SoftI2C(scl=scl, sda=sda)
    oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)

    @classmethod
    def split_text_for_width(cls, text):
        split_indices = range(0, len(text), cls.CHARS_PER_LINE)
        return [text[i : i + cls.CHARS_PER_LINE] for i in split_indices]

    @classmethod
    def wrapped_text(cls, text, start_line=0, max_line=None):
        text_segments = cls.split_text_for_width(text)

        for i, segment in enumerate(text_segments):
            position = (start_line + i) * cls.LINE_HEIGHT
            if max_line is None or position <= max_line * cls.LINE_HEIGHT:
                cls.oled.text(segment, 0, position)
            else:
                break

    @classmethod
    def centered_text(cls, text, line):
        margin_left = 0
        text_length = len(text)
        if text_length < cls.CHARS_PER_LINE:
            margin_left = round((cls.WIDTH - text_length * cls.CHAR_WIDTH) / 2)

        cls.oled.text(text, margin_left, line * cls.LINE_HEIGHT)

    @staticmethod
    def format_time(ms):
        total_seconds = int(ms / 1000)
        hours = int(total_seconds / 60 / 60)
        seconds_minus_hours = total_seconds - hours * 60 * 60
        minutes = int(seconds_minus_hours / 60)
        seconds = seconds_minus_hours - minutes * 60

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    @classmethod
    def text(cls, text, line):
        cls.oled.text(text, 0, line * cls.LINE_HEIGHT)

    @classmethod
    def render_error(cls):
        text_for_error = {
            Error.GENERAL: "Error!",
            Error.WIFI_CONNECTION: "WIFI connection error!",
            Error.CONFIG_READ: "Config read error!",
            Error.CONFIG_PARSE: "Config parse error!",
            Error.CONFIG_WIFI: "Please configure WIFI credentials!",
            Error.CONFIG_API: "Please configure API credentials!",
            Error.CONFIG_SERVICE_ID: "Please configure a service ID!",
        }

        text = text_for_error[State.error]
        if len(text) < cls.CHARS_PER_LINE:
            cls.centered_text(text, 3)
        else:
            cls.wrapped_text(text, 2)

        cls.oled.show()

    @classmethod
    def render(cls):
        cls.oled.fill(0)

        if State.error is not None:
            return cls.render_error()

        if State.active_task is not None:
            started_since_ms = ticks_diff(ticks_ms(), State.timer_started_at)
            text = cls.format_time(started_since_ms)

            cls.wrapped_text(State.active_task.name, 0, 1)
            cls.centered_text("Timer", 3)
            cls.centered_text(text, 5)
        elif State.selected_task_index is not None:
            selected_task_index = State.selected_task_index
            cls.centered_text("Select Task", 0)

            if len(Config.tasks) == 0:
                cls.text("No tasks", 3)
                cls.text("configured", 4)
            else:
                selected_task = Config.tasks[selected_task_index]
                underline_width = len(selected_task.name) * 8
                cls.oled.hline(0, 38, underline_width, 2)

                for i, task in enumerate(Config.tasks):
                    if i < selected_task_index - 1:
                        continue

                    line = 3 + (i - selected_task_index)
                    cls.text(task.name, line)

        else:
            cls.centered_text("clocko:ctrl", 2)

        cls.oled.show()






# MAIN


def init():
    gc.enable()
    Display.render()
    Config.load()
    Knob.scale = len(Config.tasks) - 1
    Wifi.connect()


def main():
    init()

    while True:
        Knob.handle_turn()
        Button.handle_push()

        Display.render()


        gc.collect()
        sleep(0.1)


main()
