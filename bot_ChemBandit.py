"""

BOT_NAME="KnowledgeTest"; modal deploy --name $BOT_NAME bot_${BOT_NAME}.py; curl -X POST https://api.poe.com/bot/fetch_settings/$BOT_NAME/$POE_ACCESS_KEY

There are three states in the conversation
- Before getting the problem
- After getting the problem, before making a submission
- After making a submission
"""

from __future__ import annotations

import re
from typing import AsyncIterable, Any

import fastapi_poe as fp
import pandas as pd
import io
from fastapi_poe.types import PartialResponse, ProtocolMessage
from modal import Dict
from datetime import datetime
import pytz

cid_to_current_question: dict[str, dict[str]] = Dict.from_name("dict-ChemBandit-cid_to_current_question", create_if_missing=True)
uid_to_history: dict[str, tuple[int, str, str]] = Dict.from_name("dict-ChemBandit-uid_to_history", create_if_missing=True)  # for bandit calculation purposes, uid -> id, correctness, response
uid_to_all_history: dict[str, list[dict[str, Any]]] = Dict.from_name("dict-ChemBandit-uid_to_all_history4", create_if_missing=True)  # for logging purposes

df = pd.read_csv("questions_and_answers.csv")

pst = pytz.timezone('America/Los_Angeles')  # PST
sgt = pytz.timezone('Asia/Singapore')       # Singapore Time

with open("syllabus.txt") as f:
    syllabus_text = f.read()

TEMPLATE_STARTING_REPLY = """
Learning outcome: **{learning_outcome}**

{question}
""".strip()


FREEFORM_SYSTEM_PROMPT = """
You will assess whether the Singapore A-level student has correctly answered the question.

This is the Singapore A-level syllabus

<syllabus>
{syllabus}
</syllabus>

This is the question
<question>
{question}
</question>

The reference answer is
<reference_answer>
{reference_answer}
</reference_answer>

The student is expected to reply with the answer.

You will begin your response with exactly either of (without the bullet point)
- Your answer is correct.
- Your answer is partially correct.
- Your answer is incorrect.

Then, after two new lines, display the reference answer. Do NOT edit the reference answer.

Then, after two new lines, you will explain where the student is correct, and where the student is incorrect.
Prefer to split the explanation across multiple bullet points where possible.

Strongly prefer nomenclature and concepts that are found in the syllabus or the reference answer.
Use unicode characters (e.g. ₂) instead of HTML tags (e.g. <sub>2</sub>) for subscripts.
Refer to the glossary of terms to determine whether the student has sufficiently answered the question. (But do not mention "glossary of terms")
Make sure the student is actually answering the question, and not just copying answers without adapting to the context.

Reply in this format:

Your answer is correct / partially correct / incorrect.

Reference answer: (the reference answer as stated in <reference_answer> and </reference_answer>. Do NOT edit the reference answer.)

Where you are correct (try to find something that the student is correct even if the answer is mostly wrong)
- (one thing that the student is correct)
- (one thing that the student is correct)
- ...

Where you are incorrect (not necessary if the student is fully correct)
- (one thing that the student is missing or wrong in their answer)
- (one thing that the student is missing or wrong in their answer)
- ...
"""

SUGGESTED_REPLIES_SYSTEM_PROMPT = """
You will suggest replies based on the conversation given by the student.
"""

SUGGESTED_REPLIES_USER_PROMPT = """
Read the conversation above.

Suggest three questions the student would ask to learn more about the topic.
Each question should only ask one thing, phrased in the most concise and readable way possible.

Begin each suggestion with <a> and end each suggestion with </a>.
Do not use inverted commas. Do not prefix each suggestion.
""".strip()

PASS_STATEMENT = "I will pass this question."

NEXT_STATEMENT = "I want another question."

HISTORY_STATEMENT = "history"

SUGGESTED_REPLIES_REGEX = re.compile(r"<a>(.+?)</a>", re.DOTALL)


def extract_suggested_replies(raw_output: str) -> list[str]:
    suggested_replies = [
        suggestion.strip() for suggestion in SUGGESTED_REPLIES_REGEX.findall(raw_output)
    ]
    return suggested_replies


def stringify_conversation(messages: list[ProtocolMessage]) -> str:
    stringified_messages = ""

    # Gemini-Flash just suggests nonsense the conversation is too long
    for message in messages[::-1][:5][::-1]:
        if message.role == "system":
            stringified_messages += f"System: {message.content}\n\n"
        elif message.role == "bot":
            stringified_messages += f"Teacher: {message.content}\n\n"
        else:
            # NB: as commit the system prompt is injected somewhere in the user prompt
            stringified_messages += f"Student: {message.content}\n\n"
    return stringified_messages


