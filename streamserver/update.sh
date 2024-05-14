#!/bin/bash

SERVER_UUID="$1"
SERVER_HOST="$2"
RECORD_NAME="$3"
ZONE_ID="$4"
CF_API_TOKEN="$5"
SERVER_IP="$6"

PUBLIC_IP=$(curl -s http://ipinfo.io/ip)
echo "Detected public IP: $PUBLIC_IP"

create_dns_record() {
    echo "Creating new DNS record for $RECORD_NAME with IP $PUBLIC_IP"
    curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
         -H "Authorization: Bearer $CF_API_TOKEN" \
         -H "Content-Type: application/json" \
         --data '{"type":"A","name":"'"$RECORD_NAME"'","content":"'"$PUBLIC_IP"'","ttl":1,"proxied":false}' | jq
}

# Function to update an existing DNS record
update_dns_record() {
    local record_id=$1
    echo "Updating existing DNS record for $RECORD_NAME with IP $PUBLIC_IP"
    curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$record_id" \
         -H "Authorization: Bearer $CF_API_TOKEN" \
         -H "Content-Type: application/json" \
         --data '{"type":"A","name":"'"$RECORD_NAME"'","content":"'"$PUBLIC_IP"'","ttl":1,"proxied":false}' | jq
}

echo "---Updating---"
sudo apt update
echo "---Installing nginx---"
sudo apt install -y nginx libnginx-mod-rtmp git ffmpeg htop curl jq certbot python-certbot-nginx

# Check if the DNS record already exists
record_id=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$RECORD_NAME" \
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

cp flowrecaster.service /etc/systemd/system/flowrecaster.service
sudo systemctl daemon-reload
sudo systemctl enable flowrecaster
sudo systemctl restart flowrecaster

sed -i "s/\$PUBLIC_IP/$SERVER_IP/g" nginx.conf

cp nginx.conf /etc/nginx/nginx.conf
mkdir -p /var/www/html/stream
chown www-data:www-data -R /var/www/html/stream

echo "---nginx reload---"
sudo nginx -s reload

popd

ufw allow 8453
ufw allow 80
ufw allow 443
ufw allow 19751

sleep 60

sudo certbot --nginx -d $RECORD_NAME

echo "---Finished---"
