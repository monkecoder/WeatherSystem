import asyncio
import struct
from datetime import datetime

from bleak import BleakClient
from bleak.exc import BleakDeviceNotFoundError
from psycopg2 import OperationalError as pc2_OperationalError, connect as pc2_connect

LOOP = asyncio.get_event_loop()


def dbConnect():
    """Database connect."""
    connection = pc2_connect(
        database="weather_system",
        host="localhost",
        user="python_connect",
        password="connect_me9382",
        port="5432"
    )
    return connection


async def readCharacteristic(device, char):
    """Read characteristic and its descriptor."""
    desc = char.descriptors[0]
    desc_value = await device.read_gatt_descriptor(desc.handle)

    name = desc_value.decode('utf-8')
    value = struct.unpack('f', await device.read_gatt_char(char))[0]

    return name, value


async def readParameters(address, i, service_uuid, weather):
    """Read all characteristics and their first descriptors in a service."""
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
                        task_list.append(LOOP.create_task(readCharacteristic(device, char)))
                    for task in task_list:
                        name, value = await task
                        param_dict[name] = value

                    result = cursor.execute(insert_query % tuple(param_dict.values()))
                    connection.commit()

                except OSError:
                    print('Ошибка BLE: устройство отключено\n')
                    weather.addresses_states[i][1] = 0
                except pc2_OperationalError:
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
    except pc2_OperationalError:
        print('Ошибка SQL: при подключении к БД\n')
        weather.addresses_states[i][1] = 0
    finally:
        await asyncio.sleep(3)


def readAll(addresses, param_service_uuid, read_delay, stop_event, weather):
    """Main function, read characteristics in loop."""
    print("Запуск чтения BLE\n")
    while True:
        i = 0
        weather_current = []
        for address in addresses:
            weather_current.append(LOOP.run_until_complete(readParameters(address, i, param_service_uuid, weather)))
            print(f'{i}:', weather_current[i], '\n', sep='')
            i += 1

        weather.weather_current = weather_current
        stop = stop_event.wait(timeout=read_delay)
        if stop:
            return
