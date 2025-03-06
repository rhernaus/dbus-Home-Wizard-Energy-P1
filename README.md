# dbus-Home-Wizard-Energy-P1
Integrate Home Wizard Energy P1 meter into [Victron Energy's Venus OS](https://github.com/victronenergy/venus)

## Purpose
This service integrates the Home Wizard Energy P1 meter with Victron Energy's Venus OS and GX devices. It provides automatic detection of single-phase and three-phase meters, ensuring proper integration with the Victron system.

## Inspiration
This project builds on ideas and approaches from the following projects:
- https://github.com/RalfZim/venus.dbus-fronius-smartmeter
- https://github.com/victronenergy/dbus-smappee
- https://github.com/Louisvdw/dbus-serialbattery
- https://community.victronenergy.com/idea/114716/power-meter-lib-for-modbus-rtu-based-meters-from-a.html - [Old Thread](https://community.victronenergy.com/questions/85564/eastron-sdm630-modbus-energy-meter-community-editi.html)
- https://github.com/fabian-lauer/dbus-shelly-3em-smartmeter

## How it works
### My setup
- Home Wizard Energy P1 with latest firmware
  - Works with both single-phase and three-phase installations (automatically detected)
  - Connected to WiFi network "A"
  - IP 192.168.2.13/24
- Victron Energy Cerbo GX with Venus OS - Firmware v3.11
  - No other devices from Victron connected (still waiting for shipment of Multiplus-2)
  - Connected to WiFi network "A"
  - IP 192.168.2.20/24

### Details / Process
The service performs the following functions:
- Runs as a background service
- Connects to the Venus OS DBus as either `com.victronenergy.grid.http_40` or `com.victronenergy.pvinverter.http_40` (based on configuration)
- Accesses the Home Wizard P1 meter via REST-API (at `/api/v1/data`) and receives JSON data with all energy metrics
- Uses the unique_id from the response as the device serial number
- Creates DBus paths with initial values and settings
- Automatically detects if the meter is single-phase or three-phase based on the response data
- Continuously polls the Home Wizard P1 meter API every 500ms and updates the DBus values

## Install & Configuration
### Get the code
Clone the repository and install it to `/data/dbus-Home-Wizard-Energy-P1`. Then run the installation script.

The following commands will do everything for you:
```
wget https://github.com/rhernaus/dbus-Home-Wizard-Energy-P1/archive/refs/heads/main.zip
unzip main.zip "dbus-Home-Wizard-Energy-P1-main/*" -d /data
mv /data/dbus-Home-Wizard-Energy-P1-main /data/dbus-Home-Wizard-Energy-P1
chmod a+x /data/dbus-Home-Wizard-Energy-P1/manage.sh
/data/dbus-Home-Wizard-Energy-P1/manage.sh install
rm main.zip
```
⚠️ Check the configuration after installation, as the service will start immediately with default settings.

### Managing the Service

The installation comes with a management script that provides several commands:

```
# Install the service
./manage.sh install

# Restart the service
./manage.sh restart

# Check service status
./manage.sh status

# Uninstall the service
./manage.sh uninstall
```

### Initialize git submodules
The service depends on the `vedbus` module which is provided by a git submodule. If you're installing the code manually (not using the installation script), you'll need to initialize the submodules:

```
cd /data/dbus-Home-Wizard-Energy-P1
git submodule update --init --recursive
```

The installation script handles this automatically.

### Change config.ini
Edit the configuration file at `/data/dbus-Home-Wizard-Energy-P1/config.ini`. The most important setting is the `Host` value in the `ONPREMISE` section.

| Section  | Config value | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | AccessType | Fixed value 'OnPremise' |
| DEFAULT  | SignOfLifeLog  | Time in minutes between status log entries in `current.log` |
| DEFAULT  | CustomName  | Name of your device - useful when running multiple instances |
| DEFAULT  | DeviceInstance  | Device instance number (e.g., 40) |
| DEFAULT  | Role | Value: 'grid' or 'pvinverter' based on desired integration |
| DEFAULT  | Position | Position value: 0 = AC, 1 = AC-Out 1, 2 = AC-Out 2 |
| DEFAULT  | LogLevel  | Logging level - see: https://docs.python.org/3/library/logging.html#levels |
| ONPREMISE  | Host | IP address or hostname of the Home Wizard Energy P1 meter |

## Used documentation
- https://github.com/victronenergy/venus/wiki/dbus#grid - DBus paths for Victron namespace GRID
- https://github.com/victronenergy/venus/wiki/dbus#pv-inverters - DBus paths for Victron namespace PVINVERTER
- https://github.com/victronenergy/venus/wiki/dbus-api - DBus API from Victron
- https://www.victronenergy.com/live/ccgx:root_access - How to get root access on GX device/Venus OS

## Discussions on the web
This module/repository has been posted on the following threads:
- https://community.victronenergy.com/questions/238117/home-wizzard-energy-p1-meter-in-venusos.html

## Running Tests
To run the tests for this project, follow these steps:

1. Create a Python virtual environment:
   ```
   python3 -m venv test_venv
   ```

2. Activate the virtual environment:
   ```
   source test_venv/bin/activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the tests with the correct Python path to include the git submodules:
   ```
   PYTHONPATH=$PYTHONPATH:./dbus-systemcalc-py:./dbus-systemcalc-py/ext/velib_python python -m pytest tests/
   ```

The tests verify the correct detection of single-phase and three-phase meters based on the JSON data from the Home Wizard Energy P1 meter.

### Checking Code Coverage

To check how much of the code is covered by tests, you can use pytest-cov:

```
PYTHONPATH=$PYTHONPATH:./dbus-systemcalc-py:./dbus-systemcalc-py/ext/velib_python python -m pytest tests/ --cov=homewizard_energy
```

For a more detailed report showing which lines are not covered:

```
PYTHONPATH=$PYTHONPATH:./dbus-systemcalc-py:./dbus-systemcalc-py/ext/velib_python python -m pytest tests/ --cov=homewizard_energy --cov-report=term-missing
```

To generate an HTML coverage report:

```
PYTHONPATH=$PYTHONPATH:./dbus-systemcalc-py:./dbus-systemcalc-py/ext/velib_python python -m pytest tests/ --cov=homewizard_energy --cov-report=html
```

This will create an `htmlcov` directory with an interactive HTML report that can be viewed in a browser.