# tapws
version: 0.4.5

## A simple virtual network interface over websocket

### How it Works

Tapws listens to WebSocket connections and forwards the data to virtual network interface.
It has built-in DHCP server (enabled by default).

![](./screenshot.gif)

### Features
- Supports IPv4 only
- DHCP Server Included
- NAT enabled to the public interface

### Example usage


#### JSLinux

- Run tapws container. `docker run --rm -p 8080:8080 --privileged -it pujianto/tapws:0.4`
- Open this emulator: https://bellard.org/jslinux/vm.html?url=alpine-x86.cfg&mem=192&net_url=ws://localhost:8080 on your browser.
- To test the internet connection, run `curl ipinfo.io` from the emulator

#### jor1k

- Run tapws container. `docker run --rm -p 8080:8080 --privileged -it pujianto/tapws:0.4`
- Open this emulator: https://s-macke.github.io/jor1k/demos/main.html?user=PhFebTBhrE&cpu=asm&n=1&relayURL=ws%3A%2F%2Flocalhost%3A8080 on your browser.
- To test the internet connection, run `curl ipinfo.io` from the emulator

#### V86

- Run tapws container. `docker run --rm -p 8080:8080 --privileged -it pujianto/tapws:0.4`
- Open https://copy.sh/v86
- Prepare a 32 bit OS image and mount it to CD drive or HDD Drive
- Set `ws://localhost:8080` as the Network proxy URL



### Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `LOG_LEVEL` | Application log level | `INFO` |
| `HOST` | The websocket listen to | `0.0.0.0` |
| `PORT` | The websocket listen port | `8080` |
| `WITH_SSL` | Set to `true` to enable ssl |`false` |
| `SSL_CERT` | SSL certificate file path | `/app/certs/fullchain.pem` |
| `SSL_KEY` | SSL key file path | `/app/certs/privkey.pem` |
| `SSL_PASSPHRASE` | SSL passphrase (private key's password)| `None` |
| `WITH_DHCP`  | Set to `true` to enable dhcp | `true` |
| `INTERFACE_IP` | Tap interface ip | `10.11.12.254` |
| `PUBLIC_INTERFACE` | Public interface name. If the `PUBLIC_INTERFACE` is set to `None`, the emulator can't access the internet (NAT not enabled). |  `None`. Dockerfile default is `eth0` |
| `INTERFACE_SUBNET` | Tap interface subnet. Valid value `0` to `30` | `24` |
| `DHCP_LEASE_TIME` | DHCP lease time. Set to `-1` to make it infinite. | `3600` (1 hour)| 




**Note:** If you want to run in `wss://` mode locally, consider to use [mkcert](https://github.com/FiloSottile/mkcert) instead of standard self-signed certificate.

### References

- https://github.com/copy/v86/blob/master/src/browser/network.js
- https://github.com/benjamincburns/websockproxy
