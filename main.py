from machine import ADC, Pin, SoftI2C
from time import sleep
import ssd1306


class State:
    def __init__(self):
        self.tasks = ClockodoTasks.all()
        self.selected_task_index = None
        self.active_task = None


class ClockodoTask:
    def __init__(self, name, project_id=None, customer_id=None):
        self.project_id = project_id
        self.customer_id = customer_id
        self.name = name


class ClockodoTasks:
    def all():
        return [
            ClockodoTask("EDM", 1214464),
            ClockodoTask("Moodle (EDM)", 1738188),
            ClockodoTask("intern", None, 758500),
            ClockodoTask("HYKIST", 1214464),
            ClockodoTask("Dolmetsch Nothilfe", 1753410),
            ClockodoTask("Triaphon", 1214464),
            ClockodoTask("ZMV", 1805778),
        ]


class ClockodoClient:
    API_KEY = "bcd38bf9222607fbf9ee97995d18c8b4"


class Knob:
    MAX_ATTN_VALUE = 4095
    GPIO_PIN = 36

    def __init__(self, scale=None):
        self.poti = ADC(Pin(Knob.GPIO_PIN))
        self.poti.atten(ADC.ATTN_11DB)
        self.scale = scale or Knob.MAX_ATTN_VALUE
        self.previous_value = self.value

    def scale_value(self, value):
        return round((self.scale / 4095) * value)

    @property
    def value(self):
        read_value = self.poti.read()
        return self.scale_value(read_value)

    def handle_turn(self, state):
        current_value = self.value
        previous_value = self.previous_value

        if current_value != previous_value:
            self.previous_value = current_value
            state.selected_task_index = current_value


class Button:
    GPIO_PIN = 13

    def __init__(self):
        self.pin = Pin(Button.GPIO_PIN, Pin.IN)
        self.previous_value = 0

    def handle_push(self, state):
        current_value = self.pin.value()

        if current_value == 1 and self.previous_value == 0:
            self.previous_value = 1

            if state.active_task:
                state.active_task = None
            else:
                state.active_task = state.tasks[state.selected_task_index]
        elif current_value == 0:
            self.previous_value = 0


class Display:
    SCL_PIN = 22
    SDA_PIN = 21
    WIDTH = 128
    HEIGHT = 64
    CHAR_WIDTH = 16

    def __init__(self):
        scl = Pin(Display.SCL_PIN)
        sda = Pin(Display.SDA_PIN)
        i2c = SoftI2C(scl=scl, sda=sda)
        self.oled = ssd1306.SSD1306_I2C(Display.WIDTH, Display.HEIGHT, i2c)

    @classmethod
    def split_text_for_width(cls, text):
        return [
            text[i : i + cls.CHAR_WIDTH] for i in range(0, len(text), cls.CHAR_WIDTH)
        ]

    def render_wrapped_text(self, text, start_pos=0, max_pos=None):
        text_segments = Display.split_text_for_width(text)

        for i, segment in enumerate(text_segments):
            position = start_pos + i * 10
            if max_pos is None or position <= max_pos:
                self.oled.text(segment, 0, position)
            else:
                break

    def render(self, state):
        active_task = state.active_task
        selected_task_index = state.selected_task_index
        oled = self.oled

        oled.fill(0)

        if active_task is not None:
            oled.text("Clock", 0, 0)
            self.render_wrapped_text(active_task.name, 20, 30)
            oled.text("00:00:00", 30, 50)
            oled.show()
        elif selected_task_index is not None:
            oled.text("Select Task", 20, 0)

            selected_task = state.tasks[selected_task_index]
            underline_width = len(selected_task.name) * 8
            oled.hline(0, 38, underline_width, 2)

            for i, task in enumerate(state.tasks):
                if i < selected_task_index - 1:
                    continue

                position = 30 + (i - selected_task_index) * 10
                oled.text(task.name, 0, position, 1)

            oled.show()
        else:
            oled.text("clockocontrol", 10, 0)
            oled.text("Turn the knob", 0, 20)
            oled.text("to select a task", 0, 30)
            oled.show()


state = State()

button = Button()
knob = Knob(scale=len(state.tasks) - 1)
display = Display()

while True:
    sleep(0.1)

    knob.handle_turn(state)
    button.handle_push(state)

    display.render(state)
