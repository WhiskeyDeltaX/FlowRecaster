#!/bin/bash

server_uuid="$1"
server_host="$2"

echo "---Updating---"
sudo apt update
echo "---Installing nginx---"
sudo apt install -y nginx libnginx-mod-rtmp git ffmpeg

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
chown flow:flow /flowrecaster/streamserver/server

echo $server_uuid > /flowrecaster_uuid.txt
chown flow:flow /flowrecaster_uuid.txt

echo $server_host > /flowrecaster_host.txt
chown flow:flow /flowrecaster_host.txt

cp flowrecaster.service /etc/systemd/system/flowrecaster.service
sudo systemctl daemon-reload
sudo systemctl enable flowrecaster
sudo systemctl restart flowrecaster

cp nginx.conf /etc/nginx/nginx.conf

echo "---nginx reload---"
sudo nginx -s reload

popd

ufw allow 8453
ufw allow 80

echo "---Finished---"
