from machine import UART, LED
import ubinascii as binascii
import sys
from utime import sleep_ms, ticks_ms


class Mesh_Device():
    def __init__(self, uart_port, baudrate=115200):
        self.uart = UART(uart_port, baudrate, timeout=100)
        self.proved = None
        self.recv_callback = None
        self.error_led = LED('ledr')
        # 使用固定容量的可變緩衝區 (bytearray) 與寫入指標，避免重複配置記憶體
        self._rxbuf = bytearray(256)  # 固定容量，可視需求調整
        self.tmp = bytearray(64)
        self._rx_w = 0  # 已填入緩衝的長度（寫入指標）
        # 啟動時重啟模組以獲取 proved 狀態
        self.uart.write(b'AT+REBOOT\r\n')

    def unprov(self):
        self.uart.write(b'AT+NR\r\n')

    def poll(self):
        # 輪詢 UART 是否有資料，有則處理
        try:
            if self.uart.any():
                line = self.uart.readline()
                if line == b'':
                    return

                recv_data = line.strip().split(b' ')

                if len(recv_data) < 4:
                    if recv_data[0:2] == [b'PROV-MSG', b'SUCCESS']:
                        self.proved = True
                    if recv_data[0:3] == [b'SYS-MSG', b'DEVICE', b'UNPROV']:
                        self.proved = False
                    del recv_data
                    del line
                    return
                if recv_data[0:2] == [b'SYS-MSG', b'DEVICE']:
                    if recv_data[2] == b'PROV-ED':
                        self.proved = True
                    del recv_data
                    del line
                    return
                if recv_data[0:2] == [b'REBOOT-MSG', b'SUCCESS']:
                    del recv_data
                    del line
                    return

                msg_type = recv_data[0]
                msg_from = recv_data[1]

                msg_data = binascii.unhexlify(recv_data[3])

                if self.recv_callback:
                    send_back = self.recv_callback(
                        type=msg_type, source=msg_from, msg=msg_data)
                    if send_back:
                        self.send(send_back)

                del recv_data
                del line
        except Exception as e:
            # 例外發生時，用 readinto 清空 UART FIFO（避免分配新 bytes）
            self.uart.any()
            self.error_led.on()
            sleep_ms(100)
            self.error_led.off()
            self.uart.write(b'AT+REBOOT\r\n')
            sleep_ms(1000)
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
