from __future__ import annotations
from typing import Any, Dict
from guardrails import Guard
from guardrails.hub import ToxicLanguage, ProfanityFree, NSFWText 
from guardrails.hub import LlamaGuard2

# Türkçe "refrain" (reddetme) mesajı
def _turkish_refrain(_: Any, __: Any) -> str:
    return (
        "Üzgünüm, bu konuda yardımcı olamam. "
        "Talebiniz güvenlik ve kullanım ilkelerimizi ihlal ediyor olabilir."
    )

# 1) Kullanıcı girdisi için “input guard”
INPUT_GUARD = Guard().use_many(
    ToxicLanguage(on_fail=_turkish_refrain, validation_method="sentence", threshold=0.50),
    ProfanityFree(on_fail=_turkish_refrain),
    NSFWText(on_fail=_turkish_refrain),
    # Daha katı bir politika istersen (model tabanlı):
    LlamaGuard2(on_fail=_turkish_refrain)
)
# yeniden sorma (reask) istemiyorsak:
INPUT_GUARD.config(num_reasks=0)

OUTPUT_GUARD = Guard.for_string(
    validators=[
        ToxicLanguage(on_fail=_turkish_refrain, validation_method="sentence", threshold=0.50),
        ProfanityFree(on_fail=_turkish_refrain),
        NSFWText(on_fail=_turkish_refrain),
    ]
)
OUTPUT_GUARD.config(num_reasks=0)

# 2) Yapılandırılmış çıktı için “struct guard”
from pydantic import BaseModel, Field
from typing import List, Literal

class SafeGenOut(BaseModel):
    answer: str = Field(
        description="Kullanıcıya nihai cevap (Türkçe).",
        validators=[
            ToxicLanguage(on_fail=_turkish_refrain),
            ProfanityFree(on_fail=_turkish_refrain),
            NSFWText(on_fail=_turkish_refrain),
        ],
    )
    citations: List[str]
    tool: Literal["billing", "roaming", "package", "coverage", "app"]
    intent: Literal["billing", "roaming", "package", "coverage", "app", "other"]
    sentiment: Literal["negative", "neutral", "positive"]

STRUCT_GUARD = Guard.for_pydantic(output_class=SafeGenOut)
STRUCT_GUARD.config(num_reasks=0)
