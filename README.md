# tapws
Version 1.x.x

Switched from `websockets` to `aiohttp`. Since `aiohttp` also support for plain http(s).
We can add features such as web managements (Mainly to manipulate port forwarding and show client list).


The concept is like this:

- http://localhost:8080 - serve admin page
- http://localhost:8080/ws - serve websocket



### Screenshot
![](./Screenshot%202022-05-22%20at%2019-06-31%20tapws.png)