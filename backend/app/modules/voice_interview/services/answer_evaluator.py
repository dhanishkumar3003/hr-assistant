from abc import ABC, abstractmethod
from typing import TypedDict
import json
from groq import Groq


class AnswerScores(TypedDict):
    relevance: float
    content_depth: float
    structure_clarity: float
    fluency: float
    pacing_wpm: float
    composite: float
    feedback: str


class IAnswerEvaluator(ABC):
    @abstractmethod
    def evaluate(self, question: str, transcript: str, start_ts: float, end_ts: float) -> AnswerScores:
        ...


SCORE_PROMPT = """You are evaluating a candidate's spoken interview answer, given only the transcript.
Score 0-10 on each dimension below. Do not infer confidence, tone, or emotion — you only have text, not audio.

Question: {question}
Transcript: {transcript}

Return ONLY valid JSON, no other text:
{{
  "relevance": <0-10>,
  "content_depth": <0-10>,
  "structure_clarity": <0-10>,
  "fluency": <0-10>,
  "feedback": "<one neutral, factual sentence>"
}}
"""


class GroqAnswerEvaluator(IAnswerEvaluator):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        self.client = Groq(api_key=api_key)
        self.model = model

    def evaluate(self, question: str, transcript: str, start_ts: float, end_ts: float) -> AnswerScores:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": SCORE_PROMPT.format(question=question, transcript=transcript)}],
            temperature=0,
        )
        parsed = json.loads(response.choices[0].message.content)

        word_count = len(transcript.split())
        duration_minutes = max((end_ts - start_ts) / 60, 0.01)
        pacing_wpm = round(word_count / duration_minutes, 1)
        pacing_score = min(pacing_wpm / 130, 1) * 10

        composite = round(
            parsed["relevance"] * 0.30
            + parsed["content_depth"] * 0.25
            + parsed["structure_clarity"] * 0.20
            + parsed["fluency"] * 0.15
            + pacing_score * 0.10,
            1,
        )

        return {
            "relevance": parsed["relevance"],
            "content_depth": parsed["content_depth"],
            "structure_clarity": parsed["structure_clarity"],
            "fluency": parsed["fluency"],
            "pacing_wpm": pacing_wpm,
            "composite": composite,
            "feedback": parsed["feedback"],
        }


def get_answer_evaluator() -> IAnswerEvaluator:
    import os
    return GroqAnswerEvaluator(api_key=os.environ["GROQ_API_KEY"])