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

### Pictures
![Tile Overview](img/VenusOs_Overview.png)
![Remote Console - Overview](img/VenusOs_DeviceList.png) 
![SmartMeter - Values](img/VenusOs_P1.png)
![SmartMeter - Device Details](img/VenusOs_Service.png)

## Install & Configuration
### Get the code
Clone the repository and install it to `/data/dbus-Home-Wizard-Energy-P1`. Then run the installation script.

The following commands will do everything for you:
```
wget https://github.com/back2basic/dbus-Home-Wizard-Energy-P1/archive/refs/heads/main.zip
unzip main.zip "dbus-Home-Wizard-Energy-P1-main/*" -d /data
mv /data/dbus-Home-Wizard-Energy-P1-main /data/dbus-Home-Wizard-Energy-P1
chmod a+x /data/dbus-Home-Wizard-Energy-P1/install.sh
/data/dbus-Home-Wizard-Energy-P1/install.sh
rm main.zip
```
⚠️ Check the configuration after installation, as the service will start immediately with default settings.

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