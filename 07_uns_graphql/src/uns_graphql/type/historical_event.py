"""
Type of data to be retrieved from the UNS
Events map to a single message in the queue or historization of those messages
"""
import logging

import strawberry

from uns_graphql.type.basetype import JSONPayload

LOGGER = logging.getLogger(__name__)


@strawberry.type
class HistoricalUNSEvent:
    """
    Model of a UNS Events
    """
    # Client id of the what/who published this messages
    published_by: str

    # Timestamp of when this event was published/historied
    timestamp: int

    # Topic
    topic: str

    # Payload
    payload: JSONPayload
