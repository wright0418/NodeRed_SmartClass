from utime import ticks_ms, ticks_diff, sleep_ms

class Timer:
    def __init__(self):
        self.tasks = []

    def add(self, callback, period_ms):
        self.tasks.append({
            'callback': callback,
            'period': period_ms,
            'last_run': ticks_ms()
        })

    def poll(self):
        now = ticks_ms()
        for task in self.tasks:
            if ticks_diff(now, task['last_run']) >= task['period']:
                task['last_run'] = now
                task['callback']()

if __name__ == '__main__':
    from machine import LED
    import utime

    led = LED('ledy')
    timer = Timer()

    def led_toggle():
        led.toggle()

    def custom_task():
        print("3 秒任務執行")

    timer.add(led_toggle, 1000)
    timer.add(custom_task, 3000)

    start = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), start) < 10000:  # 測試 10 秒
        timer.poll()
        utime.sleep_ms(50)
