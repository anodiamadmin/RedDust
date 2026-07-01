import pandas as pd
import plotly.express as px
import os
from config import DATA_DIR


def load_results(filename="RedDust_Survey_Results.csv"):
    path = os.path.join(DATA_DIR, filename)
    return pd.read_csv(path)


def plot_persona_heatmap(df):
    """
    Creates a Heatmap showing every persona's response to every question
    with a monochromatic color scale.
    """
    # 1. Select the Q-columns
    question_cols = [col for col in df.columns if col.startswith("Q") and col[1:].isdigit()]
    question_cols.sort(key=lambda x: int(x[1:]))

    # 2. Prepare data: index by persona_name
    heatmap_data = df.set_index('persona_name')[question_cols]

    # 3. Create the Heatmap
    fig = px.imshow(
        heatmap_data,
        labels=dict(x="Survey Questions", y="User Name", color="Score (1-5)"),
        x=question_cols,
        y=heatmap_data.index,
        color_continuous_scale="Reds",  # Uniform monochromatic scale
        title="Persona-by-Persona Survey Responses (Q1-Q15)",
        text_auto=True
    )

    fig.update_layout(xaxis_side="top")
    fig.write_html("persona_heatmap.html")
    print("[Success] Created 'persona_heatmap.html'")


if __name__ == "__main__":
    try:
        results_df = load_results()
        plot_persona_heatmap(results_df)
        print("\nVisualization generated! Open 'persona_heatmap.html' in your browser.")
    except Exception as e:
        print(f"Error: {e}")