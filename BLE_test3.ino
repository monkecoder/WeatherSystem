// #define DEBUG
#include <ArduinoBLE.h>
#include <Arduino_HTS221.h>
#include <Arduino_LPS22HB.h>

// declare uuids for ble objects
const char* parameterServiceUuid = "00001802-0000-1000-8000-00805f9b34fb";

const char* temperatureCharacteristicUuid = "0A10";
const char* humidityCharacteristicUuid = "0A20";
const char* pressureCharacteristicUuid = "0A30";

const char* temperatureDescriptorUuid = "0A11";
const char* humidityDescriptorUuid = "0A21";
const char* pressureDescriptorUuid = "0A31";

// declare variables for values
float temperature = 0;
float humidity = 0;
float pressure = 0;

// device connect handler function
void bleCentralConnectHandler(BLEDevice central) {
  #ifdef DEBUG
  Serial.print("Connected to central: ");
  Serial.println(central.address());
  #endif
  digitalWrite(LED_BUILTIN, HIGH);
}

// device disconnect handling function 
void bleCentralDisconnectHandler(BLEDevice central) {
  #ifdef DEBUG
  Serial.print("Disconnected from central: ");
  Serial.println(central.address());
  #endif
  digitalWrite(LED_BUILTIN, LOW);
}

// init ble objects
BLEService parameterService(parameterServiceUuid); 
BLEFloatCharacteristic temperatureCharacteristic(temperatureCharacteristicUuid, BLERead);
BLEFloatCharacteristic humidityCharacteristic(humidityCharacteristicUuid, BLERead);
BLEFloatCharacteristic pressureCharacteristic(pressureCharacteristicUuid, BLERead);
BLEDescriptor temperatureDescriptor(temperatureDescriptorUuid, "Temperature");
BLEDescriptor humidityDescriptor(humidityDescriptorUuid, "Humidity");
BLEDescriptor pressureDescriptor(pressureDescriptorUuid, "Pressure");

// read values from sensors
void readSensors() {
  temperature = HTS.readTemperature();
  humidity = HTS.readHumidity();
  pressure = BARO.readPressure();
}

// write values into characteristics
void writeParameterCharacteristicValues() {
  temperatureCharacteristic.writeValue(temperature);
  humidityCharacteristic.writeValue(humidity);
  pressureCharacteristic.writeValue(pressure);
}

// endless state for failures
void failureState() {
  while (1) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
}

void setup() {
  #ifdef DEBUG
  Serial.begin(9600);
  while (!Serial);
  #endif

  // init led
  pinMode(LED_BUILTIN, OUTPUT);

  // check ble init
  if (!BLE.begin()) {
    #ifdef DEBUG
    Serial.println("# Failed to initialize BLE module!");
    #endif
    failureState();
  }

  //check hts begin
  if (!HTS.begin()) {
    #ifdef DEBUG
    Serial.println("# Failed to initialize HTS221 sensor!");
    #endif
    failureState();
  }

  //check baro begin
  if (!BARO.begin()) {
    #ifdef DEBUG
    Serial.println("# Failed to initialize LPS22HB sensor!");
    #endif
    failureState();
  }

  // declare ble parameters
  BLE.setLocalName("Arduino Nano 33 BLE (Sending parameters)");
  BLE.setDeviceName("xXx_Arduino_xXx");

  // add descriptors to characteristics
  temperatureCharacteristic.addDescriptor(temperatureDescriptor);
  humidityCharacteristic.addDescriptor(humidityDescriptor);
  pressureCharacteristic.addDescriptor(pressureDescriptor);

  // add characteristics to service
  parameterService.addCharacteristic(temperatureCharacteristic);
  parameterService.addCharacteristic(humidityCharacteristic);
  parameterService.addCharacteristic(pressureCharacteristic);

  // add service to device
  BLE.addService(parameterService);

  // write parameters into ble characteristics from local values
  writeParameterCharacteristicValues();

  // set event handler functions
  BLE.setEventHandler(BLEConnected, bleCentralConnectHandler);
  BLE.setEventHandler(BLEDisconnected, bleCentralDisconnectHandler);

  // set advertising
  BLE.setAdvertisedService(parameterService);
  BLE.advertise();

  #ifdef DEBUG
  Serial.println("Arduino Nano 33 BLE (Sending parameters)");
  Serial.println();
  Serial.println("- Discovering central device...");
  #endif
}

void loop() {
  BLEDevice central = BLE.central();

  // check connection
  BLE.poll();

  if (central) {
    #ifdef DEBUG
    readSensors();

    Serial.print("Temperature = ");
    Serial.print(temperature);
    Serial.println(" °C");

    Serial.print("Humidity = ");
    Serial.print(humidity);
    Serial.println(" %");

    Serial.print("Pressure = ");
    Serial.print(pressure);
    Serial.println(" kPa");
    #endif

    // update characteristics
    while (central.connected()) {
      readSensors();
      writeParameterCharacteristicValues();

      BLE.poll();

      delay(100);
    }
    
    // check disconnection
    BLE.poll();

    #ifdef DEBUG
    Serial.println();
    Serial.println("- Discovering central device again...");
    #endif
  }
}