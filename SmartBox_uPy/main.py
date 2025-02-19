from machine import UART,Pin
from utime import sleep_ms,ticks_ms,ticks_diff
from mesh_device import Mesh_Device

class DigitalOut():
    
    def __init__ (self, io_port):
        self.io_port = Pin(io_port, Pin.OUT)
        self.io_port.value(0)
        
    def set(self, value):
        self.io_port.value(value)
    
    def get(self):
        return self.io_port.value()
    
class DigitalIN():
    
    def __init__ (self, io_port):
        self.io_port = Pin(io_port, Pin.IN, Pin.PULL_UP)
        self.io_callback = None
        self.io_port.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.IO_call_back)
   
    def get(self):
        return self.io_port.value()
    def IO_call_back(self, io_port):
        # print('IO_call_back:',io_port.value())
        if self.io_callback:
            self.io_callback(io_port.value())
class Rs485_Agent():
    
    def __init__ (self, port, baudrate,ctl_pin=None):
        self.ctl_pin = Pin(ctl_pin, Pin.OUT)
        self.uart_port = port 
        self.uart = UART(port, baudrate,timeout=500)
        self.char_3p5_time_ms = 3.5*(8+1+2)/baudrate *1000
        self.ctrl_timebase_ms = (8+1+3)/baudrate *1000
    
    def set_uart_baudrate(self,baudrate) :
        self.uart.deinit()
        self.uart = UART(self.uart_port, baudrate,timeout=500)

    def send(self, data):
        self.uart.read(self.uart.any())
        self.ctl_pin.value(1)
        self.uart.write(data)
        sleep_ms(int(len(data)*self.ctrl_timebase_ms))
        self.ctl_pin.value(0)
    
    def receive(self,timeout = 500):
        start = ticks_ms()
        while ticks_diff(ticks_ms(),start) < timeout:
            if self.uart.any():
                return self.uart.readline()

if __name__ == '__main__':
    from machine import Pin,LED,WDT
    import utime as time
    from utime import ticks_diff,ticks_ms
    from micropython import const
    import gc

    key_pushed_time = 0
    key_state = "release"

    def check_key_time(pin):
        global key_state,key_pushed_time
        if key_state =='release' and pin.value() == 0: #pushed
            key_pushed_time = time.ticks_ms()
            key_state = 'pushed'
        elif key_state == 'pushed' and pin.value() == 1: #release
            key_state = 'release'
        elif key_state =='pushed' and pin.value() == 0: #release
            return time.ticks_diff(time.ticks_ms(),key_pushed_time)
        return 0
           
    g_led = LED('ledg')
    unprov_KEY = Pin(Pin.epy.KEYA,Pin.IN,Pin.PULL_UP)


    # mesh device define packet format
    #          Header(2) + Type(1) + Addr(1) Data(n)
    # Response Header(2) + Type(1) + Status(1)  Data(n)
    
    HEADER   = const (b'\x82\x76')
    GET_TYPE = const (b'\x00') 
    SET_TYPE = const (b'\x01')
    RTU_TYPE = const (b'\x02')
    ADDR     = const (b'\x00')
    LENGTH   = const (b'\x01')
    STATUS_OK= const (b'\x80')
    STATUS_ERROR = const (b'\xFE')

    def mesh_callback(**msg):
        # print ('recv_data==' , msg)
        data = msg['msg']
        type =  bytes(data[2:3])
        header = bytes(data[:2])
        if len(data) == 4 and (type == GET_TYPE) and (header == HEADER):
            address = data[3:4]
            if address == b'\x00': #for DI
                DI_data = b'\x01' if DI.get() else b'\x00'
                return (HEADER + GET_TYPE + STATUS_OK + address + DI_data)
            
        if len(data) == 5 and (type == SET_TYPE) and (header== HEADER):
            address = data[3:4]
            if address == b'\x00': # for DO
                DO.set(data[4])
                return (HEADER + SET_TYPE + STATUS_OK + address)
            if address == b'\x80' : # for RS485 baaudRate , 0:2400bps ; 1:4800bps ; 2:9600bps
                set_baudrate = {0:2400,1:4800,2:9600}
                modbus.set_uart_baudrate(set_baudrate[data[4]])
                # print ('uart change baudrate' )
                return (HEADER + SET_TYPE + STATUS_OK + address)
    
        if len(data) > 3 and (type == RTU_TYPE) and (header == HEADER):
            modbus.send(data[3:])
            recv_data = modbus.receive(timeout = 200)
            if recv_data:
                return (HEADER + RTU_TYPE + recv_data)  
        return (header + type + STATUS_ERROR)  
        #print ("Error packet",len(data),data[0],data[1],data[2],list(data))

    def DI_callback(value):
        # print('DI_callback:',value)
        address = b'\x00'
        if value == 1:
            mesh.send(HEADER + GET_TYPE + STATUS_OK + address + b'\x01')
        else:
            mesh.send(HEADER + GET_TYPE + STATUS_OK + address + b'\x00')

    #P10 -- Relay control
    DO= DigitalOut(Pin.epy.P10)
    DI = DigitalIN(Pin.epy.P19)
    DI.io_callback = DI_callback
    uart_port = 0
    modbus = Rs485_Agent(uart_port, baudrate = 9600 ,ctl_pin=Pin.epy.KEYB)
    mesh = Mesh_Device(1)
    mesh.recv_callback=mesh_callback

    wdt = WDT(timeout = 2000)

    while True:
        wdt.feed()
        if mesh.proved:
            g_led.on()
        else:
            g_led.toggle()

        if check_key_time(unprov_KEY) > 5000:
            g_led.off()
            mesh.unprov()  
        time.sleep(0.5)

 

