import http.server
import socketserver
import socket

PORT = 8000

# Monkey-patch getfqdn to avoid Korean Windows hostname decode error
socket.getfqdn = lambda name='': name or '127.0.0.1'

Handler = http.server.SimpleHTTPRequestHandler
Handler.extensions_map.update({'.html': 'text/html; charset=utf-8'})

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Serving at http://127.0.0.1:{PORT}/auction_map.html")
    print("Ctrl+C to stop")
    httpd.serve_forever()
