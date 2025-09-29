from machine import UART, Pin
from utime import sleep_ms, ticks_ms, ticks_diff
from mesh_device import Mesh_Device
import gc


class DigitalOut:
    def __init__(self, io_port):
        self.io_port = Pin(io_port, Pin.OUT)
        self.io_port.value(0)

    def set(self, value):
        self.io_port.value(value)

    def get(self):
        return self.io_port.value()


class DigitalIN:
    def __init__(self, io_port):
        self.io_port = Pin(io_port, Pin.IN, Pin.PULL_UP)
        self.io_callback = None
        self.io_port.irq(
            trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.IO_call_back
        )

    def get(self):
        return self.io_port.value()

    def IO_call_back(self, io_port):
        if self.io_callback:
            self.io_callback(io_port.value())


class Rs485_Agent:
    def __init__(self, port, baudrate, ctl_pin=None):
        self.ctl_pin = Pin(ctl_pin, Pin.OUT)
        self.uart_port = port
        self.uart = UART(port, baudrate, timeout=500)
        self.char_3p5_time_ms = 3.5 * (8 + 1 + 2) / baudrate * 1000
        self.ctrl_timebase_us = (8 + 1 + 3) / baudrate * 1000000

    def set_uart_baudrate(self, baudrate):
        self.uart.deinit()
        self.uart = UART(self.uart_port, baudrate, timeout=500)

    def send(self, data):
        self.uart.read(self.uart.any())
        delay_time = int(len(data) * self.ctrl_timebase_us) // 1000
        self.ctl_pin.value(1)
        self.uart.write(data)
        sleep_ms(delay_time)
        self.ctl_pin.value(0)

    def receive(self, timeout=300):
        start = ticks_ms()
        recv_data = b""
        while ticks_diff(ticks_ms(), start) < timeout:
            if self.uart.any():
                recv_data += self.uart.read(self.uart.any())
                start = ticks_ms()
            sleep_ms(10)
        return recv_data if recv_data != b"" else None


