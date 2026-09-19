from llm import LLMProvider, GoogleCloudProvider

def main():
    provider = choose_provider()
    model = choose_model(provider)
    chat = provider.new_chat(model)

    while True:
        prompt = input("Enter your prompt (or type 'exit' to quit): ")
        if prompt.lower() == 'exit':
            break

        try:
            for chunk in chat.send(prompt):
                print(chunk, end='', flush=True)
            print()
        except Exception as e:
            print(f"Error: {e}")

def choose_provider() -> LLMProvider:
    print("Available providers:")
    print("1. Google Cloud")
    provider_id = input("Choose the provider: ")
    if provider_id == "1":
        project = input("Enter your Google Cloud project ID: ")
        return GoogleCloudProvider(project)
    else:
        raise ValueError("Invalid provider.")

def choose_model(provider: LLMProvider) -> str:
    models = provider.list_models()
    print("Available models:")
    for i, model in enumerate(models):
        print(f"{i + 1}. {model}")
    model_id = int(input("Choose a model by number: ")) - 1
    if 0 <= model_id < len(models):
        return models[model_id]
    else:
        raise ValueError("Invalid model selection.")

if __name__ == "__main__":
    main()