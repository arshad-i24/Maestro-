from maestro.notation import NotationGenerator, render_swara_symbol
from maestro.swara import SwaraConverter
from maestro.models import DetectedNote


def _pitch(midi):
    return SwaraConverter(60).convert(midi)


def test_rendered_symbols():
    conv = SwaraConverter(60)
    assert render_swara_symbol(conv.convert(60)) == "S"        # Sa madhya
    assert render_swara_symbol(conv.convert(61)) == "R(k)"     # komal Re
    assert render_swara_symbol(conv.convert(64)) == "G"        # Ga madhya
    assert render_swara_symbol(conv.convert(66)) == "M"        # tivra Ma
    assert render_swara_symbol(conv.convert(48)) == "s"        # Sa mandra (lowercase)
    assert render_swara_symbol(conv.convert(55)) == "p"        # Pa mandra
    assert render_swara_symbol(conv.convert(72)) == "S'"       # Sa taar
    assert render_swara_symbol(conv.convert(65)) == "m"        # shuddha Ma
    assert render_swara_symbol(conv.convert(63)) == "G(k)"     # komal Ga
    assert render_swara_symbol(conv.convert(58)) == "n(k)"     # komal Ni mandra
    assert render_swara_symbol(conv.convert(71)) == "N"        # shuddha Ni madhya


def test_generate_entries():
    notes = [
        DetectedNote(frequency=293.66, midi_note=62.0, start=0.1, end=0.5, duration=0.4, confidence=0.9),
        DetectedNote(frequency=440.0, midi_note=69.0, start=0.6, end=1.0, duration=0.4, confidence=0.8),
    ]
    entries = NotationGenerator(SwaraConverter(60)).generate(notes)
    assert len(entries) == 2
    assert entries[0].swara == "Re"
    assert entries[0].octave == "madhya"
    assert entries[0].duration > 0
    assert entries[0].symbol == "R"
    assert entries[1].swara == "Dha"  # A above C tonic = shuddha Dha
    assert entries[1].symbol == "D"


def test_generate_with_lyrics():
    from maestro.notation import NotationGenerator

    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.0, end=0.4, duration=0.4, confidence=0.9)
    ]
    entries = NotationGenerator(SwaraConverter(60)).generate(notes, lyric_map={0: ["tu"]})
    assert entries[0].lyric == "tu"


def test_render_sequence():
    conv = SwaraConverter(60)
    gen = NotationGenerator(conv)
    dt = DetectedNote
    notes = [
        dt(261.63, 60.0, 0.0, 0.3, 0.3, 0.9),
        dt(293.66, 62.0, 0.3, 0.6, 0.3, 0.9),
        dt(392.0, 67.0, 0.6, 0.9, 0.3, 0.9),
    ]
    line = gen.render_sequence(gen.generate(notes))
    assert line == "S R P"