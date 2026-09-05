import pytest

from maestro.errors import ErrorCode, MaestroError
from maestro.swara import SwaraConverter, swara_for_midi


def test_tonic_c4_sa():
    conv = SwaraConverter(tonic_midi=60)
    p = conv.convert(60.0, conv.tonic_frequency())
    assert p.swara == "Sa"
    assert p.swara_type == "shuddha"
    assert p.octave == "madhya"
    assert p.semitone_offset == 0


def test_shuddha_semitones():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(62).swara == "Re"
    assert conv.convert(62).swara_type == "shuddha"
    assert conv.convert(64).swara == "Ga"
    assert conv.convert(65).swara == "Ma"
    assert conv.convert(67).swara == "Pa"
    assert conv.convert(59).swara == "Ni"  # flat Ni one below Sa


def test_komal_and_tivra():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(61).swara == "Re" and conv.convert(61).swara_type == "komal"
    assert conv.convert(63).swara == "Ga" and conv.convert(63).swara_type == "komal"
    assert conv.convert(66).swara == "Ma" and conv.convert(66).swara_type == "tivra"
    assert conv.convert(68).swara == "Dha" and conv.convert(68).swara_type == "komal"
    assert conv.convert(70).swara == "Ni" and conv.convert(70).swara_type == "komal"


def test_octaves():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(48).swara == "Sa" and conv.convert(48).octave == "mandra"
    assert conv.convert(72).swara == "Sa" and conv.convert(72).octave == "taar"
    assert conv.convert(84).octave.startswith("extended")


def test_frequency_bandwidth():
    freq = 440.0  # A4
    conv = SwaraConverter(tonic_midi=69)  # tonic = A4
    p = conv.convert(69.0, freq)
    assert p.swara == "Sa" and p.swara_type == "shuddha"
    assert p.cents_from_tonic == pytest.approx(0.0)


def test_invalid_tonic():
    with pytest.raises(MaestroError) as exc:
        SwaraConverter(tonic_midi=200)
    assert exc.value.code == ErrorCode.INVALID_TONIC


def test_swara_for_midi_convenience():
    p = swara_for_midi(62, 60)
    assert p.swara == "Re"