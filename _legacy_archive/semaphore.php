<?php
function sendSemaphoreSMS($apikey, $number, $message, $sender = 'GAMETECH') {
    $url = 'https://api.semaphore.co/api/v4/messages';
    $fields = [
        'apikey'     => $apikey,
        'number'     => $number,
        'message'    => $message,
        'sendername' => $sender,
    ];
    $fields_string = http_build_query($fields);
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $fields_string);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10); // optional timeout

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        $error_msg = curl_error($ch);
        curl_close($ch);
        return json_encode(['status'=>'error', 'message'=>$error_msg]);
    }
    curl_close($ch);
    return $result;
}
?>
