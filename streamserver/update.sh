#!/bin/bash

SERVER_UUID="$1"
SERVER_HOST="$2"
FQDN_NAME="$3"
ZONE_ID="$4"
CF_API_TOKEN="$5"
SERVER_IP="$6"
STREAM_KEY="$7"
YOUTUBE_KEY="$8"
BACKUP_MP4="$9"

echo $@

PUBLIC_IP=$(curl -s http://ipinfo.io/ip)
echo "Detected public IP: $PUBLIC_IP"

create_dns_record() {
    echo "Creating new DNS record for $FQDN_NAME with IP $PUBLIC_IP"
    curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
         -H "Authorization: Bearer $CF_API_TOKEN" \
         -H "Content-Type: application/json" \
         --data '{"type":"A","name":"'"$FQDN_NAME"'","content":"'"$PUBLIC_IP"'","ttl":1,"proxied":false}' | jq
}

# Function to update an existing DNS record
update_dns_record() {
    local record_id=$1
    echo "Updating existing DNS record for $FQDN_NAME with IP $PUBLIC_IP"
    curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$record_id" \
         -H "Authorization: Bearer $CF_API_TOKEN" \
         -H "Content-Type: application/json" \
         --data '{"type":"A","name":"'"$FQDN_NAME"'","content":"'"$PUBLIC_IP"'","ttl":1,"proxied":false}' | jq
}

echo "---Updating---"
sudo apt update
echo "---Installing nginx---"
sudo apt install -y nginx libnginx-mod-rtmp git ffmpeg htop curl jq certbot python3-certbot-nginx

# Check if the DNS record already exists
record_id=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$FQDN_NAME" \
             -H "Authorization: Bearer $CF_API_TOKEN" \
             | jq -r '.result[0].id')

if [ "$record_id" != "null" ]; then
    update_dns_record $record_id
else
    create_dns_record
fi

echo "---Cloning---"
rm -rf /flowrecaster
git clone https://github.com/WhiskeyDeltaX/FlowRecaster.git /flowrecaster

pushd /flowrecaster/streamserver

echo "---pip install---"
mkdir -p ~/.config/pip/
cp pip.conf ~/.config/pip/pip.conf
pip3 install -r server/requirements.txt

echo "---Adding daemon---"

sudo useradd flow
chown flow:flow -R /flowrecaster/streamserver/server

echo $SERVER_UUID > /flowrecaster_uuid.txt
chown flow:flow /flowrecaster_uuid.txt

echo $SERVER_HOST > /flowrecaster_host.txt
chown flow:flow /flowrecaster_host.txt

echo $STREAM_KEY > /flowrecaster_stream_key.txt
chown flow:flow /flowrecaster_stream_key.txt

echo $YOUTUBE_KEY > /flowrecaster_youtube_key.txt
chown flow:flow /flowrecaster_youtube_key.txt

cp flowrecaster.service /etc/systemd/system/flowrecaster.service
sudo systemctl daemon-reload
sudo systemctl enable flowrecaster

sed -i "s/\$PUBLIC_IP/$SERVER_IP/g" nginx.conf
sed -i "s/\$FQDN_NAME/$FQDN_NAME/g" nginx.conf

cp nginx.conf /etc/nginx/nginx.conf
mkdir -p /var/www/html/streams
chown www-data:www-data -R /var/www/html/streams

echo "---nginx reload---"

popd

ufw allow 8453
ufw allow 80
ufw allow 443
ufw allow 19751

systemctl reload nginx

wget $BACKUP_MP4 -O /backup.mp4
chown www-data:www-data /backup.mp4

sleep 120

# Define retry parameters
MAX_RETRIES=10
WAIT_TIME=180  # 3 minutes in seconds

# Initialize counter
count=0

# Loop to retry certbot command
while [ $count -lt $MAX_RETRIES ]; do
    sudo certbot --email mail@$FQDN_NAME --agree-tos --non-interactive --nginx -d $FQDN_NAME
    
    # Check if certbot succeeded
    if [ $? -eq 0 ]; then
        echo "Certbot succeeded!"
        break
    else
        echo "Certbot failed. Attempt $((count+1)) of $MAX_RETRIES. Retrying in $WAIT_TIME seconds..."
        count=$((count+1))
        sleep $WAIT_TIME
    fi
done

sleep 10

systemctl reload nginx

sudo systemctl start flowrecaster

#sudo mv reboot_server.service /etc/systemd/system/
#sudo mv reboot_server.timer /etc/systemd/system/

#sudo systemctl daemon-reload
#sudo systemctl enable reboot_server.timer
#sudo systemctl start reboot_server.timer

echo "---Finished---"
