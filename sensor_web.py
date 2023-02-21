import machine
import network
import socket
import time
import json

from machine import I2C, Pin, Timer, WDT


class InvalidReadingError(Exception):
    ...


MLX90614_ADDRESS = 0x5A
MLX90614_TEMPERATURE_AMBIENT_ADDRESS = 0x6
MLX90614_TEMPERATURE1_ADDRESS = 0x7
MLX90614_TEMPERATURE2_ADDRESS = 0x8


ignore_object_temperature = False
timer = Timer()


def set_object_temperature_ignore_state(state):
    global ignore_object_temperature
    ignore_object_temperature = state


def ignore_period_over(t):
    set_object_temperature_ignore_state(False)
    timer.deinit()


def start_ignore_period():
    set_object_temperature_ignore_state(True)
    timer.deinit()
    timer.init(
        period=900000,  # 15min
        mode=Timer.ONE_SHOT,
        callback=ignore_period_over,
    )


btn_first_press = None
btn_last_release = time.ticks_ms()
MIN_PRESS_DURATION = 2000


def ignore_button_handler(p: Pin):
    global btn_first_press, btn_last_release
    if p.value() == 1:
        btn_last_release = time.ticks_ms()
        if (
            btn_first_press
            and time.ticks_ms() - btn_first_press > 500
            and time.ticks_ms() - btn_first_press < MIN_PRESS_DURATION
        ):
            btn_first_press = None
        elif btn_first_press and time.ticks_ms() - btn_first_press > MIN_PRESS_DURATION:
            start_ignore_period()
            btn_first_press = None
    else:
        if btn_first_press and time.ticks_ms() - btn_first_press < 500:
            return
        if time.ticks_ms() - btn_last_release > 1000:
            btn_first_press = time.ticks_ms()


led = Pin("LED", Pin.OUT)

ignore_btn = Pin(28, Pin.IN, Pin.PULL_UP)
ignore_btn.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=ignore_button_handler)

i2c = I2C(1, scl=Pin(27), sda=Pin(26), freq=100000)


def convert_bytes_to_int(data: bytes):
    return int.from_bytes(data, "little")


def to_celcius(temp: float) -> float:
    return (temp * 0.02) - 273.15


def read_temperature(bus: I2C) -> tuple[float, float]:
    # read temperature data words (2B)
    try:
        temp_ambient = convert_bytes_to_int(
            bus.readfrom_mem(
                MLX90614_ADDRESS, MLX90614_TEMPERATURE_AMBIENT_ADDRESS, 0x2
            )
        )
        temp_obj_1 = convert_bytes_to_int(
            bus.readfrom_mem(MLX90614_ADDRESS, MLX90614_TEMPERATURE1_ADDRESS, 0x2)
        )
        temp_obj_2 = convert_bytes_to_int(
            bus.readfrom_mem(MLX90614_ADDRESS, MLX90614_TEMPERATURE2_ADDRESS, 0x2)
        )
        return (
            to_celcius(temp_ambient),
            to_celcius(0.5 * (temp_obj_1 + temp_obj_2)),
            to_celcius(temp_obj_1),
            to_celcius(temp_obj_2),
        )
    except OSError:
        raise InvalidReadingError("The temperature sensor was not available")


def main():
    try:
        with open("pico_config.json") as config_file:
            config = json.load(config_file)

        ssid = config["wifi"]["ssid"]
        password = config["wifi"]["password"]

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(ssid, password)

        # Wait for connect or fail
        max_wait = 10
        while max_wait > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            max_wait -= 1
            time.sleep(1)

        wdt = WDT(timeout=8388)

        # Handle connection error
        if wlan.status() != 3:
            raise RuntimeError("network connection failed")

        # Open socket
        addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

        s = socket.socket()
        s.settimeout(3.0)
        s.bind(addr)
        s.listen(3)

        # Listen for connections
        while True:
            wdt.feed()
            if wlan.status() != 3:
                raise RuntimeError("network connection failed")
            try:
                client, addr = s.accept()
                led.on()

                # clear buffer
                line = client.readline()

                # check for /reset
                if "/reset" in line:
                    ignore_period_over(None)
                if "/ignore" in line:
                    start_ignore_period()

                while True:
                    if not line or line == b"\r\n":
                        break
                    line = client.readline()

                wdt.feed()
                response = dict()
                try:
                    (
                        ambient_temp,
                        object_temp_avg,
                        object_temp_1,
                        object_temp_2,
                    ) = read_temperature(i2c)
                    response["ambient_temperature"] = ambient_temp
                    response["object_temperature_1"] = object_temp_1
                    response["object_temperature_2"] = object_temp_2
                    response["object_temperature_avg"] = object_temp_avg
                    response["ignore_state"] = ignore_object_temperature
                    response["success"] = True
                except InvalidReadingError as e:
                    response["success"] = False
                    response["error"] = str(e)
                client.send("HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n")
                client.send(json.dumps(response))
                client.close()
                led.off()

            except OSError as e:
                ...
            finally:
                client.close()
    except Exception:
        ...
    finally:
        # this will cause a watchdog reset
        time.sleep(15)


main()
