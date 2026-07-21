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
const char* WIFI_SSID     = "Aashi pawar";
const char* WIFI_PASSWORD = "8221946003";

// --- Servo Hardware Trims & Direction Inversion ---
float leftOffset        = 90.0;
float rightOffset       = 90.0;
bool invertRightServo   = false;

// --- Gait Parameters (Fully Tunable via Web UI) ---
float legSwingAngle     = 25.0; // Degrees legs swing forward
float bodyPushAngle      = 25.0; // Degrees legs push backward to move body
float pitchLiftAngle     = 12.0; // Dynamic pitch lift to unweight chassis
float swingDurationMs    = 220.0; // Leg swing phase duration (ms)
float pushDurationMs     = 280.0; // Body push phase duration (ms)
float pauseDurationMs    = 80.0;  // Transition pause duration (ms)
float servoSmoothFactor  = 0.25;  // Motion smoothing interpolation factor

// --- Control Vector States ---
float targetX = 0.0, targetY = 0.0;
float currentX = 0.0, currentY = 0.0;

// --- Output Servo Angles ---
float currentLeftAngle  = 90.0;
float currentRightAngle = 90.0;

// --- Phase State Machine Definition ---
enum GaitPhase {
  PHASE_IDLE,
  PHASE_SWING_LEGS_FORWARD,
  PHASE_PLANT_LEGS,
  PHASE_PUSH_BODY_FORWARD,
  PHASE_PLANT_BODY
};

GaitPhase currentPhase = PHASE_IDLE;
unsigned long phaseStartTime = 0;

// --- Animated Moving & Wandering Eyes Engine Variables ---
unsigned long lastEyeFrame = 0;
unsigned long nextBlinkTime = 0;
bool isBlinking = false;
unsigned long blinkStartTime = 0;

