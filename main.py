import network
import gc
import urequests
from machine import ADC, Pin, SoftI2C, Timer
import json
import ssd1306
from time import sleep, ticks_ms, ticks_diff
from render_helpers import TextFormatting, TextScrolling


# APPLICATION STATE


class State:
    error: str | None = None
    triggered_request = None

    selected_task_index = None

    active_task = None
    active_entry_id = None
    timer_started_at = None

    @classmethod
    def change_for_clock_start(cls, active_task, entry_id):
        cls.active_task = active_task
        cls.timer_started_at = ticks_ms()
        cls.active_entry_id = entry_id

    @classmethod
    def change_for_clock_stop(cls):
        cls.active_task = None
        cls.timer_started_at = None
        cls.active_entry_id = None

    @classmethod
    def change_for_knob_turn(cls, index_value):
        cls.selected_task_index = index_value

    @classmethod
    def change_for_button_push(cls):
        if cls.error is not None:
            if cls.error in [Error.API_RESPONSE, Error.API_REQUEST]:
                cls.error = None

            return

        if cls.active_task:
            cls.triggered_request = ClockodoRequest.stop_clock
        else:
            cls.triggered_request = ClockodoRequest.start_clock


class Error:
    GENERAL = "GENERAL"
    WIFI_CONNECTION = "WIFI_CONNECTION"
    CONFIG_READ = "CONFIG_READ"
    CONFIG_PARSE = "CONFIG_PARSE"
    CONFIG_API = "CONFIG_API"
    CONFIG_WIFI = "CONFIG_WIFI"
    CONFIG_SERVICE_ID = "CONFIG_SERVICE_ID"
    API_REQUEST = "API_REQUEST"
    API_RESPONSE = "API_RESPONSE"


# CONFIG


class ConfigFile:
    FILENAME = "config.json"

    @classmethod
    def read_and_parse(cls):
        try:
            file = open(cls.FILENAME, "r")
            config_json = file.read()
            file.close()
            return json.loads(config_json)
        except OSError:
            State.error = Error.CONFIG_READ
        except json.JSONDecodeError:
            State.error = Error.CONFIG_PARSE
        return {}


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
    essid = None
    password = None

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

        if not cls.essid or not cls.password:
            return

        cls.station_interface.active(True)
        cls.access_point_interface.active(False)

        cls.last_connect_at = ticks_ms()

        try:
            cls.station_interface.connect(cls.essid, cls.password)
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
        result = cls.scale_value(read_value)
        return result

    @classmethod
    def handle_turn(cls):
        current_value = cls.value()

        if current_value != cls.previous_value:
            cls.previous_value = current_value
            State.change_for_knob_turn(current_value)


