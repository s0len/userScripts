#!/bin/bash

PUID=${PUID:-100}
PGID=${PGID:-99}
UMASK=${UMASK:-002}

# Create a new group called dockeruser with the specified group ID
umask $UMASK

# Create a new user called dockeruser with the specified user ID
groupmod -o -g "$PGID" dockeruser

# Modify the group ID of the dockeruser
usermod -o -u "$PUID" dockeruser

# Copy contents of /app/config to /config
#cp -Rn /app/config/* /config

# Change permissions of the /config directory to 777
#chmod -R 777 /config

chown -R dockeruser:dockeruser /app /config

# Run the command as the dockeruser
exec runuser -u dockeruser -g dockeruser -- "$@"