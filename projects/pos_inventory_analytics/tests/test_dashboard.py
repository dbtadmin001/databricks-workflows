from __future__ import annotations

import plotly.graph_objects as go
import pytest

from projects.pos_inventory_analytics.modules.dashboard import render_dashboard_html

pytestmark = [pytest.mark.unit, pytest.mark.local_fast]


def figure(title: str):
    result = go.Figure(data=[go.Bar(x=["observed"], y=[1])])
    result.update_layout(title=title)
    return result


def test_dashboard_html_contains_every_tab_and_registered_visual_once():
    pages = [
        {
            "name": "Executive overview",
            "visuals": [{"id": "overview-visual", "figure": figure("Overview")}],
        },
        {
            "name": "Drivers",
            "visuals": [{"id": "drivers-visual", "figure": figure("Drivers")}],
        },
        {
            "name": "Data Quality",
            "visuals": [
                {"id": "quality-trend", "figure": figure("Quarantine trend")},
                {"id": "quality-rules", "figure": figure("Failed rules")},
            ],
        },
    ]

    document = render_dashboard_html(
        title="Test dashboard",
        subtitle="Governed test metrics",
        summary_html='<div id="summary">summary</div>',
        trust_html='<div id="trust">trust</div>',
        pages=pages,
    )

    assert [page["name"] for page in pages][-1] == "Data Quality"
    for page in pages:
        assert f'data-tab-name="{page["name"]}"' in document
        for visual in page["visuals"]:
            assert document.count(f'data-visual-id="{visual["id"]}"') == 1
            assert f'id="{visual["id"]}"' in document
    assert document.count("cdn.plot.ly") == 1
    assert "dashboard-tab" in document
    assert "summary" in document
    assert "trust" in document


def test_dashboard_rejects_duplicate_visual_ids():
    with pytest.raises(ValueError, match="Duplicate dashboard visual id"):
        render_dashboard_html(
            title="Test",
            subtitle="Test",
            summary_html="",
            trust_html="",
            pages=[
                {"name": "One", "visuals": [{"id": "same", "figure": figure("One")}]},
                {"name": "Two", "visuals": [{"id": "same", "figure": figure("Two")}]},
            ],
        )
