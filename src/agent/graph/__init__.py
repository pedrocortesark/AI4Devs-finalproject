"""
LangGraph Agent Graph Package (US-018)

This package implements the stateful validation agent for SF-PM.
The agent uses LangGraph's StateGraph to orchestrate the validation
pipeline with conditional transitions and shared state.

Modules:
    state   — ValidationState TypedDict (shared memory across all nodes)
    nodes   — Individual processing functions (one per graph node)
    graph   — StateGraph definition, edges, and compilation
"""
