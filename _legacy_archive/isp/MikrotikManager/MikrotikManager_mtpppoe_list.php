<?php
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
        $this->port = $port ?: 22;
    }

    public function connect() {
        if (!function_exists('ssh2_connect')) {
            throw new Exception('SSH2 extension not installed.');
        }

        $connection = @ssh2_connect($this->host, $this->port);
        if (!$connection) {
            throw new Exception("Could not connect to MikroTik: {$this->host}:{$this->port}");
        }

        if (!@ssh2_auth_password($connection, $this->username, $this->password)) {
            throw new Exception("SSH authentication failed for {$this->username}@{$this->host}");
        }

        $this->ssh_connection = $connection;
        return true;
    }

    public function disconnect() {
        $this->ssh_connection = null;
    }

    private function ensureConnection() {
        if (!$this->ssh_connection) {
            $this->connect();
        }
    }

    // ✅ Improved command execution (captures stderr too)
    public function runSshCommand($command) {
        $this->ensureConnection();

        $stream = @ssh2_exec($this->ssh_connection, $command);
        if (!$stream) {
            throw new Exception("Failed to execute command: $command");
        }

        $errorStream = ssh2_fetch_stream($stream, SSH2_STREAM_STDERR);

        stream_set_blocking($stream, true);
        stream_set_blocking($errorStream, true);

        $output = stream_get_contents($stream);
        $error  = stream_get_contents($errorStream);

        fclose($stream);
        fclose($errorStream);

        if (!empty($error)) {
            throw new Exception("MikroTik error: " . trim($error));
        }

        return trim($output);
    }

    // ✅ CHECK if PPPoE user exists
    public function pppoeUserExists($username) {
        $usernameEsc = escapeshellarg($username);
        $cmd = "/ppp secret print terse where name={$usernameEsc}";
        $output = $this->runSshCommand($cmd);

        return !empty($output);
    }

    // ✅ ADD PPPoE USER
    public function addPppoeUser($username, $password, $profile) {
        $usernameEsc = escapeshellarg($username);
        $passwordEsc = escapeshellarg($password);
        $profileEsc  = escapeshellarg($profile);

        if ($this->pppoeUserExists($username)) {
            return false; // already exists
        }

        $cmd = "/ppp secret add name={$usernameEsc} password={$passwordEsc} profile={$profileEsc} service=pppoe";
        $this->runSshCommand($cmd);

        return $this->pppoeUserExists($username);
    }

    // ✅ UPDATE PPPoE USER
    public function updatePppoeUser($username, $profile, $password = null) {
        $usernameEsc = escapeshellarg($username);
        $profileEsc  = escapeshellarg($profile);

        if (!$this->pppoeUserExists($username)) {
            return false;
        }

        $setParts = ["profile={$profileEsc}"];

        if ($password !== null) {
            $setParts[] = "password=" . escapeshellarg($password);
        }

        $setString = implode(' ', $setParts);

        $cmd = "/ppp secret set [find where name={$usernameEsc}] {$setString}";
        $this->runSshCommand($cmd);

        return true;
    }

    // ✅ DELETE PPPoE USER
    public function deletePppoeUser($username) {
        $usernameEsc = escapeshellarg($username);

        if (!$this->pppoeUserExists($username)) {
            return false;
        }

        $cmd = "/ppp secret remove [find where name={$usernameEsc}]";
        $this->runSshCommand($cmd);

        return !$this->pppoeUserExists($username);
    }

    // ✅ GET USER INFO
    public function getPppoeUser($username) {
        $usernameEsc = escapeshellarg($username);
        $cmd = "/ppp secret print detail where name={$usernameEsc}";
        $output = $this->runSshCommand($cmd);

        if (empty($output)) {
            return null;
        }

        $profile = null;
        if (preg_match('/profile="?([^\s"]+)/i', $output, $matches)) {
            $profile = $matches[1];
        }

        return [
            'username' => $username,
            'profile' => $profile,
            'raw_output' => $output
        ];
    }
}
