from multiplex.box import BoxHolder


class _FakeView:
    """Minimal stand-in for the parts of Viewer that Box/BoxState touch."""

    def __init__(self, cols=100, lines=30):
        self.cols = cols
        self.lines = lines
        self.maximized = False
        self.current_focused_box = 0
        self.buffer_lines = None


def _make_box(cols=100, lines=30, box_height=13):
    view = _FakeView(cols=cols, lines=lines)
    holder = BoxHolder(index=0, iterator=None, box_height=box_height, viewer=view)
    return view, holder.box


def test_set_width_leading_blank_line_no_crash():
    """Regression: resizing a wrap-mode, stream-done buffer whose first line is
    empty used to raise KeyError. The empty first line never gets a raw_to_self
    entry, and the old code did an unguarded raw_to_self[raw_line] lookup (with
    raw_line defaulting to 0, which is itself unmapped)."""
    view, box = _make_box()
    box.buffer.write("\nhello\nworld")
    box.state.wrap = True
    box.state.auto_scroll = True
    box.state.stream_done = True
    box.state.buffer_start_line = 0

    view.cols = 60
    box.set_width(60)  # must not raise

    assert box.min_start_line <= box.state.buffer_start_line <= box.max_start_line


def test_set_width_all_blank_no_crash():
    view, box = _make_box()
    box.buffer.write("\n\n\n")
    box.state.wrap = True
    box.state.auto_scroll = True
    box.state.stream_done = True
    box.state.buffer_start_line = 0

    view.cols = 60
    box.set_width(60)  # must not raise

    assert box.min_start_line <= box.state.buffer_start_line <= box.max_start_line


def test_set_width_preserves_anchor_when_mappable():
    """When the anchor line has a valid mapping, the scroll position is preserved
    (behavior unchanged from before the fix)."""
    view, box = _make_box()
    for i in range(20):
        box.buffer.write(f"line {i}\n")
    box.state.wrap = True
    box.state.auto_scroll = True
    box.state.stream_done = True
    box.state.buffer_start_line = 5

    view.cols = 60
    box.set_width(60)

    # short lines don't wrap, so wrapped line N == raw line N; anchor stays 5
    assert box.state.buffer_start_line == 5