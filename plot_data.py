import matplotlib.pyplot as plt
import pandas as pd


def make_plot(x, y):
    plt.plot(x, y)
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Heat Flow (mW)")
    plt.title("Heat Flow vs Temperature")
    plt.grid()
    plt.show()


def main():
    # load the data from a CSV file
    data = pd.read_csv("data/GRIS - N125-180 x10.csv", encoding="utf-16")

    make_plot(data["Temperature"], data["HeatFlow"])


if __name__ == "__main__":
    main()