// Random Look / Gaze Vectors
float currentGazeX = 0.0;
float currentGazeY = 0.0;
float targetGazeX = 0.0;
float targetGazeY = 0.0;
unsigned long nextGazeShiftTime = 0;

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
    <title>TARS Controller</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #121212; color: #E0E0E0; text-align: center; margin: 0; padding: 12px; }
        h1 { font-size: 22px; letter-spacing: 3px; color: #FFF; margin-bottom: 2px; }
        .subtitle { color: #888; font-size: 11px; margin-bottom: 12px; }
        .card { background: #1E1E1E; border-radius: 12px; padding: 12px; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); text-align: left; }
        .card h3 { text-align: center; margin-top: 0; color: #007AFF; font-size: 14px; letter-spacing: 1px; }
        
        #joystick-container { position: relative; width: 170px; height: 170px; background: #2A2A2A; border-radius: 50%; margin: 8px auto; touch-action: none; border: 2px solid #444; }
        #stick { position: absolute; width: 60px; height: 60px; background: #007AFF; border-radius: 50%; top: 55px; left: 55px; box-shadow: 0 4px 8px rgba(0,0,0,0.4); }
        
        .btn { background: #FF3B30; color: white; border: none; padding: 10px; font-size: 13px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 8px;}
        
        .slider-container { margin: 10px 0; }
        label { font-weight: bold; font-size: 11px; color: #AAA; display: block; margin-bottom: 3px; }
        .slider { -webkit-appearance: none; width: 100%; height: 8px; border-radius: 4px; background: #333; outline: none; }
        .slider::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: #007AFF; cursor: pointer; }
        .slider-highlight::-webkit-slider-thumb { background: #30D158; }
        .value-display { float: right; color: #007AFF; font-weight: bold; }
    </style>
</head>
<body>
    <h1>TARS</h1>
    <div class="subtitle">KINEMATIC CONTROL SYSTEM</div>

    <div class="card" style="text-align: center;">
        <h3>JOYSTICK CONTROL</h3>
        <div id="joystick-container">
            <div id="stick"></div>
        </div>
        <button class="btn" onclick="resetJoystick()">EMERGENCY STOP</button>
    </div>

    <div class="card">
        <h3>GAIT & TIMING TUNER</h3>
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
        <h3>SERVO TRIM & INVERSION</h3>
        <div class="slider-container">
            <label>LEFT LEG TRIM <span id="leftVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="leftSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>RIGHT LEG TRIM <span id="rightVal" class="value-display">90&deg;</span></label>
            <input type="range" min="50" max="130" value="90" class="slider" id="rightSlider" oninput="updateConfig()">
        </div>
        <div class="slider-container">
            <label>INVERT RIGHT SERVO DIRECTION</label>
            <input type="checkbox" id="invRight" onchange="updateConfig()">
        </div>
    </div>

    <script>
        const container = document.getElementById('joystick-container');
        const stick = document.getElementById('stick');
        let active = false, lastX = 0, lastY = 0;

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
            let inv_r = document.getElementById('invRight').checked ? 1 : 0;
            
            document.getElementById('swingVal').innerText = swing + '°';
            document.getElementById('pushVal').innerText = push + '°';
            document.getElementById('pitchVal').innerText = pitch + '°';
            document.getElementById('swingTimeVal').innerText = stime + 'ms';
            document.getElementById('pushTimeVal').innerText = ptime + 'ms';
            document.getElementById('pauseVal').innerText = pause + 'ms';
            document.getElementById('leftVal').innerText = l_off + '°';
            document.getElementById('rightVal').innerText = r_off + '°';
            
            fetch(`/config?swing=${swing}&push=${push}&pitch=${pitch}&stime=${stime}&ptime=${ptime}&pause=${pause}&l_off=${l_off}&r_off=${r_off}&inv_r=${inv_r}`);
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

// --- OLED Animated Moving & Blinking Eyes Engine ---
void updateAnimatedEyes() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastEyeFrame < 33) return; // Smooth 30 FPS Render Rate
    lastEyeFrame = currentMillis;

    // 1. Random Blinking Mechanics
    if (!isBlinking && currentMillis >= nextBlinkTime) {
        isBlinking = true;
        blinkStartTime = currentMillis;
        nextBlinkTime = currentMillis + random(2000, 5500); // Blink every 2-5.5 sec
    }

    int eyeHeight = 34; // Fully open eye height
    if (isBlinking) {
        if (currentMillis - blinkStartTime < 130) {
            eyeHeight = 3; // Fully closed flat line
        } else {
            isBlinking = false;
        }
    }

    // 2. Dynamic Eye Wandering / Joystick Override Logic
    float joystickMag = sqrt(currentX * currentX + currentY * currentY);

    if (joystickMag > 10.0) {
        // Joystick actively overrides eye direction
        targetGazeX = (currentX / 100.0) * 14.0;
        targetGazeY = -(currentY / 100.0) * 10.0;
    } else {
        // Robot idle state: Randomly shift gaze left, right, up, down, or center
        if (currentMillis >= nextGazeShiftTime) {
            nextGazeShiftTime = currentMillis + random(1200, 3800);
            
            int gazeOption = random(0, 6);
            switch(gazeOption) {
                case 0: targetGazeX = -14.0; targetGazeY = 0.0;  break; // Look Far Left
                case 1: targetGazeX = 14.0;  targetGazeY = 0.0;  break; // Look Far Right
                case 2: targetGazeX = 0.0;   targetGazeY = 0.0;  break; // Look Center Forward
                case 3: targetGazeX = -10.0; targetGazeY = -6.0; break; // Look Up-Left
                case 4: targetGazeX = 10.0;  targetGazeY = -6.0; break; // Look Up-Right
                case 5: targetGazeX = 0.0;   targetGazeY = 6.0;  break; // Look Down
            }
        }
    }

    // Smoothly ease/LERP current gaze coordinates towards target position
    currentGazeX += (targetGazeX - currentGazeX) * 0.16;
    currentGazeY += (targetGazeY - currentGazeY) * 0.16;

    display.clearDisplay();

    // Eye Dimensions & Base Centered Locations
    int eyeWidth = 28;
    int baseLeftEyeX = 36;
    int baseRightEyeX = 92;
    int baseEyeY = 32;

    int drawLeftX  = baseLeftEyeX  + (int)currentGazeX;
    int drawRightX = baseRightEyeX + (int)currentGazeX;
    int drawY      = baseEyeY      + (int)currentGazeY;

    // Render Expressive Rectangular Eyes with Rounded Corners
    display.fillRoundRect(drawLeftX - eyeWidth/2,  drawY - eyeHeight/2, eyeWidth, eyeHeight, 6, SSD1306_WHITE);
    display.fillRoundRect(drawRightX - eyeWidth/2, drawY - eyeHeight/2, eyeWidth, eyeHeight, 6, SSD1306_WHITE);

    // Expressive Eyebrow Accents based on gaze direction
    if (targetGazeY < -3.0 || currentY > 20) { // Looking up or forward
        display.drawLine(drawLeftX - 12, drawY - eyeHeight/2 - 5, drawLeftX + 12, drawY - eyeHeight/2 - 2, SSD1306_WHITE);
        display.drawLine(drawRightX - 12, drawY - eyeHeight/2 - 2, drawRightX + 12, drawY - eyeHeight/2 - 5, SSD1306_WHITE);
    } else if (abs(currentGazeX) > 8.0 || abs(currentX) > 20) { // Looking left or right
        display.drawLine(drawLeftX - 10, drawY - eyeHeight/2 - 4, drawLeftX + 10, drawY - eyeHeight/2 - 4, SSD1306_WHITE);
        display.drawLine(drawRightX - 10, drawY - eyeHeight/2 - 4, drawRightX + 10, drawY - eyeHeight/2 - 4, SSD1306_WHITE);
    }

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
    if (server.hasArg("inv_r")) invertRightServo = (server.arg("inv_r").toInt() == 1);
    
    server.send(200, "text/plain", "OK");
}

// --- Corrected 3-Block TARS Kinematic Phase Engine ---
void updatePhaseGaitEngine() {
    static unsigned long lastLoopTime = 0;
    unsigned long currentMillis = millis();
    
    if (currentMillis - lastLoopTime < 15) return; // 66 Hz Loop
    lastLoopTime = currentMillis;

    // Filter incoming inputs using Exponential Moving Average
    currentX += (targetX - currentX) * 0.15;
    currentY += (targetY - currentY) * 0.15;

    float normX = currentX / 100.0;
    float normY = currentY / 100.0;
    float magnitude = sqrt(normX * normX + normY * normY);

    // IDLE CHECK: When Joystick is centered, reset servos to neutral trim
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

    if (abs(normY) >= abs(normX) - 0.1) {
        // --- FORWARD / BACKWARD INCHING GAIT ---
        float dirSign = (normY >= 0.0) ? 1.0 : -1.0;
        float scale = abs(normY);

        switch (currentPhase) {
            case PHASE_IDLE:
                currentPhase = PHASE_SWING_LEGS_FORWARD;
                phaseStartTime = currentMillis;
                break;

            case PHASE_SWING_LEGS_FORWARD:
                targetLeft  = leftOffset  + (dirSign * legSwingAngle * scale) + (dirSign * pitchLiftAngle);
                targetRight = rightOffset - (dirSign * legSwingAngle * scale) - (dirSign * pitchLiftAngle);

                if (elapsedTime >= swingDurationMs) {
                    currentPhase = PHASE_PLANT_LEGS;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_LEGS:
                targetLeft  = leftOffset  + (dirSign * legSwingAngle * scale);
                targetRight = rightOffset - (dirSign * legSwingAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_PUSH_BODY_FORWARD;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PUSH_BODY_FORWARD:
                targetLeft  = leftOffset  - (dirSign * bodyPushAngle * scale) - (dirSign * pitchLiftAngle);
                targetRight = rightOffset + (dirSign * bodyPushAngle * scale) + (dirSign * pitchLiftAngle);

                if (elapsedTime >= pushDurationMs) {
                    currentPhase = PHASE_PLANT_BODY;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_BODY:
                targetLeft  = leftOffset  - (dirSign * bodyPushAngle * scale);
                targetRight = rightOffset + (dirSign * bodyPushAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_SWING_LEGS_FORWARD;
                    phaseStartTime = currentMillis;
                }
                break;
        }
    } else {
        // --- LEFT / RIGHT TURNING (SCISSORING) GAIT ---
        float turnSign = (normX >= 0.0) ? 1.0 : -1.0;
        float scale = abs(normX);

        switch (currentPhase) {
            case PHASE_IDLE:
                currentPhase = PHASE_SWING_LEGS_FORWARD;
                phaseStartTime = currentMillis;
                break;

            case PHASE_SWING_LEGS_FORWARD:
                targetLeft  = leftOffset  + (turnSign * legSwingAngle * scale);
                targetRight = rightOffset + (turnSign * legSwingAngle * scale);

                if (elapsedTime >= swingDurationMs) {
                    currentPhase = PHASE_PLANT_LEGS;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_LEGS:
                targetLeft  = leftOffset  + (turnSign * legSwingAngle * scale);
                targetRight = rightOffset + (turnSign * legSwingAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_PUSH_BODY_FORWARD;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PUSH_BODY_FORWARD:
                targetLeft  = leftOffset  - (turnSign * bodyPushAngle * scale);
                targetRight = rightOffset - (turnSign * bodyPushAngle * scale);

                if (elapsedTime >= pushDurationMs) {
                    currentPhase = PHASE_PLANT_BODY;
                    phaseStartTime = currentMillis;
                }
                break;

            case PHASE_PLANT_BODY:
                targetLeft  = leftOffset  - (turnSign * bodyPushAngle * scale);
                targetRight = rightOffset - (turnSign * bodyPushAngle * scale);

                if (elapsedTime >= pauseDurationMs) {
                    currentPhase = PHASE_SWING_LEGS_FORWARD;
                    phaseStartTime = currentMillis;
                }
                break;
        }
    }

    if (invertRightServo) {
        targetRight = rightOffset - (targetRight - rightOffset);
    }

    currentLeftAngle  += (targetLeft  - currentLeftAngle)  * servoSmoothFactor;
    currentRightAngle += (targetRight - currentRightAngle) * servoSmoothFactor;

    servoLeft.write((int)constrain(currentLeftAngle, 10.0, 170.0));
    servoRight.write((int)constrain(currentRightAngle, 10.0, 170.0));
}

void setup() {
    Serial.begin(115200);

    // Initialize OLED Screen
    if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        Serial.println("OLED init failed");
        for(;;);
    }

    // Display Initial Connection Status
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 24);
    display.print("CONNECTING");
    display.display();

    // Connect to Wi-Fi Network
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        attempts++;
        if (attempts > 30) ESP.restart();
    }

    // Display "CONNECTED" Status for exactly 1 second
    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(12, 24);
    display.print("CONNECTED");
    display.display();
    delay(1000);

    // Attach Servos and set neutral stance
    servoLeft.attach(SERVO_LEFT_PIN);
    servoRight.attach(SERVO_RIGHT_PIN);
    servoLeft.write((int)leftOffset);
    servoRight.write((int)rightOffset);

    // Bind Web Server HTTP Handler Routes
    server.on("/", handleRoot);
    server.on("/vector", handleVector);
    server.on("/config", handleConfig);
    server.begin();

    nextBlinkTime = millis() + 2000;
    nextGazeShiftTime = millis() + 1500;
}

void loop() {
    server.handleClient();
    updatePhaseGaitEngine();
    updateAnimatedEyes();
}
