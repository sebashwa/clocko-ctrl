import network
import json
import ssd1306
from machine import ADC, Pin, SoftI2C
from time import sleep, ticks_ms, ticks_diff


# APPLICATION STATE


class State:
    error = None
    selected_task_index = None
    active_task = None

    @classmethod
    def change_for_knob_turn(cls, index_value):
        cls.selected_task_index = index_value

    @classmethod
    def change_for_button_push(cls):
        if cls.error is not None:
            return

        if cls.active_task:
            cls.active_task = None
        else:
            cls.active_task = Config.tasks[cls.selected_task_index]


class Error:
    GENERAL = "GENERAL"
    WIFI_CONNECTION = "WIFI_CONNECTION"
    CONFIG_READ = "CONFIG_READ"
    CONFIG_PARSE = "CONFIG_PARSE"
    CONFIG_NO_API_KEY = "CONFIG_NO_API_KEY"
    CONFIG_NO_WIFI = "CONFIG_NO_WIFI"


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
    wifi = Wifi
    tasks = []

    @classmethod
    def validate(cls):
        if not cls.wifi.essid or not cls.wifi.password:
            State.error = Error.CONFIG_NO_WIFI
        elif not cls.api_key:
            State.error = Error.CONFIG_NO_API_KEY

    @classmethod
    def load(cls):
        config_json = ConfigFile.read_and_parse()
        cls.api_key = config_json.get("api_key")
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

    poti = ADC(Pin(GPIO_PIN))
    poti.atten(ADC.ATTN_11DB)
    previous_value = 0

    @staticmethod
    def scale_value(value):
        scale = len(Config.tasks) - 1
        return round((scale / 4095) * value)

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
    pin = Pin(GPIO_PIN, Pin.IN)
    previous_value = 0

    @classmethod
    def handle_push(cls):
        current_value = cls.pin.value()

        if current_value == 1 and cls.previous_value == 0:
            cls.previous_value = 1
            State.change_for_button_push()

        elif current_value == 0:
            cls.previous_value = 0


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
    def format_time(cls, 

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
            Error.CONFIG_NO_WIFI: "WIFI config error!",
            Error.CONFIG_NO_API_KEY: "No API key configured!",
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


            cls.wrapped_text(State.active_task.name, 0, 1)
            cls.centered_text("00:00:00", 5)
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
    Display.render()
    Config.load()
    Wifi.connect()


def run():
    sleep(0.1)

    Knob.handle_turn()
    Button.handle_push()

    Display.render()


def main():
    init()

    while True:
        try:
            run()
        except:
            State.error = Error.GENERAL
main()
