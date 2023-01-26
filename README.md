# Raspberry Pico with MicroPython

## Install MicroPython

1. Download prebuilt `.uf2` file
2. Connect Pico to Computer while pressing the boot sel button
3. Copy the `.uf2` file to the Pico drive inside the terminal

## Connect with pico for python file upload with rshell

```
rshell --buffer-size=30 -p /dev/tty.usbmodem1101 -a
```

```
cp <file.py> /pyboard/main.py
```

## Connect with pico for REPL

```
minicom -b 115200 -o -D /dev/tty.usbmodem1101
```

## Temperature sensor web server

1. Copy pico_config.json to Pico
2. Copy sensor_web.py as main.py to Pico