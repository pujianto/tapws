# tapws

## A simple virtual network interface over websocket

This project complements [V86](https://github.com/copy/v86) for its networking feature. Inspired by [WebSockets Proxy](https://github.com/benjamincburns/websockproxy)

## How to use

### Using Docker


#### Pre-built Docker image
- `docker pull pujianto/tapws`
- `docker run --rm -p 8080:8080 --privileged -it pujianto/tapws`

#### Local Build
- Clone this repository
- Run `docker build -t tapws .`
- Run `docker run --rm -p 8080:8080 --privileged tapws`

![](./Screenshot_20220507_231944.jpeg)

The docker image doesn't have dhcpd, so you need set your own network configuration. 
For example on Archlinux image, you can run the following command on the Archlinux side:
- `ip addr add 10.11.12.2/24 dev enp0s5`
- `ip link set enp0s5 up`

Now you can ping the tapws server (10.11.12.1)

### TODO
- Add iptables integration
- Implement Wss 


### References

- https://github.com/copy/v86/blob/master/src/browser/network.js
- https://github.com/benjamincburns/websockproxy
