#!/bin/bash
# Pegar en EC2 > Advanced details > User data. Prepara la instancia y descarga el proyecto.
set -e
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab || true
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
apt-get install -y git postgresql-client
cd /home/ubuntu && git clone https://github.com/dportilla219/chatbot-unab.git && chown -R ubuntu:ubuntu chatbot-unab
echo "listo" > /home/ubuntu/BOOTSTRAP_OK
