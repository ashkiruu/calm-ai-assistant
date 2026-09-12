"""Deterministic scope classification for a learner question.

The learner's speech is never a routing authority.  This module only reads the
question to decide *which curated evidence may be searched*, never to decide what
is safe.  Classification is keyword based on purpose: it must be inspectable by a
reviewer and testable without invoking a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


DISASTER_TERMS = {
    "alarm", "aftershock", "bagyo", "baha", "cover", "disaster",
    "earthquake", "emergency", "evacuate", "evacuation", "exit", "fire",
    "flood", "hazard", "inside", "labas", "leave", "lindol", "ligtas",
    "manatili", "move", "outside", "pumunta", "route", "run", "sakuna",
    "safe", "safety", "shaking", "shelter", "smoke", "stay", "sunog",
    "storm", "takbo", "teacher", "typhoon", "ulan", "warning",
    # drop-cover-hold vocabulary a learner uses without naming the hazard
    "danger", "delikado", "hold", "protect", "protektahan",
    # Filipino and Taglish safety vocabulary.  A learner asking in Filipino was
    # being refused outright, which is the worst failure this gate can produce:
    # a real safety question turned away as off-topic.
    "alarma", "apoy", "assembly", "bago", "bintana", "drill", "duck",
    "ensayo", "evacuation", "habang", "labasan", "lamesa", "lumabas",
    "magtago", "mesa", "pagbaha", "pagkatapos", "pagyanig", "panganib",
    "peligro", "ruta", "saklolo", "salamin", "signal", "silong", "sugat",
    "sugatan", "sumilong", "takip", "tulong", "tulungan", "tumakbo", "ulo",
    "umalis", "usok", "yanig",
}
#: Below this length a shared prefix or suffix is coincidence, not morphology.
MIN_MORPHOLOGICAL_MATCH = 4

#: Filipino function words. Content words are a poor signal here because the
#: corpus itself mixes English safety terms into Filipino sentences; the little
#: words are what actually mark which language a child is speaking.
FILIPINO_FUNCTION_WORDS = {
    "ako", "akong", "ang", "ano", "anong", "at", "ay", "ba", "bakit", "dapat",
    "din", "dito", "gagawin", "ganyan", "gawin", "ito", "iyong", "ka",
    "kailangan", "kapag", "ko", "kong", "kung", "may", "mga", "mo", "na",
    "nang", "ng", "ngayon", "ni", "nila", "paano", "pano", "para", "pwede",
    "sa", "saan", "sino", "yung",
}
#: English function words that a Taglish sentence keeps even when the frame is
#: Filipino. Used only to tell Taglish apart from pure Filipino.
ENGLISH_FUNCTION_WORDS = {
    "a", "and", "are", "can", "do", "does", "how", "i", "is", "it", "me", "my",
    "should", "the", "to", "what", "when", "where", "why", "you", "your",
}
GENERIC_SAFETY_QUESTIONS = {
    "what should i do", "what do i do", "where should i go", "ano ang gagawin",
    "ano gagawin", "saan ako pupunta", "help me", "tulungan mo ako",
    # Filipino phrasings of the same few questions a frightened child asks.
    # These carry no hazard word at all, so without them the commonest question
    # in the language is refused as off-topic.
    "ano ang dapat", "anong dapat", "dapat kong gawin", "dapat gawin",
    "anong gagawin", "anong gawin", "ano ang gagawin ko", "paano ako",
    "paano ko", "ligtas ba", "safe ba", "delikado ba", "bakit kailangan",
    "ano ang mangyayari", "saan ako", "pwede ba ako", "kailangan ko bang",
}
HAZARD_TERMS = {
    "earthquake": {"earthquake", "lindol", "shaking", "aftershock"},
    "fire": {"fire", "sunog", "smoke", "apoy"},
    "typhoon": {"typhoon", "bagyo", "storm", "flood", "baha"},
}
PHASE_TERMS = {
    "before": {"before", "bago", "prepare", "preparing", "ready", "handa",
               "paghahanda", "practice", "drill"},
    # "now/ngayon" asks for the current task; it does not claim that the
    # disaster is in its during phase. Likewise "next/susunod" asks for the
    # next task step rather than naming the after phase. Treating those generic
    # dialogue words as trusted phase intent pulled learners away from the task
    # they were actually standing in.
    "during": {"during", "habang", "happening", "nangyayari"},
    "after": {"after", "pagkatapos", "later", "mamaya",
              "stopped", "tumigil", "over", "tapos", "finish", "finished"},
}

SCOPE_ON_TASK = "on_task"
SCOPE_IN_HAZARD_OFF_TASK = "in_hazard_off_task"
SCOPE_CROSS_HAZARD = "cross_hazard"
SCOPE_OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class QuestionScope:
    """How a learner question relates to the task the learner is standing in."""

    scope: str
    asked_hazard: str | None = None
    asked_phase: str | None = None

    @property
    def is_answerable(self) -> bool:
        return self.scope != SCOPE_OUT_OF_SCOPE


def _normalize_words(question: str) -> set[str]:
    """Casefold to bare words and fold a single trailing plural 's'.

    Without the plural fold, 'earthquakes' misses DISASTER_TERMS entirely and a
    real safety question is misread as off-topic.
    """

    words = set(re.findall(r"[a-zA-Z]+", question.casefold()))
    singulars = {word[:-1] for word in words if len(word) > 3 and word.endswith("s")}
    return words | singulars


def detect_locale(question: str, default: str = "en-PH") -> str:
    """Answer in the language the child actually asked in.

    Making a nine-year-old set a dropdown before every question is a tax on the
    learner, and one they will forget to pay. A question with Filipino function
    words gets a Filipino answer; one that mixes both gets Taglish, which is how
    the question was asked in the first place.
    """

    words = {word for word in re.findall(r"[a-zA-Z]+", question.casefold())}
    if not words:
        return default
    filipino = words & FILIPINO_FUNCTION_WORDS
    if not filipino:
        return default
    # Real English words alongside a Filipino frame is Taglish, not Filipino.
    # 'What if may lindol?' should not be answered in pure Filipino.
    english = words & ENGLISH_FUNCTION_WORDS
    return "taglish-PH" if english else "fil-PH"


def question_hazard(question: str) -> str | None:
    """Return the single hazard the question names, or None when ambiguous.

    Terms are matched as whole words.  Substring matching reads 'baha' (flood)
    inside 'bahay' (house), which turns an ordinary Filipino question about the
    home into a typhoon question.
    """

    words = _normalize_words(question)
    matches = [
        hazard for hazard, terms in HAZARD_TERMS.items() if words & terms
    ]
    return matches[0] if len(matches) == 1 else None


def question_phase(question: str) -> str | None:
    """Return the single lesson stage the question names, or None when ambiguous."""

    words = _normalize_words(question)
    matches = [phase for phase, terms in PHASE_TERMS.items() if words & terms]
    return matches[0] if len(matches) == 1 else None


#: Subjects that are plainly not disaster safety. The gate fails open, so this
#: is the only thing that can produce a refusal: a question is turned away when
#: it names one of these, never merely because it failed to name a hazard.
#:
#: Requiring positive evidence of being off-topic is the opposite of the earlier
#: design, and it is the right way round. "Why should I not touch it?" names no
#: hazard, and refusing it taught the child that asking was pointless. Sending a
#: stray question to the model costs a few hundred milliseconds and a reply that
#: says it does not have enough information; refusing a real one costs trust.
OFF_TOPIC_MARKERS = {
    # entertainment and play
    "artista", "basketball", "cartoon", "dance", "football", "game", "joke",
    "kanta", "laro", "laruan", "movie", "music", "player", "sing", "song",
    "sport", "toy", "tv", "video",
    # food
    "cake", "candy", "chocolate", "food", "kain", "pagkain", "pizza",
    # school subjects unrelated to safety
    "algebra", "capital", "divided", "history", "math", "multiply", "plus",
    "spelling", "subtract", "times",
    # personal favourites and small talk
    "colour", "color", "favorite", "favourite", "paborito",
}


def _off_topic_hit(words: set[str]) -> bool:
    return bool(words & OFF_TOPIC_MARKERS)


def _morphological_hit(words: set[str]) -> bool:
    """True when a word shares a stem with a safety term.

    Filipino inflects heavily and learners compound freely, so 'lumilindol'
    and 'after the shock' are safety questions that no exact-match list will
    ever contain.  Comparing whole-word endings catches those without the
    substring matching that once read 'baha' inside 'bahay'.
    """

    return any(
        term.endswith(word) or word.endswith(term)
        for word in words
        if len(word) >= MIN_MORPHOLOGICAL_MATCH
        for term in DISASTER_TERMS
        if len(term) >= MIN_MORPHOLOGICAL_MATCH
    )


def question_in_scope(question: str) -> bool:
    """True when the question is about disaster preparation or response.

    An empty question is in scope: the learner is following the simulation cue
    rather than asking anything, and the caller still owes them an instruction.
    """

    if not question.strip():
        return True
    lowered = question.casefold()
    words = _normalize_words(question)
    return (
        bool(words & DISASTER_TERMS)
        or any(phrase in lowered for phrase in GENERIC_SAFETY_QUESTIONS)
        or _morphological_hit(words)
    )


def classify(
    question: str,
    *,
    task_hazard: str | None,
    task_phase: str | None,
) -> QuestionScope:
    """Place a question relative to the active task before any retrieval runs."""

    # The gate fails open. A question is refused only when it names a plainly
    # unrelated subject, not merely because it failed to name a hazard: no word
    # list covers every way a nine-year-old asks about safety, and every gap in
    # one turned a real question away.
    words = _normalize_words(question)
    if not question_in_scope(question) and _off_topic_hit(words):
        return QuestionScope(SCOPE_OUT_OF_SCOPE)

    asked_hazard = question_hazard(question)
    asked_phase = question_phase(question)

    if asked_hazard and asked_hazard != task_hazard:
        return QuestionScope(SCOPE_CROSS_HAZARD, asked_hazard, asked_phase)

    if asked_phase and asked_phase != task_phase:
        return QuestionScope(SCOPE_IN_HAZARD_OFF_TASK, asked_hazard, asked_phase)

    return QuestionScope(SCOPE_ON_TASK, asked_hazard, asked_phase)


__all__ = [
    "DISASTER_TERMS",
    "GENERIC_SAFETY_QUESTIONS",
    "HAZARD_TERMS",
    "PHASE_TERMS",
    "QuestionScope",
    "SCOPE_CROSS_HAZARD",
    "SCOPE_IN_HAZARD_OFF_TASK",
    "SCOPE_ON_TASK",
    "SCOPE_OUT_OF_SCOPE",
    "classify",
    "detect_locale",
    "question_hazard",
    "question_in_scope",
    "question_phase",
]
