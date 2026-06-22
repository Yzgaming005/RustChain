from pathlib import Path


def test_tools_bcos_badge_generator_uses_dom_nodes():
    """Verify tools/bcos-badge-generator/index.html builds DOM nodes safely."""
    page = Path(__file__).resolve().parents[1] / "tools" / "bcos-badge-generator" / "index.html"
    html = page.read_text(encoding="utf-8")

    # onload branch: replaceChildren + appendChild(img)
    assert "previewArea.replaceChildren();" in html
    assert "previewArea.appendChild(img);" in html

    # onerror placeholder: replaceChildren, createElement, appendChild
    assert "const container = document.createElement('div');" in html
    assert "container.style.textAlign = 'left';" in html
    assert "warningP.textContent =" in html
    assert "urlSpan.textContent = url;" in html
    assert "previewArea.appendChild(container);" in html

    # resetForm placeholder: replaceChildren + createElement + textContent
    assert "const placeholder = document.createElement('span');" in html
    assert "placeholder.className = 'preview-placeholder';" in html
    assert 'placeholder.textContent = \'Enter a Certificate ID and click "Generate Preview" to see your badge\';' in html
    assert "previewArea.appendChild(placeholder);" in html


def test_tools_bcos_badge_generator_no_inner_html_sinks():
    """Reject any remaining innerHTML assignments in the tool page."""
    page = Path(__file__).resolve().parents[1] / "tools" / "bcos-badge-generator" / "index.html"
    html = page.read_text(encoding="utf-8")

    # The only <span class="preview-placeholder">... should not exist (replaced by DOM)
    assert '<span class="preview-placeholder">' not in html
    # No innerHTML assignments left in the script
    lines = [l.strip() for l in html.splitlines()]
    inner_html_assignments = [
        l for l in lines
        if "innerHTML" in l and "=" in l and not l.startswith("//")
    ]
    # Allow legitimate uses (e.g. generateBtn.innerHTML for spinner) but not preview
    suspicious = [
        l for l in inner_html_assignments
        if "previewArea" in l or "preview" in l.lower()
    ]
    assert not suspicious, f"Suspicious innerHTML assignments on preview elements: {suspicious}"
