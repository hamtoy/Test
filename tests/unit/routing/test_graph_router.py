"""Tests for routing graph_router module."""

from unittest.mock import Mock

from src.routing.graph_router import GraphRouter


def test_graph_router_init() -> None:
    """Test GraphRouter initialization."""
    mock_graph = Mock()
    router = GraphRouter(graph=mock_graph)
    assert router.graph is mock_graph
