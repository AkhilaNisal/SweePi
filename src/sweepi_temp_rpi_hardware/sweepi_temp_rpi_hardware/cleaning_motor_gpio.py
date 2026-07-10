"""GPIO backend for the Raspberry Pi vacuum and brush motor drivers."""

from __future__ import annotations


class CleaningMotorGpio:
    def __init__(
        self,
        pins: dict[str, int],
        pwm_frequency_hz: float,
        dry_run: bool,
        fail_if_unavailable: bool,
        gpio_chip_index: int = 0,
    ) -> None:
        self.pins = {name: int(pin) for name, pin in pins.items()}
        self.pwm_frequency_hz = float(pwm_frequency_hz)
        self.dry_run = bool(dry_run)
        self.fail_if_unavailable = bool(fail_if_unavailable)
        self.gpio_chip_index = int(gpio_chip_index)
        self.handle = None
        self.lgpio = None
        self.healthy = False
        self.state = {
            'vacuum_pwm_percent': 0.0,
            'vacuum_enabled': False,
            'brush_pwm_percent': 0.0,
            'brush_1_forward': False,
            'brush_2_forward': False,
        }
        self._initialize()

    def _initialize(self) -> None:
        if self.dry_run:
            self.healthy = True
            return
        try:
            import lgpio

            self.lgpio = lgpio
            self.handle = lgpio.gpiochip_open(self.gpio_chip_index)
            for pin in self.pins.values():
                lgpio.gpio_claim_output(self.handle, pin, 0)
            self.healthy = True
            self.all_off()
        except Exception as exc:
            self.healthy = False
            self.close()
            if self.fail_if_unavailable:
                raise RuntimeError(f'Failed to initialize cleaning motor GPIO: {exc}') from exc
            self.dry_run = True
            self.healthy = True

    def is_healthy(self) -> bool:
        return self.healthy

    def _write(self, name: str, value: bool) -> None:
        if self.dry_run:
            return
        self.lgpio.gpio_write(self.handle, self.pins[name], 1 if value else 0)

    def _pwm(self, name: str, percent: float) -> None:
        percent = max(0.0, min(100.0, float(percent)))
        if self.dry_run:
            return
        self.lgpio.tx_pwm(
            self.handle,
            self.pins[name],
            self.pwm_frequency_hz,
            percent,
        )

    def set_vacuum_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.state['vacuum_enabled'] = enabled
        self._write('vacuum_enable', enabled)

    def set_vacuum_pwm(self, percent: float) -> None:
        percent = max(0.0, min(100.0, float(percent)))
        self.state['vacuum_pwm_percent'] = percent
        self._pwm('vacuum_pwm', percent)

    def set_brush_directions(self, brush_1_forward: bool, brush_2_forward: bool) -> None:
        self.state['brush_1_forward'] = bool(brush_1_forward)
        self.state['brush_2_forward'] = bool(brush_2_forward)
        self._write('brush_1_in1', brush_1_forward)
        self._write('brush_1_in2', not brush_1_forward)
        self._write('brush_2_in1', brush_2_forward)
        self._write('brush_2_in2', not brush_2_forward)

    def set_brush_pwm(self, percent: float) -> None:
        percent = max(0.0, min(100.0, float(percent)))
        self.state['brush_pwm_percent'] = percent
        self._pwm('brush_pwm', percent)

    def stop_brushes(self) -> None:
        self.set_brush_pwm(0.0)
        self.state['brush_1_forward'] = False
        self.state['brush_2_forward'] = False
        for name in ('brush_1_in1', 'brush_1_in2', 'brush_2_in1', 'brush_2_in2'):
            self._write(name, False)

    def all_off(self) -> None:
        try:
            self.set_vacuum_pwm(0.0)
            self.set_brush_pwm(0.0)
            self.set_vacuum_enabled(False)
            self.stop_brushes()
        except Exception:
            self.healthy = False

    def close(self) -> None:
        if self.handle is None or self.lgpio is None:
            return
        try:
            self.all_off()
        finally:
            try:
                self.lgpio.gpiochip_close(self.handle)
            except Exception:
                pass
            self.handle = None
