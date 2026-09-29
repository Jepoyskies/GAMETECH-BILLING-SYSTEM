<?php
/**
 * MikroTik SSH Manager: add/delete PPPoE users via SSH.
 */
class MikroTikManager
{
    private $host;
    private $username;
    private $password;
    private $port;
    private $ssh_connection;

    public function __construct($host, $username, $password, $port = 22)
    {
        $this->host     = $host;
        $this->username = $username;
        $this->password = $password;
        $this->port     = (int)$port ?: 22;
    }

    public function connect()
    {
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

    public function disconnect()
    {
        $this->ssh_connection = null;
    }

    private function runSshCommand($command)
    {
        if (!$this->ssh_connection) {
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
     * Add PPPoE user (PPP secret).
     */
    public function addPppoeUser(string $username, string $password, string $profile = 'default')
    {
        $usernameEsc = escapeshellarg($username);
        $passwordEsc = escapeshellarg($password);
        $profileEsc  = escapeshellarg($profile);

        // RouterOS CLI command
        $cmd = "/ppp/secret/add name={$usernameEsc} password={$passwordEsc} service=pppoe profile={$profileEsc}";
        return $this->runSshCommand($cmd);
    }

    /**
     * Delete PPPoE user (PPP secret).
     */
    public function deletePppoeUser(string $username)
    {
        $usernameEsc = escapeshellarg($username);
        $cmd = "/ppp/secret/remove [find where name={$usernameEsc}]";
        return $this->runSshCommand($cmd);
    }
}
