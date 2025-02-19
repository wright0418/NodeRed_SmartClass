import _thread
from machine import UART,LED
import ubinascii as binascii
from utime import sleep_ms

class Mesh_Device():
    def __init__(self,uart_port,baudrate=115200):
        self.uart = UART(uart_port, baudrate)
        self.proved = None
        self.recv_callback= None
        self.error_led = LED('ledr')
        mesh_task = _thread.start_new_thread(self.recv_tesk,())
        # reboot module to get the proved status
        self.uart.write(b'AT+REBOOT\r\n')

    def unprov(self):
        self.uart.write(b'AT+NR\r\n')

    def recv_tesk(self):
        while True:
            try:
                if self.uart.any():
                    recv_data = self.uart.readline().strip().split(b' ')
                    if len(recv_data) < 4:
                        if recv_data[0] == b'PROV-MSG' and recv_data[1] == b'SUCCESS' :
                            self.proved = True
                        if recv_data[0] == b'SYS-MSG' and recv_data[1] == b'DEVICE' and recv_data[2] == b'UNPROV' :
                            self.proved = False
                        continue
                    if recv_data[0] == b'SYS-MSG' and recv_data[1] == b'DEVICE':
                        if recv_data[2] == b'PROV-ED':
                            self.proved = True
                        continue
                    msg_type = recv_data[0]
                    msg_from = recv_data[1]
                    msg_data = binascii.unhexlify(recv_data[3])
                    if self.recv_callback:
                        send_back = self.recv_callback(type = msg_type , source = msg_from ,msg = msg_data)
                        self.send(send_back)

            except Exception as e:
                self.uart.read(self.uart.any())
                self.error_led.on()
                sleep_ms(100)
                self.error_led.off()
                # print ('recv_tesk:',e)
                continue

    def send(self,msg_data,msg_type='bin'):
        if msg_type == 'bin':
            msg = b'AT+MDTS 0 ' + binascii.hexlify(msg_data) + b'\r\n'
            # print ('mesh_send',msg)
        elif msg_type == 'str':
            msg = b'AT+MDTS 0 ' + msg_data + b'\r\n'
        self.uart.write(msg)


if __name__ == '__main__':
    from machine import WDT
    wdt = WDT(timeout = 2000)

    def mesh_callback(data):
        
        print ('recv_data==' , data)

    mesh = Mesh_Device(1)
    mesh.recv_callback = mesh_callback  

    mesh.send(b'\x82\x76\x00\x00')
    while True:
        wdt.feed()

        pass 