##### Algorithm ->EdDSA(Edwards-Curve Digital Signature Algorithm)
# Ed25519 is a public-key signature system that is:
# Fast, Secure, Widely used in modern cryptographic systems

###### Cryptography (confidentiality, integrity, authentication)
# Encrypt(“HELLO”, key=1234) → “X7B9Z”
# Decrypt(“X7B9Z”, key=1234) → “HELLO”
# Web Security  -	HTTPS, SSL/TLS
# Blockchain    - 	Wallets, Digital Signatures (e.g., Bitcoin, Ethereum)
# Messaging	    -    End-to-end encryption (e.g., Signal, WhatsApp)
# File Security -	Encrypting sensitive files (e.g., zip, PDFs)
# Authentication-	Login systems, API tokens, SSH


################### use this code to place a market order on Binance using REST API with HMAC SHA256 signature ##################
import hmac
import hashlib
import time
import requests

api_key = '***************'
api_secret = '***************'

# Binance REST API endpoint for placing an order
base_url = 'https://api.binance.com'
endpoint = '/api/v3/order'

# Request parameters
params = {
    'symbol': 'ALICEUSDT',   # Replace with your desired trading pair
    'side': 'BUY',
    'type': 'MARKET',
    'quantity': 50,       # Must match symbol precision
    'timestamp': int(time.time() * 1000)
}

# Create the query string from parameters
query_string = '&'.join([f"{key}={value}" for key, value in params.items()])

# Create the HMAC SHA256 signature using your API secret
signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# Append the signature to the parameters
params['signature'] = signature

# Set request headers with API key
headers = {
    'X-MBX-APIKEY': api_key
}

# Send the POST request to Binance
response = requests.post(f"{base_url}{endpoint}", params=params, headers=headers)

# Print the response
print("Response:", response.status_code)
print("Data:", response.json())
