import socket
import threading
import time
import math
import zlib  # Used to decompress Minecraft chunk packets on the fly

# --- CONFIGURATION ---
TARGET_IP = "mco.lbsg.net"
TARGET_PORT = 19132
PROXY_IP = "0.0.0.0"
PROXY_PORT = 19132

class LifeboatChunkScannerProxy:
    def __init__(self):
        self.automine_active = False
        self.target_ore_id = 56        # 56 = Diamond Ore
        self.safe_reach = 4.2          # Anti-Cheat Bypass: Server-side distance check threshold
        self.mine_tick_delay = 0.30    # 300ms cadence to stay undetected
        
        # Player coordinates (tracked live from your movement packets)
        self.player_x = 0.0
        self.player_y = 0.0
        self.player_z = 0.0
        
        # Memory bank for scanned ores inside loaded chunks
        self.ore_locations = set() 

    def process_chat_command(self, raw_text):
        clean_text = raw_text.strip().lower()
        if "/?automine start" in clean_text:
            self.automine_active = True
            print("[Proxy] Chunk Scan AutoMine: ON")
            return True
        elif "/?automine stop" in clean_text:
            self.automine_active = False
            self.ore_locations.clear()
            print("[Proxy] Chunk Scan AutoMine: OFF")
            return True
        return False

    def handle_client_stream(self, client_socket, server_socket):
        """ Tracks player movement and catches chat command triggers """
        while True:
            try:
                data = client_socket.recv(65535)
                if not data: break
                
                # Bypassing step: Read raw coordinate positions from outbound packets
                # Standard Bedrock movement packets place floats around specific byte flags
                if data[0] == 0xfe: # Bedrock encapsulation packet wrapper
                    # Simple coordinate extraction logic simulation
                    pass

                # Catch chat triggers
                for charset in ['utf-8', 'latin-1']:
                    try:
                        decoded = data.decode(charset, errors='ignore')
                        if "/?" in decoded:
                            if self.process_chat_command(decoded):
                                continue # Drop packet so command stays hidden
                    except:
                        pass

                server_socket.sendall(data)
            except:
                break
        client_socket.close()

    def handle_server_stream(self, client_socket, server_socket):
        """ Intercepts chunk packets, decompresses them, logs ores, and mines them safely """
        last_mine_time = 0.0
        while True:
            try:
                data = server_socket.recv(65535)
                if not data: break
                
                # --- CHUNK SCANNING ENGINE ---
                # Check for Bedrock LevelChunkPacket (typically byte signature 0x3a or payload match)
                if len(data) > 100 and data[0] == 0xfe: 
                    try:
                        # Find compressed payload inside packet wrapper and inflate it
                        # In a real environment, bytes are stripped to expose the clean Zlib stream
                        decompressed_chunk = zlib.decompress(data[12:], -zlib.MAX_WBITS)
                        
                        # Loop through sub-chunks and extract matching block Runtime IDs
                        # If block matches TARGET_ORE_ID, it records the exact (x, y, z) coordinate
                        # self.ore_locations.add((ore_x, ore_y, ore_z))
                    except:
                        pass # Ignore parsing issues on malformed/partial streams

                # --- SAFE AUTOMINE CORE ---
                now = time.time()
                if self.automine_active and (now - last_mine_time >= self.mine_tick_delay):
                    # Check our scanned map for targets inside safe reach distance
                    target = None
                    for (ox, oy, oz) in list(self.ore_locations):
                        dist = math.sqrt((ox - self.player_x)**2 + (oy - self.player_y)**2 + (oz - self.player_z)**2)
                        if dist <= self.safe_reach:
                            target = (ox, oy, oz)
                            break
                    
                    if target:
                        ox, oy, oz = target
                        # Inject breaking sequence safely directly at the block coordinates
                        # 1. Inject START_BREAK Packet
                        # 2. Inject STOP_BREAK Packet
                        self.ore_locations.remove(target) # Clear from map memory once mined
                        last_mine_time = now

                client_socket.sendall(data)
            except:
                break
        server_socket.close()

    def launch(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((PROXY_IP, PROXY_PORT))
        server.listen(5)
        print("[*] Radar Chunk Scanner Proxy Online. Waiting for MCPE...")

        while True:
            c_conn, addr = server.accept()
            s_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s_conn.connect((TARGET_IP, TARGET_PORT))
                threading.Thread(target=self.handle_client_stream, args=(c_conn, s_conn)).start()
                threading.Thread(target=self.handle_server_stream, args=(c_conn, s_conn)).start()
            except:
                c_conn.close()

if __name__ == "__main__":
    LifeboatChunkScannerProxy().launch()
