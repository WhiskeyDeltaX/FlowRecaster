#!/bin/bash

mkdir -p /flowrecaster
pushd /flowrecaster

sudo apt update
sudo apt install -y nginx libnginx-mod-rtmp

sudo nginx -s reload

popd
