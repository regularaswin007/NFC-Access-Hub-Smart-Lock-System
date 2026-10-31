/*
 * PN532 NFC RFID Module with ESP32 WROOM32
 * Firebase Integration for Access Control System
 * with MD5 Hashing and Registration Mode
 */

#include <Wire.h>
#include <PN532_I2C.h>
#include <PN532.h>
#include <NfcAdapter.h>
#include <WiFi.h>
#include <FirebaseESP32.h>
#include <time.h>
#include <MD5Builder.h>

// Define I2C pins for ESP32
#define SDA_PIN 21
#define SCL_PIN 22

// Built-in LED pin (usually GPIO 2 on most ESP32 boards)
#define BUILTIN_LED 2

// 🔹 Wi-Fi Credentials (Replace with your actual credentials or use secrets.h)
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 🔹 Firebase Configuration (Replace with your actual database host and secret)
FirebaseConfig config;
FirebaseAuth auth;
FirebaseData firebaseData;

// NTP Server settings for Chennai, India (UTC+5:30)
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 19800;    // 5 hours and 30 minutes in seconds (5*3600 + 30*60)
const int daylightOffset_sec = 0;    // India doesn't observe Daylight Saving Time

// WiFi connection timeout
const unsigned long WIFI_TIMEOUT_MS = 20000; // 20 seconds

// NFC setup
PN532_I2C pn532_i2c(Wire);
NfcAdapter nfc = NfcAdapter(pn532_i2c);

// Variable to store the last read tag UID to prevent duplicate logs
String lastTagUID = "";
unsigned long lastTagReadTime = 0;
const unsigned long TAG_READ_COOLDOWN = 3000; // 3 seconds cooldown between reads of the same tag

// Lock state tracking
bool doorLocked = true; // Start with door locked

// Registration mode variables
bool registrationMode = false;
unsigned long registrationModeStartTime = 0;
const unsigned long REGISTRATION_TIMEOUT = 30000; // 30 seconds timeout
unsigned long lastBlinkTime = 0;
const unsigned long BLINK_INTERVAL = 500; // 500ms blink interval
bool ledState = false;

// Function declarations
bool connectToWiFi();
String getFormattedTime();
void logToFirebase(String tagUID, String status, String reason = "");
String getTagUID(NfcTag &tag);
String hashUID(String uid);
bool isTagAuthorized(String tagUID);
bool isAccessTimeValid(String tagUID);
bool validateAccess(String tagUID);
void checkRemoteCommands();
void startRegistrationMode();
void stopRegistrationMode();
void registerNewTag(String tagUID, String hashedUID);

void setup() {
  Serial.begin(115200);
  Serial.println("\n\n--- NFC Lock System Starting ---");
  
  // Configure built-in LED
  pinMode(BUILTIN_LED, OUTPUT);
  digitalWrite(BUILTIN_LED, LOW); // Start with LED off (system in locked state)
  Serial.println("Built-in LED configured for lock status indication");
  
  // Initialize I2C with specific pins for ESP32
  Wire.begin(SDA_PIN, SCL_PIN);
  
  // Initialize WiFi with timeout handling
  if (!connectToWiFi()) {
    Serial.println("WiFi connection failed! Restarting...");
    delay(3000);
    ESP.restart();
  }
  
  // Configure time
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Time synchronized with NTP server");
  
  // Firebase initialization with improved error handling
  Serial.println("Starting Firebase initialization...");
  
  config.host = "YOUR_FIREBASE_HOST.firebaseio.com"; // Replace with your actual Firebase host
  config.signer.tokens.legacy_token = "YOUR_FIREBASE_DATABASE_SECRET"; // Replace with your actual database secret
  
  Serial.println("Firebase config set, beginning connection...");
  Firebase.begin(&config, &auth);
  Serial.println("Firebase.begin completed");
  
  Firebase.reconnectWiFi(true);
  Serial.println("WiFi reconnection enabled");
  
  // Set database read timeout
  Firebase.setReadTimeout(firebaseData, 1000 * 60);
  // Set database write size limit
  Firebase.setwriteSizeLimit(firebaseData, "tiny");
  
  Serial.println("Firebase initialized successfully!");
  
  // Initialize NFC
  Serial.println("Initializing NFC reader...");
  nfc.begin();
  Serial.println("NFC reader initialized. Ready to scan tags.");
  
  // Update the system status to show we're online
  FirebaseJson statusJson;
  statusJson.set("LockStatus", doorLocked ? "Locked" : "Unlocked");
  statusJson.set("Online", true);
  statusJson.set("LastBoot", getFormattedTime());
  statusJson.set("RegistrationMode", false);
  
  if (Firebase.updateNode(firebaseData, "/SystemStatus", statusJson)) {
    Serial.println("System status updated successfully");
  } else {
    Serial.println("Failed to update system status: " + firebaseData.errorReason());
  }
  
  Serial.println("System ready! Door is LOCKED");
}

