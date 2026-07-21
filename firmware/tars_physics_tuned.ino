#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>
#include <math.h>

// --- Hardware & Display Pin Configuration ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C

#define SERVO_LEFT_PIN   18
#define SERVO_RIGHT_PIN  19

// --- Wi-Fi Network Credentials ---
const char* WIFI_SSID     = "";
const char* WIFI_PASSWORD = "";

// --- Servo Hardware Trims ---
float leftOffset  = 90.0;
float rightOffset = 90.0;

// --- Phase-Based Inching Gait Parameters (Fine-Tunable via Web UI) ---
float legSwingAngle  = 25.0; // Degrees legs reach forward relative to body
float bodyPushAngle   = 25.0; // Degrees legs push backward to drive center body forward
float pitchLiftAngle  = 12.0; // Dynamic CoM pitch shift to unweight body/legs during transitions
float swingDurationMs = 220.0; // Time in ms spent swinging legs forward
float pushDurationMs  = 280.0; // Time in ms spent pushing main body forward
float pauseDurationMs = 80.0;  // Settling delay between stance transitions
float servoSmoothFactor = 0.25; // Servo trajectory interpolation factor (0.05=slow/smooth, 0.5=fast)

bool invertRightServo = false;

String customMessage = "TARS PHASE OS";

// --- Control Vector States ---
float targetX = 0.0, targetY = 0.0;
float currentX = 0.0, currentY = 0.0;

// --- Output Servo Angles ---
float currentLeftAngle = 90.0;
float currentRightAngle = 90.0;

// --- Discrete Phase State Machine Definition ---
enum GaitPhase {
  PHASE_IDLE,
  PHASE_SWING_LEGS_FORWARD,
  PHASE_PLANT_LEGS,
  PHASE_PUSH_BODY_FORWARD,
  PHASE_PLANT_BODY
};

GaitPhase currentPhase = PHASE_IDLE;
unsigned long phaseStartTime = 0;

// --- System Objects ---
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Servo servoLeft;
Servo servoRight;
WebServer server(80);

