import time
from machine import Pin
from micropython import const

class Button:
    def __init__(self, pin_id, pull=None, inverted=False, 
                 debounce_ms=20, long_press_ms=500):
        if pull is not None:
            self.pin = Pin(pin_id, Pin.IN, pull)
        else:
            self.pin = Pin(pin_id, Pin.IN)
            
        self._inverted = inverted
        self._debounce_ms = debounce_ms
        self._long_press_ms = long_press_ms

        self._last_state = self._read_pin()
        self._current_state = self._last_state
        self._last_change_time = 0
        self._press_start_time = 0
        
        self._was_pressed_flag = False
        self._was_long_pressed_flag = False
        self._long_press_triggered = False

    def _read_pin(self):
        return not self.pin.value() if self._inverted else bool(self.pin.value())

    def update(self):
        now = time.ticks_ms()
        physical_state = self._read_pin()

        if physical_state != self._last_state:
            self._last_change_time = now
        
        if time.ticks_diff(now, self._last_change_time) > self._debounce_ms:
            if physical_state != self._current_state:
                self._current_state = physical_state
                
                if self._current_state: # Pressed
                    self._press_start_time = now
                    self._long_press_triggered = False
                    self._was_pressed_flag = True
                # else: # Released
                    # 如果松开时，长按事件没有被触发过，
                    # 那么这次按键才算是一次有效的 "短按"。
                    # 但为了简单，我们让长按事件在触发时主动清除短按标志。
                    pass
                    
        self._last_state = physical_state

        if self._current_state and not self._long_press_triggered:
            if time.ticks_diff(now, self._press_start_time) > self._long_press_ms:
                self._was_long_pressed_flag = True
                self._long_press_triggered = True
                # --- 核心修正 ---
                # 当长按事件触发时，清除掉之前设置的短按事件标志。
                self._was_pressed_flag = False

    def was_pressed(self) -> bool:
        if self._was_pressed_flag:
            self._was_pressed_flag = False
            return True
        return False

    def was_long_pressed(self) -> bool:
        if self._was_long_pressed_flag:
            self._was_long_pressed_flag = False
            return True
        return False
    def consume(self):
        """
        手动清除所有事件标志。
        用于在处理完一个事件后，防止其在后续的循环中被重复触发。
        """
        self._was_pressed_flag = False
        self._was_long_pressed_flag = False