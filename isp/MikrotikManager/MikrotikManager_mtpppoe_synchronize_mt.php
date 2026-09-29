<?php
class MikroTikManager
{
    private string $host;
    private string $username;
    private string $password;
    private int $port;
    private $ssh_connection = null;

    public function __construct(string $host, string $username, string $password, int $port = 22)
    {
        $this->host = $host;
        $this->username = $username;
        $this->password = $password;
        $this->port = $port;
    }

    public function connect(): void
    {
        $this->ssh_connection = ssh2_connect($this->host, $this->port);

        if (!$this->ssh_connection) {
            throw new Exception("SSH connection failed");
        }

        if (!ssh2_auth_password($this->ssh_connection, $this->username, $this->password)) {
            throw new Exception("SSH authentication failed");
        }
    }

    public function disconnect(): void
    {
        $this->ssh_connection = null;
    }

    private function run(string $cmd): string
    {
        $stream = ssh2_exec($this->ssh_connection, $cmd);
        stream_set_blocking($stream, true);
        $output = stream_get_contents($stream);
        fclose($stream);
        return $output ?: '';
    }

    private function esc(string $v): string
    {
        return '"' . str_replace('"', '\"', $v) . '"';
    }

    /* ✅ ADD OR UPDATE PPPoE USER */
    public function addOrUpdatePppoeUser(string $username, string $password, string $profile): void
    {
        $u = $this->esc($username);
        $p = $this->esc($password);
        $pr = $this->esc($profile);

        $check = $this->run("/ppp/secret/print where name=$u");

        if (stripos($check, $username) !== false) {
            $this->run("/ppp/secret/set [find name=$u] password=$p profile=$pr");
        } else {
            $this->run("/ppp/secret/add name=$u password=$p service=pppoe profile=$pr");
        }
    }

    /* ✅ DELETE USER */
    public function deletePppoeUser(string $username): void
    {
        $u = $this->esc($username);
        $this->run("/ppp/secret/remove [find name=$u]");
    }
}
