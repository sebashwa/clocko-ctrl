# clocko:ctrl
A device for [clocko:do](https://www.clockodo.com) time tracking

## Hardware

The hardware part is not very complex. The device consists of:

* 1 display
* 1 knob to select a task
* 1 button to start / stop tracking time for the selected task

You can easily find tutorials on how to solder the individual components to the ESP32.

### Components

I used the following:

* [Olimex ESP32-WROVER-DevKit](https://www.olimex.com/Products/IoT/ESP32/ESP32-DevKit-LiPo/)
* SSD1306 OLED Display
* 10k Ω Potentiometer
* Button

### Pins

These Pins are hardcoded at the moment:

* Display: 21 for SDA, 22 for SCL
* Potentiometer: 36
* Button: 15 (using the internal pull up resistor)

## Software

For the software part only some configuration and copying of files is necessary.

### Configuration

You need to configure some values for _clocko:ctrl_ to work.
Copy `config.example.json` to `config.json` and set all values:

* Wifi SSID and Password
* [clocko:do API credentials](https://www.clockodo.com/de/api/)
* A service id for the activity you want to track
* Multiple tasks you want to choose from.
  This can be a combination of `customer_id` and `project_id` or just a `customer_id`.
  You can choose whatever name you want for the tasks.

### Deployment

1) Load the [micropython firmware](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#getting-the-firmware) to your ESP32 so it can understand python.
1) Install [ampy](https://github.com/scientifichackers/ampy#installation). This is used to copy files to the ESP32.
1) Run `deploy.sh [port]` with the device plugged in (`[port]` is usually something like `/dev/ttyUSB0`).
