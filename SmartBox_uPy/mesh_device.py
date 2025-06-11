from machine import UART, LED
import ubinascii as binascii
from utime import sleep_ms

class Mesh_Device():
    def __init__(self, uart_port, baudrate=115200):
        self.uart = UART(uart_port, baudrate)
        self.proved = None
        self.recv_callback = None
        self.error_led = LED('ledr')
        self._rxbuf = b''  # 新增 bytes 緩衝區
        # 啟動時重啟模組以獲取 proved 狀態
        self.uart.write(b'AT+REBOOT\r\n')

    def unprov(self):
        self.uart.write(b'AT+NR\r\n')

    def poll(self):
        # 輪詢 UART 是否有資料，有則處理
        try:
            if self.uart.any():
                # 讀取 UART 資料並加入緩衝區

                self._rxbuf += self.uart.read(self.uart.any())
                while b'\n' in self._rxbuf:
                    line, self._rxbuf = self._rxbuf.split(b'\n', 1)

                    line = line.strip()
                    if not line:
                        continue
                    recv_data = line.split(b' ')

                    if len(recv_data) < 4:
                        if recv_data[0:2] == [b'PROV-MSG', b'SUCCESS']:
                            self.proved = True
                        if recv_data[0:3] == [b'SYS-MSG', b'DEVICE', b'UNPROV']:
                            self.proved = False
                        continue
                    if recv_data[0:2] == [b'SYS-MSG', b'DEVICE']:
                        if recv_data[2] == b'PROV-ED':
                            self.proved = True
                        continue
                    msg_type = recv_data[0]
                    msg_from = recv_data[1]
                    msg_data = binascii.unhexlify(recv_data[3])
                    
                    if self.recv_callback:
                        send_back = self.recv_callback(type=msg_type, source=msg_from, msg=msg_data)
                        self.send(send_back)
        except Exception as e:
            self.uart.read(self.uart.any())
            self.error_led.on()
            sleep_ms(100)
            self.error_led.off()
            # print('poll:', e)

    def send(self, msg_data, msg_type='bin'):
        if msg_type == 'bin':
            msg = b'AT+MDTS 0 ' + binascii.hexlify(msg_data) + b'\r\n'
        elif msg_type == 'str':
            msg = b'AT+MDTS 0 ' + msg_data + b'\r\n'
        self.uart.write(msg)

# 測試用 main
if __name__ == '__main__':
    from machine import WDT
    wdt = WDT(timeout=2000)

    def mesh_callback(**data):
        print('recv_data==', data)

    mesh = Mesh_Device(1)
    mesh.recv_callback = mesh_callback

    # mesh.send(b'\x82\x76\x00\x00')
    print("Mesh Device is ready. Waiting for data...")
    while True:
        wdt.feed()
        mesh.poll()  # 主動呼叫 poll 處理 UART 資料
        print(".", end='')
        sleep_ms(100)
        pass