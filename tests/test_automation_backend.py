import pytest
from unittest.mock import patch, MagicMock
from src.gui.backend.automation_backend import AutomationBackend

@pytest.fixture
def mock_backend():
    with patch('src.gui.backend.automation_backend.AutomationBackend._initialize_engine') as mock_init:
        # Mocking the parser/client inside the engine so status_monitor can init
        mock_engine = MagicMock()
        mock_engine.parser.client.host = "http://localhost:11434"
        mock_engine.parser.client.model = "test_model"
        mock_init.return_value = mock_engine
        
        backend = AutomationBackend()
        yield backend
        backend.shutdown()

def test_is_executing_initial_state(mock_backend):
    assert mock_backend.is_executing() is False

def test_execution_signals(mock_backend):
    engine_states = []
    modes = []
    tasks = []
    
    mock_backend.engine_status_changed.connect(lambda s: engine_states.append(s))
    mock_backend.mode_changed.connect(lambda s: modes.append(s))
    mock_backend.task_changed.connect(lambda s: tasks.append(s))
    
    # Force emit
    mock_backend.force_emit_all()
    assert engine_states[-1] == "Online"
    assert modes[-1] == "Idle"
    assert tasks[-1] == "None"
    
    # Execution started
    mock_backend._on_execution_started()
    assert mock_backend.is_executing() is True
    assert engine_states[-1] == "Busy"
    assert modes[-1] == "Executing"
    
    # Step started
    mock_backend._on_step_started("Opening Chrome")
    assert tasks[-1] == "Opening Chrome"
    
    # Execution finished
    mock_backend._on_execution_finished({})
    assert mock_backend.is_executing() is False
    assert engine_states[-1] == "Online"
    assert modes[-1] == "Idle"
    assert tasks[-1] == "None"

def test_voice_signals(mock_backend):
    modes = []
    voices = []
    
    mock_backend.mode_changed.connect(lambda s: modes.append(s))
    mock_backend.voice_status_changed.connect(lambda s: voices.append(s))
    
    with patch('PySide6.QtCore.QMetaObject.invokeMethod'):
        mock_backend.start_voice()
        assert modes[-1] == "Listening"
        assert voices[-1] == "Listening"
        
        mock_backend.stop_voice()
        assert modes[-1] == "Processing"
        assert voices[-1] == "Processing"

