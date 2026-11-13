"""Infrastructure-as-code files told apart by what they say near their top."""
from __future__ import annotations


def is_cloudformation(head: str) -> bool:
    """Whether the start of a YAML or JSON file is a CloudFormation template (the version key, or resources of
    an `AWS::` type; SAM and CDK output are templates too)."""
    return "AWSTemplateFormatVersion" in head or ("AWS::" in head and "Resources" in head)
