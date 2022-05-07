FROM python:3.10
ENV LOG_LEVEL=DEBUG
WORKDIR /app
RUN apt update -y && apt install iptables bridge-utils iproute2 inetutils-ping -y
RUN mkdir -p /dev/net
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
