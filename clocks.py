#!/usr/bin/python3

import RPi.GPIO as GPIO
import time
import os
import requests
import datetime
import logging
import socket

# On production clock, set 'CLOCK_ENVIRONMENT' in '/etc/environment' to 'production'
CLOCK_ENVIRONMENT = os.getenv('CLOCK_ENVIRONMENT', 'development')

# These URLs are used to post start/stop times from the button to the website
# displaying the live stream of the event.
if CLOCK_ENVIRONMENT == 'production':
    BASE_URL = '<production url>'
elif CLOCK_ENVIRONMENT == 'staging':
    BASE_URL = '<staging url>'
else:
    BASE_URL = '<local development url>'

NETWORK_FAILURE = False
TEAM_1_START_TIME = ''
TEAM_2_START_TIME = ''
HEAT_START_TIME = ''
WEB_APP_USER_NAME = '' # Username for posting to web app
WEB_APP_PASSWORD = '' # Password for the basic authentication of posting to web app
WEB_APP_URL = '{}/clock_start'.format(BASE_URL)
DIAGNOSTIC_INFO_URL = '{}/button_box_info'.format(BASE_URL)
HEALTH_CHECK_URL = '{}/health_check'.format(BASE_URL)
HEALTH_CHECK_URL_CHECKED_AT = 0
HEALTHCHECK_WAIT_SECONDS = 0.2
HEALTHCHECK_INTERVAL_MAX_SECONDS = 300
HEALTHCHECK_INTERVAL_MIN_SECONDS = 5
AIRHORN_OPEN_SECONDS = 0.15
RELAY_OPEN_SECONDS = 1
BTN_HEAT_START_STOP = 6
BTN_TEAM_1_START_STOP = 5
BTN_TEAM_2_START_STOP = 11
BTN_RESET_TEAMS = 9
RELAY_TEAM_1_CLOCK = 4
RELAY_TEAM_2_CLOCK = 17
RELAY_RESET_ALL_CLOCKS = 27
RELAY_AIR_HORN = 22
LED_WEBSITE_GREEN = 23
LED_WEBSITE_RED = 24
LED_TEAM_1_GREEN = 7
LED_TEAM_1_RED = 10
LED_TEAM_2_GREEN = 25
LED_TEAM_2_RED = 8

GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1)) # Just an IP to see if the PI has L3 connectivity at all
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def check_website():
    global NETWORK_FAILURE

    logging.info('connecting... %s', BASE_URL)

    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=10)
        network_status = 'Up'
        NETWORK_FAILURE = False
        logging.info('health_check status: %s', response.status_code)
        if response.status_code == requests.codes.ok:
            website_status = 'Up'
            GPIO.output(LED_WEBSITE_RED, True)
            GPIO.output(LED_WEBSITE_GREEN, False)
            send_diagnostic_info()
        else:
            website_status = 'Down'
            NETWORK_FAILURE = True
            GPIO.output(LED_WEBSITE_GREEN, True)
            GPIO.output(LED_WEBSITE_RED, False)
    except requests.exceptions.Timeout as e:
        logging.info('network_request timeout: %s', e)
        NETWORK_FAILURE = True
        network_status = 'Timeout'
        website_status = 'Inaccessible'
        GPIO.output(LED_WEBSITE_GREEN, True)
        GPIO.output(LED_WEBSITE_RED, False)
    except requests.exceptions.RequestException as e:
        logging.info('network_request unknown: %s', e)
        NETWORK_FAILURE = True
        network_status = 'Unknown'
        website_status = 'Inaccessible'
        GPIO.output(LED_WEBSITE_GREEN, True)
        GPIO.output(LED_WEBSITE_RED, False)

    logging.info('network: %s, website: %s', network_status, website_status)


def air_horn():
    GPIO.output(RELAY_AIR_HORN, GPIO.HIGH)
    time.sleep(AIRHORN_OPEN_SECONDS)
    GPIO.output(RELAY_AIR_HORN, GPIO.LOW)


