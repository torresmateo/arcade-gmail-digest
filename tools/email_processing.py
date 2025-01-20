from pydantic import BaseModel
from enum import Enum


class GmailStatsSummary(BaseModel):
    main_points: list[str]


class GmailStatsPercent(BaseModel):
    percent: int


class GmailStatCategory(Enum):
    """The detected category"""
    PERSONAL = "Personal"
    WORK = "Work"
    DUTIES = "Official duties"
    ADS = "Marketing and promotions"
    NEWS = "News and newsletters"
    OTHER = "Other"


class GmailStatsCategoryDetection(BaseModel):
    category: GmailStatCategory


PROMPTS = {
    "detect_spam": "You are an expert e-mail assistant, please assess whether the following email is spam or not."
    " Your output must be a single number from 0 to 100, indicating the probability you give to the email"
    " being spam (0 meaning not spam, 100 meaning absolute certainty to be spam)"
    "\nHere's the email in JSON format: {email_json}",

    "determine_importance": "You are an expert e-mail assistant, please assess whether the following email is important or not."
    " Your output must be a single number from 0 to 100, indicating the probability you give to the email"
    " being important (0 meaning not important, 100 meaning critically important and/or urgent)"
    "\nHere's the email in JSON format: {email_json}",

    "summarize_body": "This is an important email, please summarize in 3 bullet points that encapsulate the most"
    " important points of the emails. Prioritize any deadlines or actions that the recipient of the email has to do"
    "\nHere's the email in JSON format: {email_json}",

    "categorize_email": "Please categorize this email in one of the following categories: "
    " 1. Personal"
    " 2. Work"
    " 3. Official Duties"
    " 4. Marketing and promotions"
    " 5. News and newsletters"
    " 6. Other\n\n"
    " If there are multiple matching categories, choose the most appropriate one."
    "\nHere's the email in JSON format: {email_json}",
}

BODY_TEMPLATE = """Your Gmail digest

After analyzing {n_emails} on your behalf, here's a summary:

The top 5 most important/urgent
{top_5}

Here's the distribution of detected categories
{categories}

{spam}

generated with https://www.arcade-ai.com
"""


def format_email_plain_text(email):
    pt = """
from: {f}
date: {date}
subject: {subject}
summary:
    {summary}

"""
    return pt.format(f=email["email"]["from"],
                     subject=email["email"]["subject"],
                     date=email["email"]["date"],
                     summary="\n    ".join(email["summary"]),
                     )
