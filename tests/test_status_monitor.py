import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QCoreApplication

from src.gui.backend.status_monitor import HealthCheckWorker, StatusMonitor

@pytest.fixture
def worker():
    return HealthCheckWorker("http://localhost:11434", "test_model:latest")

def test_ollama_connected(worker):
    with patch('src.gui.backend.status_monitor.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "test_model:latest"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        emitted_status = []
        worker.ollama_checked.connect(lambda s: emitted_status.append(s))
        worker._check_ollama()

        assert "Ollama Connected" in emitted_status

def test_ollama_model_unavailable(worker):
    with patch('src.gui.backend.status_monitor.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "other_model:latest"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        emitted_status = []
        worker.ollama_checked.connect(lambda s: emitted_status.append(s))
        worker._check_ollama()

        assert "Ollama Model Unavailable" in emitted_status

def test_ollama_offline(worker):
    import requests
    with patch('src.gui.backend.status_monitor.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException()

        emitted_status = []
        worker.ollama_checked.connect(lambda s: emitted_status.append(s))
        worker._check_ollama()

        assert "Ollama Offline" in emitted_status

def test_microphone_ready(worker):
    with patch('src.gui.backend.status_monitor.sd.query_devices') as mock_query:
        mock_query.return_value = [{'name': 'Mic 1', 'max_input_channels': 2}]

        emitted_status = []
        worker.microphone_checked.connect(lambda s: emitted_status.append(s))
        worker._check_microphone()

        assert "Microphone Ready" in emitted_status

def test_microphone_unavailable(worker):
    with patch('src.gui.backend.status_monitor.sd.query_devices') as mock_query:
        mock_query.return_value = [{'name': 'Speaker 1', 'max_input_channels': 0}]

        emitted_status = []
        worker.microphone_checked.connect(lambda s: emitted_status.append(s))
        worker._check_microphone()

        assert "Microphone Unavailable" in emitted_status

def test_microphone_error(worker):
    with patch('src.gui.backend.status_monitor.sd.query_devices') as mock_query:
        mock_query.side_effect = Exception("Audio error")

        emitted_status = []
        worker.microphone_checked.connect(lambda s: emitted_status.append(s))
        worker._check_microphone()

        assert "Microphone Error" in emitted_status

@pytest.fixture
def status_monitor():
    monitor = StatusMonitor("http://localhost:11434", "test_model:latest")
    yield monitor
    monitor.shutdown()

def test_status_monitor_executor_status(status_monitor):
    emitted = []
    status_monitor.executor_status_changed.connect(lambda s, ok: emitted.append((s, ok)))

    status_monitor.set_executor_status("Executor Busy")
    assert emitted[-1] == ("Executor Busy", True)

    status_monitor.set_executor_status("Executor Error")
    assert emitted[-1] == ("Executor Error", False)

def test_status_monitor_force_emit(status_monitor):
    emitted_exec = []
    emitted_ollama = []
    
    status_monitor.executor_status_changed.connect(lambda s, ok: emitted_exec.append((s, ok)))
    status_monitor.ollama_status_changed.connect(lambda s, ok: emitted_ollama.append((s, ok)))
    
    # It should emit its current states
    status_monitor.force_emit_all()
    
    assert len(emitted_exec) == 1
    assert emitted_exec[0] == ("Checking...", False)
    
    assert len(emitted_ollama) == 1
    assert emitted_ollama[0] == ("Checking...", False)

