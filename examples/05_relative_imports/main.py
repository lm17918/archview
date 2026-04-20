"""Entry point that uses the yolo package via its top-level API."""
from yolo import detect


if __name__ == "__main__":
    detect("frame.jpg")
