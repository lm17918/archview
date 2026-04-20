"""Entry point exercising package imports and re-exports."""
from detector import FasterRCNN, CocoDataset, Resize


def main():
    ds = CocoDataset("data/")
    model = FasterRCNN(num_classes=80)
    transform = Resize(640)
    print(model, ds, transform)


if __name__ == "__main__":
    main()
