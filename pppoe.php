<?php
require('routeros_api.class.php');

/* =========================
   DATABASE CONFIG
========================= */
$dbHost = 'localhost';
$dbName = 'gametech';
$dbUser = 'root';
$dbPass = '@Marille2012';

/* =========================
   CACHE SETTINGS
========================= */
$cacheFile = 'cache.json';
$cacheTime = 2; // seconds

function toMbps($bps) {
    return round($bps / 1000000, 2);
}

// serve cache if fresh
if (file_exists($cacheFile) && (time() - filemtime($cacheFile)) < $cacheTime) {
    header('Content-Type: application/json');
    echo file_get_contents($cacheFile);
    exit;
}

/* =========================
   DB CONNECTION
========================= */
try {
    $pdo = new PDO("mysql:host=$dbHost;dbname=$dbName;charset=utf8", $dbUser, $dbPass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (Exception $e) {
    die(json_encode(['error' => 'Database connection failed']));
}

/* =========================
   FETCH DEVICES
========================= */
$stmt = $pdo->query("
    SELECT 
        device_name,
        ip_address,
        api_username,
        api_password,
        api_port_8700
    FROM mikrotik_devices
");

$devices = $stmt->fetchAll(PDO::FETCH_ASSOC);

$data = [];

foreach ($devices as $device) {

    $API = new RouterosAPI();

    // set custom port
    $API->port = $device['api_port_8700'];

    if ($API->connect(
        $device['ip_address'],
        $device['api_username'],
        $device['api_password']
    )) {

        $queues = $API->comm('/queue/simple/print', ['stats' => '']);

        foreach ($queues as $q) {

            $rate = $q['rate'] ?? '0/0';
            list($rx, $tx) = explode('/', $rate);

            $data[] = [
                'device_name' => $device['device_name'],
                'device_ip'   => $device['ip_address'],
                'user'        => $q['name'],
                'rx_mbps'     => toMbps($rx),
                'tx_mbps'     => toMbps($tx)
            ];
        }

        $API->disconnect();

    } else {
        // mark device offline
        $data[] = [
            'device_name' => $device['device_name'],
            'device_ip'   => $device['ip_address'],
            'status'      => 'offline'
        ];
    }
}

/* =========================
   SAVE CACHE
========================= */
file_put_contents($cacheFile, json_encode($data));

header('Content-Type: application/json');
echo json_encode($data);
