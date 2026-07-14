#include <WiFi.h>
#include <driver/i2s.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

// --- Network Settings ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_ip = "192.168.1.100"; // REPLACE with your PC's local IP address
const uint16_t server_port = 5000;

// --- Pin Assignments ---
#define MIC_WS  25
#define MIC_SCK 33
#define MIC_SD  32

#define AMP_WS  26
#define AMP_SCK 27
#define AMP_SD  23

#define OLED_SDA 21
#define OLED_SCL 19

#define SERVO_L  14
#define SERVO_R  12

// --- Peripherals Initialization ---
Adafruit_SSD1306 display(128, 64, &Wire, -1);
Servo servoLeft;
Servo servoRight;
WiFiClient client;

// Audio buffer settings
uint8_t micBuffer[512];

// FreeRTOS Task Handle
TaskHandle_t rxTaskHandle = NULL;

// --- Function Declarations ---
void initI2SMic();
void initI2SAmp();
void updateOLED(String text);
void handleIncomingPackets();
void audioRxTask(void* parameter);

void setup() {
  Serial.begin(115200);
  
  // 1. Initialize OLED on Custom Pins
  Wire.begin(OLED_SDA, OLED_SCL);
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 allocation failed");
    for(;;);
  }
  updateOLED("BOOTING...");

  // 2. Initialize Servos
  servoLeft.attach(SERVO_L);
  servoRight.attach(SERVO_R);
  servoLeft.write(90);  // Center position
  servoRight.write(90); // Center position

  // 3. Initialize I2S Audio Channels
  initI2SMic();
  initI2SAmp();

  // 4. Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    updateOLED("WIFI CONNECTING");
  }
  Serial.println("\nWiFi Connected!");
  updateOLED("WIFI OK");

  // 5. Connect to Host Server
  while (!client.connect(server_ip, server_port)) {
    Serial.println("Waiting for TARS Host Server...");
    updateOLED("WAITING FOR HOST");
    delay(2000);
  }
  updateOLED("ONLINE");

  // 6. Spawn Background Audio Playback & Command Task on Core 0
  xTaskCreatePinnedToCore(
    audioRxTask,
    "AudioRxTask",
    10000,
    NULL,
    1,
    &rxTaskHandle,
    0
  );
}

void loop() {
  if (client.connected()) {
    // Read from INMP441 Microphone (Core 1)
    size_t bytes_read = 0;
    i2s_read(I2S_NUM_0, micBuffer, sizeof(micBuffer), &bytes_read, portMAX_DELAY);
    
    if (bytes_read > 0) {
      // Packet Frame: [0xAA, 0xBB, Type=0x01, Len High, Len Low, Payload]
      uint8_t header[5];
      header[0] = 0xAA;
      header[1] = 0xBB;
      header[2] = 0x01; // Mic stream type
      header[3] = (bytes_read >> 8) & 0xFF;
      header[4] = bytes_read & 0xFF;
      
      client.write(header, 5);
      client.write(micBuffer, bytes_read);
    }
  } else {
    // Reconnection mechanism if TCP drops out
    updateOLED("RECONNECTING...");
    delay(1000);
    client.connect(server_ip, server_port);
  }
}

// Background listening task running on Core 0 (No mic lag or audio stuttering)
void audioRxTask(void* parameter) {
  while (true) {
    if (client.connected()) {
      handleIncomingPackets();
    }
    vTaskDelay(1 / portTICK_PERIOD_MS); // Feed the watchdog
  }
}

void handleIncomingPackets() {
  if (client.available() < 5) return;

  // Peek to ensure packet alignment
  uint8_t peek_buf[2];
  client.peekBytes(peek_buf, 2);
  if (peek_buf[0] != 0xAA || peek_buf[1] != 0xBB) {
    client.read(); // Discard corrupted byte, realign
    return;
  }

  // Read Header
  uint8_t header[5];
  client.readBytes(header, 5);
  uint8_t type = header[2];
  uint16_t len = (header[3] << 8) | header[4];

  // Allocate safe payload space
  uint8_t* payload = (uint8_t*)malloc(len);
  if (payload == NULL) return;

  // Read complete payload
  size_t read_bytes = 0;
  unsigned long start_time = millis();
  while (read_bytes < len && (millis() - start_time < 500)) {
    if (client.available()) {
      payload[read_bytes++] = client.read();
    } else {
      delay(1);
    }
  }

  // Process Packet Type if read succeeded
  if (read_bytes == len) {
    if (type == 0x01) { // Type 0x01: Audio Data output to MAX98357A
      size_t bytes_written;
      i2s_write(I2S_NUM_1, payload, len, &bytes_written, portMAX_DELAY);
    } 
    else if (type == 0x02) { // Type 0x02: Servo Movements [Left Servo, Right Servo]
      if (len == 2) {
        servoLeft.write(payload[0]);
        servoRight.write(payload[1]);
      }
    } 
    else if (type == 0x03) { // Type 0x03: OLED Update Text
      String text = "";
      for (int i = 0; i < len; i++) {
        text += (char)payload[i];
      }
      updateOLED(text);
    }
  }
  free(payload);
}

void initI2SMic() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = MIC_SCK,
    .ws_io_num = MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = MIC_SD
  };
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
}

void initI2SAmp() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = AMP_SCK,
    .ws_io_num = AMP_WS,
    .data_out_num = AMP_SD,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  i2s_driver_install(I2S_NUM_1, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pin_config);
}

void updateOLED(String text) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("TARS-SYSTEM CONFIG");
  display.println("--------------------");
  display.println("");
  display.setTextSize(2);
  display.println(text);
  display.display();
}
