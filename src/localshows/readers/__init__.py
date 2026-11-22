"""One reader per way of listing shows."""

from collections.abc import Callable
from datetime import date

from localshows.config import Venue
from localshows.models import Listing
from localshows.readers import bearsville, colony, dice, partition, pearl_moon
from localshows.web import Web

READERS: dict[str, Callable[[Venue, Web, date], list[Listing]]] = {
    "bearsville": bearsville.read,
    "colony": colony.read,
    "dice": dice.read,
    "partition": partition.read,
    "pearl_moon": pearl_moon.read,
}
