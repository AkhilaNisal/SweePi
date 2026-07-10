"""Small, testable PWM ramp helpers for cleaning motors."""


def clamp_pwm(value: float, maximum: float) -> float:
    return max(0.0, min(float(maximum), float(value)))


def move_toward(current: float, target: float, maximum_change: float) -> float:
    current = float(current)
    target = float(target)
    maximum_change = max(0.0, float(maximum_change))
    if current < target:
        return min(current + maximum_change, target)
    if current > target:
        return max(current - maximum_change, target)
    return target


def ramp_step(
    current: float,
    target: float,
    maximum_pwm: float,
    ramp_up_sec: float,
    ramp_down_sec: float,
    elapsed_sec: float,
) -> float:
    maximum_pwm = max(0.0, float(maximum_pwm))
    current = clamp_pwm(current, maximum_pwm)
    target = clamp_pwm(target, maximum_pwm)
    duration = float(ramp_up_sec if target > current else ramp_down_sec)
    if duration <= 0.0:
        return target
    rate = maximum_pwm / duration
    return clamp_pwm(move_toward(current, target, rate * max(0.0, elapsed_sec)), maximum_pwm)
