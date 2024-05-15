# FlowRecaster

## Description
FlowRecaster is a sophisticated FastAPI application designed for dynamic management of RTMP streams. It enables automatic creation of instances that can take in an RTMP stream and restream it to YouTube using FFmpeg. This system is designed to be highly scalable and efficient, providing robust stream management capabilities.

## Components
- **streamserver**: Manages and configures RTMP streams with Nginx.
- **webserver**: FastAPI backend that provides APIs to control and monitor streams, and dynamically create streaming instances.
- **webclient**: React-based frontend for interacting with the webserver, offering a Bootstrap-based user interface.

## Prerequisites
- Debian-ish Web Server running Python 3.8+
- Locally (or on web server) Node.js 14+
- Vultr account
- Domain hosted on CloudFlare

## Setup
### Domain Configuration
1. Pick a domain and add an A record in your DNS settings to point to the IP address of your web service.

For this README, we will assume the domain is `flowrecaster.com`.

### Webclient Setup
2. On your local machine or the web server:
   ```bash
   cd webclient

   # Install npm if needed
   # curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
   # sudo apt-get install -y nodejs
   
   npm install
   # Add your domain to the environment file
   npm run build
   # Transfer the build files to your web server's directory
   scp -r build/* yourserver:/var/www/html/flowrecaster.com/
   ```

### Webserver Setup
3. On your web server (Assumed Debian 12):
   ```bash
   
   
   
   # Assuming SSH access to your server
   cd .. # Now we are at the root of the git project)
   
   # Copy the webserver files to the FlowRecaster directory
   scp -r webserver/* yourserver:/FlowRecaster
   
   ssh yourserver

   # Install code-server if you want
   # curl -fsSL https://code-server.dev/install.sh | sh

   cd /FlowRecaster
   pip3 install -r requirements.txt
   # Add a new system user called "flowrecaster"
   sudo useradd -m flowrecaster
   sudo chown flowrecaster:flowrecaster -R /FlowRecaster
   ```

   Install Nginx and MongoDB if you don't have it
   ```bash
    # Update your package listings
    sudo apt update
    
    # Install MongoDB
    curl -fsSL https://pgp.mongodb.com/server-7.0.asc |sudo gpg  --dearmor -o /etc/apt/trusted.gpg.d/mongodb-server-7.0.gpg
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    sudo apt-get update
    sudo apt-get install -y mongodb-org
    sudo systemctl start mongod
    sudo systemctl enable mongod

    # Install Nginx
    sudo apt install -y nginx
    
    # Start and enable MongoDB and Nginx services
    sudo systemctl start mongodb
    sudo systemctl enable mongodb
    sudo systemctl start nginx
    sudo systemctl enable nginx
   ```

   Add an `/FlowRecaster/.env` file with your local variables
   ```bash
   VULTR_API_KEY=ZTHJSDFGTJHFDGSDFGER5GSDFG
   PUBLIC_IP=8.8.4.4
   SSH_KEY_PATH=/server@flowrecaster.com.pem
   VULTR_V4_SUBNET=10.69.2.0
   SERVER_HOST_URL=https://flowrecaster.com
   CF_API_TOKEN=asfefarsdgFregfdfgsdfgsdfgdrg
   CF_ZONE_ID=123gdsg5r345tgwdfgsdfgsdfg
   CF_DOMAIN_NAME=flowrecaster.com
   BACKUP_MP4_URL=https://download.samplelib.com/mp4/sample-5s.mp4
   ```
   
   Add the following to your Nginx configuration `/etc/nginx/sites-enabled/flowrecaster.com`:
   ```bash
   server {
       listen 80;
       server_name flowrecaster.com www.flowrecaster.com;

       location / {
           root /var/www/html/flowrecaster.com;
           try_files $uri $uri/ =404;
       }

       location /api {
           proxy_pass http://unix:/FlowRecaster/flowrecaster.sock;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

   Run certbot
   ```bash
   # Install Certbot and its Nginx plugin
   sudo apt install certbot python3-certbot-nginx
   
   # Configure SSL for your domain
   sudo certbot --nginx -d flowrecaster.com -d www.flowrecaster.com
   
   # Enable automatic renewal of SSL certificates
   sudo systemctl enable certbot-renew.timer
   sudo systemctl start certbot-renew.timer
   ```

5. Create a gunicorn service:
   ```bash
   sudo nano /etc/systemd/system/flowrecaster.service
   ```
   Include:
   ```
   [Unit]
   Description=Gunicorn instance to serve FlowRecaster
   After=network.target

   [Service]
   User=flowrecaster
   Group=www-data
   WorkingDirectory=/FlowRecaster
   Environment="PATH=/usr/bin/python3"
   ExecStart=/usr/local/bin/gunicorn --workers 3 --bind unix:flowrecaster.sock -m 007 --worker-class uvicorn.workers.UvicornWorker app:app

   [Install]
   WantedBy=multi-user.target
   ```

6. Enable and start the service:
   ```bash
   sudo systemctl enable flowrecaster.service
   sudo systemctl start flowrecaster.service
   sudo nginx -t # Make sure the reverse proxy configuration is good
   sudo systemctl reload nginx
   ```

## Contributing
We welcome contributions! Please read our CONTRIBUTING.md for details on how to submit patches and the contribution workflow.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
