from streamlit.testing.v1 import AppTest


APP = "app.py"


def test_initial_state() -> None:
    app = AppTest.from_file(APP).run()
    assert app.title[0].value == "Penilaian Jurnal SIBangkom"
    assert app.text_area[0].label == "Jurnal atau Rangkuman Pembelajaran"
    assert app.button[0].label == "Nilai Jurnal"
    assert "20,000" in app.caption[0].value


def test_blank_submit_shows_validation() -> None:
    app = AppTest.from_file(APP).run()
    app.button[0].click().run()
    assert app.error[0].value == "Tuliskan jurnal sebelum menilai."


def test_valid_submit_shows_unavailable_message_without_result() -> None:
    app = AppTest.from_file(APP).run()
    app.text_area[0].input("Refleksi pembelajaran yang bermakna.").run()
    app.button[0].click().run()
    assert "Mesin penilaian belum tersedia" in app.info[0].value
    assert not app.metric
    assert not app.json