class Button:
    GPIO_PIN = 15
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
    scroll_timer = Timer(0).init(period=500, mode=Timer.PERIODIC, callback=lambda _: TextScrolling.scroll())


    @classmethod
    def wrapped_text(cls, text, start_line=0, max_line=None):
        text_segments = TextFormatting.split_for_wrapping(text, cls.CHARS_PER_LINE)

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

    @classmethod
    def text(cls, text, line):
        cls.oled.text(text, 0, line * cls.LINE_HEIGHT)

    @classmethod
    def render_error(cls, error):
        text_for_error = {
            Error.GENERAL: "Error!",
            Error.WIFI_CONNECTION: "WIFI connection error!",
            Error.API_REQUEST: "API request failed!",
            Error.API_RESPONSE: "API response unsuccessful!",
            Error.CONFIG_READ: "Config read error!",
            Error.CONFIG_PARSE: "Config parse error!",
            Error.CONFIG_WIFI: "Please configure WIFI credentials!",
            Error.CONFIG_API: "Please configure API credentials!",
            Error.CONFIG_SERVICE_ID: "Please configure a service ID!",
        }

        text = text_for_error[error]
        if len(text) < cls.CHARS_PER_LINE:
            cls.centered_text(text, 3)
        else:
            cls.wrapped_text(text, 2)

    @classmethod
    def render(cls):
        cls.oled.fill(0)

        if State.error is not None:
            cls.render_error(State.error)
        elif State.triggered_request is not None:
            texts = {
                ClockodoRequest.start_clock: "Starting timer",
                ClockodoRequest.stop_clock: "Stopping timer",
            }
            text = texts.get(State.triggered_request)

            dots_line = 2
            if text is not None:
                dots_line = 3
                cls.centered_text(text, 2)

            cls.centered_text("...", dots_line)
        elif State.active_task is not None:
            started_since_ms = ticks_diff(ticks_ms(), State.timer_started_at)
            timer_text = TextFormatting.format_time(started_since_ms)

            task_name = State.active_task.name
            text, is_scrolling = TextScrolling.maybe_scroll(task_name, cls.CHARS_PER_LINE)
            if is_scrolling:
                cls.text(text, 0)
            else:
                cls.centered_text(text, 0)


            cls.centered_text("Timer", 3)
            cls.centered_text(timer_text, 5)
        elif State.selected_task_index is not None:
            selected_task_index = State.selected_task_index
            cls.centered_text("Select Task", 0)

            if len(Config.tasks) == 0:
                cls.wrapped_text("No tasks configured", 3)
            else:
                task_name = Config.tasks[selected_task_index].name
                underline_width = len(task_name) * cls.CHAR_WIDTH
                cls.oled.hline(0, 38, underline_width, 2)

                for i, task in enumerate(Config.tasks):
                    if i < selected_task_index - 1:
                        continue

                    task_name = task.name
                    if i == selected_task_index:
                        task_name, _ = TextScrolling.maybe_scroll(task_name, cls.CHARS_PER_LINE)

                    line = 3 + (i - selected_task_index)
                    cls.text(task_name, line)

        else:
            cls.centered_text("clocko:ctrl", 2)

        cls.oled.show()


# API INTERACTION


class ClockodoClient:
    BASE_URL = "https://my.clockodo.com/api/v2"

    @staticmethod
    def headers():
        return {
            "X-Clockodo-External-Application": "clocko:ctrl;sebashwa@mailbox.org",
            "X-ClockodoApiUser": Config.api_user,
            "X-ClockodoApiKey": Config.api_key,
        }

    @classmethod
    def endpoint(cls, name):
        return f"{cls.BASE_URL}/{name}"

    @classmethod
    def start_clock(cls, task):
        data = {
            "customers_id": task.customer_id,
            "projects_id": task.project_id,
            "services_id": Config.service_id,
        }
        return urequests.post(cls.endpoint("clock"), headers=cls.headers(), json=data)

    @classmethod
    def stop_clock(cls, entry_id):
        return urequests.delete(
            cls.endpoint(f"clock/{entry_id}"), headers=cls.headers()
        )


class ClockodoRequest:
    @staticmethod
    def send(request, on_success):
        try:
            response = request()

            if response.status_code == 200:
                on_success(response)
            else:
                State.error = Error.API_RESPONSE
        except:
            State.error = Error.API_REQUEST
        finally:
            State.triggered_request = None


    @classmethod
    def start_clock(cls):
        active_task = Config.tasks[State.selected_task_index]

        def request():
            return ClockodoClient.start_clock(active_task)

        def on_success(response):
            entry_id = response.json()["running"]["id"]
            State.change_for_clock_start(active_task, entry_id)

        cls.send(request, on_success)



    @classmethod
    def stop_clock(cls):
        def request():
            return ClockodoClient.stop_clock(State.active_entry_id)

        def on_success(_):
            State.change_for_clock_stop()

        cls.send(request, on_success)

# MAIN


def init():
    gc.enable()
    Display.render()

    Config.load()

    Knob.scale = len(Config.tasks) - 1
    Wifi.essid = Config.wifi.essid
    Wifi.password = Config.wifi.password

    Wifi.connect()


def main():
    init()

    while True:
        Knob.handle_turn()
        Button.handle_push()

        Display.render()

        if State.triggered_request is not None:
            State.triggered_request()

        gc.collect()
        sleep(0.1)


main()
