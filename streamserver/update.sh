#!/bin/bash

sudo apt update
sudo apt install -y nginx libnginx-mod-rtmp git ffmpeg

git clone https://github.com/WhiskeyDeltaX/FlowRecaster.git /flowrecaster

pushd /flowrecaster/streamserver

pip3 install -r server/requirements.txt

mv flowrecaster.service /etc/systemd/system/flowrecaster.service
sudo systemctl daemon-reload
sudo systemctl enable
sudo systemctl start flowrecaster

mv nginx.conf /etc/nginx/nginx.conf

sudo nginx -s reload

popd
