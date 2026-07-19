#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

// --- Configuration Constants ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C  // Standard I2C address for 0.96" OLED panels

#define SERVO_LEFT_PIN   18
#define SERVO_RIGHT_PIN  19

// --- Anti-Topple Safe Calibration Degrees ---
const int SERVO_CENTER = 90; // Upright home position
const int TILT_OFFSET  = 4;  // Degrees to tilt during boot scan (safely low)

// --- Hardware Object Instantiation ---
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Servo servoLeft;
Servo servoRight;

// --- UI Rendering Routine ---
void printStatus(const char* title, const char* subtitle) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    
    // Header
    display.setTextSize(2);
    display.setCursor(12, 10);
    display.print(title);
    
    // Status message
    display.setTextSize(1);
    display.setCursor(12, 42);
    display.print(subtitle);
    
    display.display();
}

void setup() {
    Serial.begin(115200);
    
    // 1. Initialize Screen
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println(F("SSD1306 allocation failed. Check I2C connections."));
        for(;;); // Lock up if screen is missing
    }
    
    printStatus("TARS", "BOOTING SYSTEM...");
    delay(1500);

    // 2. Initialize and Center Actuators
    printStatus("TARS", "CALIBRATING LIMBS");
    servoLeft.attach(SERVO_LEFT_PIN);
    servoRight.attach(SERVO_RIGHT_PIN);
    
    // Move cleanly to baseline upright center line
    servoLeft.write(SERVO_CENTER);
    servoRight.write(SERVO_CENTER);
    delay(1000);

    // 3. Execution of Safe Physical Diagnostic Sweep
    printStatus("TARS", "TESTING TILT: L");
    servoLeft.write(SERVO_CENTER + TILT_OFFSET);
    servoRight.write(SERVO_CENTER + TILT_OFFSET);
    delay(800);

    printStatus("TARS", "TESTING TILT: R");
    servoLeft.write(SERVO_CENTER - TILT_OFFSET);
    servoRight.write(SERVO_CENTER - TILT_OFFSET);
    delay(800);

    // 4. Return to Stable Stance
    printStatus("TARS", "LOCKING POSTURE");
    servoLeft.write(SERVO_CENTER);
    servoRight.write(SERVO_CENTER);
    delay(1000);

    // 5. Diagnostics Finished
    printStatus("TARS", "SYSTEM: ONLINE");
    Serial.println("Boot diagnostic sequence successfully finished.");
}

void loop() {
    // Keeps the status locked on screen. No periodic movements here 
    // to protect the physical chassis from tipping over unmonitored.
}
