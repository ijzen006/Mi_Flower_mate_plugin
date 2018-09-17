"""
<plugin key="Mi_flower_mate" name="Xiaomi Mi Flower Mate" author="blauwebuis" version="1.1.0" wikilink="https://www.domoticz.com/wiki/Plugins/Mi_flower_mate" externallink="https://www.domoticz.com/forum/viewtopic.php?f=65&t=22281">
<description>
    This plugin connects to Mi Flower Mate flower sensors over Bluetooth LE. It requires the BluePy library to be installed on the system.
</description>
    <params>
        <param field="Mode1" label="Device selection" width="300px" required="true">
            <options>
                <option label="Automatic scanning" value="auto" default="true"/>
                <option label="Manual selection (add below)" value="manual"/>
            </options>
        </param>
        <param field="Mode2" label="Devices mac adresses, capitalised and comma separated" width="300px" required="false" default=""/>
        <param field="Mode4" label="Poll interval in minutes" width="100px" required="true" default=60 />
        <param field="Mode6" label="Debug" width="75px">
            <options>
                 <option label="True" value="Debug"/>
                 <option label="False" value="Normal"  default="False" />
            </options>
        </param>
    </params>
</plugin>
"""

bluepyError = 0

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

import time
import sys
import shelve
import os
from miflora import miflora_scanner, BluepyBackend
import miflora
from datetime import datetime, timedelta

try:
    from miflora.miflora_poller import MiFloraPoller, \
    MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
except:
    bluepyError = 1

try:
    from miflora.backends.bluepy import BluepyBackend
except:
    bluepyError = 1

class BasePlugin:

    def __init__(self):
        self.macs = []
        self.pollinterval = 60
        self.nextupdate = datetime.now()
        Domoticz.Debugging(0)
        return

    def onStart(self):
        Domoticz.Heartbeat(20)

        if Parameters["Mode6"] == "Debug":
            Domoticz.Log("Debug mode set to " + str(Parameters["Mode6"]) )
            Domoticz.Debugging(1)
            DumpConfigToLog()

        sys.path.append("/usr/local/lib/python3.4/dist-packages")
        sys.path.append("/usr/local/lib/python3.5/dist-packages")

        Domoticz.Debug("Mi Flora - devices made so far (max 255): " + str(len(Devices)))

        if bluepyError == 1:
            Domoticz.Error("Error loading Flora libraries")
        else:
            Domoticz.Debug("Loaded Flora Libraries")

        # check polling interval parameter
        try:
            temp = int(Parameters["Mode4"])
        except:
            Domoticz.Error("Invalid polling interval parameter")
        else:
            if temp < 60:
                temp = 60  # minimum polling interval
                Domoticz.Error("Specified polling interval too short: changed to 60 minutes")
            elif temp > 1440:
                temp = 1440  # maximum polling interval is 1 day
                Domoticz.Error("Specified polling interval too long: changed to 1440 minutes (24 hours)")
        finally:
            self.pollinterval = temp
            Domoticz.Log("Using polling interval of {} minutes".format(self.pollinterval))
            now = datetime.now()
            self.nextupdate = now + timedelta(minutes=self.pollinterval)
            Domoticz.Debug("Next update at :" + str(self.nextupdate))

        # create master toggle switch
        if 1 not in Devices:
            Domoticz.Log("Creating the master Mi Flower Mate poll switch. Flip it to poll the sensors.")
            #Domoticz.Device(Name="push to update Mi Flowermates", Unit=1, Type=17, Switchtype=9, Used=1).Create()
            Domoticz.Device(Name="update Mi Flowermates",  Unit=1, Type=17,  Switchtype=9, Used=1).Create()

        # get the mac addresses of the sensors
        if Parameters["Mode1"] == 'auto':
            Domoticz.Log("Automatic mode is selected")
            self.floraScan()
        else:
            Domoticz.Log("Manual mode is selected")
            self.macs = parseCSV(Parameters["Mode2"])
            Domoticz.Debug("macs = {}".format(self.macs))
        if ((len(Devices) - 1)/4) < len(self.macs):
            self.createSensors()
        else:
            Domoticz.Log("All Devices are created")
        return;

    def onStop(self):
        Domoticz.Log("onStop called")
        return;

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")
        return;

    def onMessage(self, Connection, Data, Status, Extra):
        Domoticz.Log("onMessage called")
        return;

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        Domoticz.Log("amount of Flower Mates to now ask for data: " + str(len(self.macs)) )

        # flip the switch icon, and then get the plant data.
        if Unit == 1:
            GetData()
        return;

    def onHeartbeat(self):
        # for now this uses the shelve database as its source of truth.
        now = datetime.now()
        Domoticz.Debug("Current time   :" + str(now))
        if now >= self.nextupdate:
            self.nextupdate = now + timedelta(minutes=self.pollinterval)
            Domoticz.Debug("Next update at :" + str(self.nextupdate))
            GetData()
        return;

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()
    return;

def onStop():
    global _plugin
    _plugin.onStop()
    return;

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)
    return;

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()
    return;

def parseCSV(strCSV):
    listvals = []
    for value in strCSV.split(","):
        listvals.append(value)
    return listvals;

