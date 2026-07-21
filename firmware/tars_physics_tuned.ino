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

// --- Wi-Fi Credentials ---
const char* WIFI_SSID     = "Aashi pawar";
const char* WIFI_PASSWORD = "8221946003";

// --- Calibration & Physics Parameters ---
int leftOffset = 90;        
int rightOffset = 90;       
int maxAmplitude = 15;      // Step width
int gaitSpeed = 350;        // Oscillation rhythm in ms (crucial for resonance)
int leanBias = 15;          // How far to lean the body into the walk (Center of Gravity shift)
String customMessage = "TARS READY"; 

// --- Real-Time Joystick Inputs (-100 to 100) ---
int joystickX = 0; 
int joystickY = 0; 

// --- Hardware Instantiation ---
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Servo servoLeft;
Servo servoRight;
WebServer server(80);

// Smooth Gait Engine Variables
unsigned long lastStepTime = 0;
int gaitStepState = 0;

// --- Mobile Web Interface (HTML/CSS/JS) ---
const char HTML_INTERFACE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TARS Physics Controller</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #121212; color: #E0E0E0; text-align: center; margin: 0; padding: 15px; }
        h1 { font-size: 24px; letter-spacing: 3px; color: #FFF; margin-bottom: 2px; }
        .subtitle { color: #888; font-size: 12px; margin-bottom: 15px; }
        .card { background: #1E1E1E; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); text-align: left; }
        .card h3 { text-align: center; margin-top: 0; color: #007AFF; font-size: 15px; letter-spacing: 1px; }
        
        #joystick-container { position: relative; width: 160px; height: 160px; background: #2A2A2A; border-radius: 50%; margin: 10px auto; touch-action: none; border: 2px solid #444; }
        #stick { position: absolute; width: 60px; height: 60px; background: #007AFF; border-radius: 50%; top: 50px; left: 50px; box-shadow: 0 4px 8px rgba(0,0,0,0.4); transition: transform 0.02s linear; }
        
        .btn { background: #FF3B30; color: white; border: none; padding: 12px; font-size: 14px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px;}
        .btn-blue { background: #007AFF; margin-top: 10px;}
        
        .slider-container { margin: 12px 0; }
        label { font-weight: bold; font-size: 11px; color: #AAA; display: block; margin-bottom: 4px; letter-spacing: 0.5px;}
        .slider { -webkit-appearance: none; width: 100%; height: 10px; border-radius: 5px; background: #333; outline: none; }
        .slider::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; border-radius: 50%; background: #007AFF; cursor: pointer; }
        .slider-alert::-webkit-slider-thumb { background: #FF3B30; }
        .value-display { float: right; color: #007AFF; font-weight: bold; }
        
        input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; background: #222; color: #00FF00; border: 1px solid #444; border-radius: 6px; font-family: monospace; font-size: 16px; text-transform: uppercase; text-align: center; }
    </style>
</head>
<body>
    <h1>TARS</h1>
    <div class="subtitle">PHYSICS & KINEMATICS TUNER</div>

    <div class="card" style="text-align: center;">
        <h3>FLIGHT STICK</h3>
        <div id="joystick-container">
            <div id="stick"></div>
        </div>
        <button class="btn" onclick="resetJoystick()">STOP & CENTER</button>
    </div>

    <div class="card">
        <h3>PHYSICS TUNING</h3>
        <div class="slider-container">
            <label>OSCILLATION SPEED (RESONANCE) <span id="spdVal" class="value-display">350ms</span></label>
            <input type="range" min="100" max="800" value="350" class="slider slider-alert" id="spdSlider" onchange="updateConfig()">
        </div>
        <div class="slider-container">
            <label>FORWARD LEAN BIAS (C.o.G.) <span id="leanVal" class="value-display">15&deg;</span></label>
            <input type="range" min="0" max="45" value="15" class="slider slider-alert" id="leanSlider" onchange="updateConfig()">
        </div>
        <div class="slider-container">
            <label>STEP AMPLITUDE (WIDTH) <span id="ampVal" class="value-display">15&deg;</span></label>
            <input type="range" min="2" max="40" value="15" class="slider" id="ampSlider" onchange="updateConfig()">
        </div>
    </div>

    <div class="card">
        <h3>STATIC TRIM</h3>
        <div class="slider-container">
            <label>LEFT TRIM <span id="leftVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="leftSlider" onchange="updateConfig()">
        </div>
        <div class="slider-container">
            <label>RIGHT TRIM <span id="rightVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="rightSlider" onchange="updateConfig()">
        </div>
    </div>

    <script>
        const container = document.getElementById('joystick-container');
        const stick = document.getElementById('stick');
        let active = false, lastX = 0, lastY = 0;

        function sendVector(x, y) {
            if (Math.abs(x - lastX) < 3 && Math.abs(y - lastY) < 3) return;
            lastX = x; lastY = y;
            fetch(`/vector?x=${x}&y=${y}`);
        }

        function resetJoystick() {
            stick.style.transform = `translate(0px, 0px)`;
            lastX = 0; lastY = 0;
            fetch('/vector?x=0&y=0');
        }

        function updateConfig() {
            let spd = document.getElementById('spdSlider').value;
            let lean = document.getElementById('leanSlider').value;
            let amp = document.getElementById('ampSlider').value;
            let l_off = document.getElementById('leftSlider').value;
            let r_off = document.getElementById('rightSlider').value;
            
            document.getElementById('spdVal').innerText = spd + 'ms';
            document.getElementById('leanVal').innerText = lean + '°';
            document.getElementById('ampVal').innerText = amp + '°';
            document.getElementById('leftVal').innerText = l_off + '°';
            document.getElementById('rightVal').innerText = r_off + '°';
            
            fetch(`/config?amp=${amp}&l_off=${l_off}&r_off=${r_off}&spd=${spd}&lean=${lean}`);
        }

        function handleMove(clientX, clientY) {
            const rect = container.getBoundingClientRect();
            let dx = clientX - rect.left - 80;
            let dy = clientY - rect.top - 80;
            let dist = Math.sqrt(dx * dx + dy * dy);
            let maxDist = 50;

            if (dist > maxDist) {
                dx = (dx / dist) * maxDist;
                dy = (dy / dist) * maxDist;
            }

            stick.style.transform = `translate(${dx}px, ${dy}px)`;

            let normX = Math.round((dx / maxDist) * 100);
            let normY = Math.round((-dy / maxDist) * 100); 
            
            if(Math.abs(normX) < 10 && Math.abs(normY) < 10) { normX = 0; normY = 0; }
            sendVector(normX, normY);
        }

        container.addEventListener('pointerdown', (e) => { active = true; handleMove(e.clientX, e.clientY); });
        window.addEventListener('pointermove', (e) => { if (active) handleMove(e.clientX, e.clientY); });
        window.addEventListener('pointerup', () => { if (active) { active = false; stick.style.transform = `translate(0px, 0px)`; resetJoystick(); } });
    </script>
</body>
</html>
)rawliteral";

// --- OLED Screen Update Helper ---
void updateDisplay(String statusText) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("SYS: TARS OS");
    display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
    
    display.setTextSize(2);
    display.setCursor(0, 22);
    display.print(customMessage);
    
    display.setTextSize(1);
    display.setCursor(0, 50);
    display.print("CMD: ");
    display.print(statusText);
    
    display.display();
}

// --- Web Server Request Handlers ---
void handleRoot() { server.send(200, "text/html", HTML_INTERFACE); }

void handleVector() {
    if (server.hasArg("x") && server.hasArg("y")) {
        joystickX = server.arg("x").toInt();
        joystickY = server.arg("y").toInt();

        if (joystickX == 0 && joystickY == 0) {
            servoLeft.write(leftOffset);
            servoRight.write(rightOffset);
            updateDisplay("IDLE / HOLD");
        }
        server.send(200, "text/plain", "OK");
    }
}

void handleConfig() {
    if (server.hasArg("amp")) maxAmplitude = server.arg("amp").toInt();
    if (server.hasArg("l_off")) leftOffset = server.arg("l_off").toInt();
    if (server.hasArg("r_off")) rightOffset = server.arg("r_off").toInt();
    if (server.hasArg("spd")) gaitSpeed = server.arg("spd").toInt();
    if (server.hasArg("lean")) leanBias = server.arg("lean").toInt();

    if (joystickX == 0 && joystickY == 0) {
        servoLeft.write(leftOffset);
        servoRight.write(rightOffset);
    }
    server.send(200, "text/plain", "OK");
}

// --- Advanced Physics-Based Gait Engine ---
void executeProportionalGait() {
    if (joystickX == 0 && joystickY == 0) return;

    unsigned long currentMillis = millis();
    // Use the dynamically adjustable speed slider for the step interval
    if (currentMillis - lastStepTime >= gaitSpeed) {
        lastStepTime = currentMillis;

        float v = joystickY / 100.0; // Forward/Reverse velocity
        float w = joystickX / 100.0; // Rotation velocity

        float leftScale = v + w;
        float rightScale = v - w;

        float maxScale = max(abs(leftScale), abs(rightScale));
        if (maxScale > 1.0) {
            leftScale /= maxScale;
            rightScale /= maxScale;
        }

        // Apply amplitude scaling
        int currentLeftAmp = maxAmplitude * leftScale;
        int currentRightAmp = maxAmplitude * rightScale;
        
        // Calculate dynamic Center of Gravity Lean
        // If pushing forward, body leans forward (legs shift back relative to center)
        int activeLean = 0;
        if (abs(joystickY) > 20) {
            activeLean = leanBias * (joystickY / 100.0);
        }

        // Determine Status String for OLED
        String modeString = "MOVING";
        if (abs(joystickX) > abs(joystickY) + 20) modeString = "AXIS PIVOT";
        else if (joystickY > 0) modeString = "WALK FWD";
        else modeString = "WALK REV";
        
        updateDisplay(modeString);

        // Calculate final step targets (Offset + CoG Lean +/- Step Amplitude)
        int targetLeft, targetRight;
        
        if (gaitStepState == 0) {
            targetLeft  = leftOffset + activeLean + currentLeftAmp;
            targetRight = rightOffset - activeLean - currentRightAmp; 
            gaitStepState = 1;
        } else {
            targetLeft  = leftOffset + activeLean - currentLeftAmp;
            targetRight = rightOffset - activeLean + currentRightAmp;
            gaitStepState = 0;
        }

        // Constrain safely to prevent servo damage, but wide enough for the new tuning
        servoLeft.write(constrain(targetLeft, 20, 160));
        servoRight.write(constrain(targetRight, 20, 160));
    }
}

void setup() {
    Serial.begin(115200);

    // Initialize OLED Display
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println("OLED init failed");
        for(;;);
    }
    
    // Connect to Wi-Fi
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(0, 20);
    display.print("CONNECTING");
    display.display();

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        attempts++;
        if (attempts > 30) ESP.restart();
    }

    customMessage = WiFi.localIP().toString();
    updateDisplay("SYS ONLINE");

    // Initialize Servos
    servoLeft.attach(SERVO_LEFT_PIN);
    servoRight.attach(SERVO_RIGHT_PIN);
    servoLeft.write(leftOffset);
    servoRight.write(rightOffset);

    // Register Web Routes
    server.on("/", handleRoot);
    server.on("/vector", handleVector);
    server.on("/config", handleConfig);
    server.begin();
}

void loop() {
    server.handleClient();     
    executeProportionalGait(); 
}
