import os
from ultralytics import YOLO

# 设定模型训练的配置
dataset_root = 'dataset'  # 数据集根目录，包含 train/ 和 val/
yaml_file = os.path.join(dataset_root, 'data.yaml')  # data.yaml 文件路径

if __name__ == "__main__":
# 选择一个YOLO模型，例如YOLOv8
    model = YOLO("yolo11n.pt")  # 使用YOLOv8小型模型，你也可以选择 "yolov8s.yaml", "yolov8m.yaml", "yolov8l.yaml" 等

# 启动训练
    model.train(
        data="E:\\YOLO11\\ultralytics-main\\YOLO\\data.yaml",         # 数据集的配置文件路径
        epochs=20,              # 训练的轮数
        batch=4,          # 每个批次的图像数量
        imgsz=640,              # 输入图片的大小 (图像会调整为该大小进行训练)
        project='output',   # 存储训练结果的文件夹
        name='ORADS', # 训练实验的名字
        exist_ok=True ,          # 如果目录已存在，是否覆盖
        device=0
    )

print("训练已完成！")
