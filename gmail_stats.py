import os
import json
import operator
import heapq
from arcadepy import Arcade
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from tools.email_processing import (GmailStatsPercent,
                                    GmailStatsCategoryDetection,
                                    GmailStatsSummary,
                                    GmailStatCategory,
                                    format_email_plain_text,
                                    PROMPTS,
                                    BODY_TEMPLATE)
from typing_extensions import TypedDict
from typing import Annotated, Any


arcade_api_key = os.environ["ARCADE_API_KEY"]
openai_api_key = os.environ["OPENAI_API_KEY"]

# Create a language model instance and bind it with the tools
model = ChatOpenAI(model="gpt-4o", api_key=openai_api_key)
model_with_tools = ChatOpenAI(model="gpt-4o", api_key=openai_api_key)

# Arcade client for direct function calling to gmail


def get_permissions(client: Arcade, provider_to_scopes: dict, user_id: str) -> None:
    """Prompt the user to authorize necessary permissions for each provider."""
    for provider, scopes in provider_to_scopes.items():
        auth_response = client.auth.start(
            user_id=user_id,
            provider=provider,
            scopes=scopes,
        )

        if auth_response.status != "completed":
            print(
                f"Click this link to authorize: {auth_response.authorization_url}")
            input("After you have authorized, press Enter to continue...")


class OverallState(TypedDict):
    arcade_client: Any
    user_id: str
    n_emails: int
    input_emails: list
    processed_emails: Annotated[list, operator.add]


def categorize_email(email_state):
    email_json = json.dumps(email_state["email"], ensure_ascii=False)
    prompt = PROMPTS["categorize_email"].format(email_json=email_json)
    r = model.with_structured_output(
        GmailStatsCategoryDetection).invoke(prompt)
    email_state["category"] = r.category
    return email_state


def summarize_body(email_state):
    importance = email_state["importance"]
    if importance <= 60:
        return email_state
    email_json = json.dumps(email_state["email"], ensure_ascii=False)
    prompt = PROMPTS["summarize_body"].format(email_json=email_json)
    r = model.with_structured_output(GmailStatsSummary).invoke(prompt)
    email_state["summary"] = r.main_points
    return email_state


def determine_importance(email_state):
    spam_likelihood = email_state["spam_likelihood"]
    if spam_likelihood >= 60:
        email_state["importance"] = 0
        return email_state
    email_json = json.dumps(email_state["email"], ensure_ascii=False)
    prompt = PROMPTS["determine_importance"].format(email_json=email_json)
    r = model.with_structured_output(GmailStatsPercent).invoke(prompt)
    email_state["importance"] = r.percent
    return email_state


def process_emails(email):
    email_dict = email["email"]
    email_json = json.dumps(email_dict, ensure_ascii=False)
    prompt = PROMPTS["detect_spam"].format(email_json=email_json)
    r = model.with_structured_output(GmailStatsPercent).invoke(prompt)
    email_state = {"email": email_dict, "spam_likelihood": r.percent}
    email_state = determine_importance(email_state)
    email_state = summarize_body(email_state)
    email_state = categorize_email(email_state)
    return {"processed_emails": [email_state]}


def email_dispatcher(state: OverallState):
    return [
        Send("process_emails", {"email": e}) for e in state["input_emails"]
    ]


def get_emails(state: OverallState):
    user_id = state["user_id"]
    client = state["arcade_client"]
    n_emails = int(state["n_emails"])

    # Get the latest emails
    inputs = {
        "n_emails": n_emails,
    }

    response = client.tools.execute(
        tool_name="Google.ListEmails",
        input=inputs,
        user_id=user_id
    )

    if not response.success:
        raise RuntimeError("response from API was not successful")
    return {"input_emails": response.output.value["emails"]}


def build_report(state: OverallState):
    user_id = state["user_id"]
    client = state["arcade_client"]
    n_emails = int(state["n_emails"])

    top_5_emails = heapq.nlargest(5, state["processed_emails"],
                                  lambda e: e["importance"])
    top_5 = "".join([format_email_plain_text(e) for e in top_5_emails])
    counters = {
        c: 0
        for c in [i.name for i in list(GmailStatCategory)]
    }
    spam_counter = 0
    for email in state["processed_emails"]:
        counters[email["category"].name] += 1
        if email["spam_likelihood"] > 70:
            spam_counter += 1

    spam = ""
    if spam_counter > 1:
        spam = f"{spam_counter} out of {n_emails}"
        spam += f" ({spam_counter/n_emails*100:.2f}%) of all analyzed emails"
        spam += " tagged as SPAM."

    categories_list = ""
    for category, count in sorted(counters.items(),
                                  key=lambda x: x[1], reverse=True):
        if count > 0:
            categories_list += f"- {category}: {count}\n"

    # Get the latest emails
    inputs = {
        "subject": f"Gmail digest (latest {n_emails} emails)",
        "body": BODY_TEMPLATE.format(
            n_emails=n_emails,
            top_5=top_5,
            categories=categories_list,
            spam=spam,
        ),
        "recipient": user_id,
    }

    response = client.tools.execute(
        tool_name="Google.SendEmail",
        input=inputs,
        user_id=user_id
    )

    if not response.success:
        raise RuntimeError("response from API was not successful")


def run(user_id: str,
        n_emails: int):

    client = Arcade()

    # get required permissions
    auth_response = client.auth.start(
        user_id=user_id,
        provider="google",
        scopes=[
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ]
    )

    if auth_response.status != "completed":
        print(
            f"Click this link to authorize: {auth_response.url}")

    # Wait for the authorization to complete
    client.auth.wait_for_completion(auth_response)
    # Create graph
    workflow = StateGraph(OverallState)

    # Add nodes with branching to process all emails in parallel
    workflow.add_node("get_emails", get_emails)
    workflow.add_node("process_emails", process_emails)
    workflow.add_node("build_report", build_report)

    workflow.add_edge(START, "get_emails")
    workflow.add_conditional_edges("get_emails",
                                   email_dispatcher, ["process_emails"])
    workflow.add_edge("process_emails", "build_report")
    workflow.add_edge("build_report", END)

    app = workflow.compile()

    c = 0
    for s in app.stream({"user_id": user_id,
                         "n_emails": n_emails,
                         "arcade_client": client,
                         }):
        if "process_emails" in s:
            d = s["process_emails"]
            c += 1
            print(f'Processing email ({c}/{n_emails}):'
                  f' {d["processed_emails"][0]["email"]["subject"]}')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a summary of the latest gmail entries")
    parser.add_argument("-u", "--user", required=True,
                        help="gmail account to use")
    parser.add_argument("-n", "--n-emails", required=True,
                        type=int,
                        help="number of emails to process")
    args = parser.parse_args()
    run(args.user, args.n_emails)
