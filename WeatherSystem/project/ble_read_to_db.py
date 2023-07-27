###### imports ######
import asyncio
import struct
from datetime import datetime
from bleak.exc import BleakDeviceNotFoundError
from bleak import BleakClient
import psycopg2
from psycopg2 import OperationalError

from datastruct import DataStruct
from main import Weather
loop = asyncio.get_event_loop()

###### database connect ######
def dbConnect():
    connection = psycopg2.connect(
        database="weather_system",
        host="localhost",
        user="python_connect",
        password="connect_me9382",
        port="5432"
    )
    return connection


###### read characteristic and its descriptor ######
async def readCharacteristic(device, char):
        desc = char.descriptors[0]
        desc_value = await device.read_gatt_descriptor(desc.handle)

        name = desc_value.decode('utf-8')
        value = struct.unpack('f', await device.read_gatt_char(char))[0]

        return name, value


###### read all characteristics and their first descriptors in a service ######
async def readParameters(address, i, service_uuid, weather):
    try:
        async with BleakClient(address) as device:
            serv = next(service for service in device.services if service.uuid == service_uuid)
            print('Устройство найдено\n')
            weather.addresses_states[i][1] = 1

            connection = dbConnect()
            cursor = connection.cursor()
            insert_query = f"""insert into value{i} (date, time, temperature, humidity, pressure)
                            values ('%s', '%s', %s, %s, %s);"""
            
            while device.is_connected:
                try:
                    task_list = list()
                    param_dict = dict()
                    param_dict['Date'] = datetime.now().date().isoformat()
                    param_dict['Time'] = datetime.now().time().isoformat()
                    for char in serv.characteristics:
                        task_list.append(loop.create_task(readCharacteristic(device, char)))
                    for task in task_list:
                        name, value = await task
                        param_dict[name] = value

                    result = cursor.execute(insert_query % tuple(param_dict.values()))
                    connection.commit()

                except OSError:
                    print('Ошибка BLE: устройство отключено\n')
                    weather.addresses_states[i][1] = 0
                except OperationalError:
                    print('Ошибка SQL: прерывание подключения\n')
                    weather.addresses_states[i][1] = 0
                finally:
                    await asyncio.sleep(3)
                    return param_dict

    except BleakDeviceNotFoundError:
        print('Ошибка BLE: устройство не найдено\n')
        weather.addresses_states[i][1] = 0
    except OSError:
        print('Ошибка BLE: ошибка системного bluetooth^a\n')
        weather.addresses_states[i][1] = 0
    except OperationalError:
        print('Ошибка SQL: при подключении к БД\n')
        weather.addresses_states[i][1] = 0
    finally:
        await asyncio.sleep(3)


###### main function ######
def readAll(addresses, param_service_uuid, read_delay, stop_event, weather):
    print("Запуск чтения BLE\n")
    while True:
        i = 0
        weather_current = list()
        for address in addresses:
            weather_current.append(loop.run_until_complete(readParameters(address, i, param_service_uuid, weather)))
            print(f'{i}:', weather_current[i], '\n', sep='')
            i += 1
        
        weather.weather_current = weather_current
        stop = stop_event.wait(timeout=read_delay)
        if stop:
            return