void loop() {
  // Check if registration mode timed out
  if (registrationMode && (millis() - registrationModeStartTime > REGISTRATION_TIMEOUT)) {
    stopRegistrationMode();
  }
  
  // Handle LED blinking in registration mode
  if (registrationMode && (millis() - lastBlinkTime > BLINK_INTERVAL)) {
    lastBlinkTime = millis();
    ledState = !ledState;
    digitalWrite(BUILTIN_LED, ledState);
  }
  
  Serial.println("\nScan an NFC tag");
  
  // Check if a tag is present
  if (nfc.tagPresent()) {
    Serial.println("Tag detected!");
    
    // Read the tag
    NfcTag tag = nfc.read();
    
    // Get the UID as a string
    String tagUID = getTagUID(tag);
    String hashedUID = hashUID(tagUID);
    
    // Print tag info
    Serial.println("Tag Type: " + tag.getTagType());
    Serial.println("UID: " + tagUID);
    Serial.println("Hashed UID: " + hashedUID);
    
    // Check if this is a new tag or if enough time has passed since last read
    unsigned long currentTime = millis();
    if (tagUID != lastTagUID || (currentTime - lastTagReadTime) > TAG_READ_COOLDOWN) {
      // If in registration mode, register this tag
      if (registrationMode) {
        registerNewTag(tagUID, hashedUID);
        stopRegistrationMode();
      } 
      // Normal operation mode
      else {
        // Validate access
        if (validateAccess(tagUID)) {
          // Toggle lock state
          doorLocked = !doorLocked;
          
          // Update LED based on lock state
          digitalWrite(BUILTIN_LED, !doorLocked); // LED ON when unlocked, OFF when locked
          
          // Log the access and action
          logToFirebase(tagUID, doorLocked ? "LOCKED" : "UNLOCKED");
          
          // Print status to serial
          Serial.print("Door is now ");
          Serial.println(doorLocked ? "LOCKED" : "UNLOCKED");
        }
      }
      
      // Update last tag info regardless of authorization
      lastTagUID = tagUID;
      lastTagReadTime = currentTime;
    } else {
      Serial.println("Skipping duplicate tag read");
    }
  }
  
  // Check for remote commands
  checkRemoteCommands();
  
  // Small delay to prevent excessive polling
  delay(500);
}

// Function to convert UID to MD5 hash
String hashUID(String uid) {
  MD5Builder md5;
  md5.begin();
  md5.add(uid);
  md5.calculate();
  return md5.toString();
}

bool connectToWiFi() {
  unsigned long startAttemptTime = millis();
  
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  // Keep trying to connect with a timeout
  while (WiFi.status() != WL_CONNECTED && 
         millis() - startAttemptTime < WIFI_TIMEOUT_MS) {
    Serial.print(".");
    delay(500);
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  
  Serial.println("\nConnected to WiFi!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  return true;
}

String getFormattedTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    return "1970-01-01_00-00-00"; // Return a default date instead of millis
  }
  
  char timeStringBuff[30];
  strftime(timeStringBuff, sizeof(timeStringBuff), "%Y-%m-%d_%H-%M-%S", &timeinfo);
  return String(timeStringBuff);
}

// Function to check if a tag is authorized
bool isTagAuthorized(String tagUID) {
  Serial.print("Checking authorization for tag: ");
  Serial.println(tagUID);
  
  // Generate MD5 hash of the UID
  String hashedUID = hashUID(tagUID);
  Serial.print("Hashed UID: ");
  Serial.println(hashedUID);
  
  // Check for authorization using hash
  String path = "/AuthorizedUsers/" + hashedUID;
  
  if (Firebase.getBool(firebaseData, path)) {
    Serial.println("Found as boolean value");
    return firebaseData.boolData();
  } else if (Firebase.getJSON(firebaseData, path)) {
    Serial.println("Found as JSON object (user with details)");
    return true;
  } else {
    Serial.print("Firebase error checking tag: ");
    Serial.println(firebaseData.errorReason());
    return false;
  }
}

