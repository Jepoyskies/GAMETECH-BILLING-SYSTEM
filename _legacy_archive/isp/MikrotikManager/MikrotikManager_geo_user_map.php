<?php
// MikroTik + Geo data loader for geo_user_map.php

// === DATABASE SETTINGS (PDO for Mikrotik devices) ===
$dbHost = 'localhost';
$dbName = 'gametech';
$dbUser = 'root';
$dbPass = '@Marille2012';

/**
 * MikroTik SSH Manager
 */
class MikroTikManager {
    private $host;
    private $username;
    private $password;
    private $port;
    private $ssh_connection;

    public function __construct($host, $username, $password, $port = 22) {
        $this->host     = $host;
        $this->username = $username;
        $this->password = $password;
        $this->port     = $port;
    }

    public function connect() {
        if (!function_exists('ssh2_connect')) {
            throw new Exception('SSH2 extension not installed.');
        }

        $connection = @ssh2_connect($this->host, $this->port);
        if (!$connection) {
            throw new Exception("Could not connect to MikroTik device: {$this->host}:{$this->port}");
        }

        $auth = @ssh2_auth_password($connection, $this->username, $this->password);
        if (!$auth) {
            throw new Exception("SSH authentication failed for user {$this->username} on {$this->host}");
        }

        $this->ssh_connection = $connection;
        return true;
    }

    public function disconnect() {
        $this->ssh_connection = null;
    }

    public function runSshCommand($command) {
        if (empty($this->ssh_connection)) {
            $this->connect();
        }

        $stream = @ssh2_exec($this->ssh_connection, $command);
        if (!$stream) {
            throw new Exception("Failed to execute command: $command");
        }

        stream_set_blocking($stream, true);
        $output = stream_get_contents($stream);
        fclose($stream);

        return $output;
    }

    /**
     * Get PPP active sessions via SSH.
     * Command: /ppp/active/print terse
     */
    public function getPppActive() {
        $cmd = "/ppp/active/print terse";
        $raw = $this->runSshCommand($cmd);
        return $this->parseTerseOutput($raw);
    }

    /**
     * Very simple parser for "terse" output.
     */
    private function parseTerseOutput($raw) {
        $sessions = [];
        $lines = preg_split('/\r\n|\r|\n/', trim($raw));

        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, 'Flags:') === 0) {
                continue;
            }

            // Remove leading index (e.g. "0 " or " 1 ")
            $line = preg_replace('/^[0-9]+\s+/', '', $line);

            $parts = preg_split('/\s+/', $line);
            $row   = [];

            foreach ($parts as $part) {
                if (strpos($part, '=') === false) {
                    continue;
                }
                [$k, $v] = explode('=', $part, 2);
                $row[$k] = $v;
            }

            if (!empty($row)) {
                $sessions[] = $row;
            }
        }

        return $sessions;
    }
}

// === DB CONNECTION (PDO) FOR MIKROTIK DEVICES ===
try {
    $pdo = new PDO(
        "mysql:host=$dbHost;dbname=$dbName;charset=utf8mb4",
        $dbUser,
        $dbPass,
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (PDOException $e) {
    die("Database connection failed: " . $e->getMessage());
}

// === FETCH DEVICES ===
$devices      = [];
$devicesError = '';

try {
    $stmt    = $pdo->query("SELECT device_name, ip_address, api_username, api_password, api_port FROM mikrotik_devices");
    $devices = $stmt->fetchAll();

    if (!$devices) {
        $devicesError = "No MikroTik devices found in the database.";
    }
} catch (PDOException $e) {
    $devicesError = "Error fetching devices: " . $e->getMessage();
}

// === COLLECT ACTIVE PPP USERS FROM ALL DEVICES ===
$activeUsernames = [];   // set of active usernames from Mikrotik
$errors          = [];

if (empty($devicesError)) {
    foreach ($devices as $device) {
        $mHost      = $device['ip_address'];
        $mUser      = $device['api_username'];   // SSH username
        $mPass      = $device['api_password'];   // SSH password
        $mPort      = $device['api_port'] ?: 22;
        $deviceName = $device['device_name'];

        try {
            $mtik     = new MikroTikManager($mHost, $mUser, $mPass, $mPort);
            $sessions = $mtik->getPppActive();

            foreach ($sessions as $s) {
                if (!empty($s['name'])) {
                    // Normalize username the same way you store it in DB
                    $uname = trim($s['name']);
                    $activeUsernames[$uname] = true;
                }
            }
        } catch (Exception $ex) {
            $errors[] = "Device {$deviceName} ({$mHost}): " . $ex->getMessage();
        }
    }
}

// === FETCH NAP BOXES & CUSTOMERS (WITH is_connected FLAG) ===

// database.php must define $host, $user, $pass, $db for mysqli
require __DIR__ . '/database.php';
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

try {
    $conn = new mysqli($host, $user, $pass, $db);
    $conn->set_charset('utf8mb4');

    // NAP boxes
    $sqlNap = "SELECT id, napbox_no, nap_latitude, nap_longitude, marker_color
               FROM napbox_mapping
               WHERE nap_latitude IS NOT NULL AND nap_longitude IS NOT NULL
                 AND nap_latitude <> '' AND nap_longitude <> ''";
    $stmtNap = $conn->prepare($sqlNap);
    $stmtNap->execute();
    $resultNap = $stmtNap->get_result();
    $napboxes  = $resultNap->fetch_all(MYSQLI_ASSOC);
    $stmtNap->close();

    // Customers
    $sqlCust = "SELECT id, full_name, username, latitude, longitude
                FROM customers
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND latitude <> '' AND longitude <> ''";
    $stmtCust = $conn->prepare($sqlCust);
    $stmtCust->execute();
    $resultCust = $stmtCust->get_result();
    $customers  = $resultCust->fetch_all(MYSQLI_ASSOC);
    $stmtCust->close();

    $conn->close();
} catch (Exception $e) {
    error_log("Geo Mixed Map DB Error: " . $e->getMessage());
    $napboxes  = [];
    $customers = [];
}

// === ADD is_connected FIELD TO CUSTOMERS BASED ON MIKROTIK ACTIVE USERS ===
foreach ($customers as &$c) {
    $u = isset($c['username']) ? trim($c['username']) : '';
    $c['is_connected'] = (!empty($u) && isset($activeUsernames[$u])) ? 1 : 0;
}
unset($c);

// Encode to JSON for JavaScript
$napboxesJson  = json_encode($napboxes, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
$customersJson = json_encode($customers, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
