FROM python:3.10
ARG DEBIAN_FRONTEND=noninteractive
ENV LOG_LEVEL=INFO
ENV PUBLIC_INTERFACE=eth0
ENV WITH_SSL=False
ENV INTERFACE_IP=10.11.12.254
ENV INTERFACE_SUBNET=24

WORKDIR /app
RUN apt update -y && apt install iptables bridge-utils iproute2 inetutils-ping ca-certificates -y
RUN dpkg-reconfigure ca-certificates
RUN mkdir -p /dev/net
COPY . .
RUN pip install pip --upgrade
RUN pip install -r requirements.txt
EXPOSE 8080
CMD ["python", "main.py"]
