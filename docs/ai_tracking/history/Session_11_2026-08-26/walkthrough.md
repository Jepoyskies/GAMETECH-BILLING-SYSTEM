# Automatic Deployment Pipeline Ready!

I have built the pipeline and generated a secure Deployment SSH Key on your Droplet! 

The final step is to securely paste the private key into your GitHub repository settings so that the GitHub Actions runner is authorized to log in to your server.

## Instructions
1. Open your browser and go to your GitHub repository: [https://github.com/Jepoyskies/GAMETECH-BILLING-SYSTEM](https://github.com/Jepoyskies/GAMETECH-BILLING-SYSTEM)
2. Go to **Settings** > **Secrets and variables** > **Actions**
3. Click the green **New repository secret** button.
4. Set the Name to exactly: `SSH_PRIVATE_KEY`
5. Copy the entire block of text below and paste it into the Secret field. Make sure to include the `BEGIN` and `END` lines!

```text
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACB4Jp4x3kuw9pZQU+9swPnPKFgy5oXVXzs9GBDwKwC0ywAAAKBDbJEVQ2yR
FQAAAAtzc2gtZWQyNTUxOQAAACB4Jp4x3kuw9pZQU+9swPnPKFgy5oXVXzs9GBDwKwC0yw
AAAEDMjEfv2kfpzKQU+mriKiZXYTBmbXZZaP6bsd/I+tyPjXgmnjHeS7D2llBT72zA+c8o
WDLmhdVfOz0YEPArALTLAAAAGWdpdGh1Yl9hY3Rpb25zQGRlcGxveW1lbnQBAgME
-----END OPENSSH PRIVATE KEY-----
```

Once you save the secret, you are done! 
From now on, every time you push to the `main` branch, your Droplet will automatically update itself!