// Function to get user details including time restrictions
bool isAccessTimeValid(String tagUID) {
  // Generate MD5 hash of the UID
  String hashedUID = hashUID(tagUID);
  String path = "/AuthorizedUsers/" + hashedUID;
  
  if (Firebase.getJSON(firebaseData, path)) {
    FirebaseJson json;
    json = firebaseData.jsonObject();
    FirebaseJsonData validFrom;
    FirebaseJsonData validUntil;
    
    // Get valid time range if it exists
    json.get(validFrom, "ValidFrom");
    json.get(validUntil, "ValidUntil");
    
    if (validFrom.success && validUntil.success) {
      // Get current time
      struct tm timeinfo;
      if (!getLocalTime(&timeinfo)) {
        Serial.println("Failed to obtain time - allowing access");
        return true; // If we can't get time, default to allowing access
      }
      
      // Convert current time to timestamp for comparison
      time_t now = mktime(&timeinfo);
      
      // Parse the stored timestamps (format: "YYYY-MM-DD_HH-MM-SS")
      struct tm tmFrom = {0};
      struct tm tmUntil = {0};
      
      // Parse validFrom
      String fromStr = validFrom.stringValue;
      fromStr.replace("_", " ");
      fromStr.replace("-", ":");
      
      // Parse validUntil
      String untilStr = validUntil.stringValue;
      untilStr.replace("_", " ");
      untilStr.replace("-", ":");
      
      // Parse the time strings manually
      int yearFrom, monthFrom, dayFrom, hourFrom, minFrom, secFrom;
      int yearUntil, monthUntil, dayUntil, hourUntil, minUntil, secUntil;
      
      sscanf(fromStr.c_str(), "%d:%d:%d %d:%d:%d", &yearFrom, &monthFrom, &dayFrom, &hourFrom, &minFrom, &secFrom);
      sscanf(untilStr.c_str(), "%d:%d:%d %d:%d:%d", &yearUntil, &monthUntil, &dayUntil, &hourUntil, &minUntil, &secUntil);
      
      // Set up tm structures
      tmFrom.tm_year = yearFrom - 1900;
      tmFrom.tm_mon = monthFrom - 1;
      tmFrom.tm_mday = dayFrom;
      tmFrom.tm_hour = hourFrom;
      tmFrom.tm_min = minFrom;
      tmFrom.tm_sec = secFrom;
      
      tmUntil.tm_year = yearUntil - 1900;
      tmUntil.tm_mon = monthUntil - 1;
      tmUntil.tm_mday = dayUntil;
      tmUntil.tm_hour = hourUntil;
      tmUntil.tm_min = minUntil;
      tmUntil.tm_sec = secUntil;
      
      // Convert to time_t
      time_t fromTime = mktime(&tmFrom);
      time_t untilTime = mktime(&tmUntil);
      
      Serial.print("Current time: ");
      Serial.println(ctime(&now));
      Serial.print("Valid from: ");
      Serial.println(ctime(&fromTime));
      Serial.print("Valid until: ");
      Serial.println(ctime(&untilTime));
      
      // Compare times
      bool isValid = (now >= fromTime && now <= untilTime);
      Serial.print("Time-based access: ");
      Serial.println(isValid ? "VALID" : "INVALID");
      return isValid;
    }
    
    Serial.println("No time restrictions found, access valid");
    return true; // No time restrictions
  } 
  
  Serial.println("Error getting user details or user not found");
  return false; // Error or user not found
}

// Main validation function
bool validateAccess(String tagUID) {
  // First check if the tag is authorized
  if (!isTagAuthorized(tagUID)) {
    logToFirebase(tagUID, "UNAUTHORIZED", "TAG_NOT_AUTHORIZED");
    Serial.println("Access denied: Tag not authorized");
    return false;
  }
  
  // Then check if the current time is within allowed period
  if (!isAccessTimeValid(tagUID)) {
    logToFirebase(tagUID, "UNAUTHORIZED", "OUTSIDE_VALID_PERIOD");
    Serial.println("Access denied: Outside valid time period");
    return false;
  }
  
  // If we got here, access is granted
  logToFirebase(tagUID, "AUTHORIZED");
  Serial.println("Access granted!");
  return true;
}

