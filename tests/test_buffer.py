from multiplex.buffer import Buffer


def test_erase_in_display():
    # Regression: erase-in-display CSI sequences (\x1b[J, \x1b[1J, \x1b[2J, \x1b[3J)
    # crashed with AttributeError because Screen.erase_in_display referenced the
    # non-existent LinedBuffer.max_lines instead of max_line. Any command that emits
    # such a sequence (progress bars, clear, TUIs) took the whole viewer down.
    buffer = Buffer(width=5)
    buffer.write("12345\n67890\n")
    assert buffer.get_lines(2, 0, 5, 0, wrap=False) == [(5, "12345"), (5, "67890")]

    # how=2: erase the whole display -> all visible lines blank
    buffer.write("\x1b[2J")
    assert buffer.get_lines(2, 0, 5, 0, wrap=False) == [(5, "     "), (5, "     ")]

    # the other erase-in-display forms must not raise either
    for seq in ("\x1b[J", "\x1b[1J", "\x1b[3J"):
        b = Buffer(width=5)
        b.write("12345\n67890\n")
        b.write(seq)


def test_buffer_kitchen():
    width = 5
    buffer = Buffer(width)
    assert buffer.width == width
    text = "123456789"
    buffer.write(text)
    assert buffer.get_max_line(wrap=False) == 0
    assert buffer.get_max_line(wrap=True) == 1
    assert buffer.get_lines(1, 0, width, 0, wrap=False) == [(9, "12345")]
    assert buffer.get_lines(1, 0, width, 0, wrap=True) == [(5, "12345")]
    assert buffer.get_lines(2, 0, width, 0, wrap=False) == [(9, "12345"), (0, " " * 5)]
    assert buffer.get_lines(2, 0, width, 0, wrap=True) == [(5, "12345"), (4, "6789 ")]
    assert buffer.get_lines(1, 1, width, 0, wrap=True) == [(4, "6789 ")]
    assert buffer.get_lines(1, 0, width, 3, wrap=False) == [(9, "45678")]

    width = 3
    buffer.width = width
    assert buffer.get_max_line(wrap=False) == 0
    assert buffer.get_max_line(wrap=True) == 2
    assert buffer.get_lines(1, 0, width, 0, wrap=False) == [(9, "123")]
    assert buffer.get_lines(3, 0, width, 0, wrap=True) == [(3, "123"), (3, "456"), (3, "789")]

    assert buffer.raw_buffer.getvalue() == text

    buffer.write("\nabcd")
    assert buffer.convert_line_number(0, from_wrapped=False) == 0
    assert buffer.convert_line_number(1, from_wrapped=False) == 3
    assert buffer.convert_line_number(0, from_wrapped=True) == 0
    assert buffer.convert_line_number(2, from_wrapped=True) == 0
    assert buffer.convert_line_number(3, from_wrapped=True) == 1
    assert buffer.convert_line_number(4, from_wrapped=True) == 1
