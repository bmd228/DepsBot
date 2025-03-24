#FROM ubuntu:22.04
FROM python:3.10-slim
RUN apt update && apt install -y \
#    sudo wget curl gnupg  python3 python3-pip\
    sudo wget curl gnupg apt-utils  \
    schroot tar skopeo distro-info \
    && wget https://ftp.debian.org/debian/pool/main/d/debootstrap/debootstrap_1.0.140_all.deb -O debootstrap.deb && sudo dpkg -i debootstrap.deb && rm -f debootstrap.deb  \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Копируем код бота
COPY bot.py /app/bot.py
WORKDIR /app

CMD ["python3", "bot.py"]
