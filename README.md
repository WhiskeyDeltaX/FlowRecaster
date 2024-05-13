# FlowRecaster

## Description
FlowRecaster is a sophisticated FastAPI application designed for dynamic management of RTMP streams. It enables automatic creation of instances that can take in an RTMP stream and restream it to YouTube using FFmpeg. This system is designed to be highly scalable and efficient, providing robust stream management capabilities.

## Components
- **streamserver**: Manages and configures RTMP streams with Nginx.
- **webserver**: FastAPI backend that provides APIs to control and monitor streams, and dynamically create streaming instances.
- **webclient**: React-based frontend for interacting with the webserver, offering a Bootstrap-based user interface.

## Prerequisites
- Debian-ish Web Server running Python 3.8+
- Locally Node.js 14+
- Vultr account

## Setup
### Domain Configuration
1. Pick a domain and add an A record in your DNS settings to point to the IP address of your web service.
2. For this README, we will assume the domain is `flowrecaster.com`.

### Webclient Setup
2. On your local machine or the web server:
   ```bash
   cd webclient
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
   cd /FlowRecaster
   pip3 install -r requirements.txt
   # Add a new system user called "flowrecaster"
   sudo useradd -m flowrecaster
   sudo chown flowrecaster:flowrecaster -R /FlowRecaster
   ```

   Install Nginx and MongoDB if you don't have it
   ```
    # Update your package listings
    sudo apt update
    
    # Install MongoDB
    sudo apt install -y mongodb
    
    # Install Nginx
    sudo apt install -y nginx
    
    # Start and enable MongoDB and Nginx services
    sudo systemctl start mongodb
    sudo systemctl enable mongodb
    sudo systemctl start nginx
    sudo systemctl enable nginx
   ```

   Add an `/FlowRecaster/.env` file with your local variables
   ```
    VULTR_API_KEY=Z123123123123123123123123123
    PUBLIC_IP=127.0.0.1
    SSH_KEY_PATH=./server@flowrecaster.com.pem
    SERVER_HOST_URL=https://flowrecaster.com
   ```
   
   Add the following to your Nginx configuration `/etc/nginx/sites-enabled/flowrecaster.com`:
   ```
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
   ```
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
