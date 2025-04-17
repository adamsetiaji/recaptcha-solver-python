

# LINUX
```
sudo apt update && sudo apt upgrade -y
```

```
sudo apt-get install libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 libatspi2.0-0t64 xvfb x11vnc fluxbox python3-pip python3.12-venv -y
```

# Install Docker
## Set up Docker's apt repository
```
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```
## Install the Docker packages
```
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```
```
snap install docker
```
# Docker Command
## Build & Down Image
```
docker-compose down
docker-compose up -d --build
```

## Logs Image
```
docker logs -f {NAMES}
```


## List Image Active
```
docker ps
```

## List Image
```
docker images
```

## Stop & Remove Running Image
```
docker stop {Image NAMES}
docker rm {Image NAMES}
```

## Delete Image Permanent
```
docker rmi {IMAGE ID}
```

```
python3 -m venv venv
source venv/bin/activate
```

```
pip install flask python-dotenv psutil playwright
python -m playwright install chromium
```