class KnowledgeTestBot(fp.PoeBot):
    async def get_response(
        self, request: fp.QueryRequest
    ) -> AsyncIterable[fp.PartialResponse]:
        history_to_log = {}
        last_user_reply = request.query[-1].content
        history_to_log["user_id"] = request.user_id
        history_to_log["conversation_id"] = request.conversation_id
        history_to_log["last_user_reply"] = last_user_reply

        utc_now = datetime.now(pytz.utc)
        pst_time = utc_now.astimezone(pst).strftime('%Y-%m-%d %I:%M:%S %p')
        sgt_time = utc_now.astimezone(sgt).strftime('%Y-%m-%d %I:%M:%S %p')
        history_to_log["utc_now"] = utc_now
        history_to_log["pst_time"] = pst_time
        history_to_log["sgt_time"] = sgt_time

        print(last_user_reply)

        if last_user_reply == HISTORY_STATEMENT and request.user_id in uid_to_all_history:
            # If you want to get history from all users either read from `modal dict` or implement a backdoor
            all_history = uid_to_all_history[request.user_id]
            df_history = pd.DataFrame(all_history)

            buffer = io.BytesIO()
            df_history.to_csv(buffer, index=False)
            file_data = buffer.getvalue()

            _ = await self.post_message_attachment(
                message_id=request.message_id,
                file_data=file_data,
                filename="history.csv",
            )
 
            df_truncated = df_history[["learning_outcome", "question", "reference_answer", "last_user_reply"]]

            buffer = io.BytesIO()
            df_truncated.to_csv(buffer, index=False)
            file_data = buffer.getvalue()

            _ = await self.post_message_attachment(
                message_id=request.message_id,
                file_data=file_data,
                filename="history.csv",
            )

            # make this look nice if you want
            html_table = df_truncated.to_html(index=False)
            yield self.text_event(f"```html\n<html>\n{html_table}\n</html>\n```")
            return

        # reset if the user passes or asks for the next statement
        if last_user_reply in (NEXT_STATEMENT, PASS_STATEMENT):
            if request.conversation_id in cid_to_current_question:
                cid_to_current_question.pop(request.conversation_id)

        # for new conversations, sample a problem
        if request.conversation_id not in cid_to_current_question:
            question_info: dict[str] = df.sample(n=1).to_dict(orient="records")[0]
            cid_to_current_question[request.conversation_id] = question_info

            yield self.text_event(
                TEMPLATE_STARTING_REPLY.format(
                    learning_outcome=question_info["learning_outcome"],
                    question=question_info["question"],
                )
            )

            yield PartialResponse(text=PASS_STATEMENT, is_suggested_reply=True)
            return

        # retrieve the previously cached question
        question_info = cid_to_current_question[request.conversation_id]
        history_to_log["question_info"] = question_info
        for key, value in question_info.items():
            history_to_log[key] = value
        history_to_log["actual_conversation_history"] = str(request.query)

        # inject system prompt
        request.query = [
            ProtocolMessage(
                role="system",
                content=FREEFORM_SYSTEM_PROMPT.format(
                    syllabus=syllabus_text,
                    question=question_info["question"],
                    reference_answer=question_info["reference_answer"],
                ),
            )
        ] + request.query

        # inject system prompt again
        if len(request.query) >= 5:
            # Gemini-Flash just drops the system prompt when the conversation is long
            request.query = request.query[:-3] + [
                ProtocolMessage(
                    role="user",
                    content=FREEFORM_SYSTEM_PROMPT.format(
                        syllabus=syllabus_text,
                        question=question_info["question"],
                        reference_answer=question_info["reference_answer"],
                    ),
                )
            ] + request.query[-3:]
        history_to_log["simulated_converation_history"] = str(request.query)

        bot_reply = ""
        async for msg in fp.stream_request(request, "Gemini-1.5-Flash", request.access_key):
            bot_reply += msg.text
            yield msg.model_copy()
        print(bot_reply)
        history_to_log["bot_reply"] = bot_reply

        # generate suggested replies
        request.query = request.query + [ProtocolMessage(role="bot", content=bot_reply)]
        current_conversation_string = stringify_conversation(request.query)

        request.query = [
            ProtocolMessage(role="system", content=SUGGESTED_REPLIES_SYSTEM_PROMPT),
            ProtocolMessage(role="user", content=current_conversation_string),
            ProtocolMessage(role="user", content=SUGGESTED_REPLIES_USER_PROMPT),
        ]
        response_text = ""
        async for msg in fp.stream_request(request, "Gemini-1.5-Flash", request.access_key):
            response_text += msg.text
        print("suggested_reply", response_text)

        suggested_replies = extract_suggested_replies(response_text)
        history_to_log["suggested_replies"] = suggested_replies

        for suggested_reply in suggested_replies[:3]:
            yield PartialResponse(text=suggested_reply, is_suggested_reply=True)
        yield PartialResponse(text=NEXT_STATEMENT, is_suggested_reply=True)

        all_history = uid_to_all_history.get(request.user_id, [])
        all_history.append(history_to_log)
        uid_to_all_history[request.user_id] = all_history
        return

    async def get_settings(self, setting: fp.SettingsRequest) -> fp.SettingsResponse:
        return fp.SettingsResponse(
            server_bot_dependencies={"Gemini-1.5-Flash": 2},
            introduction_message="Say 'start' to get question in Chemistry.",
        )
