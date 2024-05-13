#!/bin/bash

# Load UUID from the configuration file
source /flowrecaster/rtmp_auth.conf

# Check if the UUID matches
if [ "$RTMP_CLIENT_UUID" = "none" ]; then
    exit 1
elif [ "$RTMP_CLIENT_UUID" = "$auth_uuid" ]; then
    exit 0
else
    exit 1
fi
