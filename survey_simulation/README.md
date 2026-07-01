# **RedDust Survey Simulation**

This project simulates customer research interviews for a new wellbeing application called "RedDust." It uses Groq's LLM API to process persona profiles from a CSV dataset and collect survey responses based on the questionnaire provided.

## Prerequisites

Python 3.11 (Recommended)

A Groq API Key

## **Setup Instructions**

1. Clone the repository (skip this step if you are a collaborator)
```Bash
git clone <your-repository-url>
cd survey_simulation
```
2. Create and Activate Virtual Environment
It is highly recommended to use a virtual environment to manage dependencies.

On Windows:
```Bash
python -m venv .venv
.venv\Scripts\activate
```

On macOS/Linux:
```Bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install Requirements
```Bash
pip install -r requirements.txt
```

4. Configuration
You need to provide your API key for the LLM to function.

Create a file named .env in the root directory.

Add your Groq API key to this file:

Plaintext
GROQ_API_KEY=your_api_key_here
(Note: Ensure your .gitignore includes .env to keep your key secure.)

## **How to Run**

### **Running the Simulation**

To generate survey responses for your personas, run the main.py script:

```Bash
python main.py
```
The script will ask you for a range of personas to process (e.g., 1-50 or all).

Results will be saved to data/RedDust_Survey_Results.csv.

### **Running the Visualizer**

To generate a visual heatmap of the responses:

```Bash
python visualize.py
```
This will create an persona_heatmap.html file in the root directory.

Open this file in your browser to interact with the data and see individual persona scores.

## Project Structure

data/: Contains the raw PersonaSociety.csv and generated results.

main.py: The engine that manages the survey workflow.

survey_engine.py: Handles prompts and API communication.

visualize.py: Contains logic to generate interactive heatmaps.

Questionnaire.txt: The survey questions used for the AI personas.

response-meaning-explanation.txt: Defines the scoring logic (1–5 scale).

## Pro-Tips for Success:

Rate Limits: If you hit LLM API rate limits, the script is designed to pause. If you run out of daily tokens, you can resume by running the script again and entering the specific range of personas you haven't processed yet.

Security: Never commit your .env file to Git. Your .gitignore is already set up to prevent this, but always double-check.

Updating: If you get TypeError, make sure to run pip install --upgrade -r requirements.txt.