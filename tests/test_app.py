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
    activity = list(app.session_state["workflow_activity"])
    calls = [message for message in activity if ": Calling" in message]
    assert ["search" if message.startswith("You.com") else "llm" for message in calls] == (
        ["search"] * 4 + ["llm"] + (["search"] * 9 + ["llm"]) * 3
    )
    assert sum("LLM: Completed" in message for message in activity) == 4
    assert sum(message.startswith("You.com") and ": Completed" in message for message in activity) == 31
    assert any("01. Discovery:" in item.value for item in app.text)
    assert any("You.com search 1/4: Calling" in item.value for item in app.text)
    assert any("LLM: Calling" in item.value for item in app.text)

    app.run()
    assert list(app.session_state["workflow_activity"]) == activity
    assert len(app.text) == len(activity)
    app.button[1].click().run()
    assert not app.text_input[0].value
    assert "workflow_activity" not in app.session_state
    assert "report" not in app.session_state


def test_streamlit_failed_model_call_keeps_activity(monkeypatch, settings, search):
    from config import Settings
    import llm_factory
    import tools.youcom_tools

    class BrokenModel:
        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            raise RuntimeError("private-provider-response")

    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(llm_factory, "create_llm", lambda _: BrokenModel())
    monkeypatch.setattr(tools.youcom_tools, "create_search_tool", lambda _: search)
    app = AppTest.from_file(APP).run(timeout=20)
    app.text_input[0].set_value("Japan")
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert app.error
    activity = list(app.session_state["workflow_activity"])
    assert any(message.startswith("LLM: Failed") for message in activity)
    assert not any(message.startswith("LLM: Completed") for message in activity)
    assert "private-provider-response" not in str(activity)
    assert "report" not in app.session_state
    app.run()
    assert len(app.text) == len(activity)
