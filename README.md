# Python webserver for a Raspberry Pico with MLX90614 temperature sensor

## Install MicroPython

1. Download the prebuilt `.uf2` file from the offical Raspberry site
2. Connect your Pico to the computer while pressing the boot sel button
3. Copy the `.uf2` file to the Pico drive (inside the terminal)

## Temperature sensor web server

1. Copy pico_config.json to Pico
2. Copy sensor_web.py as main.py to Pico

## Useful commands:

### File transfer with rshell

```
rshell --buffer-size=30 -p /dev/tty.usbmodem1101 -a
```

```
cp <file.xyz> /pyboard/<file.xyz>
cp sensor_web.py /pyboard/main.py
```

### Micropython REPL

```
minicom -b 115200 -o -D /dev/tty.usbmodem1101
```
