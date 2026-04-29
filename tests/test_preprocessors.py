import pytest
from pathlib import Path
from indexer.preprocessors.manager import PreprocessorManager
from indexer.preprocessors.text import TextPreprocessor
from indexer.preprocessors.pdf import PdfPreprocessor
from indexer.preprocessors.docx import DocxPreprocessor

@pytest.fixture
def manager():
    return PreprocessorManager()

def test_preprocessor_discovery(manager):
    """Test that all pre-processors are correctly discovered."""
    assert ".py" in manager.supported_extensions
    assert ".pdf" in manager.supported_extensions
    assert ".docx" in manager.supported_extensions
    assert "Dockerfile" in manager.supported_extensions
    
    assert isinstance(manager.get_preprocessor(Path("test.py")), TextPreprocessor)
    assert isinstance(manager.get_preprocessor(Path("test.pdf")), PdfPreprocessor)
    assert isinstance(manager.get_preprocessor(Path("test.docx")), DocxPreprocessor)

def test_text_preprocessing(manager, tmp_path):
    """Test standard text pre-processing."""
    file = tmp_path / "test.py"
    content = "print('hello world')"
    file.write_text(content)
    
    result = manager.preprocess(file)
    assert result == content

def test_pdf_preprocessing_invalid(manager, tmp_path):
    """Test PDF pre-processing with an invalid file (should log error and return error message)."""
    file = tmp_path / "test.pdf"
    file.write_text("not a pdf")
    
    result = manager.preprocess(file)
    assert "Error processing PDF" in result
    assert "test.pdf" in result

def test_docx_preprocessing_placeholder(manager, tmp_path):
    """Test Docx pre-processing (currently a placeholder)."""
    file = tmp_path / "test.docx"
    file.write_text("dummy content")
    
    result = manager.preprocess(file)
    assert "DOCX Content Placeholder" in result
    assert "test.docx" in result

def test_unknown_extension(manager):
    """Test that unknown extensions return None."""
    assert manager.get_preprocessor(Path("unknown.xyz")) is None
    assert manager.preprocess(Path("unknown.xyz")) is None