// Updated logToFirebase function with reason parameter
void logToFirebase(String tagUID, String status, String reason) {
  Serial.println("Starting Firebase log function...");
  
  // Get current timestamp
  Serial.println("Getting formatted time...");
  String timestamp = getFormattedTime();
  Serial.print("Current time: ");
  Serial.println(timestamp);
  
  // Create a more organized path structure
  String path = "/AccessLogs/";
  
  // JSON object for log entry
  Serial.println("Preparing JSON data...");
  FirebaseJson json;
  json.set("UID", tagUID);
  json.set("Status", status);
  json.set("Timestamp", timestamp);
  if (reason != "") {
    json.set("Reason", reason);
  }
  Serial.println("JSON prepared successfully");
  
  // Push data to Firebase with error checking
  Serial.print("Sending log to Firebase... ");
  if (Firebase.pushJSON(firebaseData, path, json)) {
    Serial.println("SUCCESS");
    Serial.print("Path: ");
    Serial.println(firebaseData.dataPath());
    Serial.print("Push name: ");
    Serial.println(firebaseData.pushName());
  } else {
    Serial.println("FAILED");
    Serial.print("REASON: ");
    Serial.println(firebaseData.errorReason());
    
    // Handle specific error conditions
    if (firebaseData.errorReason() == "connection lost" || 
        firebaseData.errorReason().indexOf("WiFi") >= 0) {
      Serial.println("Reconnecting to WiFi...");
      connectToWiFi();
    }
  }
  
  // Update the system status
  FirebaseJson statusJson;
  statusJson.set("LockStatus", doorLocked ? "Locked" : "Unlocked");
  statusJson.set("Online", true);
  statusJson.set("LastAccess/UID", tagUID);
  statusJson.set("LastAccess/Status", status);
  statusJson.set("LastAccess/Timestamp", timestamp);
  
  Firebase.updateNode(firebaseData, "/SystemStatus", statusJson);
}

// Function to check for remote commands
void checkRemoteCommands() {
  if (Firebase.getJSON(firebaseData, "/Commands")) {
    FirebaseJson json = firebaseData.jsonObject();
    FirebaseJsonData actionData;
    FirebaseJsonData timestampData;
    
    json.get(actionData, "action");
    json.get(timestampData, "timestamp");
    
    if (actionData.success) {
      String action = actionData.stringValue;
      String timestamp = timestampData.success ? timestampData.stringValue : "";
      
      // Process commands
      if (action == "lock" && !doorLocked) {
        doorLocked = true;
        digitalWrite(BUILTIN_LED, LOW);
        Serial.println("Remote command: Door locked");
        
        // Clear the command
        Firebase.deleteNode(firebaseData, "/Commands");
        
        // Log the action
        logToFirebase("REMOTE", "LOCKED", "REMOTE_COMMAND");
      }
      else if (action == "unlock" && doorLocked) {
        doorLocked = false;
        digitalWrite(BUILTIN_LED, HIGH);
        Serial.println("Remote command: Door unlocked");
        
        // Clear the command
        Firebase.deleteNode(firebaseData, "/Commands");
        
        // Log the action
        logToFirebase("REMOTE", "UNLOCKED", "REMOTE_COMMAND");
      }
      else if (action == "restart") {
        Serial.println("Remote command: System restart");
        
        // Clear the command
        Firebase.deleteNode(firebaseData, "/Commands");
        
        // Log the action before restart
        logToFirebase("REMOTE", "RESTART", "REMOTE_COMMAND");
        
        delay(1000);
        ESP.restart();
      }
      else if (action == "register_mode") {
        Serial.println("Remote command: Start Registration Mode");
        
        // Clear the command
        Firebase.deleteNode(firebaseData, "/Commands");
        
        // Start registration mode
        startRegistrationMode();
      }
    }
  }
}

// Function to start registration mode
void startRegistrationMode() {
  registrationMode = true;
  registrationModeStartTime = millis();
  Serial.println("Registration mode ACTIVE for 30 seconds!");
  
  // Update system status in Firebase
  FirebaseJson statusJson;
  statusJson.set("RegistrationMode", true);
  Firebase.updateNode(firebaseData, "/SystemStatus", statusJson);
}

// Function to stop registration mode
void stopRegistrationMode() {
  registrationMode = false;
  digitalWrite(BUILTIN_LED, doorLocked ? LOW : HIGH); // Restore LED state
  Serial.println("Registration mode DEACTIVATED");
  
  // Update system status in Firebase
  FirebaseJson statusJson;
  statusJson.set("RegistrationMode", false);
  Firebase.updateNode(firebaseData, "/SystemStatus", statusJson);
}

// Function to register a new tag
void registerNewTag(String tagUID, String hashedUID) {
  Serial.println("Registering new tag...");
  
  // Create user data
  FirebaseJson userData;
  userData.set("Name", "New Tag");
  userData.set("OriginalUID", tagUID);
  userData.set("ValidFrom", getFormattedTime());
  userData.set("ValidUntil", "2099-12-31_23-59-59");
  userData.set("AddedOn", getFormattedTime());
  
  // Save to Firebase
  if (Firebase.setJSON(firebaseData, "/AuthorizedUsers/" + hashedUID, userData)) {
    Serial.println("Tag registered successfully!");
    logToFirebase(tagUID, "REGISTERED", "NEW_TAG_REGISTRATION");
  } else {
    Serial.print("Error registering tag: ");
    Serial.println(firebaseData.errorReason());
  }
}

// Helper function to get tag UID as a string
String getTagUID(NfcTag &tag) {
  // Simply use the built-in method to get the UID as a string
  return tag.getUidString();
}