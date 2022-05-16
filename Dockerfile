FROM python:3.10
ARG DEBIAN_FRONTEND=noninteractive
ENV LOG_LEVEL=ERROR
ENV PUBLIC_INTERFACE_NAME=eth0
ENV WITH_SSL=False
ENV INTERFACE_IP=10.11.12.254

WORKDIR /app
RUN apt update -y && apt install iptables bridge-utils iproute2 inetutils-ping ca-certificates -y
RUN dpkg-reconfigure ca-certificates
RUN mkdir -p /dev/net
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8080
CMD ["python", "main.py"]