def createSensors(self):
    # function to create corresponding sensors in Domoticz if there are Mi Flower Mates which don't have them yet.
    # create the domoticz sensors if necessary
    Domoticz.Debug("Creating new sensors")
    # Create the sensors. Later we get the data.
    for idx, mac in enumerate(self.macs):
        Domoticz.Debug("Creating new sensors for Mi Flower Mate at "+str(mac))
        sensorBaseName = "#" + str(idx) + " "

        #moisture
        sensorNumber = (idx*4) + 2
        if sensorNumber not in Devices:

            sensorName = sensorBaseName + "Moisture"
            CreateDevice(sensorNumber, sensorName, "Humidity")

            sensorNumber = (idx*4) + 3
            sensorName = sensorBaseName + "Temperature"
            CreateDevice(sensorNumber, sensorName, "Temperature")

            sensorNumber = (idx*4) + 4
            sensorName = sensorBaseName + "Light"
            CreateDevice(sensorNumber, sensorName, "Illumination")

            sensorNumber = (idx*4) + 5
            sensorName = sensorBaseName + "Fertility"
            CreateDevice(sensorNumber, sensorName, "Custom")

            #Domoticz.Debug("Creating first sensor, #"+str(sensorNumber)+" name: "+str(sensorName) )
            #Domoticz.Device(Name=sensorName, Unit=sensorNumber, TypeName="Humidity", Used=1).Create()
            #Domoticz.Log("Created device: "+Devices[sensorNumber].Name)

            #temperature
            #sensorNumber = (idx*4) + 3
            #sensorName = sensorBaseName + "Temperature"
       	    #Domoticz.Device(Name=sensorName, Unit=sensorNumber, TypeName="Temperature", Used=1).Create()
            #Domoticz.Log("Created device: "+Devices[sensorNumber].Name)

            #light
            #sensorNumber = (idx*4) + 4
            #sensorName = sensorBaseName + "Light"
            #Domoticz.Device(Name=sensorName, Unit=sensorNumber, TypeName="Illumination", Used=1).Create()
            #Domoticz.Log("Created device: "+Devices[sensorNumber].Name)
            #fertility
            #sensorNumber = (idx*4) + 5
            #sensorName = sensorBaseName + "Conductivity"
            #Domoticz.Device(Name=sensorName, Unit=sensorNumber, TypeName="Custom", Used=1).Create()
            #Domoticz.Log("Created device: "+Devices[sensorNumber].Name)
    return;

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

def GetData():
    idx = 0
    for mac in Parameters["Mode2"].split(','):
        Domoticz.Log("getting data from sensor: "+str(mac) )
        poller = MiFloraPoller(str(mac), BluepyBackend)
        Domoticz.Debug("Firmware: {}".format(poller.firmware_version()))
        val_bat  = int("{}".format(poller.parameter_value(MI_BATTERY)))

        #moisture
        moist = (idx*4) + 2
        val_moist = "{}".format(poller.parameter_value(MI_MOISTURE))
        UpdateDevice(moist, 0, val_moist, val_bat, "")

        #temperature
        temp  = (idx*4) + 3
        val_temp = "{}".format(poller.parameter_value(MI_TEMPERATURE))
        UpdateDevice(temp, 0, val_temp, val_bat, "")

        #Light
        lux   = (idx*4) + 4
        val_lux = "{}".format(poller.parameter_value(MI_LIGHT))
        UpdateDevice(lux, 0, val_lux, val_bat, "")

        #fertility
        cond  = (idx*4) + 5
        val_cond = "{}".format(poller.parameter_value(MI_CONDUCTIVITY))
        UpdateDevice(cond, 0, val_cond, val_bat, "")
        Domoticz.Debug("Data retrieved : " + str(val_moist)+","+str(val_temp)+","+str(val_lux)+","+str(val_cond) )
        idx += 1
    return

def CreateDevice(sensorNumber, sensorName, Type):
    # Create Device
    Domoticz.Device(Name=sensorName, Unit=sensorNumber, TypeName=Type, Used=1).Create()
    Domoticz.Log("Created "+str(sensorName)+":'"+str(Type)+"' ("+Devices[sensorNumber].Name+")")
    return

def UpdateDevice(Unit, nValue, sValue, vValue, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if (Unit in Devices):
        if ((Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue) or (AlwaysUpdate == True)):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue),BatteryLevel=vValue)
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return

def floraScan(self):
    # function to scan for devices, and store and compare the outcome
    Domoticz.Log("Scanning for Mi Flower Mate sensors")

    #databaseFile=os.path.join(os.environ['HOME'],'XiaomiMiFlowerMates')
    # first, let's get the list of devices we already know about
    database = shelve.open('XiaomiMiMates')

    try:
        knownSensors = database['macs']
        oldLength = len(knownSensors)
        Domoticz.Debug("Already know something:" + str(oldLength))
        Domoticz.Log("Already known devices:" + str(knownSensors))
    except:
        knownSensors = []
        database['macs'] = knownSensors
        oldLength = 0;
        Domoticz.Debug("No existing sensors in system?")

    #Next we scan to look for new sensors
    try:
        foundFloras = miflora_scanner.scan(BluepyBackend, 3)
        Domoticz.Log("Number of devices found via bluetooth scan = " + str(len(foundFloras)))
    except:
        foundFloras = []
        Domoticz.Log("Scan failed")

    for sensor in foundFloras:
        if sensor not in knownSensors:
            knownSensors.append(str(sensor))
            Domoticz.Log("Found new device: " + str(sensor))

    if len(knownSensors) != oldLength:
        database['macs'] = knownSensors
        Domoticz.Log("Updating database")

    database.close()

    self.macs = knownSensors
    self.createSensors()
    return;
