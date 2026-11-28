"""What readers produce (listings) and what the parser turns them into (shows)."""

from dataclasses import dataclass, field
from datetime import date, time


@dataclass(frozen=True)
class Listing:
    """One event, as the venue's site words it."""

    venue: str
    day: date
    start: time | None
    title: str
    url: str
    description: str = ""
    support: str = ""
    lineup: tuple[str, ...] = ()
    # The write-up on the show's own page, used only as evidence for artist matching.
    page_text: str = ""


@dataclass
class Act:
    name: str
    role: str  # "headliner", "opener" or "guest"
    # Other names to try, in order, if the billed name isn't an artist.
    also: list[str] = field(default_factory=list)
    # Covers someone else's music, so only an exact name match is safe.
    tribute: bool = False


@dataclass
class Show:
    listing: Listing
    acts: list[Act] = field(default_factory=list)
    skipped: str = ""

    @property
    def headliner(self) -> Act | None:
        return next((act for act in self.acts if act.role == "headliner"), None)

    @property
    def support(self) -> list[Act]:
        return [act for act in self.acts if act.role != "headliner"]
