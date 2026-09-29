<?php
/**
 * MikroTik SSH Manager for PPPoE users (update profile, comment, disconnect).
 */
class MikroTikManager
{
    private string $host;
    private string $username;
    private string $password;
    private int    $port;
    private $ssh_connection = null;

    private bool $logging;
    private string $logFile;

    public function __construct(
        string $host,
        string $username,
        string $password,
        int $port = 22,
        bool $logging = false,
        string $logFile = ''
    ) {
        $this->host     = $host;
        $this->username = $username;
        $this->password = $password;
        $this->port     = $port > 0 ? $port : 22;

        $this->logging  = $logging;
        $this->logFile  = $logFile ?: __DIR__ . '/mikrotik.log';
    }

    private function log(string $msg): void
    {
        if (!$this->logging) return;
        @file_put_contents(
            $this->logFile,
            '[' . date('Y-m-d H:i:s') . '] ' . $msg . PHP_EOL,
            FILE_APPEND
        );
    }

    public function connect(): bool
    {
        if (!function_exists('ssh2_connect')) {
            throw new Exception('SSH2 extension not installed. Please enable php-ssh2.');
        }

        $this->log("Connecting to {$this->host}:{$this->port} as {$this->username}");

        $connection = @ssh2_connect($this->host, $this->port);
        if (!$connection) {
            $this->log("Connection failed");
            throw new Exception("Could not connect to MikroTik device: {$this->host}:{$this->port}");
        }

        $auth = @ssh2_auth_password($connection, $this->username, $this->password);
        if (!$auth) {
            $this->log("Auth failed");
            throw new Exception("SSH authentication failed for user {$this->username} on {$this->host}");
        }

        $this->ssh_connection = $connection;
        $this->log("Connected");
        return true;
    }

    public function disconnect(): void
    {
        $this->log("Disconnecting");
        $this->ssh_connection = null;
    }

    private function runSshCommand(string $command): string
    {
        if (!$this->ssh_connection) {
            $this->connect();
        }

        $this->log("CMD: $command");

        $stream = @ssh2_exec($this->ssh_connection, $command);
        if (!$stream) {
            $this->log("Failed to exec");
            throw new Exception("Failed to execute command: $command");
        }

        stream_set_blocking($stream, true);
        $output = stream_get_contents($stream);
        fclose($stream);

        $this->log("OUT: " . trim((string)$output));
        return $output !== false ? $output : '';
    }

    /**
     * RouterOS-safe value: "value" with internal " escaped as \".
     * This is NOT shell escaping; it's for RouterOS CLI arguments only.
     */
    private function rosEscape(string $value): string
    {
        return '"' . str_replace('"', '\"', $value) . '"';
    }

    /**
     * Update PPPoE user (/ppp secret).
     *
     * @param string      $oldUsername current secret name
     * @param string|null $newUsername new name (or null to keep)
     * @param string|null $newPassword new password (or null to keep)
     * @param string|null $profile     new profile (or null to keep)
     */
    public function updatePppoeUser(
        string $oldUsername,
        ?string $newUsername = null,
        ?string $newPassword = null,
        ?string $profile = null
    ): string {
        $nameEsc = $this->rosEscape($oldUsername);

        $setParts = [];
        if ($newUsername !== null && $newUsername !== '') {
            $setParts[] = 'name=' . $this->rosEscape($newUsername);
        }
        if ($newPassword !== null && $newPassword !== '') {
            $setParts[] = 'password=' . $this->rosEscape($newPassword);
        }
        if ($profile !== null && $profile !== '') {
            $setParts[] = 'profile=' . $this->rosEscape($profile);
        }

        if (empty($setParts)) {
            // nothing to change
            return '';
        }

        $setStr = implode(' ', $setParts);

        // /ppp/secret/set [find name="user"] name="new" profile="plan"
        $cmd = "/ppp/secret/set [find name={$nameEsc}] {$setStr}";
        return $this->runSshCommand($cmd);
    }

    /**
     * Update /ppp secret comment for a user.
     */
    public function setPppSecretComment(string $username, string $comment): string
    {
        $nameEsc    = $this->rosEscape($username);
        $commentEsc = $this->rosEscape($comment);

        $cmd = "/ppp/secret/set [find name={$nameEsc}] comment={$commentEsc}";
        return $this->runSshCommand($cmd);
    }

    /**
     * Disconnect PPPoE user from /ppp active.
     */
    public function disconnectPppoeUser(string $username): string
    {
        $nameEsc = $this->rosEscape($username);

        // /ppp/active/remove [find name="user"]
        $cmd = "/ppp/active/remove [find name={$nameEsc}]";
        return $this->runSshCommand($cmd);
    }
}
