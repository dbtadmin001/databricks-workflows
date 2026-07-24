from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any


def render_dashboard_html(
    *,
    title: str,
    subtitle: str,
    summary_html: str,
    trust_html: str,
    pages: Sequence[Mapping[str, Any]],
) -> str:
    """Render a tabbed dashboard and load Plotly JavaScript exactly once."""
    if not pages:
        raise ValueError("At least one dashboard page is required")
    names = [str(page["name"]) for page in pages]
    if len(names) != len(set(names)):
        raise ValueError("Dashboard page names must be unique")

    visual_ids: set[str] = set()
    rendered_pages: list[str] = []
    tab_buttons: list[str] = []
    first_figure = True
    for page_index, page in enumerate(pages):
        page_name = str(page["name"])
        page_id = f"dashboard-page-{page_index}"
        active = " active" if page_index == 0 else ""
        tab_buttons.append(
            f'<button class="dashboard-tab{active}" data-page="{page_id}" '
            f'type="button">{html.escape(page_name)}</button>'
        )
        visuals: list[str] = []
        for visual in page.get("visuals", []):
            visual_id = str(visual["id"])
            if visual_id in visual_ids:
                raise ValueError(f"Duplicate dashboard visual id: {visual_id}")
            visual_ids.add(visual_id)
            figure_html = visual["figure"].to_html(
                full_html=False,
                include_plotlyjs="cdn" if first_figure else False,
                div_id=visual_id,
                config={"displayModeBar": False, "responsive": True},
            )
            first_figure = False
            annotation = html.escape(str(visual.get("annotation", "")))
            visuals.append(
                f'<article class="dashboard-visual" data-visual-id="{html.escape(visual_id)}">'
                f'{figure_html}<p class="visual-note">{annotation}</p></article>'
            )
        content = str(page.get("content_html", ""))
        rendered_pages.append(
            f'<section id="{page_id}" class="dashboard-page{active}" '
            f'data-tab-name="{html.escape(page_name)}">{content}{"".join(visuals)}</section>'
        )

    return f"""
<style>
  .mvp-dashboard {{font-family:Inter,Arial,sans-serif;color:#17212b;padding:8px 4px 24px}}
  .mvp-dashboard h1 {{font-size:28px;letter-spacing:0;margin:0 0 4px}}
  .dashboard-subtitle {{color:#52616f;margin-bottom:16px}}
  .dashboard-grid {{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px}}
  .dashboard-card {{border:1px solid #d9e0e5;border-left:5px solid #007f73;border-radius:6px;padding:14px;background:#fff}}
  .dashboard-label {{font-size:12px;text-transform:uppercase;color:#52616f;font-weight:700}}
  .dashboard-value {{font-size:24px;font-weight:750;margin-top:7px;overflow-wrap:anywhere}}
  .dashboard-trust {{margin-top:12px;border:1px solid #d9e0e5;border-left:5px solid #228b57;border-radius:6px;padding:12px 14px}}
  .dashboard-trust-grid {{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:10px;margin-top:9px}}
  .dashboard-trust-item {{border-left:1px solid #d9e0e5;padding-left:10px;min-width:0}}
  .dashboard-trust-value {{font-size:14px;font-weight:700;margin-top:4px;overflow-wrap:anywhere}}
  .dashboard-tabs {{display:flex;gap:4px;margin:18px 0 8px;border-bottom:1px solid #d9e0e5;overflow-x:auto}}
  .dashboard-tab {{border:0;background:#f4f7f8;color:#344451;padding:10px 14px;cursor:pointer;font-weight:700}}
  .dashboard-tab.active {{background:#fff;color:#007f73;border-bottom:3px solid #007f73}}
  .dashboard-page {{display:none;padding-top:8px}}
  .dashboard-page.active {{display:block}}
  .dashboard-visual {{border-bottom:1px solid #e5eaed;padding:4px 0 14px;margin-bottom:14px}}
  .visual-note {{margin:0 12px;color:#52616f;font-size:12px}}
  @media(max-width:800px) {{.dashboard-grid,.dashboard-trust-grid {{grid-template-columns:1fr 1fr}}}}
</style>
<section class="mvp-dashboard">
  <h1>{html.escape(title)}</h1>
  <div class="dashboard-subtitle">{html.escape(subtitle)}</div>
  {summary_html}
  {trust_html}
  <nav class="dashboard-tabs" aria-label="Dashboard pages">{"".join(tab_buttons)}</nav>
  {"".join(rendered_pages)}
</section>
<script>
(() => {{
  const root = document.currentScript.previousElementSibling;
  if (!root) return;
  const tabs = root.querySelectorAll('.dashboard-tab');
  const pages = root.querySelectorAll('.dashboard-page');
  tabs.forEach((tab) => tab.addEventListener('click', () => {{
    tabs.forEach((item) => item.classList.remove('active'));
    pages.forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
    const page = root.querySelector(`#${{tab.dataset.page}}`);
    if (page) {{
      page.classList.add('active');
      window.dispatchEvent(new Event('resize'));
    }}
  }}));
}})();
</script>
"""
