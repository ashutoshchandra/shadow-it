import psutil
import socket

def list_outbound_connections():
    connections = psutil.net_connections(kind='inet')
    outbound = []
    for conn in connections:
        if conn.status == 'ESTABLISHED' and conn.raddr:
            outbound.append({
                'pid': conn.pid,
                'remote_ip': conn.raddr.ip,
                'remote_port': conn.raddr.port
            })
    return outbound

if __name__ == "__main__":
    for conn in list_outbound_connections():
        print(conn)
