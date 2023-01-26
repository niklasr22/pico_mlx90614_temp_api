import network
import socket
import time
import json

from machine import I2C, Pin


class InvalidReadingError(Exception):
    ...


MLX90614_ADDRESS = 0x5A
MLX90614_TEMPERATURE_AMBIENT_ADDRESS = 0x6
MLX90614_TEMPERATURE1_ADDRESS = 0x7
MLX90614_TEMPERATURE2_ADDRESS = 0x8

led = Pin("LED", Pin.OUT)

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


def clear_buffer(buffer):
    while True:
        line = buffer.readline()
        if not line or line == b"\r\n":
            break

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
    print("waiting for connection...")
    time.sleep(1)

# Handle connection error
if wlan.status() != 3:
    raise RuntimeError("network connection failed")

# Open socket
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

s = socket.socket()
s.bind(addr)
s.listen(1)

# Listen for connections
while True:
    try:
        cl, addr = s.accept()
        led.on()
        cl_file = cl.makefile("rwb", 0)
        clear_buffer(cl_file)
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
            response["success"] = True
        except InvalidReadingError as e:
            response["success"] = False
            response["error"] = str(e)
        cl.send("HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n")
        cl.send(json.dumps(response))
        cl.close()
        led.off()

    except OSError as e:
        cl.close()
        print("connection closed")
