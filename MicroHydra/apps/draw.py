import time
import os
import math
import ntptime
import network
import framebuf
import array
from lib import smartkeyboard, beeper, battlevel
import machine
from launcher import st7789hybrid as st7789
from launcher.icons import battery
from font import vga1_8x16 as fontsmall
from font import vga2_16x32 as font
from lib.mhconfig import Config

# bump up our clock speed so the UI feels smoother (240mhz is the max officially supported, but the default is 160mhz)
machine.freq(240_000_000)

"""

VERSION: 1.0

CHANGES:
    Overhaul launcher.py! (FINALLY)
    - overhauled scrolling graphics to use a framebuffer, now the statusbar doesn't blink out on scroll
    - broke code up into smaller functions to save memory (and make it easier to read!)
    - added key-repeater logic from settings.py
    - added custom 'st7789hybrid.py' for launcher-specific use
    - replaced bitmap icons with vector icons to save memory
    - added support for app icons
    
    Added log output on launch failure to main.py
    Improved copy/paste in Files app
    Added smartkeyboard to lib
    general bugfixes
    
This program is designed to be used in conjunction with "main.py" apploader, to select and launch MPy apps.

The basic app loading logic works like this:
 - apploader reads reset cause and RTC.memory to determine which app to launch
 - apploader launches 'launcher.py' when hard reset, or when RTC.memory is blank
 - launcher scans app directories on flash and SDCard to find apps
 - launcher shows list of apps, allows user to select one
 - launcher stores path to app in RTC.memory, and soft-resets the device
 - apploader reads RTC.memory to find path of app to load
 - apploader clears the RTC.memory, and imports app at the given path
 - app at given path now has control of device.
 - pressing the reset button will relaunch the launcher program, and so will calling machine.reset() from the app. 

This approach was chosen to reduce the chance of conflicts or memory errors when switching apps.
Because MicroPython completely resets between apps, the only "wasted" ram from the app switching process will be from main.py

"""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ _CONSTANTS: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_ICON_Y = const(36)
_APPNAME_Y = const(80)


_DISPLAY_WIDTH = const(240)
_DISPLAY_HEIGHT = const(135)

_DISPLAY_WIDTH_HALF = const(_DISPLAY_WIDTH//2)

_FONT_WIDTH = const(16)
_FONT_HEIGHT = const(32)
_SMALLFONT_WIDTH = const(8)
_SMALLFONT_HEIGHT = const(16)

_ICON_HEIGHT = const(32)
_ICON_WIDTH = const(32)

_ICON_FBUF_WIDTH = const(_FONT_WIDTH*3)  # wide enough to fit the word "off"

_SCROLL_ANIMATION_TIME = const(300)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GLOBALS: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


# init driver for the graphics
DISPLAY = st7789.ST7789(
    machine.SPI(1, baudrate=40000000, sck=machine.Pin(
        36), mosi=machine.Pin(35), miso=None),
    _DISPLAY_HEIGHT,
    _DISPLAY_WIDTH,
    reset=machine.Pin(33, machine.Pin.OUT),
    cs=machine.Pin(37, machine.Pin.OUT),
    dc=machine.Pin(34, machine.Pin.OUT),
    backlight=machine.Pin(38, machine.Pin.OUT),
    rotation=1,
    color_order=st7789.BGR
)
DISPLAY.vscrdef(20, 240, 40)

CANVAS = framebuf.FrameBuffer(
    bytearray(_DISPLAY_WIDTH * _DISPLAY_HEIGHT),
    _DISPLAY_WIDTH, _DISPLAY_HEIGHT, framebuf.RGB565,
)

BEEP = beeper.Beeper()
CONFIG = Config()
KB = smartkeyboard.KeyBoard(config=CONFIG)
SD = None
RTC = machine.RTC()
BATT = battlevel.Battery()


CANVAS.fill(1)
