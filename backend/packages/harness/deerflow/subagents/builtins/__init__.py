"""Built-in subagent configurations."""

from .bash_agent import BASH_AGENT_CONFIG
from .deep_document_analyzer import DEEP_DOCUMENT_ANALYZER_CONFIG
from .document_downloader_agent import DOCUMENT_DOWNLOADER_AGENT_CONFIG
from .general_purpose import GENERAL_PURPOSE_CONFIG
from .parameter_classifier_agent import PARAMETER_CLASSIFIER_AGENT_CONFIG
from .parameter_searching_agent import PARAMETER_SEARCHING_AGENT_CONFIG

__all__ = [
    "GENERAL_PURPOSE_CONFIG",
    "BASH_AGENT_CONFIG",
    "DOCUMENT_DOWNLOADER_AGENT_CONFIG",
    "PARAMETER_CLASSIFIER_AGENT_CONFIG",
    "PARAMETER_SEARCHING_AGENT_CONFIG",
    "DEEP_DOCUMENT_ANALYZER_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
    "document-downloader-agent": DOCUMENT_DOWNLOADER_AGENT_CONFIG,
    "parameter-classifier-agent": PARAMETER_CLASSIFIER_AGENT_CONFIG,
    "parameter-searching-agent": PARAMETER_SEARCHING_AGENT_CONFIG,
    "deep-document-analyzer": DEEP_DOCUMENT_ANALYZER_CONFIG,
}
