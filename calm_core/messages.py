"""Reviewed learner-facing fallback strings shared by every CALM answer path.

These strings are the deterministic voice of the assistant.  They are used
whenever the router or the RAG service declines to generate an answer, so they
must stay short, calm, and Grade 4 readable in all three supported locales.
"""

from __future__ import annotations


#: A deferral is the card's own reviewed instruction plus one of these lines,
#: and the headset subtitle band holds about 115 characters before it overruns
#: (MissionHUD.cs:114).  The instruction is already most of that budget, so the
#: added line stays short: the safety cue is what the child must read, and the
#: promise that their question will be answered is a reassurance, not the point.
FALLBACKS = {
    "en-PH": {
        "missing": "I need the current VR safety state. Stay with your teacher while the simulation checks it.",
        "conflict": "The safety information does not match. Stay with your teacher and wait for the corrected instruction.",
        "critical_no_protocol": "I do not have a matching approved instruction for this active earthquake state. Stay low, protect your head and neck, do not run, and stay with your teacher or responsible adult while the simulation checks the safety state.",
        "no_card": "Stay in the current safe place with your teacher and wait for the next approved instruction.",
        "no_route": "The simulation has no approved open route right now. Stay with your teacher and do not choose your own exit.",
        "outside": "CALM helps with disaster preparation and emergency-response learning. Please ask a safety question.",
        "general": "General disaster information: ",
        "defer_cross_hazard": "We will learn about that later.",
        "no_relevant_evidence": "I do not have an approved answer for that yet. Please ask your teacher.",
    },
    "fil-PH": {
        "missing": "Kailangan ko ang kasalukuyang VR safety state. Manatili sa guro habang sinusuri ito ng simulation.",
        "conflict": "Hindi nagtutugma ang safety information. Manatili sa guro at hintayin ang tamang instruction.",
        "critical_no_protocol": "Wala akong tugmang aprubadong tagubilin para sa aktibong lindol na ito. Manatiling mababa, protektahan ang ulo at batok, huwag tumakbo, at manatili sa guro o responsableng nakatatanda habang sinusuri ng simulation ang safety state.",
        "no_card": "Manatili sa kasalukuyang ligtas na lugar kasama ang guro at hintayin ang susunod na tamang instruction.",
        "no_route": "Walang aprubadong bukas na ruta ang simulation ngayon. Manatili sa guro at huwag pumili ng sariling labasan.",
        "outside": "Ang CALM ay para sa paghahanda sa sakuna at pag-aaral ng emergency response. Magtanong tungkol sa kaligtasan.",
        "general": "Pangkalahatang impormasyon sa sakuna: ",
        "defer_cross_hazard": "Pag-aaralan natin iyon mamaya.",
        "no_relevant_evidence": "Wala pa akong aprubadong sagot diyan. Itanong mo sa iyong guro.",
    },
    "taglish-PH": {
        "missing": "Kailangan ko ang current VR safety state. Stay with your teacher habang chine-check ito ng simulation.",
        "conflict": "Hindi tugma ang safety information. Stay with your teacher at hintayin ang corrected instruction.",
        "critical_no_protocol": "Wala akong matching approved instruction para sa active earthquake state na ito. Stay low, protect your head and neck, huwag tumakbo, at stay with your teacher or responsible adult habang chine-check ng simulation ang safety state.",
        "no_card": "Stay sa current safe place with your teacher at hintayin ang next approved instruction.",
        "no_route": "Walang approved open route ang simulation ngayon. Stay with your teacher at huwag pumili ng sariling exit.",
        "outside": "CALM helps with disaster preparation and emergency-response learning. Ask a safety question.",
        "general": "General disaster information: ",
        "defer_cross_hazard": "Pag-aaralan natin iyon later.",
        "no_relevant_evidence": "Wala pa akong approved na sagot diyan. Ask your teacher about it.",
    },
}

__all__ = ["FALLBACKS"]
