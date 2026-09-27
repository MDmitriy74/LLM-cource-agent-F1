import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
MODEL = os.environ["MODEL_CHEAP"]

SYSTEM = """You answer questions using a movie quote database.

Work in a loop and use exactly this format:

Thought: what you need to find out
Action: find_movie_quote("<query>")
Observation: <what the tool returned>

When you know the answer, reply with:

Final Answer: <your answer>
"""

STOP_RULE = "\nAfter the Action line STOP and wait: never write the Observation yourself."
QUESTION = "Which movie features a character saying something about kung fu?"

MOVIES = [
    ("The Matrix", "I know kung fu", "Neo"),
    ("Star Wars", "May the Force be with you", "Obi-Wan Kenobi"),
    ("The Terminator", "I'll be back", "T-800"),
    ("Jurassic Park", "Life finds a way", "Ian Malcolm"),
    ("Titanic", "I'm the king of the world", "Jack Dawson"),
    ("The Godfather", "I'm going to make him an offer he can't refuse", "Vito Corleone"),
]


def find_movie_quote(argument: str) -> str:
    needle = argument.strip().lower()
    hits = [
        f"Movie: {title} | Quote: '{quote}' | Character: {char}"
        for title, quote, char in MOVIES
        if needle in title.lower() or needle in quote.lower() or needle in char.lower()
    ]
    if not hits:
        return f"No match for {argument!r}. Try a single keyword, for example: matrix, force, terminator."
    return "; ".join(hits)


TOOL = find_movie_quote


def parse_action(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Action:") and "(" in line:
            return line[line.index("(") + 1 : line.rindex(")")].strip().strip("\"'")
    return None

def cut_at_observation(text: str) -> str:
    marker = text.find("Observation:")
    return text if marker == -1 else text[:marker].rstrip()


def run(honest: bool = True, steps: int = 5) -> list[str]:
    messages = [{"role": "system", "content": SYSTEM + (STOP_RULE if honest else "")},
                {"role": "user", "content": QUESTION}]
    transcript = [f"Question: {QUESTION}"]
    for _ in range(steps):
        answer = client.chat.completions.create(
            # pre-set high: hidden reasoning is billed from this budget too
            model=MODEL, messages=messages, max_completion_tokens=2000
        )
        choice = answer.choices[0]
        reply = choice.message.content or ""
        # a budget bug, not a parser bug: name it
        if not reply and choice.finish_reason == "length":
            raise RuntimeError(
                "Empty reply at the length limit: the budget went on hidden "
                "reasoning, not on your parser. Raise max_completion_tokens."
            )
        if honest:
            reply = cut_at_observation(reply)
        transcript.append(reply)
        print(reply)

        argument = parse_action(reply)
        if argument is None:
            break
        observation = f"Observation: {TOOL(argument)}"
        transcript.append(observation)
        print(observation)
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": observation})
    return transcript


if __name__ == "__main__":
    # --break removes both safeties: the second transcript you commit
    run(honest="--break" not in sys.argv)
