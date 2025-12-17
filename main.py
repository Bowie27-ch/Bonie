import json
import math
import time
from my_udp import UDPClient


class Control:
    def __init__(self):
        # 初始化UDP通信
        net = "BzkAhScaaaIlqLA2Hf8c1hnMUNXP,192.168.2.1,9902,9903"
        parts = net.split(',')
        vehicle_name = parts[0]
        ip = parts[1]
        port = int(parts[2])
        send_port = int(parts[3])
        self.udp_client = UDPClient(ip, port, send_port, vehicle_name)

        self.m_v = 0
        self.m_x = 0
        self.m_y = 0
        self.m_yaw = 0

        self.control_rate = 10  # hz

    def control_node(self):
        start_time = time.time()
        while True:
            vehicle_data = self.udp_client.get_vehicle_state()
            self.m_x = vehicle_data.x
            self.m_y = vehicle_data.y
            self.m_yaw = vehicle_data.yaw / 180 * math.pi

            v, w=0, 0
            self.udp_client.send_control_command(v, w)

            elapsed_time = time.time() - start_time
            sleep_time = max((1.0 / self.control_rate) - elapsed_time, 0.0)
            time.sleep(sleep_time)
            start_time = time.time()


if __name__ == '__main__':
    control = Control()
    control.udp_client.start()
    control.control_node()

    # PID控制器参数
    self.kp = 0.1  # 比例增益
    self.ki = 0.01  # 积分增益
    self.kd = 0.05  # 微分增益
    self.previous_error = 0  # 上一次误差
    self.integral = 0  # 积分项
    self.last_time = time.time()  # 上一次更新时间


def calculate_speed(self):
    """计算当前速度"""
    current_time = time.time()
    dt = current_time - self.last_time

    if dt > 0:
        dx = self.m_x - self.previous_x
        dy = self.m_y - self.previous_y
        self.real_speed = math.hypot(dx, dy) / dt
    else:
        self.real_speed = 0

    self.previous_x = self.m_x
    self.previous_y = self.m_y
    self.last_time = current_time

    return self.real_speed


def pid_control(self, target_speed):
    """PID速度控制"""
    current_time = time.time()
    error = target_speed - self.calculate_speed()

    dt = current_time - self.last_time
    self.integral += error * dt
    derivative = (error - self.previous_error) / dt if dt > 0 else 0

    output = self.kp * error + self.ki * self.integral + self.kd * derivative

    # 限制输出速度在0到11之间
    output = max(0, min(output, 11))

    # 更新上一次误差和时间
    self.previous_error = error
    self.last_time = current_time

    return output

def switch_track(x0, y0, carsInRegion1, carsInRegion2, track1, track2):
    # 转弯区块判定
    if track_ == track1:
        # 如果小车此时靠近(10.586, 9.791)，距离小于0.7米，则开放切换渠道
        if 10.586 - 0.7 < x0 < 10.586 + 0.7 and 9.791 - 0.7 < y0 < 9.791 + 0.7:
            # 如果区域1车多于区域2车，切换到track2
            if carsInRegion1 > carsInRegion2:
                track_ = track2
    else:
        # 如果小车此时靠近(10.472, 15.001)，距离小于0.7米，则开放切换渠道
        if 10.472 - 0.7 < x0 < 10.472 + 0.7 and 15.001 - 0.7 < y0 < 15.001 + 0.7:
            # 如果区域2车多于区域1车，切换到track1
            if carsInRegion2 > carsInRegion1:
                track_ = track1

    return track_
