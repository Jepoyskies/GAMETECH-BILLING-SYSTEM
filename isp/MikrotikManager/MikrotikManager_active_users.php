<?php
include 'header.php';

// === DATABASE SETTINGS ===
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
        $this->host = $host;
        $this->username = $username;
        $this->password = $password;
        $this->port = $port;
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
        if (!isset($this->ssh_connection) || !$this->ssh_connection) {
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
     * Very simple parser for "terse" output:
     * Example line:
     *  0 name=client1 service=pppoe address=10.0.0.10 uptime=1h5m ...
     */
    private function parseTerseOutput($raw) {
        $sessions = [];
        $lines = preg_split('/\r\n|\r|\n/', trim($raw));
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, 'Flags:') === 0) continue;

            // Remove leading index (e.g. "0 " or " 1 ")
            $line = preg_replace('/^[0-9]+\s+/', '', $line);

            $parts = preg_split('/\s+/', $line);
            $row = [];
            foreach ($parts as $part) {
                if (strpos($part, '=') === false) continue;
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

// === DATABASE CONNECTION ===
try {
    $pdo = new PDO(
        "mysql:host=$dbHost;dbname=$dbName;charset=utf8mb4",
        $dbUser,
        $dbPass,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (PDOException $e) {
    die("Database connection failed: " . $e->getMessage());
}

// === FETCH DEVICES ===
try {
    $stmt = $pdo->query("SELECT device_name, ip_address, api_username, api_password, api_port FROM mikrotik_devices");
    $devices = $stmt->fetchAll();
    if (!$devices) {
        $devicesError = "No MikroTik devices found in the database.";
    }
} catch (PDOException $e) {
    $devicesError = "Error fetching devices: " . $e->getMessage();
}

// === COLLECT ACTIVE USERS FROM ALL DEVICES ===
$allActive = [];  // each row: device_name, name, address, uptime, service
$errors = [];

if (empty($devicesError)) {
    foreach ($devices as $device) {
        $host = $device['ip_address'];
        $user = $device['api_username'];   // SSH username in your table
        $pass = $device['api_password'];   // SSH password
        $port = $device['api_port'] ?: 22; // assume SSH port stored here
        $deviceName = $device['device_name'];

        try {
            $mtik = new MikroTikManager($host, $user, $pass, $port);
            $sessions = $mtik->getPppActive();
            foreach ($sessions as $s) {
                $allActive[] = [
                    'device'  => $deviceName,
                    'name'    => $s['name']    ?? '',
                    'address' => $s['address'] ?? '',
                    'uptime'  => $s['uptime']  ?? '',
                    'service' => $s['service'] ?? '',
                ];
            }
        } catch (Exception $ex) {
            $errors[] = "Device {$deviceName} ({$host}): " . $ex->getMessage();
        }
    }
}
?>