def send_diagnostic_info():
    ip_address = get_ip()
    r = requests.post(
            DIAGNOSTIC_INFO_URL,
            json={"button_box_info": {"ip_address": ip_address}},
            auth=(WEB_APP_USER_NAME, WEB_APP_PASSWORD)
        )

    logging.info('diagnostic information: ip_address: %s, response: %s', ip_address, r.status_code)


def notify_web_app(start_time):
    r = requests.post(WEB_APP_URL, data={'start_time': start_time}, auth=(WEB_APP_USER_NAME, WEB_APP_PASSWORD))
    logging.info('website response code: %s reason: %s', r.status_code, r.reason)


def team_1_start_stop(pin):
    if GPIO.input(pin):
        logging.info("start/stop team 1")
        GPIO.output(RELAY_TEAM_1_CLOCK, GPIO.HIGH)
        toggle_led(LED_TEAM_1_GREEN, LED_TEAM_1_RED)
        time.sleep(RELAY_OPEN_SECONDS)
        GPIO.output(RELAY_TEAM_1_CLOCK, GPIO.LOW)
    else:
        pass


def team_2_start_stop(pin):
    if GPIO.input(pin):
        logging.info("start/stop team 2")
        GPIO.output(RELAY_TEAM_2_CLOCK, GPIO.HIGH)
        toggle_led(LED_TEAM_2_GREEN, LED_TEAM_2_RED)
        time.sleep(RELAY_OPEN_SECONDS)
        GPIO.output(RELAY_TEAM_2_CLOCK, GPIO.LOW)
    else:
        pass


def reset_both_teams(pin):
    global TEAM_1_START_TIME
    global TEAM_2_START_TIME
    global HEAT_START_TIME

    if GPIO.input(pin):
        logging.info("reseting both teams")
        GPIO.output(RELAY_RESET_ALL_CLOCKS, GPIO.HIGH)
        time.sleep(RELAY_OPEN_SECONDS)
        GPIO.output(RELAY_RESET_ALL_CLOCKS, GPIO.LOW)
        logging.info('reseting clocks')
        reset_team_leds()
        logging.info('reseting LEDs')
        HEAT_START_TIME = ''
        logging.info('clearing heat start time')
    else:
        pass


def heat_start_stop(pin):
    global HEAT_START_TIME
    clock_relays = [RELAY_TEAM_1_CLOCK, RELAY_TEAM_2_CLOCK]
    if GPIO.input(pin):
        current_time = int(time.time()*1000)
        current_time
        # Start the clocks by setting relays to HIGH
        logging.info("toggling both clocks")
        GPIO.output(clock_relays, GPIO.HIGH)

        # Sound the airhorn
        air_horn()

        logging.info('pushed button at %s', current_time)

        # Toggle Team 1 LED
        toggle_led(LED_TEAM_1_GREEN, LED_TEAM_1_RED)

        # Toggle Team 2 LED
        toggle_led(LED_TEAM_2_GREEN, LED_TEAM_2_RED)

        # Wait to open the relays for the clocks so that we are sure
        # that the clocks have actually had time to start.
        time.sleep(RELAY_OPEN_SECONDS)

        # set the relays to open for the clocks
        GPIO.output(clock_relays, GPIO.LOW)

        # if we haven't already started a heat then do so and
        # notify the website of the start time so that we
        # are all in sync.
        if HEAT_START_TIME == '':
            logging.info('starting a heat')
            HEAT_START_TIME = current_time

            notify_web_app(current_time)
            logging.info('Notified website of start time: %s', current_time)
        else:
            logging.info("pausing/unpausing")
            notify_web_app(current_time)
            logging.info('Notified website of pause/restart time: %s', current_time)
    else:
        GPIO.output(clock_relays, GPIO.LOW)


def reset_team_leds():
    GPIO.output([LED_TEAM_1_GREEN, LED_TEAM_2_GREEN], True)
    GPIO.output([LED_TEAM_2_RED, LED_TEAM_1_RED], False)


