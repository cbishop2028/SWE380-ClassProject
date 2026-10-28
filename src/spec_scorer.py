import re
from typing import Dict, Any, List

class SpecQualityScorer:
    """
    Evaluates the quality of specification text based on acceptance criteria,
    structured scenarios, and source file references.
    """
    
    AC_PATTERNS = [
        re.compile(r"acceptance\s+criteria", re.IGNORECASE),
        re.compile(r"definition\s+of\s+done", re.IGNORECASE),
        re.compile(r"expected\s+behavior", re.IGNORECASE),
        re.compile(r"- \[[ xX]\]"),  # Checkboxes
    ]
    
    SCENARIO_PATTERNS = [
        re.compile(r"\b(given|when|then|and|but)\b", re.IGNORECASE),
        re.compile(r"scenario:", re.IGNORECASE),
        re.compile(r"```(json|python|js|ts|bash|yaml)?\n[\s\S]*?\n```"), # Code blocks
    ]
    
    FILE_REF_PATTERNS = [
        re.compile(r"`[^`]+\.(py|js|ts|java|cpp|go|rs|rb|php|sql|md|json|yml|yaml)`"),
        re.compile(r"(?:src|lib|app|components|tests?)/[a-zA-Z0-9_\-/\.]+\.[a-zA-Z0-9]+"),
    ]

    def __init__(self, ac_weight: float = 0.4, scenario_weight: float = 0.3, file_ref_weight: float = 0.3):
        self.ac_weight = ac_weight
        self.scenario_weight = scenario_weight
        self.file_ref_weight = file_ref_weight

    def score_acceptance_criteria(self, text: str) -> float:
        matches = sum(len(p.findall(text)) for p in self.AC_PATTERNS)
        return min(1.0, matches / 3.0)

    def score_scenarios(self, text: str) -> float:
        kw_matches = sum(len(p.findall(text)) for p in self.SCENARIO_PATTERNS)
        list_items = len(re.findall(r"^\s*\d+\.\s+", text, re.MULTILINE))
        total_signal = kw_matches + (0.5 * list_items)
        return min(1.0, total_signal / 4.0)

    def score_file_references(self, text: str) -> float:
        file_matches = sum(len(p.findall(text)) for p in self.FILE_REF_PATTERNS)
        return min(1.0, file_matches / 2.0)

    def evaluate_spec(self, spec_text: str) -> Dict[str, Any]:
        if not spec_text or not str(spec_text).strip():
            return {
                "total_score": 0.0,
                "ac_score": 0.0,
                "scenario_score": 0.0,
                "file_ref_score": 0.0,
                "word_count": 0
            }

        text = str(spec_text)
        ac_score = self.score_acceptance_criteria(text)
        scenario_score = self.score_scenarios(text)
        file_ref_score = self.score_file_references(text)

        total_score = (
            (ac_score * self.ac_weight) +
            (scenario_score * self.scenario_weight) +
            (file_ref_score * self.file_ref_weight)
        )

        return {
            "total_score": round(total_score, 4),
            "ac_score": round(ac_score, 4),
            "scenario_score": round(scenario_score, 4),
            "file_ref_score": round(file_ref_score, 4),
            "word_count": len(text.split())
        }