// --- Mobile Web Controller Interface ---
const char HTML_INTERFACE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TARS Discrete Phase Controller</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #121212; color: #E0E0E0; text-align: center; margin: 0; padding: 12px; }
        h1 { font-size: 22px; letter-spacing: 3px; color: #FFF; margin-bottom: 2px; }
        .subtitle { color: #888; font-size: 11px; margin-bottom: 12px; }
        .card { background: #1E1E1E; border-radius: 12px; padding: 12px; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); text-align: left; }
        .card h3 { text-align: center; margin-top: 0; color: #007AFF; font-size: 14px; letter-spacing: 1px; }
        
        #joystick-container { position: relative; width: 170px; height: 170px; background: #2A2A2A; border-radius: 50%; margin: 8px auto; touch-action: none; border: 2px solid #444; }
        #stick { position: absolute; width: 60px; height: 60px; background: #007AFF; border-radius: 50%; top: 55px; left: 55px; box-shadow: 0 4px 8px rgba(0,0,0,0.4); }
        
        .btn { background: #FF3B30; color: white; border: none; padding: 10px; font-size: 13px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 8px;}
        .btn-blue { background: #007AFF; margin-top: 6px;}
        
        .slider-container { margin: 10px 0; }
        label { font-weight: bold; font-size: 11px; color: #AAA; display: block; margin-bottom: 3px; }
        .slider { -webkit-appearance: none; width: 100%; height: 8px; border-radius: 4px; background: #333; outline: none; }
        .slider::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: #007AFF; cursor: pointer; }
        .slider-highlight::-webkit-slider-thumb { background: #30D158; }
        .value-display { float: right; color: #007AFF; font-weight: bold; }
        
        input[type="text"] { width: 100%; padding: 8px; box-sizing: border-box; background: #222; color: #00FF00; border: 1px solid #444; border-radius: 6px; font-family: monospace; font-size: 14px; text-transform: uppercase; text-align: center; }
    </style>
</head>
<body>
    <h1>TARS</h1>
    <div class="subtitle">2-STAGE DISCRETE INCHING GAIT</div>

    <div class="card" style="text-align: center;">
        <h3>OLED TELEMETRY</h3>
        <input type="text" id="screenText" maxlength="12" placeholder="CUSTOM MESSAGE" value="TARS PHASE OS">
        <button class="btn btn-blue" onclick="updateScreen()">UPDATE SCREEN</button>
    </div>

    <div class="card" style="text-align: center;">
        <h3>DIRECTIONAL CONTROLLER</h3>
        <div id="joystick-container">
            <div id="stick"></div>
        </div>
        <button class="btn" onclick="resetJoystick()">EMERGENCY STOP</button>
    </div>

    <div class="card">
        <h3>PHASE GAIT TIMING & KINEMATICS</h3>
        <div class="slider-container">
            <label>LEG SWING ANGLE <span id="swingVal" class="value-display">25&deg;</span></label>
            <input type="range" min="5" max="45" value="25" class="slider slider-highlight" id="swingSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>BODY PUSH ANGLE <span id="pushVal" class="value-display">25&deg;</span></label>
            <input type="range" min="5" max="45" value="25" class="slider slider-highlight" id="pushSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>PITCH LIFT ANGLE <span id="pitchVal" class="value-display">12&deg;</span></label>
            <input type="range" min="0" max="30" value="12" class="slider" id="pitchSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>SWING DURATION <span id="swingTimeVal" class="value-display">220ms</span></label>
            <input type="range" min="100" max="600" step="10" value="220" class="slider" id="swingTimeSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>PUSH DURATION <span id="pushTimeVal" class="value-display">280ms</span></label>
            <input type="range" min="100" max="800" step="10" value="280" class="slider" id="pushTimeSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>TRANSITION PAUSE <span id="pauseVal" class="value-display">80ms</span></label>
            <input type="range" min="20" max="300" step="10" value="80" class="slider" id="pauseSlider" oninput="updateConfig()">
        </div>
    </div>

    <div class="card">
        <h3>SERVO ZERO TRIM</h3>
        <div class="slider-container">
            <label>LEFT LEG TRIM <span id="leftVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="leftSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>RIGHT LEG TRIM <span id="rightVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="rightSlider" oninput="updateConfig()">
        </div>
    </div>

    <script>
        const container = document.getElementById('joystick-container');
        const stick = document.getElementById('stick');
        let active = false, lastX = 0, lastY = 0;

        function updateScreen() {
            let msg = document.getElementById('screenText').value;
            fetch('/text?msg=' + encodeURIComponent(msg));
        }

        function sendVector(x, y) {
            if (Math.abs(x - lastX) < 2 && Math.abs(y - lastY) < 2) return;
            lastX = x; lastY = y;
            fetch(`/vector?x=${x}&y=${y}`);
        }

        function resetJoystick() {
            stick.style.transform = `translate(0px, 0px)`;
            lastX = 0; lastY = 0;
            fetch('/vector?x=0&y=0');
        }

        function updateConfig() {
            let swing = document.getElementById('swingSlider').value;
            let push = document.getElementById('pushSlider').value;
            let pitch = document.getElementById('pitchSlider').value;
            let stime = document.getElementById('swingTimeSlider').value;
            let ptime = document.getElementById('pushTimeSlider').value;
            let pause = document.getElementById('pauseSlider').value;
            let l_off = document.getElementById('leftSlider').value;
            let r_off = document.getElementById('rightSlider').value;
            
            document.getElementById('swingVal').innerText = swing + '°';
            document.getElementById('pushVal').innerText = push + '°';
            document.getElementById('pitchVal').innerText = pitch + '°';
            document.getElementById('swingTimeVal').innerText = stime + 'ms';
            document.getElementById('pushTimeVal').innerText = ptime + 'ms';
            document.getElementById('pauseVal').innerText = pause + 'ms';
            document.getElementById('leftVal').innerText = l_off + '°';
            document.getElementById('rightVal').innerText = r_off + '°';
            
            fetch(`/config?swing=${swing}&push=${push}&pitch=${pitch}&stime=${stime}&ptime=${ptime}&pause=${pause}&l_off=${l_off}&r_off=${r_off}`);
        }

        function handleMove(clientX, clientY) {
            const rect = container.getBoundingClientRect();
            let dx = clientX - rect.left - 85;
            let dy = clientY - rect.top - 85;
            let dist = Math.sqrt(dx * dx + dy * dy);
            let maxDist = 55;

            if (dist > maxDist) {
                dx = (dx / dist) * maxDist;
                dy = (dy / dist) * maxDist;
            }

            stick.style.transform = `translate(${dx}px, ${dy}px)`;

            let normX = Math.round((dx / maxDist) * 100);
            let normY = Math.round((-dy / maxDist) * 100); 
            
            if(Math.abs(normX) < 8 && Math.abs(normY) < 8) { normX = 0; normY = 0; }
            sendVector(normX, normY);
        }

        container.addEventListener('pointerdown', (e) => { active = true; handleMove(e.clientX, e.clientY); });
        window.addEventListener('pointermove', (e) => { if (active) handleMove(e.clientX, e.clientY); });
        window.addEventListener('pointerup', () => { if (active) { active = false; stick.style.transform = `translate(0px, 0px)`; resetJoystick(); } });
    </script>
</body>
</html>
)rawliteral";

// --- OLED Screen Telemetry ---
void updateDisplay(String statusText) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("TARS DISCRETE GAIT");
    display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
    
    display.setTextSize(2);
    display.setCursor(0, 22);
    display.print(customMessage);
    
    display.setTextSize(1);
    display.setCursor(0, 52);
    display.print("STATE: ");
    display.print(statusText);
    
    display.display();
}

// --- HTTP Route Handlers ---
void handleRoot() { server.send(200, "text/html", HTML_INTERFACE); }

void handleVector() {
    if (server.hasArg("x") && server.hasArg("y")) {
        targetX = server.arg("x").toFloat();
        targetY = server.arg("y").toFloat();
        server.send(200, "text/plain", "OK");
    }
}

void handleConfig() {
    if (server.hasArg("swing")) legSwingAngle  = server.arg("swing").toFloat();
    if (server.hasArg("push"))  bodyPushAngle   = server.arg("push").toFloat();
    if (server.hasArg("pitch")) pitchLiftAngle  = server.arg("pitch").toFloat();
    if (server.hasArg("stime")) swingDurationMs = server.arg("stime").toFloat();
    if (server.hasArg("ptime")) pushDurationMs  = server.arg("ptime").toFloat();
    if (server.hasArg("pause")) pauseDurationMs = server.arg("pause").toFloat();
    if (server.hasArg("l_off")) leftOffset     = server.arg("l_off").toFloat();
    if (server.hasArg("r_off")) rightOffset    = server.arg("r_off").toFloat();
    
    server.send(200, "text/plain", "OK");
}

void handleText() {
    if (server.hasArg("msg")) {
        customMessage = server.arg("msg");
        customMessage.toUpperCase();
        updateDisplay("TEXT UPDATED");
        server.send(200, "text/plain", "OK");
    }
}

// --- Discrete State Machine Gait Engine ---
void updatePhaseGaitEngine() {
    static unsigned long lastLoopTime = 0;
    unsigned long currentMillis = millis();
    
    if (currentMillis - lastLoopTime < 15) return; // 66 Hz execution loop
    lastLoopTime = currentMillis;

    // Filter incoming vector inputs for smooth transitions
    currentX += (targetX - currentX) * 0.15;
    currentY += (targetY - currentY) * 0.15;

    float normX = currentX / 100.0;
    float normY = currentY / 100.0;
    float magnitude = sqrt(normX * normX + normY * normY);

    // IDLE CHECK: If joystick is neutral, gently reset servos to zero trim
    if (magnitude < 0.08) {
        currentPhase = PHASE_IDLE;
        currentLeftAngle  += (leftOffset - currentLeftAngle) * 0.1;
        currentRightAngle += (rightOffset - currentRightAngle) * 0.1;
        
        servoLeft.write((int)currentLeftAngle);
        servoRight.write((int)currentRightAngle);
        return;
    }

    unsigned long elapsedTime = currentMillis - phaseStartTime;

    float targetLeft = leftOffset;
    float targetRight = rightOffset;

    // Execute state machine based on directional vector
    if (abs(normY) >= abs(normX) - 0.1) {
        // --- INCHING GAIT ENGINE (FORWARD / REVERSE) ---
        float dirSign = (normY >= 0.0) ? 1.0 : -1.0;
        float scale = abs(normY);

        switch (currentPhase) {
            case PHASE_IDLE:
                currentPhase = PHASE_SWING_LEGS_FORWARD;
                phaseStartTime = currentMillis;
                updateDisplay("SWING LEGS");
                break;

            case PHASE_SWING_LEGS_FORWARD:
                // STAGE 1: Both legs swing forward while main body tilts backward to break friction
                targetLeft  = leftOffset  + (dirSign * legSwingAngle * scale) + (dirSign * pitchLiftAngle);
                targetRight = rightOffset + (dirSign * legSwingAngle * scale) + (dirSign * pitchLiftAngle);

                if (elapsedTime >= swingDurationMs) {
                    currentPhase = PHASE_PLANT_LEGS;
                    phaseStartTime = currentMillis;
                    updateDisplay("PLANT LEGS");
                }
                break;

            case PHASE_PLANT_LEGS:
                // TRANSITION: Settle leg contact with the floor
                targetLeft  = leftOffset  + (dirSign * legSwingAngle * scale);
                targetRight = rightOffset + (dirSign * legSwingAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_PUSH_BODY_FORWARD;
                    phaseStartTime = currentMillis;
                    updateDisplay("PUSH BODY");
                }
                break;

            case PHASE_PUSH_BODY_FORWARD:
                // STAGE 2: Both legs rotate backward, anchoring on floor and pushing main body forward
                targetLeft  = leftOffset  - (dirSign * bodyPushAngle * scale) - (dirSign * pitchLiftAngle);
                targetRight = rightOffset - (dirSign * bodyPushAngle * scale) - (dirSign * pitchLiftAngle);

                if (elapsedTime >= pushDurationMs) {
                    currentPhase = PHASE_PLANT_BODY;
                    phaseStartTime = currentMillis;
                    updateDisplay("PLANT BODY");
                }
                break;

            case PHASE_PLANT_BODY:
                // TRANSITION: Transfer weight back to center body to unweight legs
                targetLeft  = leftOffset  - (dirSign * bodyPushAngle * scale);
                targetRight = rightOffset - (dirSign * bodyPushAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_SWING_LEGS_FORWARD;
                    phaseStartTime = currentMillis;
                    updateDisplay("SWING LEGS");
                }
                break;
        }
    } else {
        // --- AXIAL SCISSORING ENGINE (TURNING LEFT / RIGHT) ---
        float turnSign = (normX >= 0.0) ? 1.0 : -1.0;
        float scale = abs(normX);

        switch (currentPhase) {
            case PHASE_IDLE:
                currentPhase = PHASE_SWING_LEGS_FORWARD;
                phaseStartTime = currentMillis;
                updateDisplay("PIVOT STRIKE");
                break;

            case PHASE_SWING_LEGS_FORWARD:
                // Left leg moves forward, Right leg moves backward
                targetLeft  = leftOffset  + (turnSign * legSwingAngle * scale);
                targetRight = rightOffset - (turnSign * legSwingAngle * scale);

                if (elapsedTime >= swingDurationMs) {
                    currentPhase = PHASE_PLANT_LEGS;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_LEGS:
                targetLeft  = leftOffset  + (turnSign * legSwingAngle * scale);
                targetRight = rightOffset - (turnSign * legSwingAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_PUSH_BODY_FORWARD;
                    phaseStartTime = currentMillis;
                    updateDisplay("PIVOT REVERSE");
                }
                break;

            case PHASE_PUSH_BODY_FORWARD:
                // Reverse scissor directions to spin chassis
                targetLeft  = leftOffset  - (turnSign * bodyPushAngle * scale);
                targetRight = rightOffset + (turnSign * bodyPushAngle * scale);

                if (elapsedTime >= pushDurationMs) {
                    currentPhase = PHASE_PLANT_BODY;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_BODY:
                targetLeft  = leftOffset  - (turnSign * bodyPushAngle * scale);
                targetRight = rightOffset + (turnSign * bodyPushAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_SWING_LEGS_FORWARD;
                    phaseStartTime = currentMillis;
                    updateDisplay("PIVOT STRIKE");
                }
                break;
        }
    }

    if (invertRightServo) {
        targetRight = rightOffset - (targetRight - rightOffset);
    }

    // Exponential Moving Average Interpolation for Servo Angles (Removes hard mechanical shocks)
    currentLeftAngle  += (targetLeft  - currentLeftAngle)  * servoSmoothFactor;
    currentRightAngle += (targetRight - currentRightAngle) * servoSmoothFactor;

    // Write signals safely constrained to hardware limits
    servoLeft.write((int)constrain(currentLeftAngle, 10.0, 170.0));
    servoRight.write((int)constrain(currentRightAngle, 10.0, 170.0));
}

void setup() {
    Serial.begin(115200);

    // Initialize OLED Display
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println("OLED init failed");
        for(;;);
    }

    // Connect to WiFi Network
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

    // Initialize Servo Hardware
    servoLeft.attach(SERVO_LEFT_PIN);
    servoRight.attach(SERVO_RIGHT_PIN);
    servoLeft.write((int)leftOffset);
    servoRight.write((int)rightOffset);

    // Bind HTTP Web Server Routes
    server.on("/", handleRoot);
    server.on("/vector", handleVector);
    server.on("/config", handleConfig);
    server.on("/text", handleText);
    server.begin();
}

void loop() {
    server.handleClient();
    updatePhaseGaitEngine();
}
