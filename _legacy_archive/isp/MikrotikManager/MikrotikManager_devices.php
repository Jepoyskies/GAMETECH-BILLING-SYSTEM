<?php
/**
 * Remove PPPoE users from multiple MikroTik devices using credentials from database.
 */

// === DATABASE SETTINGS ===
$dbHost = 'localhost';
$dbName = 'gametech';
$dbUser = 'root';
$dbPass = '@Marille2012';

// === PPPoE User to remove ===
$pppoeUsernameToRemove = 'testuser'; // CHANGE THIS as needed

/**
 * MikroTik SSH Manager (no config file, uses direct credentials)
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

    public function deletePppoeUser($username) {
        $usernameEsc = escapeshellarg($username);
        $delCmd = "/ppp/secret/remove [find where name={$usernameEsc}]";
        return $this->runSshCommand($delCmd);
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
        die("No MikroTik devices found in the database.");
    }
} catch (PDOException $e) {
    die("Error fetching devices: " . $e->getMessage());
}

// === PROCESS EACH DEVICE ===
foreach ($devices as $device) {
    $host = $device['ip_address'];
    $user = $device['api_username'];
    $pass = $device['api_password'];
    $port = $device['api_port'];

  //  echo "Processing device: {$device['device_name']} ({$host}:{$port}) ... ";

    try {
        $mtik = new MikroTikManager($host, $user, $pass, $port);
        $output = $mtik->deletePppoeUser($pppoeUsernameToRemove);
 //       echo "User '{$pppoeUsernameToRemove}' deleted successfully.\n";
    } catch (Exception $ex) {
        echo "Failed: " . $ex->getMessage() . "\n";
    }
}
?>
