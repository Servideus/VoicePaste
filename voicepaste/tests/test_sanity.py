def test_import_package():
    import importlib
    m = importlib.import_module('voicepaste')
    assert hasattr(m, '__all__')

