from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_streamlit_launches_without_keys():
    app = AppTest.from_file(APP).run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "Country & City Research"
    assert app.button[0].label == "Run Research"


def test_streamlit_ambiguity_is_actionable():
    app = AppTest.from_file(APP).run(timeout=20)
    app.text_input[0].set_value("Congo")
    app.button[0].click().run()
    assert not app.exception
    assert "Specify Republic of the Congo" in app.error[0].value


def test_streamlit_full_submission_and_results(monkeypatch, settings, discovery, cities, search):
    from conftest import FakeLLM, report_for
    from config import Settings
    import llm_factory
    import tools.youcom_tools

    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: FakeLLM([discovery, *map(report_for, cities)]))
    monkeypatch.setattr(tools.youcom_tools, "create_search_tool", lambda _: search)
    app = AppTest.from_file(APP).run(timeout=20)
    app.text_input[0].set_value("Japan")
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert not app.error
    assert len(app.session_state["report"].cities) == 3
    assert len(app.metric) == 3
    assert app.get("download_button")
