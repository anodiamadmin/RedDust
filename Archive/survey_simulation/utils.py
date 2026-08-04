import os
import pandas as pd
from config import DATA_DIR


def load_text(filename):
    """Reads a text file from the data directory."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()


def load_personas(filename="PersonaSociety.csv"):
    """Loads the personas into a Pandas DataFrame."""
    path = os.path.join(DATA_DIR, filename)
    return pd.read_csv(path)


def save_results(original_df, results_list, output_filename="RedDust_Survey_Results.csv"):
    """Merges the original data with the survey scores and saves to CSV."""
    results_df = pd.DataFrame(results_list)
    final_df = pd.concat([original_df, results_df], axis=1)

    path = os.path.join(DATA_DIR, output_filename)
    final_df.to_csv(path, index=False)
    print(f"\n[Success] Results saved to '{path}'")