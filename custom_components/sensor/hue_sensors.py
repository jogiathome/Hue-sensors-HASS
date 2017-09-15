"""
Sensor for checking the status of Hue sensors.
"""
import logging
from datetime import datetime, timedelta

import requests

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=1)
URL = 'http://192.168.0.YOURS/api/your_pass/sensors'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tube sensor."""
    data = HueSensorData()
    data.update()
    sensors = []
    for key in data.data.keys():
        sensors.append(HueSensor(key, data))
    add_devices(sensors, True)


class HueSensorData(object):
    """Get the latest sensor data."""

    def __init__(self):
        """Initialize the object."""
        self.data = None

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data"""
        response = requests.get(URL)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = parse_hue_api_response(response.json())


class HueSensor(Entity):
    """Class to hold Hue Sensor basic info."""

    ICON = 'mdi:run-fast'

    def __init__(self, hue_id, data):
        self._hue_id = hue_id
        self._data = data    # data is in .data
        self._name = self._data.data[self._hue_id]['name']
        self._model = self._data.data[self._hue_id]['model']
        self._state = self._data.data[self._hue_id]['state']
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Only motion sensors have attributes currently, but could extend."""
        return self._attributes

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = self._data.data[self._hue_id]['state']
        if self._model == 'SML001':
            self._attributes['light_level'] = self._data.data[
                self._hue_id]['light_level']
            self._attributes['temperature'] = self._data.data[
                self._hue_id]['temperature']
        elif self._model == 'RWL021':
            self._attributes['last updated'] = self._data.data[
                self._hue_id]['last_updated']


def parse_hue_api_response(response):
    """Take in the Hue API json response."""
    data_dict = {}    # The list of sensors, referenced by their hue_id.

    # Loop over all keys (1,2 etc) to identify sensors and get data.
    for key in response.keys():
        sensor = response[key]

        if sensor['modelid'] in ['RWL021', 'SML001']:
            _key = sensor['uniqueid'].split(':')[-1][0:5]

            if sensor['modelid'] == 'RWL021':
                data_dict[_key] = parse_RWL021(sensor)
            else:
                if _key not in data_dict.keys():
                    data_dict[_key] = parse_SML001(sensor)
                else:
                    data_dict[_key].update(parse_SML001(sensor))

        elif sensor['modelid'] == 'HA_GEOFENCE':
            data_dict['Geofence'] = parse_GEOFENCE(sensor)
    return data_dict


def parse_SML001(response):
    '''Parse the json for a SML001 Hue motion sensor and return the data.'''
    if 'ambient light' in response['name']:
        data = {'light_level': response['state']['lightlevel']}

    elif 'temperature' in response['name']:
        data = {'temperature': response['state']['temperature']/100.0}

    else:
        # Some logic to conver 'Hall Sensor' to 'Hall Motion Sensor'
        name_raw = response['name']
        arr = name_raw.split()
        arr.insert(-1, 'motion')
        name = ' '.join(arr)

        data = {'model': response['modelid'],
                'state': response['state']['presence'],
                'name': name}
    return data


def parse_RWL021(response):
    '''Parse the json response for a RWL021 Hue remote and return the data.
       If button held for 2 seconds then a hold.'''
    # check if long or short hold
    press = str(response['state']['buttonevent'])

    if press[-1] in ['0', '2']:    # 1002, 4001 etc, check if even
        button = str(press)[0] + '_click'
    else:
        button = str(press)[0] + '_hold'

    data = {'model': 'RWL021',
            'name': response['name'],
            'state': button,
            'last_updated': response['state']['lastupdated'].split('T')}
    return data


def parse_GEOFENCE(response):
    '''Parse the json response for a GEOFENCE and return the data'''
    data = {'name': response['name'],
            'model': 'Geofence',
            'state': response['state']['presence']}
    return data
