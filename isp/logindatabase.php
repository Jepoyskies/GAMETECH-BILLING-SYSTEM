<?php
declare(strict_types=1);

class BillingDB {
    private PDO $pdo;

    public function __construct(PDO $pdo) {
        $this->pdo = $pdo;
    }

    public function getAdminByUsername(string $username): ?array {
        $stmt = $this->pdo->prepare('SELECT * FROM admins WHERE username = :username LIMIT 1');
        $stmt->execute(['username' => $username]);
        return $stmt->fetch() ?: null;
    }

    public function logAdminLogin(int $adminId, string $username, string $ip, string $userAgent): void {
        $stmt = $this->pdo->prepare(
            "INSERT INTO admin_logins (admin_id, username, event_type, ip_address, user_agent)
             VALUES (:admin_id, :username, 'login', :ip, :user_agent)"
        );
        $stmt->execute([
            'admin_id'   => $adminId,
            'username'   => $username,
            'ip'         => $ip,
            'user_agent' => $userAgent,
        ]);
    }
}