def toggle_led(pin1, pin2):
    if GPIO.input(pin1):
        GPIO.output(pin1, False)
        GPIO.output(pin2, True)
        logging.info("turning off %s and turning on %s", pin1, pin2)
    else:
        GPIO.output(pin2, False)
        GPIO.output(pin1, True)
        logging.info("turning off %s and turning on %s", pin2, pin1)


def time_difference(time1, time2, minimum_time):
    elapsed = time2 - time1
    if elapsed >= minimum_time:
        return True
    else:
        return False


def setup_gpio():
    # Setup the 4 input buttons that will be used in the program
    # Button 14 is the heat start/stop button
    GPIO.setup(BTN_HEAT_START_STOP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # Button 15 is the Team 1 start/stop
    GPIO.setup(BTN_TEAM_1_START_STOP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # Button 18 is the Team 2 start/stop
    GPIO.setup(BTN_TEAM_2_START_STOP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # Button 23 is the Global Reset
    GPIO.setup(BTN_RESET_TEAMS, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # setup the event handlers for button presses
    GPIO.add_event_detect(BTN_HEAT_START_STOP, GPIO.BOTH, callback=heat_start_stop, bouncetime=400)
    GPIO.add_event_detect(BTN_TEAM_1_START_STOP, GPIO.BOTH, callback=team_1_start_stop, bouncetime=400)
    GPIO.add_event_detect(BTN_TEAM_2_START_STOP, GPIO.BOTH, callback=team_2_start_stop, bouncetime=400)
    GPIO.add_event_detect(BTN_RESET_TEAMS, GPIO.BOTH, callback=reset_both_teams, bouncetime=400)

    # setup the relay for action
    relays = [RELAY_TEAM_1_CLOCK, RELAY_TEAM_2_CLOCK, RELAY_RESET_ALL_CLOCKS, RELAY_AIR_HORN]
    for i in relays:
        GPIO.setup(i, GPIO.OUT)
        GPIO.output(i, GPIO.LOW)

    # setup the LEDs
    # Initialize Website LED pins
    # 22 = Green
    # 27 = Red
    GPIO.setup(LED_WEBSITE_GREEN, GPIO.OUT)
    GPIO.setup(LED_WEBSITE_RED, GPIO.OUT)

    # Initialize Clock Status LED pins
    # Team 1:
    # 17 = Green
    # 4 = Red
    #
    # Team 2:
    # 3 = Green
    # 2 = Red
    GPIO.setup(LED_TEAM_1_GREEN, GPIO.OUT)
    GPIO.setup(LED_TEAM_1_RED, GPIO.OUT)
    GPIO.setup(LED_TEAM_2_GREEN, GPIO.OUT)
    GPIO.setup(LED_TEAM_2_RED, GPIO.OUT)


def cleanup_gpio():
    GPIO.cleanup()


def perform_healthcheck():
    global HEALTH_CHECK_URL_CHECKED_AT
    global NETWORK_FAILURE

    interval = HEALTHCHECK_INTERVAL_MIN_SECONDS if NETWORK_FAILURE else HEALTHCHECK_INTERVAL_MAX_SECONDS

    # here we need to store the last time that we checked in and only check in if we
    # are after N seconds later.
    if time_difference(HEALTH_CHECK_URL_CHECKED_AT, time.time(), interval):
        check_website()
        HEALTH_CHECK_URL_CHECKED_AT = time.time()

    time.sleep(HEALTHCHECK_WAIT_SECONDS)


def main():
    logging.basicConfig(
        filename='engine_builder_showdown.log',
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logging.info('starting app in... %s', CLOCK_ENVIRONMENT)
    setup_gpio()
    reset_team_leds()

    try:
        while True:
            perform_healthcheck()
            pass

    except KeyboardInterrupt:
        logging.info('Closing Program')

    cleanup_gpio()


if __name__ == "__main__":
    main()
