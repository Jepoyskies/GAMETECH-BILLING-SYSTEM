<?php
require_once __DIR__ . '/routeros_api.class.php';

class MikroTikManager
{
    private $host;
    private $user;
    private $pass;
    private $port;
    private $api;
    private $logEnabled;
    private $logFile;

    public function __construct(
        $host = '172.30.120.2',
        $user = 'lordkris5566',
        $pass = '@Marille2012',
        $port = 8700,
        $logEnabled = false,
        $logFile = 'mikrotik_manager.log'
        
    ) {
        $this->host = $host;
        $this->user = $user;
        $this->pass = $pass;
        $this->port = $port;
        $this->logEnabled = $logEnabled;
        $this->logFile = $logFile;
        $this->api = new RouterosAPI();
    }








    

    public function connect()
    {
        if (!$this->api->connect($this->host, $this->user, $this->pass, $this->port)) {
            $this->log("❌ Failed to connect to MikroTik");
            throw new Exception("Failed to connect to MikroTik router.");
        }
        $this->log("✅ Connected to MikroTik");
    }

    public function disconnect()
    {
        $this->api->disconnect();
        $this->log("🔌 Disconnected from MikroTik");
    }

    private function log($message)
    {
        if ($this->logEnabled && $this->logFile) {
            $date = date('Y-m-d H:i:s');
            file_put_contents($this->logFile, "[$date] $message\n", FILE_APPEND);
        }
    }

    public function setLogging($enabled, $logFile = null)
    {
        $this->logEnabled = $enabled;
        if ($logFile) $this->logFile = $logFile;
    }

    public function addPppoeUser($username, $password, $profile = 'default')
    {
        $this->connect();
        try {
            $existing = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            if (!empty($existing)) {
                throw new Exception("User '$username' already exists on MikroTik.");
            }
            $params = [
                "name" => $username,
                "password" => $password,
                "profile" => $profile,
                "service" => "pppoe"
            ];
            $this->api->comm("/ppp/secret/add", $params);
            $this->log("➕ Added PPPoE user: $username ($profile)");
        } finally {
            $this->disconnect();
        }
    }

    /**
     * Update PPPoE user (username, password, profile)
     * Only changes password if you provide a non-null, non-empty value.
     */
    public function updatePppoeUser($original_username, $username, $password, $profile)
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $original_username]);
            if (empty($users)) {
                throw new Exception("User '$original_username' not found on MikroTik.");
            }
            $userId = $users[0]['.id'];
            $params = [
                ".id" => $userId,
                "name" => $username,
                "profile" => $profile
            ];
            // Only set password if provided and not blank
            if ($password !== null && $password !== '') {
                $params["password"] = $password;
            }
            $this->api->comm("/ppp/secret/set", $params);
            $this->log("✏️ Updated PPPoE user: $original_username → $username ($profile)" . (isset($params["password"]) ? " [password changed]" : ""));
        } finally {
            $this->disconnect();
        }
    }

    public function deletePppoeUser($username)
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            if (empty($users)) {
                throw new Exception("User '$username' not found on MikroTik.");
            }
            $userId = $users[0]['.id'];
            $this->api->comm("/ppp/secret/remove", [".id" => $userId]);
            $this->log("🗑️ Deleted PPPoE user: $username");
        } finally {
            $this->disconnect();
        }
    }

    public function disconnectPppoeUser($username)
    {
        $this->connect();
        try {
            $activeUsers = $this->api->comm('/ppp/active/print', [
                "?name" => $username
            ]);
            if (is_array($activeUsers)) {
                foreach ($activeUsers as $user) {
                    if (isset($user['.id'])) {
                        $this->api->comm('/ppp/active/remove', [
                            ".id" => $user['.id']
                        ]);
                    }
                }
            }
            $this->log("🔌 Disconnected PPPoE active sessions for user: $username");
        } finally {
            $this->disconnect();
        }
    }

    public function listPppoeUsers()
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?service" => "pppoe"]);
            $this->log("📄 Listed PPPoE users");
            return $users;
        } finally {
            $this->disconnect();
        }
    }

    public function getPppoeUser($username)
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            $this->log("🔍 Retrieved PPPoE user: $username");
            return empty($users) ? null : $users[0];
        } finally {
            $this->disconnect();
        }
    }

    public function changePppoePassword($username, $newPassword)
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            if (empty($users)) {
                throw new Exception("User '$username' not found on MikroTik.");
            }
            $userId = $users[0]['.id'];
            $this->api->comm("/ppp/secret/set", [
                ".id" => $userId,
                "password" => $newPassword
            ]);
            $this->log("🔑 Changed password for PPPoE user: $username");
        } finally {
            $this->disconnect();
        }
    }

    public function changePppoeProfile($username, $newProfile)
    {
        $this->connect();
        try {
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            if (empty($users)) {
                throw new Exception("User '$username' not found on MikroTik.");
            }
            $userId = $users[0]['.id'];
            $this->api->comm("/ppp/secret/set", [
                ".id" => $userId,
                "profile" => $newProfile
            ]);
            $this->log("⚡ Changed profile for PPPoE user: $username → $newProfile");
        } finally {
            $this->disconnect();
        }
    }

    /**
     * Suspend PPPoE user: set profile to "expired" and disconnect their session.
     */
    public function suspendPppoeUser($username)
    {
        $this->connect();
        try {
            // Change profile to 'expired'
            $users = $this->api->comm("/ppp/secret/print", ["?name" => $username]);
            if (empty($users)) {
                throw new Exception("User '$username' not found on MikroTik.");
            }
            $userId = $users[0]['.id'];
            $this->api->comm("/ppp/secret/set", [
                ".id" => $userId,
                "profile" => "expired"
            ]);
            $this->log("⚡ Changed profile for PPPoE user: $username → expired");

            // Disconnect active session (if any)
            $activeUsers = $this->api->comm('/ppp/active/print', ["?name" => $username]);
            if (is_array($activeUsers)) {
                foreach ($activeUsers as $user) {
                    if (isset($user['.id'])) {
                        $this->api->comm('/ppp/active/remove', [".id" => $user['.id']]);
                    }
                }
            }
            $this->log("🔌 Disconnected PPPoE active sessions for user: $username");
        } finally {
            $this->disconnect();
        }
    }

    /**
     * Sets the comment of a PPP secret user by username.
     * - Looks up the PPP secret by name
     * - Retrieves its .id
     * - Sets the comment field for that secret
     */
    public function setPppSecretComment($username, $comment)
    {
        $this->connect();
        try {
            // Find PPP secret by username
            $secret = $this->api->comm('/ppp/secret/print', [
                '?name' => $username
            ]);
            if (empty($secret) || !isset($secret[0]['.id'])) {
                throw new Exception("PPP secret for username '$username' not found.");
            }

            $id = $secret[0]['.id'];
            // Update the comment
            $this->api->comm('/ppp/secret/set', [
                '.id' => $id,
                'comment' => $comment
            ]);
            $this->log("💬 Set PPP secret comment for user '$username' to: $comment");
        } finally {
            $this->disconnect();
        }
    }




public function getActiveCount()
{
    $this->connect();
    try {
        // Get all active PPPoE sessions
        $activeUsers = $this->api->comm('/ppp/active/print', [
            '?service' => 'pppoe'
        ]);
        $this->log("🔢 Counted active PPPoE users: " . count($activeUsers));
        return is_array($activeUsers) ? count($activeUsers) : 0;
    } finally {
        $this->disconnect();
    }
}
}