if __name__ == "__main__":
    # 每次 main 開始前，在 simulated_msg_log.txt 加入 "==="
    try:
        with open("simulated_msg_log.txt", "a") as f:
            f.write("===\n")
    except Exception as e:
        pass

    from machine import Pin, LED, WDT
    import utime as time
    from utime import ticks_diff, ticks_ms
    from micropython import const
    import gc
    import ubinascii as binascii

    key_pushed_time = 0
    key_state = "release"

    def check_key_time(pin):
        global key_state, key_pushed_time
        if key_state == "release" and pin.value() == 0:  # pushed
            key_pushed_time = time.ticks_ms()
            key_state = "pushed"
        elif key_state == "pushed" and pin.value() == 1:  # release
            key_state = "release"
        elif key_state == "pushed" and pin.value() == 0:  # release
            return time.ticks_diff(time.ticks_ms(), key_pushed_time)
        return 0

    g_led = LED("ledg")
    unprov_KEY = Pin(Pin.epy.KEYA, Pin.IN, Pin.PULL_UP)

    # mesh device define packet format
    #          Header(2) + Type(1) + Addr(1) Data(n)
    # Response Header(2) + Type(1) + Status(1)  Data(n)

    HEADER = const(b"\x82\x76")
    GET_TYPE = const(b"\x00")
    SET_TYPE = const(b"\x01")
    RTU_TYPE = const(b"\x02")
    KWS301_V_TYPE = const(b"\x03")
    KWS301_I_TYPE = const(b"\x04")
    KWS301_P_TYPE = const(b"\x05")
    KWS301_KW_TYPE = const(b"\x06")
    ADDR = const(b"\x00")
    LENGTH = const(b"\x01")
    STATUS_OK = const(b"\x80")
    STATUS_ERROR = const(b"\xfe")

    def modbus_crc16(data):
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        # Micropython 沒有 to_bytes，直接用 bytes 組合
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    def mesh_callback(**msg):
        data = msg["msg"]
        type = bytes(data[2:3])
        header = bytes(data[:2])

        if len(data) == 4 and (type == GET_TYPE) and (header == HEADER):
            address = data[3:4]
            if address == b"\x00":  # for DI
                DI_data = b"\x01" if DI.get() else b"\x00"
                return HEADER + GET_TYPE + STATUS_OK + address + DI_data
        if len(data) == 5 and (type == SET_TYPE) and (header == HEADER):
            address = data[3:4]
            if address == b"\x00":  # for DO
                DO.set(data[4])
                return HEADER + SET_TYPE + STATUS_OK + address
            if (
                address == b"\x80"
            ):  # for RS485 baaudRate , 0:2400bps ; 1:4800bps ; 2:9600bps
                set_baudrate = {0: 2400, 1: 4800, 2: 9600}
                modbus.set_uart_baudrate(set_baudrate[data[4]])
                return HEADER + SET_TYPE + STATUS_OK + address
        if (
            len(data) >= 3
            and type in (KWS301_V_TYPE, KWS301_I_TYPE, KWS301_P_TYPE, RTU_TYPE, KWS301_KW_TYPE)
            and header == HEADER
        ):
            address = data[3:4]
            if address == b"\xa5":  # for IR RTU
                modbus.send(data[3:])
                recv_data = modbus.receive(timeout=300)
                return HEADER + RTU_TYPE + recv_data

            retry = 0

            while retry <= 1:
                modbus.send(data[3:])
                recv_data = modbus.receive(timeout=300)

                if recv_data and len(recv_data) >= 2:
                    crc_calc = modbus_crc16(recv_data[:-2])
                    crc_recv = recv_data[-2:]
                    """
                    print(
                        "MODBUS CRC 檢查: Recv CRC =",
                        [hex(b) for b in crc_recv],
                        "Calc CRC =",
                        [hex(b) for b in crc_calc],
                    )
                    """
                    if crc_calc == crc_recv:
                        # print("CRC 正確")
                        return HEADER + type + recv_data
                    else:
                        # print("CRC 錯誤，重送")
                        retry += 1
                        pass
                elif recv_data == b"" or recv_data is None:
                    return header + type + STATUS_ERROR

            # 若兩次都錯誤，回傳錯誤
            # print("CRC 連續錯誤，回傳 STATUS_ERROR")
            return header + type + STATUS_ERROR
        else:  # RTU bypass mode
            modbus.send(data)
            recv_data = modbus.receive(timeout=300)
            if recv_data and recv_data != b"":
                return recv_data
        return header + type + STATUS_ERROR

    def DI_callback(value):
        address = b"\x00"
        if value == 1:
            mesh.send(HEADER + GET_TYPE + STATUS_OK + address + b"\x01")
        else:
            mesh.send(HEADER + GET_TYPE + STATUS_OK + address + b"\x00")

    def handle_simulated_msg():
        simulated_data = HEADER + RTU_TYPE + b"\x03\x04\x00\x00\x00\x06\x71\xea"
        result = mesh_callback(msg=simulated_data)
        try:
            with open("simulated_msg_log.txt", "a") as f:
                f.write("{}\n".format(
                    str(binascii.hexlify(result[3:]), "utf-8")))
        except Exception as e:
            pass

    # P10 -- Relay control
    DO = DigitalOut(Pin.epy.P10)
    DI = DigitalIN(Pin.epy.P19)
    DI.io_callback = DI_callback
    uart_port = 0
    modbus = Rs485_Agent(uart_port, baudrate=9600, ctl_pin=Pin.epy.KEYB)
    mesh = Mesh_Device(1)
    mesh.recv_callback = mesh_callback

    wdt = WDT(timeout=10000)

    while True:
        wdt.feed()
        mesh.poll()  # 主動呼叫 poll 處理 UART 資料
        if mesh.proved:
            g_led.on()
        else:
            g_led.toggle()

        if check_key_time(unprov_KEY) > 5000:
            g_led.off()
            mesh.unprov()

        # # --- 模擬每10秒觸發一次 RTU_TYPE 且 header==HEADER 的流程 ---
        # if 'last_sim_time' not in globals():
        #     global last_sim_time
        #     last_sim_time = time.ticks_ms()
        # if time.ticks_diff(time.ticks_ms(), last_sim_time) > (10 * 1000):  # 10秒
        #     last_sim_time = time.ticks_ms()
        #     handle_simulated_msg()

        time.sleep_ms(100)  # 等待垃圾回收完成
