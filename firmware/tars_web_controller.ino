#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

// --- Configuration Constants ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C

#define SERVO_LEFT_PIN   18
#define SERVO_RIGHT_PIN  19

// --- Enforced Safety Limits (Prevents Tipping Over) ---
const int SERVO_CENTER = 90;
const int MIN_SAFE_ANGLE = 84; // Hard ceiling for backward tilt
const int MAX_SAFE_ANGLE = 96; // Hard ceiling for forward tilt

// --- Object Instantiation ---
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Servo servoLeft;
Servo servoRight;
WebServer server(80); // HTTP web server running on standard port 80

int currentLeftAngle = 90;
int currentRightAngle = 90;

// --- HTML / CSS / JS Interface Code (Stored in Flash Memory) ---
const char HTML_INTERFACE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TARS Controller</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #121212; color: #E0E0E0; text-align: center; margin: 0; padding: 20px; }
        h1 { font-size: 28px; letter-spacing: 4px; color: #FFFFFF; margin-bottom: 5px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 30px; }
        .card { background: #1E1E1E; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        .btn { background: #333; color: white; border: none; padding: 15px 25px; font-size: 16px; border-radius: 8px; margin: 8px; cursor: pointer; width: 80%; transition: 0.2s; }
        .btn-home { background: #007AFF; }
        .btn:active { transform: scale(0.98); opacity: 0.9; }
        .slider-container { margin: 25px 0; text-align: left; }
        label { font-weight: bold; font-size: 14px; color: #AAA; display: block; margin-bottom: 8px; }
        .slider { -webkit-appearance: none; width: 100%; height: 12px; border-radius: 6px; background: #333; outline: none; }
        .slider::-webkit-slider-thumb { -webkit-appearance: none; width: 26px; height: 26px; border-radius: 50%; background: #007AFF; cursor: pointer; }
        .value-display { float: right; color: #007AFF; font-weight: bold; }
    </style>
</head>
<body>
    <h1>TARS</h1>
    <div class="subtitle">TACTICAL AUTONOMOUS ROBOTIC STABILIZER</div>

    <div class="card">
        <h3>PRESET POSTURES</h3>
        <button class="btn btn-home" onclick="sendMove(90,90)">STAND UPRIGHT (90&deg;)</button>
        <button class="btn" onclick="sendMove(94,94)">SAFE LEAN LEFT</button>
        <button class="btn" onclick="sendMove(86,86)">SAFE LEAN RIGHT</button>
    </div>

    <div class="card">
        <h3>FINE TUNING (SAFETY LOCKED)</h3>
        <div class="slider-container">
            <label>LEFT LEG <span id="leftVal" class="value-display">90&deg;</span></label>
            <input type="range" min="84" max="96" value="90" class="slider" id="leftSlider" onchange="updateSliders()">
        </div>
        <div class="slider-container">
            <label>RIGHT LEG <span id="rightVal" class="value-display">90&deg;</span></label>
            <input type="range" min="84" max="96" value="90" class="slider" id="rightSlider" onchange="updateSliders()">
        </div>
    </div>

    <script>
        function sendMove(l, r) {
            document.getElementById('leftSlider').value = l;
            document.getElementById('rightSlider').value = r;
            document.getElementById('leftVal').innerText = l + '°';
            document.getElementById('rightVal').innerText = r + '°';
            fetch('/move?left=' + l + '&right=' + r);
        }
        function updateSliders() {
            let l = document.getElementById('leftSlider').value;
            let r = document.getElementById('rightSlider').value;
            document.getElementById('leftVal').innerText = l + '°';
            document.getElementById('rightVal').innerText = r + '°';
            fetch('/move?left=' + l + '&right=' + r);
        }
    </script>
</body>
</html>
)rawliteral";

// --- UI Status Updater ---
void displayStatus(const char* state, const char* details) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    
    display.setTextSize(2);
    display.setCursor(10, 8);
    display.print("TARS WEB");
    
    display.setTextSize(1);
    display.setCursor(10, 38);
    display.print(state);
    display.setCursor(10, 50);
    display.print(details);
    
    display.display();
}

// --- Web Server Request Handlers ---
void handleRoot() {
    server.send(200, "text/html", HTML_INTERFACE);
}

void handleMove() {
    if (server.hasArg("left") && server.hasArg("right")) {
        int reqLeft = server.arg("left").toInt();
        int reqRight = server.arg("right").toInt();

        // Software constraint injection protecting physical structural limits
        currentLeftAngle = constrain(reqLeft, MIN_SAFE_ANGLE, MAX_SAFE_ANGLE);
        currentRightAngle = constrain(reqRight, MIN_SAFE_ANGLE, MAX_SAFE_ANGLE);

        servoLeft.write(currentLeftAngle);
        servoRight.write(currentRightAngle);

        char angleBuffer[20];
        sprintf(angleBuffer, "L: %d  R: %d", currentLeftAngle, currentRightAngle);
        displayStatus("MOVING...", angleBuffer);
        
        server.send(200, "text/plain", "OK");
    } else {
        server.send(400, "text/plain", "Bad Request");
    }
}

void setup() {
    Serial.begin(115200);

    // Initialize OLED screen
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println("OLED connection failure");
        for(;;);
    }
    displayStatus("CONNECTING", "AWAITING WIFI...");

    // Setup Actuators
    servoLeft.attach(SERVO_LEFT_PIN);
    servoRight.attach(SERVO_RIGHT_PIN);
    servoLeft.write(SERVO_CENTER);
    servoRight.write(SERVO_CENTER);

    // Connect to Wireless Local Area Network
    WiFi.begin("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD");
    while (WiFi.status() != WL_CONNECTED) {
        delay(400);
        Serial.print(".");
    }

    Serial.println("\nWiFi Connected!");
    Serial.print("Local IP Address: ");
    Serial.println(WiFi.localIP());

    // Update screen to tell user how to access the app
    String ipStr = WiFi.localIP().toString();
    displayStatus("ONLINE", ipStr.c_str());

    // Configure Web Routing Architecture
    server.on("/", handleRoot);
    server.on("/move", handleMove);
    server.begin();
}

void loop() {
    server.handleClient(); // Watch for incoming phone connection packets
}
