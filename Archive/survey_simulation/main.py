import time
from utils import load_text, load_personas, save_results
from survey_engine import build_prompt, get_survey_response


def get_user_range(max_personas):
    """Prompts the user for start and end indices with strict bounds checking."""
    while True:
        user_input = input(
            f"Enter the range of personas to survey (1-{max_personas}), e.g., '2-10', '50-100', or 'all': ").strip().lower()

        if user_input == 'all' or user_input == '':
            return 0, max_personas

        try:
            # 1. Split the input
            if '-' not in user_input:
                raise ValueError("Format must be start-end (e.g., 2-10).")

            start_str, end_str = user_input.split('-')
            start, end = int(start_str), int(end_str)

            # 2. Strict Bounds Checking
            if start < 1 or end > max_personas or start > end:
                print(f" [!] Range Error: Please ensure numbers are between 1-{max_personas} and start <= end.")
                continue

            # 3. Return 0-indexed slice (Python is 0-indexed, users use 1-indexing)
            return start - 1, end

        except ValueError:
            print(" [!] Invalid format. Please use 'start-end' (e.g., '1-50') or 'all'.")


def run_simulation():
    print("Loading source files...")
    try:
        questionnaire = load_text("Questionnaire.txt")
        response_meaning = load_text("response-meaning-explanation.txt")
        situation_prompt = load_text("SituationExplanationPromptForPersona.txt")
        df = load_personas()
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure your files are in the 'data' folder.")
        return

    survey_results = []

    # Get the specific range from the user
    start_idx, end_idx = get_user_range(len(df))

    # Slice using iloc (inclusive of end_idx by adding 1)
    target_personas = df.iloc[start_idx: end_idx]

    print(f"\nStarting simulation for {len(target_personas)} personas...\n")

    for index, row in target_personas.iterrows():
        persona_name = row['persona_name']
        # index is the original row index from the CSV
        print(f"Processing [Index {index + 1}]: {persona_name}...")

        # 1. Build the prompt
        prompt = build_prompt(row, df.columns, situation_prompt, response_meaning, questionnaire)

        # 2. Get the LLM response
        response_json = get_survey_response(prompt, persona_name)

        # 3. Store the result
        survey_results.append(response_json)

        # 4. Rate Limiting Pause
        time.sleep(3)

    # Compile and save
    print("\nCompiling data...")
    save_results(target_personas, survey_results)


if __name__ == "__main__":
    run_simulation()