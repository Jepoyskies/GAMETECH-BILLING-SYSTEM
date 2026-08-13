import socket
import sys
import routeros_api

def test_physical_router():
    host = "192.168.88.1"
    port = 8728
    username = "admin"
    
    print("=== MikroTik Physical Router Test ===")
    print(f"Target: {host}:{port}")
    print(f"User: {username}")
    password = input("Enter password for 'admin' (leave blank if none): ")

    print(f"\nAttempting to connect to MikroTik at {host}:{port}...")
    
    # 1. First, check if the IP is reachable on the API port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        sock.connect((host, port))
        sock.close()
        print(f"[\u2713] Socket connection to {host}:{port} successful!")
    except Exception as e:
        print(f"[\u274c] Network Error: Cannot reach {host}:{port}. Is the router on and accessible? Error: {e}")
        return

    # 2. Proceed with actual RouterOS API connection
    def attempt_connection(use_plaintext):
        print(f"\n--- Trying connection with modern login (plaintext_login={use_plaintext}) ---")
        connection = routeros_api.RouterOsApiPool(
            host=host,
            username=username,
            password=password,
            port=port,
            plaintext_login=use_plaintext,
            use_ssl=False
        )

        try:
            api = connection.get_api()
            
            system_identity = api.get_resource('/system/identity')
            identity = system_identity.get()[0]['name']
            print(f"[\u2713] Authentication successful! Router Identity: {identity}")
            
            active_ppp = api.get_resource('/ppp/active')
            users = active_ppp.get()
            print(f"[\u2713] Successfully retrieved active PPPoE users (Count: {len(users)})")
            
            for user in users:
                print(f"   - {user.get('name')} (Uptime: {user.get('uptime')})")

            connection.disconnect()
            print("\n[\u2713] SUCCESS! Your Python script can talk to the MikroTik router.")
            return True

        except Exception as e:
            print(f"[\u274c] API Authentication Failed: {e}")
            return False

    # Try modern login first (RouterOS 6.43+)
    success = attempt_connection(use_plaintext=True)
    
    # If it failed, try legacy challenge-response login (RouterOS < 6.43)
    if not success:
        print("\nNotice: First attempt failed. Retrying with legacy authentication method (for older RouterOS versions)...")
        success = attempt_connection(use_plaintext=False)
        
        if not success:
            print("\n[\u274c] ALL AUTHENTICATION ATTEMPTS FAILED.")

if __name__ == '__main__':
    test_physical_router()
