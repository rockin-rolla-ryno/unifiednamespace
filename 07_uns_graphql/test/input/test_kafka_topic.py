"""*******************************************************************************
* Copyright (c) 2021 Ashwin Krishnan
*
* All rights reserved. This program and the accompanying materials
* are made available under the terms of MIT and  is provided "as is",
* without warranty of any kind, express or implied, including but
* not limited to the warranties of merchantability, fitness for a
* particular purpose and noninfringement. In no event shall the
* authors, contributors or copyright holders be liable for any claim,
* damages or other liability, whether in an action of contract,
* tort or otherwise, arising from, out of or in connection with the software
* or the use or other dealings in the software.
*
* Contributors:
*    -
*******************************************************************************
"""

import pytest
import strawberry
from pydantic import ValidationError
from uns_graphql.input.kafka import KAFKATopic, KAFKATopicInput

# Test data for parameterized tests
test_data_valid = [
    "topic1",
    "level1.level2.level3" "valid_topic_1",
    "another_valid_topic",
    "topic_123_with_underscores",
]

test_data_invalid = [
    "",  # Empty string (fails min_length constraint)
    "topic_with_invalid@character",  # Invalid character (fails pattern constraint)
    "a" * 101,  # Exceeds max_length constraint
    None,  # None value (not a string)
    123,  # Integer (not a string)
    "a/b/c",  # string with slashes (not a string)
]


@pytest.mark.parametrize("topic", test_data_valid)
def test_valid_topics(topic):
    """
    Test valid topics.

    Tests the validation of valid topics using the `KAFKATopic` constructor.

    Args:
    - topic: A string representing a valid topic.

    Raises:
    - pytest.fail: If a validation error occurs for a valid topic.
    """
    try:
        kafka_topic = KAFKATopic(topic=topic)
        assert kafka_topic.topic == topic
    except ValidationError:
        pytest.fail(f"Validation error for valid topic: {topic}")


@pytest.mark.parametrize("topic", test_data_valid)
def test_valid_topics_input(topic):
    """
    Test valid topics for the Strawberry wrapper over the pydantic base

    Tests the validation of valid topics using `KAFKATopicInput.from_pydantic`
    to convert from `KAFKATopic`.

    Args:
    - topic: A string representing a valid topic.

    Raises:
    - pytest.fail: If a validation error occurs for a valid topic.
    """
    try:
        kafka_topic_input = KAFKATopicInput.from_pydantic(KAFKATopic(topic=topic))
        assert kafka_topic_input.topic == topic
    except ValidationError:
        pytest.fail(f"Validation error for valid topic: {topic}")


@pytest.mark.parametrize("topic", test_data_invalid)
def test_invalid_topics(topic):
    """
    Test invalid topic for the Strawberry wrapper over the pydantic base

    Tests the validation of invalid topics using the `KAFKATopic` constructor.

    Args:
    - topic: A value representing an invalid topic.

    Raises:
    - pytest.raises: Expects a validation error for invalid topics.
    """
    with pytest.raises(ValidationError):
        KAFKATopic(topic=topic)


@pytest.mark.parametrize("topic", test_data_invalid)
def test_invalid_topics_input(topic):
    """
    Test invalid topics for input.

    Tests the validation of invalid topics using `KAFKATopicInput.from_pydantic`
    to convert from `KAFKATopic`.

    Args:
    - topic: A value representing an invalid topic.

    Raises:
    - pytest.raises: Expects a validation error for invalid topics.
    """
    with pytest.raises(ValidationError):
        KAFKATopicInput.from_pydantic(KAFKATopic(topic=topic))


@pytest.mark.parametrize(
    "topic",
    test_data_valid,
)
def test_strawberry_type(topic: str):
    @strawberry.type
    class Query:
        @strawberry.field
        def get_topic(self, inputs: KAFKATopicInput) -> str:
            return inputs.topic

    schema = strawberry.Schema(query=Query, types=[KAFKATopicInput])

    input_data = {"topic": f"{topic}"}

    result = schema.execute_sync(
        query="query ($inputs: KAFKATopicInput!) { getTopic(inputs: $inputs) }",  # Update the query here
        root_value=Query(),
        variable_values={"inputs": input_data},
    )

    assert not result.errors
