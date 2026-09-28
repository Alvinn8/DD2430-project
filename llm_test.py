"""Testing the llm module."""

import csv
from collections.abc import Generator
from llm import Image, LLMProvider, GoogleCloudProvider


def example_tool(text: str) -> str:
    """An example tool that can be used by the LLM."""
    return f"Tool received input: {text}"


TEMP_HARDCODED_PATH = "/Users/Alvin/Downloads/DSC data testing - Blad3.csv"


def data_in_t_range(start_t: float, end_t: float) -> Generator[tuple[float, float]]:
    """Get all data points in the range [start_t, end_t] from the .csv data."""
    path = TEMP_HARDCODED_PATH
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        for row in rows[1:]:  # Skip the header row
            t = float(row[1])
            y = float(row[2])
            if start_t <= t <= end_t:
                yield t, y


def max_value_in_range(start_t: float, end_t: float) -> tuple[float, float]:
    """Get the maximum value in the range [start_t, end_t] from the .csv data.
    The interval is a range in temperature and the return value is a tuple of
    (t, y) where t is the temperature of the maximum and y is the maximum value itself.
    """
    max_y = float("-inf")
    max_t = 0.0
    for t, y in data_in_t_range(start_t, end_t):
        if y > max_y:
            max_y = y
            max_t = t
    return max_t, max_y


def min_value_in_range(start_t: float, end_t: float) -> tuple[float, float]:
    """Get the minimum value in the range [start_t, end_t] from the .csv data.
    The interval is a range in temperature and the return value is a tuple of
    (t, y) where t is the temperature of the minimum and y is the minimum value itself.
    """
    min_y = float("inf")
    min_t = 0.0
    for t, y in data_in_t_range(start_t, end_t):
        if y < min_y:
            min_y = y
            min_t = t
    return min_t, min_y


def approximate_derivative_at(t: float, steps: int = 1) -> float:
    """Approximate the derivative of the heat flow at a given temperature t using a
    central difference method.
    The steps parameter determines how many data points to use on each side of t
    for the approximation.
    """
    path = TEMP_HARDCODED_PATH
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        # Find the index of the row with the closest temperature to t
        closest_index = min(
            range(1, len(rows)), key=lambda i: abs(float(rows[i][1]) - t)
        )
        # Get the indices for the points to use for the derivative approximation
        start_index = max(1, closest_index - steps)
        end_index = min(len(rows) - 1, closest_index + steps)
        # Calculate the central difference approximation
        t1, y1 = float(rows[start_index][1]), float(rows[start_index][2])
        t2, y2 = float(rows[end_index][1]), float(rows[end_index][2])
        return (y2 - y1) / (t2 - t1)


def main():
    """Main function for testing the LLM code."""
    provider = choose_provider()
    model = choose_model(provider)
    chat = provider.new_chat(
        model,
        tools=[
            example_tool,
            max_value_in_range,
            min_value_in_range,
            approximate_derivative_at,
        ],
    )

    with open("prompts/main.md", encoding="utf-8") as f:
        system_prompt = f.read()
    for chunk in chat.send(system_prompt):
        print(chunk, end="", flush=True)
    print()

    while True:
        prompt = input("Enter your prompt (or type 'exit' to quit): ")
        if prompt.lower() == "exit":
            break

        image_path = input("Attach an image? (path or leave blank): ")
        images = [Image.from_file(image_path)] if image_path else None

        try:
            for chunk in chat.send(prompt, images):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"Error: {e}")


def choose_provider() -> LLMProvider:
    """Prompt the user to choose a provider and return the LLMProvider instance."""
    print("Available providers:")
    print("1. Google Cloud")
    provider_id = input("Choose the provider: ")
    if provider_id == "1":
        project = input("Enter your Google Cloud project ID: ")
        return GoogleCloudProvider(project)
    raise ValueError("Invalid provider.")


def choose_model(provider: LLMProvider) -> str:
    """Prompt the user to choose a model and return the model name."""
    models = provider.list_models()
    print("Available models:")
    for i, model in enumerate(models):
        print(f"{i + 1}. {model}")
    model_id = int(input("Choose a model by number: ")) - 1
    if 0 <= model_id < len(models):
        return models[model_id]
    raise ValueError("Invalid model selection.")


if __name__ == "__main__":
    main()
