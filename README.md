# Gmail digest 

A sample application that relies on langgraph and Arcade-AI to read and digest 
your inbox.

# How this app works

This app uses a simple LLM graph with multiple agents that assess the following
aspects of your inbox:

1. detects spam
2. determines importance
3. summarizes important emails
4. categorizes all analyzed emails into 6 categories: 
    a. Personal
    b. Work
    c. Official Duties
    d. Marketing and promotions
    e. News and newsletters
    e. Other

The full graph starts by getting the desired number of emails, and dispatching
them in parallel to the agents, which will assign a score or category. Then, 
a report is put together with the annotated emails and sent to the user as an
email.

# Usage

1. Install the requirements
    ```bash
    pip install -r requirements.txt
    pip install --upgrade arcadepy
    ```
    >> This may generate a warning from pip saying that arcadepy > 0.2.2 is not
    >> compatible with langchain-argade, but not upgrading results in a 
    >> `TypeError` being raised when creating the client


2. Set your environment variable
    ```bash
    export ARCADE_API_KEY=<your_key_here>
    ```

3. Run the script
    ```bash
    python gmail_stats.py -u example@gmail.com -n 100
    ```

You'll get an email with the summary!

# Extending the functionality

Adding more capabilities to this digest tool is very simple. Just add more steps
(using LLMs or not) to the `process_emails` function in the 
[gmail_stats.py](gmail_stats.py) script. It would ideally follow the pattern set
by functions such as `determine_importance` or `summarize` body, which receive
a dictionary with the half-processed email, adds a specific key to it, and 
returns it for further processing.
